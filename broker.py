# ============================================
#  TwitchBroker - Full EventSub Publisher
#  Envoie tous les events Twitch → Mod Fabric
# ============================================

import asyncio
import socket
import json
import unicodedata
import re
import os
from dotenv import load_dotenv
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.helper import first

# ===========================
#  LOAD ENV
# ===========================
load_dotenv()

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_USERNAME = os.getenv("TWITCH_USERNAME")

if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET or not TWITCH_USERNAME:
    raise RuntimeError("Variables .env manquantes : TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET / TWITCH_USERNAME")


# ===========================
#  Utils
# ===========================
def _norm(s: str) -> str:
    if not s:
        return ''
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip().casefold()


# ===========================
#  PUBLISH TO FABRIC MOD
# ===========================
MOD_HOST = "127.0.0.1"
MOD_PORT = 25570

def publish_to_mod(event_type: str, event_name: str, value=None):
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
    except Exception as e:
        # VERSION QUI N’IGNORE PAS L’ÉVÈNEMENT
        print(f"[BROKER] Failed to send (mod offline?) → {payload}")
        print(f"[ERROR] {e}")
        # Pas de “ignore”, tu logs seulement.


# ===========================
#  CALLBACKS EVENTSUB
# ===========================

# Points de chaîne (custom reward)
async def on_points_redeem(data):
    ev = data.event
    title = ev.reward.title
    user = ev.user_name
    publish_to_mod("points", "reward_redeem", {
        "user": user,
        "reward": title
    })


# Follow
async def on_follow(data):
    ev = data.event
    follower = ev.user_name
    publish_to_mod("follow", "new_follower", follower)


# Subscription (NOUVEAU SUB, non gift)
async def on_sub(data):
    ev = data.event
    publish_to_mod("sub", "new", {
        "user": ev.user_name,
        "tier": ev.tier,
        "is_gift": ev.is_gift,  # true si c'est un sub reçu via gift
    })


# Re-sub (message de resub)
async def on_resub(data):
    ev = data.event
    publish_to_mod("sub", "resub", {
        "user": ev.user_name,
        "months": ev.cumulative_months,
        "tier": ev.tier
    })


# Sub gifted (gift bundle)
async def on_sub_gift(data):
    ev = data.event
    gifter = ev.user_name  # peut être None
    publish_to_mod("sub", "gift", {
        "gifter": gifter,
        "total": ev.total,
        "tier": ev.tier,
        "cumulative_total": ev.cumulative_total,
        "is_anonymous": ev.is_anonymous
    })


# Bits
async def on_bits(data):
    ev = data.event
    publish_to_mod("bits", "cheer", {
        "user": ev.user_name,
        "bits": ev.bits
    })


# # Raid
# async def on_raid(data):
#     ev = data.event
#     publish_to_mod("raid", "incoming_raid", {
#         "from": ev.from_broadcaster_user_name,
#         "viewers": ev.viewers
#     })


# ===========================
#  MAIN EVENT LOOP
# ===========================
async def main():
    print("[SYSTEM] Init Twitch…")
    twitch = await Twitch(TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET)
    await twitch.authenticate_app([])

    user = await first(twitch.get_users(logins=[TWITCH_USERNAME.lower()]))
    user_id = user.id
    print(f"[SYSTEM] Broadcaster ID = {user_id}")

    # Permissions complètes
    scopes = [
        AuthScope.CHANNEL_READ_REDEMPTIONS,
        AuthScope.CHANNEL_READ_SUBSCRIPTIONS,
        AuthScope.MODERATOR_READ_FOLLOWERS,
        AuthScope.BITS_READ
    ]

    auth = UserAuthenticator(twitch, scopes)
    token, refresh = await auth.authenticate()
    await twitch.set_user_authentication(token, scopes, refresh)

    eventsub = EventSubWebsocket(twitch)
    eventsub.start()

    # Listen events
    await eventsub.listen_channel_points_custom_reward_redemption_add(user_id, on_points_redeem)
    await eventsub.listen_channel_follow_v2(user_id, user_id, on_follow)
    await eventsub.listen_channel_subscribe(user_id, on_sub)
    await eventsub.listen_channel_subscription_message(user_id, on_resub)
    await eventsub.listen_channel_subscription_gift(user_id, on_sub_gift)
    await eventsub.listen_channel_cheer(user_id, on_bits)
    # await eventsub.listen_channel_raid(user_id, on_raid)

    print("[SYSTEM] TwitchBroker en écoute. Ctrl+C pour quitter.")

    try:
        while True:
            await asyncio.sleep(1)
    finally:
        await eventsub.stop()
        await twitch.close()


if __name__ == "__main__":
    asyncio.run(main())
