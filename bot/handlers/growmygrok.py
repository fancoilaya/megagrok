# bot/handlers/growmygrok.py
# GrowMyGrok 2.1 — Train / Forage / Gamble with:
# - Always-visible streak info
# - XP needed to level
# - Time until next action
# - Mode display
# - Micro-events, fair XP loss, streak bonuses, evo scaling

import os
import time
import random
import json
from telebot import TeleBot

from bot.db import (
    get_user,
    update_user_xp,
    get_quests,
    record_quest,
    get_cooldowns,
    set_cooldowns
)
from bot.utils import safe_send_gif
import bot.evolutions as evolutions
from bot.leaderboard_tracker import announce_leaderboard_if_changed

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

COOLDOWNS = {
    "train": 20 * 60,     # 20m
    "forage": 30 * 60,    # 30m
    "gamble": 45 * 60     # 45m
}

XP_RANGES = {
    "train": (-2, 10),
    "forage": (-8, 20),
    "gamble": (-25, 40)
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

MAX_LOSS_PCT = 0.05  # cap negative XP to 5% of xp_to_next_level


# ---------------------------------------------------------
# UTILS
# ---------------------------------------------------------

def _now_ts():
    return int(time.time())


def _user_cooldowns(uid: int) -> dict:
    try:
        cd = get_cooldowns(uid)
        if isinstance(cd, dict):
            return cd
    except:
        pass
    return {}


def _save_user_cooldowns(uid: int, cd: dict):
    try:
        set_cooldowns(uid, cd)
    except:
        pass


def _time_of_day_modifier():
    hr = time.localtime().tm_hour
    if 6 <= hr < 12:
        return (5, 1.0, 1.0)      # +5 XP morning
    if 18 <= hr < 22:
        return (0, 1.10, 1.0)     # +10% XP evening
    if 0 <= hr < 4:
        return (0, 0.95, 1.2)     # slight negative risk late night
    return (0, 1.0, 1.0)


def _cap_negative_loss(value: int, xp_to_next: int):
    if value >= 0:
        return value
    cap = max(1, int(xp_to_next * MAX_LOSS_PCT))
    return -min(cap, abs(value))


def _apply_leveling_logic_and_persist(uid, user_before, delta_xp):
    level = int(user_before["level"])
    xp_total = int(user_before["xp_total"])
    cur = int(user_before["xp_current"])
    xp_to_next = int(user_before["xp_to_next_level"])
    curve = float(user_before["level_curve_factor"])

    xp_total = max(0, xp_total + delta_xp)
    cur += delta_xp

    leveled_up = False
    leveled_down = False

    while cur >= xp_to_next:
        cur -= xp_to_next
        level += 1
        xp_to_next = int(max(1, xp_to_next * curve))
        leveled_up = True

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

    return get_user(uid), leveled_up, leveled_down


def _maybe_micro_event():
    if random.random() < MICRO_EVENT_CHANCE:
        return random.choice(MICRO_EVENTS)
    return None


# ---------------------------------------------------------
# HANDLER
# ---------------------------------------------------------

def setup(bot: TeleBot):

    @bot.message_handler(commands=["growmygrok"])
    def grow(message):
        uid = message.from_user.id
        args = (message.text or "").split()

        # Mode selection
        action = "train"
        if len(args) > 1 and args[1].lower() in XP_RANGES:
            action = args[1].lower()

        now = _now_ts()

        user = get_user(uid)
        if not user:
            return bot.reply_to(message, "❌ You do not have a Grok yet.")

        # Cooldowns
        cd = _user_cooldowns(uid)
        last_ts = cd.get("grow_last_action", {}).get(action, 0)
        cd_seconds = COOLDOWNS[action]

        if last_ts and now - last_ts < cd_seconds:
            left = cd_seconds - (now - last_ts)
            m, s = left // 60, left % 60
            return bot.reply_to(
                message,
                f"⏳ You must wait {m}m {s}s before using <code>{action}</code> again.",
                parse_mode="HTML"
            )

        # XP roll
        lo, hi = XP_RANGES[action]
        base = random.randint(lo, hi)

        flat_td, pct_td, _lossrisk_td = _time_of_day_modifier()

        # Evolution multiplier
        try:
            evo_mult = (
                evolutions.get_xp_multiplier_for_level(user["level"])
                * float(user.get("evolution_multiplier", 1.0))
            )
        except:
            evo_mult = 1.0

        # Streak
        streak = int(cd.get(STREAK_KEY, 0))
        streak_mult = 1.0 + min(STREAK_CAP, streak) * STREAK_BONUS_PER

        # Apply multipliers
        effective = base

        if effective > 0:
            effective = int(round(effective * pct_td))

        effective += flat_td
        effective = int(round(effective * evo_mult * streak_mult))

        # Micro-event
        micro = _maybe_micro_event()
        micro_msg = None
        if micro:
            key, msg_text, delta = micro
            micro_msg = msg_text
            if delta < 0:
                delta = _cap_negative_loss(delta, user["xp_to_next_level"])
            effective += delta

        if effective < 0:
            effective = _cap_negative_loss(effective, user["xp_to_next_level"])

        success = effective > 0

        # Persist XP
        new_user, up, down = _apply_leveling_logic_and_persist(uid, user, effective)

        # Update cooldowns
        cd.setdefault("grow_last_action", {})
        cd["grow_last_action"][action] = now
        cd[STREAK_KEY] = (streak + 1) if success else 0
        _save_user_cooldowns(uid, cd)

        # Leaderboard updates
        try:
            announce_leaderboard_if_changed(bot)
        except:
            pass

        # Build message
        mode_names = {
            "train": "🛠️ Train (low risk)",
            "forage": "🍃 Forage (medium risk)",
            "gamble": "🎲 Gamble (high risk)"
        }

        parts = []
        parts.append(f"{mode_names[action]}")
        parts.append(f"📈 Effective XP: <code>{effective:+d}</code>")

        # Always show streak (Option B)
        new_streak = cd.get(STREAK_KEY, 0)
        bonus_pct = int(new_streak * STREAK_BONUS_PER * 100)
        if success:
            parts.append(f"🔥 Streak: {new_streak} (bonus +{bonus_pct}%)")
        else:
            parts.append("❌ Streak reset.")

        if micro_msg:
            parts.append(micro_msg)

        if up:
            parts.append("🎉 <b>LEVEL UP!</b>")
        if down:
            parts.append("💀 <b>LEVEL DOWN!</b>")

        # Progress bar + XP needed
        cur = new_user["xp_current"]
        nxt = new_user["xp_to_next_level"]
        pct = int((cur / nxt) * 100) if nxt > 0 else 0

        bar_len = 20
        filled = int((pct / 100) * bar_len)
        bar = "▓" * filled + "░" * (bar_len - filled)
        xp_needed = max(0, nxt - cur)

        parts.append(f"🧬 Level {new_user['level']} — <code>{bar}</code> {pct}% ({cur}/{nxt})")
        parts.append(f"➡️ XP needed to next level: <b>{xp_needed}</b>")

        # Next action timer
        parts.append(f"⏳ Next {action} available in {cd_seconds//60}m {cd_seconds%60}s")

        return bot.reply_to(message, "\n".join(parts), parse_mode="HTML")
