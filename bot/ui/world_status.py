# bot/ui/world_status.py
#
# World status & "since you were gone" UI helpers
# Pure text generation — no bot calls, no edits

import time
import bot.db as db


# -------------------------------------------------
# WORLD STATUS (GLOBAL, CACHED)
# -------------------------------------------------

# Simple in-memory cache (can be replaced later)
_WORLD_STATUS_CACHE = {
    "arena_activity": "Calm",
    "active_trainers": 0,
    "top_grok": "—",
    "updated_at": 0,
}


def get_world_status() -> str:
    """
    Returns a formatted World Status block.
    Uses cached values to avoid heavy queries.
    """

    now = time.time()

    # Refresh every 180 seconds (3 minutes)
    if now - _WORLD_STATUS_CACHE["updated_at"] > 180:
        _refresh_world_status()

    return (
        "🌍 <b>WORLD STATUS</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"⚔️ Arena Activity: {_WORLD_STATUS_CACHE['arena_activity']}\n"
        f"🧠 Trainers Active: {_WORLD_STATUS_CACHE['active_trainers']}\n"
        f"🏆 Current Apex Grok: {_WORLD_STATUS_CACHE['top_grok']}\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
    )


def _refresh_world_status():
    """
    Lightweight refresh of global world stats.
    This should be cheap.
    """
    # NOTE: These DB calls should already exist or be easy
    try:
        _WORLD_STATUS_CACHE["arena_activity"] = db.get_arena_activity_level()  # e.g. Low / Medium / High
    except Exception:
        _WORLD_STATUS_CACHE["arena_activity"] = "Unknown"

    try:
        _WORLD_STATUS_CACHE["active_trainers"] = db.get_active_user_count(hours=24)
    except Exception:
        _WORLD_STATUS_CACHE["active_trainers"] = 0

    try:
        top = db.get_top_users(limit=1)
        _WORLD_STATUS_CACHE["top_grok"] = (
            top[0].get("display_name")
            or top[0].get("username")
            or "—"
        )
    except Exception:
        _WORLD_STATUS_CACHE["top_grok"] = "—"

    _WORLD_STATUS_CACHE["updated_at"] = time.time()


# -------------------------------------------------
# SINCE YOU WERE GONE (PERSONAL)
# -------------------------------------------------

def get_since_you_were_gone(uid: int) -> str:
    """
    Builds a short 'since you were gone' block
    based on rank movement only (Phase 1).
    """

    user = db.get_user(uid)
    if not user:
        return ""

    last_rank = user.get("last_known_rank")
    current_rank = db.get_user_rank(uid)

    lines = []

    if last_rank and current_rank:
        diff = last_rank - current_rank
        if diff > 0:
            lines.append(f"• You climbed +{diff} ranks")
            lines.append("• Momentum is on your side")
        elif diff < 0:
            lines.append(f"• Your rank dropped by {abs(diff)}")
            lines.append("• Other Groks have advanced")
    else:
        lines.append("• No major events affected your Grok")

    # Update snapshot (IMPORTANT)
    db.update_user(uid, {
        "last_known_rank": current_rank,
        "last_awaken_at": int(time.time())
    })

    return (
        "🧬 <b>SINCE YOUR LAST AWAKENING</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines[:2]) +  # max 2 lines
        "\n\n"
    )
