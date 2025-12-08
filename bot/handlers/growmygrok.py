# bot/handlers/growmygrok.py
# GrowMyGrok 2.2 — Cleaned + cooldown migration + optional debug logging
# Features:
# - Universal 45-minute cooldown
# - Backwards-compatible cooldown migration (old dict -> new int)
# - DEBUG_GROW env toggle to print diagnostic logs
# - Train / Forage / Gamble modes, streaks, micro-events, evo scaling
# - Capped negative XP and leaderboard announce on change
#
# Usage:
#  - Set DEBUG_GROW=1 in env to enable debug prints
#  - Place this at bot/handlers/growmygrok.py and ensure commands.py registers handlers

import os
import time
import random
from telebot import TeleBot

from bot.db import (
    get_user,
    update_user_xp,
    get_cooldowns,
    set_cooldowns,
    record_quest,
)
import bot.evolutions as evolutions
from bot.leaderboard_tracker import announce_leaderboard_if_changed

# ----------------------------
# Configuration
# ----------------------------
GLOBAL_GROW_COOLDOWN = 45 * 60  # 45 minutes

XP_RANGES = {
    "train": (-2, 10),
    "forage": (-8, 20),
    "gamble": (-25, 40),
}

STREAK_KEY = "grow_streak"
STREAK_BONUS_PER = 0.03
STREAK_CAP = 10

MICRO_EVENT_CHANCE = 1.0 / 20.0
MICRO_EVENTS = [
    ("lucky_find", "🌟 Your Grok found a glowing mushroom!", 50),
    ("bad_weather", "🌧️ Bad weather! Your Grok got damp and lost energy.", -10),
    ("mini_fight", "⚔️ Your Grok fought a tiny critter and trained through the scuffle.", 12),
    ("mystic_whisper", "🔮 A whisper passes — you feel closer to evolution.", 0),
]

MAX_LOSS_PCT = 0.05  # negative XP capped to 5% of xp_to_next_level

# Debug toggle
DEBUG = os.getenv("DEBUG_GROW", "0") in ("1", "true", "True", "TRUE")


# ----------------------------
# Helpers
# ----------------------------
def _now_ts():
    return int(time.time())


def _debug(*args, **kwargs):
    if DEBUG:
        print("[growmygrok DEBUG]", *args, **kwargs)


def _load_cooldowns(uid: int) -> dict:
    """
    Load cooldowns safely. Always returns a dict.
    """
    try:
        cd = get_cooldowns(uid)
        if isinstance(cd, dict):
            return cd
        # If DB returned JSON string, db.get_cooldowns should parse it; but be defensive:
        return {}
    except Exception as e:
        _debug("Failed loading cooldowns for", uid, ":", e)
        return {}


def _save_cooldowns(uid: int, cd: dict):
    try:
        set_cooldowns(uid, cd)
    except Exception as e:
        _debug("Failed saving cooldowns for", uid, ":", e)


def _time_of_day_modifier():
    hr = time.localtime().tm_hour
    if 6 <= hr < 12:
        return (5, 1.0)     # +5 flat XP morning
    if 18 <= hr < 22:
        return (0, 1.10)    # +10% evening
    if 0 <= hr < 4:
        return (0, 0.95)    # slight late-night penalty
    return (0, 1.0)


def _cap_negative(value: int, xp_to_next: int) -> int:
    if value >= 0:
        return value
    cap = max(1, int(xp_to_next * MAX_LOSS_PCT))
    return -min(cap, abs(value))


def _apply_leveling_and_persist(uid: int, user_before: dict, delta_xp: int):
    """
    Apply delta_xp to user and persist. Returns new_user, leveled_up, leveled_down.
    """
    level = int(user_before.get("level", 1))
    xp_total = int(user_before.get("xp_total", 0))
    cur = int(user_before.get("xp_current", 0))
    xp_to_next = int(user_before.get("xp_to_next_level", 100))
    curve = float(user_before.get("level_curve_factor", 1.15))

    xp_total = max(0, xp_total + delta_xp)
    cur += delta_xp

    leveled_up = False
    leveled_down = False

    # level up
    while cur >= xp_to_next:
        cur -= xp_to_next
        level += 1
        xp_to_next = int(max(1, xp_to_next * curve))
        leveled_up = True

    # level down
    while cur < 0 and level > 1:
        level -= 1
        xp_to_next = int(max(1, xp_to_next / curve))
        cur += xp_to_next
        leveled_down = True

    cur = max(0, cur)

    update_user_xp(uid, {
        "xp_total": xp_total,
        "xp_current": cur,
        "xp_to_next_level": xp_to_next,
        "level": level
    })

    new_user = get_user(uid)
    return new_user, leveled_up, leveled_down


def _maybe_micro_event():
    if random.random() < MICRO_EVENT_CHANCE:
        return random.choice(MICRO_EVENTS)
    return None


