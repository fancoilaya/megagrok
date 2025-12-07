# bot/handlers/growmygrok.py
# GrowMyGrok 2.2 (clean version) — Universal cooldown, streaks, micro-events,
# time-of-day bonuses, fair XP loss, evolution scaling, leaderboard updates.
# No GIF sending, no external utils imports.

import os
import time
import random
from telebot import TeleBot

from bot.db import (
    get_user,
    update_user_xp,
    get_cooldowns,
    set_cooldowns,
    record_quest
)

import bot.evolutions as evolutions
from bot.leaderboard_tracker import announce_leaderboard_if_changed


# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

GLOBAL_GROW_COOLDOWN = 45 * 60  # 45 minutes

XP_RANGES = {
    "train": (-2, 10),
    "forage": (-8, 20),
    "gamble": (-25, 40),
}

STREAK_KEY = "grow_streak"
STREAK_BONUS_PER = 0.03
STREAK_CAP = 10

MICRO_EVENT_CHANCE = 1 / 20.0
MICRO_EVENTS = [
    ("lucky_find", "🌟 Your Grok found a glowing mushroom!", 50),
    ("bad_weather", "🌧️ Bad weather! Your Grok got damp and lost energy.", -10),
    ("mini_fight", "⚔️ Your Grok fought a tiny critter and trained through the scuffle.", 12),
    ("mystic_whisper", "🔮 A whisper passes — you feel closer to evolution.", 0),
]

MAX_LOSS_PCT = 0.05  # 5% of xp_to_next_level max negative XP


# ---------------------------------------------------------
# INTERNAL HELPERS
# ---------------------------------------------------------

def _now():
    return int(time.time())


def _load_cooldowns(uid: int) -> dict:
    try:
        cd = get_cooldowns(uid)
        return cd if isinstance(cd, dict) else {}
    except:
        return {}


def _save_cooldowns(uid: int, cd: dict):
    try:
        set_cooldowns(uid, cd)
    except:
        pass


def _time_of_day_modifier():
    hr = time.localtime().tm_hour
    if 6 <= hr < 12:
        return (5, 1.0)         # morning +5 XP
    if 18 <= hr < 22:
        return (0, 1.10)        # evening +10%
    if 0 <= hr < 4:
        return (0, 0.95)        # late night slight penalty
    return (0, 1.0)


def _cap_negative(val, xp_to_next):
    if val >= 0:
        return val
    cap = max(1, int(xp_to_next * MAX_LOSS_PCT))
    return -min(cap, abs(val))


def _apply_leveling_and_save(uid, user, delta):
    level = user["level"]
    xp_total = user["xp_total"]
    cur = user["xp_current"]
    nxt = user["xp_to_next_level"]
    curve = user["level_curve_factor"]

    xp_total = max(0, xp_total + delta)
    cur += delta

    leveled_up = False
    leveled_down = False

    while cur >= nxt:
        cur -= nxt
        level += 1
        nxt = int(max(1, nxt * curve))
        leveled_up = True

    while cur < 0 and level > 1:
        level -= 1
        nxt = int(max(1, nxt / curve))
        cur += nxt
        leveled_down = True

    cur = max(0, cur)

    update_user_xp(uid, {
        "xp_total": xp_total,
        "xp_current": cur,
        "xp_to_next_level": nxt,
        "level": level
    })

    return get_user(uid), leveled_up, leveled_down


def _micro_event():
    if random.random() < MICRO_EVENT_CHANCE:
        return random.choice(MICRO_EVENTS)
    return None


# ---------------------------------------------------------
# HANDLER SETUP
# ---------------------------------------------------------

