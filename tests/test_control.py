import unittest
from mcbot.control import Config, Engine, parse


class ControlTests(unittest.TestCase):
    def send(self, engine, text, at=0, user="a", mid="1"):
        return engine.ingest(user, mid, text, at)

    def test_parallel_majority_and_one_shot(self):
        e = Engine()
        self.send(e, "w right hit slot3")
        self.send(e, "w d right jump", user="b", mid="2")
        self.send(e, "s left", user="c", mid="3")
        out = e.tick(0)
        self.assertEqual(out["keys"], ["d", "w"])
        self.assertGreater(out["camera"]["yaw"], 0)
        self.assertEqual(set(out["pulses"]), {"hit", "jump"})
        self.assertEqual(out["slot"], 3)
        self.assertEqual(e.tick(.1)["pulses"], [])

    def test_silence_and_discussion_do_not_extend_movement(self):
        e = Engine()
        self.send(e, "w right mine slot3 sprint")
        e.tick(0)
        self.assertFalse(self.send(e, "a nice day", .9, mid="2"))
        out = e.tick(3)
        self.assertEqual(out["keys"], [])
        self.assertEqual(out["camera"], {"yaw": 0, "pitch": 0})
        self.assertEqual(out["pulses"], [])
        self.assertEqual(out["slot"], 3)
        self.assertTrue(out["sprint"])

    def test_renewal_and_reversal(self):
        e = Engine()
        self.send(e, "w")
        self.assertEqual(e.tick(0)["keys"], ["w"])
        self.send(e, "w", .8, mid="2")
        self.assertEqual(e.tick(1)["keys"], ["w"])
        self.send(e, "s", 1.1, mid="3")
        self.assertEqual(e.tick(1.1)["keys"], ["s"])

    def test_equal_votes_are_neutral(self):
        e = Engine()
        self.send(e, "w right")
        self.send(e, "s left", user="b", mid="2")
        out = e.tick(0)
        self.assertEqual(out["keys"], [])
        self.assertEqual(out["camera"]["yaw"], 0)

    def test_old_direction_not_revived_by_other_axis(self):
        e = Engine()
        self.send(e, "w")
        e.tick(0)
        self.send(e, "d", 1.05, mid="2")
        self.assertEqual(e.tick(1.05)["keys"], ["d"])

    def test_sneak_persists_and_reset_clears_it(self):
        e = Engine()
        self.send(e, "sprint sneak w")
        self.assertEqual(e.tick(0)["keys"], ["sneak", "w"])
        self.assertEqual(e.tick(3)["keys"], ["sneak"])
        self.send(e, "stand w", 3.1, mid="2")
        self.assertEqual(e.tick(3.1)["keys"], ["sprint", "w"])
        e.reset()
        self.assertEqual(e.tick(3.2)["keys"], [])

    def test_parser_is_strict_and_deduplicates_tokens(self):
        self.assertEqual(parse("HIT W RIGHT slot3"), parse("w right hit slot3"))
        self.assertEqual(parse("w w w"), {"forward": "w"})
        self.assertEqual(parse("w s right"), {"yaw": "right"})
        self.assertEqual(parse("please go right"), {})

    def test_spam_replay_and_invalid_messages(self):
        e = Engine()
        for n in range(10):
            self.assertFalse(self.send(e, "hello", mid=str(n)))
        self.assertTrue(self.send(e, "w"))
        self.assertFalse(self.send(e, "w"))
        self.assertTrue(self.send(e, "w", mid="2"))
        self.assertTrue(self.send(e, "w", mid="3"))
        self.assertFalse(self.send(e, "w", mid="4"))
        self.assertTrue(self.send(e, "w", 1, mid="4"))

    def test_consumes_losing_action_without_replay(self):
        e = Engine()
        for i, text in enumerate(("hit", "hit", "use")):
            self.send(e, text, user=str(i), mid=str(i))
        self.assertEqual(e.tick(0)["pulses"], ["hit"])
        self.assertEqual(e.tick(.1)["pulses"], [])

    def test_activity_is_independent_per_channel(self):
        e = Engine()
        for i in range(250):
            self.send(e, "w", i / 50, str(i), str(i))
        self.send(e, "slot3", 5, "pack", "pack")
        out = e.tick(5)
        self.assertEqual(out["channels"]["forward"]["window_ms"], 300)
        self.assertEqual(out["channels"]["slot"]["window_ms"], 1200)
        self.assertEqual(out["slot"], 3)

    def test_clock_and_config_validation(self):
        e = Engine()
        e.tick(5)
        with self.assertRaises(ValueError):
            e.tick(4)
        with self.assertRaises(ValueError):
            Config(window_min=2, window_max=1)


if __name__ == "__main__":
    unittest.main()
