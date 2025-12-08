# bot/handlers/hop.py
# Hop 2.0 — Rarity Hops + Streak System + Micro-Events + Evolution Scaling
# Daily limited. Fully balanced with GrowMyGrok/Battle XP system.

import os
import time
import random
from telebot import TeleBot

from bot.db import (
    get_user,
    update_user_xp,
    get_quests,
    record_quest,
)

import bot.evolutions as evolutions

from bot.leaderboard_tracker import announce_leaderboard_if_changed

# ------------ CONFIG ----------------------------------

# Hop is once per day
HOP_DAILY_KEY = "hop"

# Debug toggle
DEBUG = os.getenv("DEBUG_HOP", "0") in ("1", "true", "True", "TRUE")

def _debug(*args):
    if DEBUG:
        print("[HOP DEBUG]:", *args)


# ------------ HELPERS ----------------------------------

def _now_day():
    """Return current day number as integer (UTC)."""
    return int(time.time() // 86400)


def _get_streak(user):
    cooldowns = user.get("cooldowns") or {}
    streak = cooldowns.get("hop_streak", 0)
    last_day = cooldowns.get("hop_last_day", None)

    today = _now_day()

    if last_day is None:
        return streak, today, True  # new user, fresh streak

    if last_day == today - 1:
        # Continued streak
        return streak, today, True
    elif last_day == today:
        # Already hopped today, streak stays same
        return streak, today, False
    else:
        # Missed a day → streak resets
        return 0, today, True


def _save_streak(uid, new_streak, today):
    from bot.db import set_cooldowns
    cooldowns = {
        "hop_streak": new_streak,
        "hop_last_day": today
    }
    set_cooldowns(uid, cooldowns)


def _rarity_roll():
    """Return rarity name and base XP range."""
    r = random.random()
    if r < 0.01:
        return "legendary", random.randint(150, 250)
    elif r < 0.10:
        return "epic", random.randint(70, 120)
    elif r < 0.30:
        return "rare", random.randint(35, 65)
    else:
        return "common", random.randint(15, 35)


def _micro_event():
    """10% chance of micro-event."""
    if random.random() < 0.10:
        events = [
            ("🍃 Lucky Leaf", random.randint(10, 25)),
            ("🌌 Cosmic Ripple", random.randint(20, 50)),
            ("💦 Hop Slip", random.randint(-15, -5)),
            ("🐸 Spirit Whisper", 0),
        ]
        return random.choice(events)
    return None


# ------------ MAIN HANDLER -----------------------------

def setup(bot: TeleBot):

    @bot.message_handler(commands=["hop"])
    def hop_handler(message):
        uid = message.from_user.id
        user = get_user(uid)

        if not user:
            return bot.reply_to(message, "❌ You do not have a Grok yet.")

        # Check if hop already done today
        quests = get_quests(uid)
        if quests.get(HOP_DAILY_KEY, 0) == 1:
            return bot.reply_to(message, "🕒 You already used /hop today.")

        # Handle streak logic
        streak, today, can_continue = _get_streak(user)
        _debug("streak_before:", streak, "today:", today, "can_continue:", can_continue)

        if can_continue:
            streak = streak + 1 if streak > 0 else 1  # start at 1
        bonus_pct = min(20,  # cap bonus
                        0 + (3 if streak >= 2 else 0) +
                        (2 if streak >= 3 else 0) +
                        (2 if streak >= 5 else 0) +
                        (3 if streak >= 7 else 0) +
                        (5 if streak >= 14 else 0) +
                        (5 if streak >= 30 else 0))

        # Rarity roll
        rarity, base_xp = _rarity_roll()

        # Micro-event
        micro = _micro_event()
        micro_label = None
        micro_xp = 0
        if micro:
            micro_label, micro_xp = micro
            base_xp += micro_xp

        # Evolution multiplier
        try:
            evo_mult = float(evolutions.get_xp_multiplier_for_level(user["level"]))
            evo_mult *= float(user.get("evolution_multiplier", 1.0))
        except Exception as e:
            _debug("Evolution multiplier failed:", e)
            evo_mult = 1.0

        # Apply streak multiplier
        effective = int(base_xp * (1 + bonus_pct / 100.0) * evo_mult)

        # Persist XP and level logic
        prev = user
        level = prev["level"]
        total = prev["xp_total"] + effective
        cur = prev["xp_current"] + effective
        nxt = prev["xp_to_next_level"]
        curve = prev["level_curve_factor"]

        leveled = False
        while cur >= nxt:
            cur -= nxt
            nxt = int(nxt * curve)
            level += 1
            leveled = True

        update_user_xp(uid, {
            "xp_total": total,
            "xp_current": cur,
            "xp_to_next_level": nxt,
            "level": level
        })

        # Save streak + hop usage
        _save_streak(uid, streak, today)
        record_quest(uid, HOP_DAILY_KEY)

        # Announce leaderboard change
        try:
            announce_leaderboard_if_changed(bot)
        except:
            pass

        # Build progress bar
        pct = int((cur / nxt) * 100)
        bar_len = 20
        filled = int(bar_len * pct / 100)
        bar = "▓" * filled + "░" * (bar_len - filled)

        # Emoji per rarity
        rarity_emoji = {
            "legendary": "🌈",
            "epic": "💎",
            "rare": "✨",
            "common": "🐸",
        }[rarity]

        # Build output
        parts = []
        parts.append(f"{rarity_emoji} <b>{rarity.upper()} HOP!</b>")
        parts.append(f"📈 XP gained: <b>{effective}</b>")

        if micro_label:
            parts.append(f"{micro_label} ({'+' if micro_xp>0 else ''}{micro_xp} XP)")

        parts.append(f"🔥 Hop streak: <b>{streak} days</b> (+{bonus_pct}% bonus)")
        if leveled:
            parts.append("🎉 <b>LEVEL UP!</b>")

        parts.append(f"🧬 Level {level} — <code>{bar}</code> {pct}% ({cur}/{nxt})")
        parts.append("⏳ Next hop available tomorrow")

        bot.reply_to(message, "\n".join(parts), parse_mode="HTML")
