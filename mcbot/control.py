"""Pure decision engine. Timestamps are local monotonic seconds, not Twitch time."""
from collections import Counter, deque
from dataclasses import dataclass, field
import math


AXES = {"forward": ("w", "s"), "strafe": ("d", "a"),
        "yaw": ("right", "left"), "pitch": ("down", "up")}
CHOICES = {**AXES, "sprint": ("sprint", "walk"),
           "sneak": ("sneak", "stand"),
           "slot": tuple(f"slot{i}" for i in range(1, 10)),
           "hand": ("hit", "use", "mine"), "jump": ("jump",),
           "drop": ("drop",)}
TOKEN_CHANNEL = {token: channel for channel, tokens in CHOICES.items() for token in tokens}


@dataclass(frozen=True)
class Config:
    window_min: float = .3
    window_max: float = 1.2
    target_commands: int = 12
    rate_period: float = 5.0
    margin: float = .15
    movement_ttl: float = 1.0
    camera_ttl: float = .35
    mine_ttl: float = .7
    event_ttl: float = 1.0
    per_user_per_second: int = 3
    max_events: int = 10000

    def __post_init__(self):
        durations = (self.window_min, self.window_max, self.rate_period,
                     self.movement_ttl, self.camera_ttl, self.mine_ttl, self.event_ttl)
        if any(not math.isfinite(x) or x <= 0 for x in durations):
            raise ValueError("Durations must be finite and positive")
        if self.window_min > self.window_max or not 0 < self.margin <= 1:
            raise ValueError("Invalid decision window or margin")
        if any(not isinstance(x, int) or x <= 0 for x in
               (self.target_commands, self.per_user_per_second, self.max_events)):
            raise ValueError("Limits must be positive integers")


def parse(message):
    """One vote per channel/message. Conflicting tokens abstain on that channel.

    Require command-only messages to avoid interpreting 'a nice day' as strafe.
    This strict grammar is a deliberate prototype choice; no natural language.
    """
    tokens = message.casefold().split()
    if not tokens or any(token not in TOKEN_CHANNEL for token in tokens):
        return {}
    result = {}
    for channel, choices in CHOICES.items():
        selected = set(tokens).intersection(choices)
        if len(selected) == 1:
            result[channel] = selected.pop()
    return result


@dataclass
class Vote:
    at: float
    commands: dict
    consumed: set = field(default_factory=set)


class Engine:
    def __init__(self, config=None):
        self.config = config or Config()
        self.votes = deque()
        self.users = {}
        self.seen = {}
        self.last_time = -math.inf
        self.sprint = False
        self.sneak = False
        self.slot = None

    def _advance(self, now):
        if not math.isfinite(now) or now < self.last_time:
            raise ValueError("Time must be finite and monotonic")
        self.last_time = now
        c = self.config
        horizon = max(c.rate_period, c.window_max)
        while self.votes and now - self.votes[0].at >= horizon:
            self.votes.popleft()
        self.users = {u: deque(t for t in times if now - t < 1)
                      for u, times in self.users.items() if times and now - times[-1] < 1}
        # Bounded replay protection; ingress must also reject old deliveries.
        self.seen = {key: at for key, at in self.seen.items() if now - at < 60}

    def ingest(self, user_id, message_id, text, now):
        self._advance(now)
        commands = parse(text)
        if not commands or not user_id or not message_id or message_id in self.seen:
            return False
        c = self.config
        times = self.users.get(user_id, deque())
        if len(times) >= c.per_user_per_second or len(self.votes) >= c.max_events:
            return False
        if len(self.seen) >= c.max_events:
            return False
        times.append(now)
        self.users[user_id] = times
        self.seen[message_id] = now
        self.votes.append(Vote(now, commands))
        return True

    def _ttl(self, channel):
        c = self.config
        if channel in ("forward", "strafe"):
            return c.movement_ttl
        if channel in ("yaw", "pitch"):
            return c.camera_ttl
        return c.event_ttl

    def tick(self, now):
        self._advance(now)
        c = self.config
        keys, pulses, camera, telemetry = set(), [], {"yaw": 0., "pitch": 0.}, {}
        for channel, choices in CHOICES.items():
            rate = sum(channel in v.commands and now - v.at < c.rate_period
                       for v in self.votes) / c.rate_period
            window = max(c.window_min, min(c.window_max, c.target_commands / max(rate, .001)))
            eligible = [v for v in self.votes if channel in v.commands
                        and channel not in v.consumed
                        and now - v.at < min(window, self._ttl(channel))
                        and (v.commands[channel] != "mine" or now - v.at < c.mine_ttl)]
            scores = Counter()
            for vote in eligible:
                scores[vote.commands[channel]] += 2 ** (-2 * (now - vote.at) / window)
            total = sum(scores.values())
            ranked = sorted(scores, key=lambda token: (-scores[token], token))
            winner = ranked[0] if ranked else None
            second = scores[ranked[1]] if len(ranked) > 1 else 0
            lead = (scores[winner] - second) / total if total else 0
            if lead < c.margin:
                winner = None
            telemetry[channel] = {"window_ms": round(window * 1000),
                                  "support": {t: s / total for t, s in scores.items()},
                                  "winner": winner, "samples": len(eligible)}
            if winner is None:
                continue
            if channel in ("forward", "strafe"):
                keys.add(winner)
            elif channel in ("yaw", "pitch"):
                # Signed normalized speed, not a mouse displacement per tick.
                camera[channel] = lead * (1 if winner == choices[0] else -1)
            elif channel == "hand" and winner == "mine":
                keys.add("attack")
            else:
                if channel == "sprint":
                    self.sprint = winner == "sprint"
                elif channel == "sneak":
                    self.sneak = winner == "sneak"
                elif channel == "slot":
                    self.slot = int(winner[4:])
                else:
                    pulses.append(winner)
                # Consume the whole competing batch: losing votes must not
                # trigger later just because the winner has disappeared.
                for vote in eligible:
                    vote.consumed.add(channel)
        if self.sneak:
            keys.add("sneak")
        elif self.sprint and "w" in keys:
            keys.add("sprint")
        return {"keys": sorted(keys), "camera": camera, "pulses": pulses,
                "sprint": self.sprint, "sneak": self.sneak,
                "slot": self.slot, "channels": telemetry}

    def reset(self):
        """Disconnect/emergency stop: clear all intentions, including toggles."""
        self.votes.clear()
        self.sprint = self.sneak = False
        self.slot = None