def setup(bot: TeleBot):

    @bot.message_handler(commands=["growmygrok"])
    def grow(message):
        uid = message.from_user.id
        args = (message.text or "").split()

        # Determine action
        action = "train"
        if len(args) > 1 and args[1].lower() in XP_RANGES:
            action = args[1].lower()

        user = get_user(uid)
        if not user:
            return bot.reply_to(message, "❌ You do not have a Grok yet.")

        cd = _load_cooldowns(uid)
        now = _now()

        # Universal cooldown
        last_used = cd.get("grow_last_action", 0)
        if last_used and now - last_used < GLOBAL_GROW_COOLDOWN:
            left = GLOBAL_GROW_COOLDOWN - (now - last_used)
            m, s = left // 60, left % 60
            return bot.reply_to(
                message,
                f"⏳ You must wait {m}m {s}s before using <code>/growmygrok</code> again.",
                parse_mode="HTML"
            )

        # Base XP roll
        lo, hi = XP_RANGES[action]
        base = random.randint(lo, hi)

        # Time-of-day bonuses
        flat_td, pct_td = _time_of_day_modifier()

        # Evolution multiplier
        try:
            evo_mult = (
                evolutions.get_xp_multiplier_for_level(user["level"])
                * float(user.get("evolution_multiplier", 1.0))
            )
        except:
            evo_mult = 1.0

        # Streak multiplier
        streak = int(cd.get(STREAK_KEY, 0))
        streak_mult = 1.0 + min(STREAK_CAP, streak) * STREAK_BONUS_PER

        # XP math
        effective = base
        if effective > 0:
            effective = int(round(effective * pct_td))
        effective += flat_td
        effective = int(round(effective * evo_mult * streak_mult))

        # Micro-event
        micro = _micro_event()
        micro_msg = None
        if micro:
            key, txt, delta = micro
            micro_msg = txt
            if delta < 0:
                delta = _cap_negative(delta, user["xp_to_next_level"])
            effective += delta

        # Final cap negative losses
        if effective < 0:
            effective = _cap_negative(effective, user["xp_to_next_level"])

        success = effective > 0

        # Apply XP + leveling
        new_user, up, down = _apply_leveling_and_save(uid, user, effective)

        # Save cooldown + streak
        cd["grow_last_action"] = now
        cd[STREAK_KEY] = streak + 1 if success else 0
        _save_cooldowns(uid, cd)

        # Update leaderboard
        try:
            announce_leaderboard_if_changed(bot)
        except:
            pass

        # -----------------------------
        # Build Telegram response
        # -----------------------------

        mode_labels = {
            "train": "🛠️ Train (low risk)",
            "forage": "🍃 Forage (medium risk)",
            "gamble": "🎲 Gamble (high risk)",
        }

        parts = []
        parts.append(mode_labels[action])
        parts.append(f"📈 Effective XP: <code>{effective:+d}</code>")

        # Always show streak
        new_streak = cd.get(STREAK_KEY, 0)
        bonus_pct = int(new_streak * STREAK_BONUS_PER * 100)
        parts.append(
            f"🔥 Streak: {new_streak} (bonus +{bonus_pct}%)"
            if success else
            "❌ Streak reset."
        )

        if micro_msg:
            parts.append(micro_msg)

        if up:
            parts.append("🎉 <b>LEVEL UP!</b>")
        if down:
            parts.append("💀 <b>LEVEL DOWN!</b>")

        # Progress bar
        cur = new_user["xp_current"]
        nxt = new_user["xp_to_next_level"]
        pct = int((cur / nxt) * 100) if nxt > 0 else 0

        bar_len = 20
        filled = int((pct / 100) * bar_len)
        bar = "▓" * filled + "░" * (bar_len - filled)

        xp_needed = max(0, nxt - cur)

        parts.append(
            f"🧬 Level {new_user['level']} — <code>{bar}</code> {pct}% ({cur}/{nxt})"
        )
        parts.append(f"➡️ XP needed to next level: <b>{xp_needed}</b>")

        # Universal cooldown message
        parts.append("⏳ Next grow action available in 45m 0s")

        bot.reply_to(message, "\n".join(parts), parse_mode="HTML")
