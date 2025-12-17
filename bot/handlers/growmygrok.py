# bot/handlers/growmygrok.py
# GrowMyGrok 2.2 — Cleaned + cooldown migration + optional debug logging
# STEP 1: Mode explanation UI added (NO logic refactor yet)

import os
import time
import random
from telebot import TeleBot
from telebot import types

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

MODE_DESCRIPTIONS = {
    "train": (
        "🛠️ <b>Train</b> — Low Risk\n"
        "• Small, guaranteed XP\n"
        "• Safe progression\n"
        "• No penalties"
    ),
    "forage": (
        "🍃 <b>Forage</b> — Medium Risk\n"
        "• Higher XP potential\n"
        "• Chance of failure\n"
        "• Balanced choice"
    ),
    "gamble": (
        "🎲 <b>Gamble</b> — High Risk\n"
        "• Massive XP if successful\n"
        "• Chance to lose XP\n"
        "• High-risk, high-reward"
    ),
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

MAX_LOSS_PCT = 0.05
DEBUG = os.getenv("DEBUG_GROW", "0") in ("1", "true", "True", "TRUE")

# ----------------------------
# Helpers
# ----------------------------
def _now_ts():
    return int(time.time())


def _debug(*args):
    if DEBUG:
        print("[growmygrok DEBUG]", *args)


def _load_cooldowns(uid: int) -> dict:
    try:
        cd = get_cooldowns(uid)
        return cd if isinstance(cd, dict) else {}
    except Exception as e:
        _debug("Cooldown load failed:", e)
        return {}


def _save_cooldowns(uid: int, cd: dict):
    try:
        set_cooldowns(uid, cd)
    except Exception as e:
        _debug("Cooldown save failed:", e)


def _time_of_day_modifier():
    hr = time.localtime().tm_hour
    if 6 <= hr < 12:
        return (5, 1.0)
    if 18 <= hr < 22:
        return (0, 1.10)
    if 0 <= hr < 4:
        return (0, 0.95)
    return (0, 1.0)


def _cap_negative(value: int, xp_to_next: int) -> int:
    if value >= 0:
        return value
    cap = max(1, int(xp_to_next * MAX_LOSS_PCT))
    return -min(cap, abs(value))


def _apply_leveling_and_persist(uid: int, user_before: dict, delta_xp: int):
    level = int(user_before.get("level", 1))
    xp_total = int(user_before.get("xp_total", 0))
    cur = int(user_before.get("xp_current", 0))
    xp_to_next = int(user_before.get("xp_to_next_level", 100))
    curve = float(user_before.get("level_curve_factor", 1.15))

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
        "level": level,
    })

    return get_user(uid), leveled_up, leveled_down


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

        # --------------------------------------------------
        # MODE SELECTION UI (shown every time)
        # --------------------------------------------------
        if len(args) == 1:
            kb = types.InlineKeyboardMarkup(row_width=1)
            for mode in XP_RANGES:
                kb.add(
                    types.InlineKeyboardButton(
                        MODE_DESCRIPTIONS[mode].split("\n")[0],
                        callback_data=f"grow:{mode}"
                    )
                )

            text = (
                "🌱 <b>Choose how to grow your Grok</b>\n\n"
                f"{MODE_DESCRIPTIONS['train']}\n\n"
                f"{MODE_DESCRIPTIONS['forage']}\n\n"
                f"{MODE_DESCRIPTIONS['gamble']}\n\n"
                "👇 Select an option below:"
            )

            return bot.send_message(
                message.chat.id,
                text,
                reply_markup=kb,
                parse_mode="HTML"
            )

        action = args[1].lower()
        if action not in XP_RANGES:
            return bot.reply_to(message, "❌ Invalid grow mode.")

        user = get_user(uid)
        if not user:
            return bot.reply_to(message, "❌ You do not have a Grok yet.")

        cd = _load_cooldowns(uid)
        last_used = cd.get("grow_last_action", 0)

        if last_used and now - last_used < GLOBAL_GROW_COOLDOWN:
            left = GLOBAL_GROW_COOLDOWN - (now - last_used)
            m, s = divmod(left, 60)
            return bot.reply_to(
                message,
                f"⏳ You must wait {m}m {s}s before growing again.",
                parse_mode="HTML"
            )

        # --------------------------------------------------
        # EXISTING XP LOGIC (UNCHANGED)
        # --------------------------------------------------
        lo, hi = XP_RANGES[action]
        base_xp = random.randint(lo, hi)

        flat_td, pct_td = _time_of_day_modifier()
        evo_mult = evolutions.get_xp_multiplier_for_level(int(user.get("level", 1)))
        streak = int(cd.get(STREAK_KEY, 0))
        streak_mult = 1.0 + min(STREAK_CAP, streak) * STREAK_BONUS_PER

        effective = base_xp
        if effective > 0:
            effective = int(round(effective * pct_td))
        effective += flat_td
        effective = int(round(effective * evo_mult * streak_mult))

        micro = _maybe_micro_event()
        micro_msg = None
        if micro:
            _, micro_msg, mdelta = micro
            if mdelta < 0:
                mdelta = _cap_negative(mdelta, int(user.get("xp_to_next_level", 100)))
            effective += mdelta

        effective = _cap_negative(effective, int(user.get("xp_to_next_level", 100)))
        success = effective > 0

        new_user, leveled_up, leveled_down = _apply_leveling_and_persist(uid, user, effective)

        cd["grow_last_action"] = now
        cd[STREAK_KEY] = (streak + 1) if success else 0
        _save_cooldowns(uid, cd)

        record_quest(uid, "grow")
        announce_leaderboard_if_changed(bot)

        # --------------------------------------------------
        # RESULT MESSAGE (UNCHANGED STRUCTURE)
        # --------------------------------------------------
        parts = [
            MODE_DESCRIPTIONS[action].split("\n")[0],
            f"📈 Effective XP: <code>{effective:+d}</code>",
        ]

        if success:
            parts.append(f"🔥 Streak: {cd[STREAK_KEY]}")
        else:
            parts.append("❌ Streak reset.")

        if micro_msg:
            parts.append(micro_msg)
        if leveled_up:
            parts.append("🎉 <b>LEVEL UP!</b>")
        if leveled_down:
            parts.append("💀 <b>LEVEL DOWN!</b>")

        cur = new_user["xp_current"]
        nxt = new_user["xp_to_next_level"]
        pct = int((cur / nxt) * 100) if nxt > 0 else 0
        filled = int((pct / 100) * 20)
        bar = "▓" * filled + "░" * (20 - filled)

        parts.append(f"🧬 Level {new_user['level']} — <code>{bar}</code> {pct}%")
        parts.append(f"➡️ XP needed to next level: <b>{nxt - cur}</b>")
        parts.append("⏳ Next grow available in 45m")

        bot.reply_to(message, "\n".join(parts), parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("grow:"))
    def grow_callback(call):
        mode = call.data.split(":", 1)[1]
        call.message.text = f"/growmygrok {mode}"
        grow_handler(call.message)
        # DO NOT answer callback (prevents timeout issues)

    _debug("growmygrok handler registered")
