# bot/handlers/hop.py
# Hop 2.2 — XP Hub integrated (single-message UX, command preserved)

import os
import time
import random
from telebot import TeleBot, types

from bot.db import (
    get_user,
    update_user_xp,
    get_quests,
    record_quest,
    get_cooldowns,
    set_cooldowns,
)

import bot.evolutions as evolutions
from bot.leaderboard_tracker import announce_leaderboard_if_changed

# -------------------------
# Config
# -------------------------
GLOBAL_HOP_KEY = "hop"
HOP_STREAK_KEY = "hop_streak"
HOP_LAST_DAY_KEY = "hop_last_day"

DEBUG = os.getenv("DEBUG_HOP", "0") in ("1", "true", "True", "TRUE")
MICRO_EVENT_CHANCE = 0.10


def _debug(*args):
    if DEBUG:
        print("[HOP DEBUG]", *args)


# -------------------------
# Helpers
# -------------------------
def _now_day():
    return int(time.time() // 86400)


def _safe_get_cd(uid):
    try:
        cd = get_cooldowns(uid)
        return cd if isinstance(cd, dict) else {}
    except Exception:
        return {}


def _safe_set_cd(uid, cd):
    try:
        set_cooldowns(uid, cd)
    except Exception:
        pass


def _rarity_and_base():
    r = random.random()
    if r < 0.01:
        return "legendary", random.randint(150, 250)
    if r < 0.10:
        return "epic", random.randint(70, 120)
    if r < 0.30:
        return "rare", random.randint(35, 65)
    return "common", random.randint(15, 35)


def _micro_event_roll():
    if random.random() < MICRO_EVENT_CHANCE:
        return random.choice([
            ("🍃 Lucky Leaf", random.randint(10, 25)),
            ("🌌 Cosmic Ripple", random.randint(20, 50)),
            ("💦 Hop Slip", random.randint(-15, -5)),
            ("🐸 Spirit Whisper", 0),
        ])
    return None


def _streak_bonus_pct(streak: int) -> int:
    if streak >= 30:
        return 20
    if streak >= 14:
        return 15
    if streak >= 7:
        return 10
    if streak >= 5:
        return 7
    if streak >= 3:
        return 5
    if streak == 2:
        return 3
    return 0


# -------------------------
# PUBLIC UI ENTRY
# -------------------------
def show_hop_ui(bot: TeleBot, chat_id: int, message_id: int | None = None):
    text = (
        "🐾 <b>HOP</b>\n\n"
        "Leap through the rift and see what you find.\n"
        "You can hop <b>once per day</b>.\n\n"
        "👇 Ready?"
    )

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🐾 Hop Now", callback_data="hop:go"),
        types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="xphub:home"),
    )

    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb, parse_mode="HTML")
    else:
        bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")


# -------------------------
# CORE EXECUTION (shared)
# -------------------------
def _execute_hop(uid: int):
    user = get_user(uid)
    if not user:
        return None, "❌ You do not have a Grok yet."

    quests = get_quests(uid)
    if quests.get(GLOBAL_HOP_KEY) == 1:
        return None, "🕒 You already hopped today."

    cd = _safe_get_cd(uid)
    today = _now_day()
    last_day = cd.get(HOP_LAST_DAY_KEY)

    prev_streak = int(cd.get(HOP_STREAK_KEY, 0) or 0)
    if last_day == today - 1:
        streak = prev_streak + 1
    else:
        streak = 1

    bonus_pct = _streak_bonus_pct(streak)
    rarity, base_xp = _rarity_and_base()

    micro = _micro_event_roll()
    micro_label = None
    if micro:
        micro_label, delta = micro
        base_xp += delta

    evo_mult = evolutions.get_xp_multiplier_for_level(user["level"])
    effective = int(round(base_xp * (1 + bonus_pct / 100) * evo_mult))

    # Apply XP
    level = user["level"]
    cur = user["xp_current"] + effective
    nxt = user["xp_to_next_level"]
    curve = user.get("level_curve_factor", 1.15)
    leveled = False

    while cur >= nxt:
        cur -= nxt
        level += 1
        nxt = int(nxt * curve)
        leveled = True

    update_user_xp(uid, {
        "level": level,
        "xp_current": cur,
        "xp_to_next_level": nxt,
        "xp_total": user["xp_total"] + effective,
    })

    cd[HOP_STREAK_KEY] = streak
    cd[HOP_LAST_DAY_KEY] = today
    _safe_set_cd(uid, cd)

    record_quest(uid, GLOBAL_HOP_KEY)
    announce_leaderboard_if_changed(None)

    return {
        "rarity": rarity,
        "xp": effective,
        "streak": streak,
        "bonus": bonus_pct,
        "leveled": leveled,
        "micro": micro_label,
        "level": level,
        "cur": cur,
        "nxt": nxt,
    }, None


# -------------------------
# Handlers
# -------------------------
def setup(bot: TeleBot):

    @bot.message_handler(commands=["hop"])
    def hop_cmd(message):
        show_hop_ui(bot, message.chat.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("hop:"))
    def hop_cb(call):
        chat_id = call.message.chat.id
        msg_id = call.message.message_id
        uid = call.from_user.id

        if call.data == "hop:go":
            result, err = _execute_hop(uid)
            if err:
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="xphub:home"))
                bot.edit_message_text(err, chat_id, msg_id, reply_markup=kb)
                return

            rarity_emoji = {
                "legendary": "🌈",
                "epic": "💎",
                "rare": "✨",
                "common": "🐸",
            }.get(result["rarity"], "🐸")

            text = (
                f"{rarity_emoji} <b>{result['rarity'].upper()} HOP!</b>\n\n"
                f"📈 XP gained: <b>{result['xp']}</b>\n"
                f"🔥 Streak: {result['streak']} days (+{result['bonus']}%)"
            )

            if result["micro"]:
                text += f"\n\n{result['micro']}"
            if result["leveled"]:
                text += "\n\n🎉 <b>LEVEL UP!</b>"

            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="xphub:home"))

            bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb, parse_mode="HTML")
