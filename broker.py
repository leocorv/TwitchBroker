# ============================
#  SurvieInteract - Twitch Broker
#  Twitch EventSub → TCP → Mod Fabric (port 25570)
# ============================



# =============================
#  IMPORTS
# =============================
import asyncio
import json
import socket
import unicodedata
import re

from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.helper import first

from dotenv import load_dotenv
import os

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_USERNAME = os.getenv("TWITCH_USERNAME").lower()

# ============================
#  Utils
# ============================

def _norm(s: str) -> str:
    if not s:
        return ''
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip().casefold()


# ============================
#  Publisher vers Minecraft
# ============================

MOD_HOST = "127.0.0.1"
MOD_PORT = 25570

def publish_to_mod(event_type: str, event_name: str, value=None):
    """Envoie un JSON au mod Fabric via TCP (push-only)."""
    payload = {
        "event_type": event_type,
        "event_name": event_name
    }
    if value is not None:
        payload["value"] = value

    data = json.dumps(payload) + "\n"

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        s.connect((MOD_HOST, MOD_PORT))
        s.send(data.encode())
        s.close()
        print(f"[BROKER] Sent → {payload}")
    except Exception:
        print(f"[BROKER] Mod offline, ignored → {payload}")


# ============================
#  EventSub callback
# ============================

async def on_points_redeem(data):
    ev = data.event
    user = ev.user_name
    reward_title = ev.reward.title
    status = ev.status

    print(f"[POINTS] {user} a utilisé: {reward_title} (status={_norm(status)})")

    # Envoi direct au mod Minecraft
    publish_to_mod("points", "reward_redeem", reward_title)


# ============================
#  MAIN
# ============================

async def main():
    print("[SYSTEM] Init Twitch API…")
    twitch = await Twitch(TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET)
    await twitch.authenticate_app([])

    user = await first(twitch.get_users(logins=[TWITCH_USERNAME]))
    user_id = user.id

    print(f"[SYSTEM] Broadcaster ID = {user_id}")

    auth = UserAuthenticator(twitch, [AuthScope.CHANNEL_READ_REDEMPTIONS])
    token, refresh_token = await auth.authenticate()
    await twitch.set_user_authentication(
        token,
        [AuthScope.CHANNEL_READ_REDEMPTIONS],
        refresh_token
    )

    eventsub = EventSubWebsocket(twitch)
    eventsub.start()

    await eventsub.listen_channel_points_custom_reward_redemption_add(
        user_id, on_points_redeem
    )

    print("[SYSTEM] Listening to Twitch… (Ctrl+C pour quitter)")

    try:
        while True:
            await asyncio.sleep(1)
    finally:
        await eventsub.stop()
        await twitch.close()


if __name__ == "__main__":
    asyncio.run(main())
