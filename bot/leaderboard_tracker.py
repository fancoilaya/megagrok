# bot/leaderboard_tracker.py
# Shared module for detecting leaderboard rank changes
# and broadcasting announcements to a public Telegram channel.

import os
import json

# Persistent snapshot file
CACHE_PATH = "/var/data/leaderboard_cache.json"

# Channel where rank-change announcements will be posted
LEADERBOARD_CHANNEL_ID = os.getenv("LEADERBOARD_CHANNEL_ID")


# ---------------------------------------------------------
# Cache Helpers
# ---------------------------------------------------------
def _load_cache():
    try:
        if not os.path.exists(CACHE_PATH):
            return {}
        with open(CACHE_PATH, "r") as f:
            return json.load(f)
    except:
        return {}


def _save_cache(data):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            json.dump(data, f)
    except:
        pass


def _snapshot(users):
    """
    Convert get_top_users() → {user_id: rank}
    """
    snap = {}
    for i, u in enumerate(users):
        snap[str(u["user_id"])] = i + 1
    return snap


def _detect(old_snap, new_snap):
    """
    Returns list of (user_id(str), old_rank or None, new_rank or None)
    """
    changes = []
    keys = set(list(old_snap.keys()) + list(new_snap.keys()))

    for k in keys:
        old = old_snap.get(k)
        new = new_snap.get(k)
        if old != new:
            changes.append((k, old, new))

    return changes


# ---------------------------------------------------------
# MAIN PUBLIC FUNCTION — CALL THIS AFTER XP CHANGES
# ---------------------------------------------------------
def announce_leaderboard_if_changed(bot, top_n=20):
    """
    - Recomputes leaderboard
    - Detects changes
    - Posts messages to public channel
    """

    if not LEADERBOARD_CHANNEL_ID:
        return []  # announcements disabled

    try:
        from bot.db import get_top_users
        users = get_top_users(limit=top_n)
    except Exception:
        return []

    new_snap = _snapshot(users)
    old_snap = _load_cache()
    changes = _detect(old_snap, new_snap)

    uid_map = {str(u["user_id"]): u for u in users}
    announcements = []

    for uid, old_rank, new_rank in changes:
        user = uid_map.get(uid)
        username = (user and user.get("username")) or f"User{uid}"
        tag = f"@{username.lstrip('@')}"

        # Build message
        if old_rank is None and new_rank is not None:
            msg = f"🔥 *NEW ENTRY!* {tag} enters the Top {top_n} at **#{new_rank}**!"
        elif new_rank is None:
            msg = f"⚔️ {tag} has dropped out of the Top {top_n} (was #{old_rank})."
        else:
            # Movement inside the leaderboard
            if new_rank < old_rank:
                if new_rank == 1:
                    msg = f"👑 *NEW #1!* {tag} is now **Rank #1**!"
                else:
                    msg = f"🚀 *RANK UP!* {tag} climbed from **#{old_rank}** → **#{new_rank}**!"
            else:
                msg = f"🔻 *RANK DOWN!* {tag} dropped from **#{old_rank}** → **#{new_rank}**."

        # Send to public channel
        try:
            bot.send_message(int(LEADERBOARD_CHANNEL_ID), msg, parse_mode="Markdown")
            announcements.append(msg)
        except:
            pass

    # Save snapshot
    _save_cache(new_snap)

    return announcements