# ----------------------------
# Handler setup
# ----------------------------
def setup(bot: TeleBot):

    @bot.message_handler(commands=["growmygrok"])
    def grow_handler(message):
        uid = message.from_user.id
        args = (message.text or "").split()
        now = _now_ts()

        action = "train"
        if len(args) > 1 and args[1].lower() in XP_RANGES:
            action = args[1].lower()

        user = get_user(uid)
        if not user:
            _debug("No user found for", uid)
            return bot.reply_to(message, "❌ You do not have a Grok yet.")

        # Load cooldowns and migrate old format if needed
        cd = _load_cooldowns(uid)
        _debug("Loaded cooldowns (raw):", cd)

        # MIGRATION: old-format grow_last_action may be a dict like {"train": 170...}
        last_used_raw = cd.get("grow_last_action", 0)

        # If it's a dict (pre-universal-cooldown format), extract a timestamp (first value)
        if isinstance(last_used_raw, dict):
            # pick any integer value inside (prefer numeric)
            extracted = 0
            for v in last_used_raw.values():
                if isinstance(v, int):
                    extracted = v
                    break
                # if stored as string numeric, try parse
                if isinstance(v, str) and v.isdigit():
                    extracted = int(v)
                    break
            last_used = extracted
            cd["grow_last_action"] = last_used
            # persist migration
            try:
                _save_cooldowns(uid, cd)
                _debug(f"Migrated cooldowns for user {uid}: set grow_last_action ->", last_used)
            except Exception as e:
                _debug("Failed to persist migrated cooldowns for", uid, ":", e)
        else:
            # not a dict — might be int or string
            last_used = last_used_raw if isinstance(last_used_raw, int) else (
                int(last_used_raw) if isinstance(last_used_raw, str) and last_used_raw.isdigit() else 0
            )

        # Now last_used is an int
        _debug("Using last_used timestamp:", last_used)

        # Cooldown check (universal)
        if last_used and now - last_used < GLOBAL_GROW_COOLDOWN:
            left = GLOBAL_GROW_COOLDOWN - (now - last_used)
            m, s = divmod(left, 60)
            _debug(f"User {uid} on cooldown, left {m}m {s}s")
            return bot.reply_to(
                message,
                f"⏳ You must wait {m}m {s}s before using <code>/growmygrok</code> again.",
                parse_mode="HTML"
            )

        # Calculate base XP
        lo, hi = XP_RANGES[action]
        base_xp = random.randint(lo, hi)

        # Time-of-day
        flat_td, pct_td = _time_of_day_modifier()

        # Evolution multiplier safely
        try:
            evo_mult = evolutions.get_xp_multiplier_for_level(int(user.get("level", 1)))
            evo_mult *= float(user.get("evolution_multiplier", 1.0))
        except Exception as e:
            _debug("evolutions.get_xp_multiplier_for_level failed:", e)
            evo_mult = 1.0

        # Streak multiplier
        streak = int(cd.get(STREAK_KEY, 0))
        streak_mult = 1.0 + min(STREAK_CAP, streak) * STREAK_BONUS_PER

        # Effective XP math
        effective = base_xp
        if effective > 0:
            effective = int(round(effective * pct_td))
        effective += flat_td
        effective = int(round(effective * evo_mult * streak_mult))

        # Micro event
        micro = _maybe_micro_event()
        micro_msg = None
        if micro:
            key, mmsg, mdelta = micro
            micro_msg = mmsg
            if mdelta < 0:
                mdelta = _cap_negative(mdelta, int(user.get("xp_to_next_level", 100)))
            effective += mdelta

        # Cap negative losses finally
        if effective < 0:
            effective = _cap_negative(effective, int(user.get("xp_to_next_level", 100)))

        success = effective > 0

        # Persist XP and leveling
        try:
            new_user, leveled_up, leveled_down = _apply_leveling_and_persist(uid, user, effective)
        except Exception as e:
            _debug("Leveling/persist failed for", uid, ":", e)
            return bot.reply_to(message, "⚠️ Error applying XP — please try again later.")

        # Update cooldowns & streak and save
        try:
            cd["grow_last_action"] = now
            cd[STREAK_KEY] = (streak + 1) if success else 0
            _save_cooldowns(uid, cd)
        except Exception as e:
            _debug("Failed to update cooldowns for", uid, ":", e)

        # Record quest usage
        try:
            record_quest(uid, "grow")
        except Exception:
            pass

        # Announce leaderboard changes (best-effort)
        try:
            announce_leaderboard_if_changed(bot)
        except Exception as e:
            _debug("announce_leaderboard_if_changed failed:", e)

        # Build reply
        mode_labels = {
            "train": "🛠️ Train (low risk)",
            "forage": "🍃 Forage (medium risk)",
            "gamble": "🎲 Gamble (high risk)",
        }

        parts = []
        parts.append(mode_labels.get(action, action))
        parts.append(f"📈 Effective XP: <code>{effective:+d}</code>")

        # Always show streak
        new_streak = cd.get(STREAK_KEY, 0)
        bonus_pct = int(new_streak * STREAK_BONUS_PER * 100)
        if success:
            parts.append(f"🔥 Streak: {new_streak} (bonus +{bonus_pct}%)")
        else:
            parts.append("❌ Streak reset.")

        if micro_msg:
            parts.append(micro_msg)

        if leveled_up:
            parts.append("🎉 <b>LEVEL UP!</b>")
        if leveled_down:
            parts.append("💀 <b>LEVEL DOWN!</b>")

        # Progress bar & XP needed
        cur = int(new_user.get("xp_current", 0))
        nxt = int(new_user.get("xp_to_next_level", 100))
        pct = int((cur / nxt) * 100) if nxt > 0 else 0
        bar_len = 20
        filled = int((pct / 100.0) * bar_len)
        bar = "▓" * filled + "░" * (bar_len - filled)
        xp_needed = max(0, nxt - cur)

        parts.append(f"🧬 Level {new_user.get('level', 1)} — <code>{bar}</code> {pct}% ({cur}/{nxt})")
        parts.append(f"➡️ XP needed to next level: <b>{xp_needed}</b>")

        # Next action timer (universal cooldown)
        parts.append("⏳ Next grow action available in 45m 0s")

        # Reply
        try:
            bot.reply_to(message, "\n".join(parts), parse_mode="HTML")
        except Exception:
            # fallback plain reply
            try:
                bot.reply_to(message, "\n".join(parts))
            except Exception as e:
                _debug("Failed to send reply for", uid, ":", e)

    _debug("growmygrok handler registered")

