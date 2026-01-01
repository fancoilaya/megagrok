# bot/handlers/hop.py
# -------------------------------------------------
# Hop — Daily XP Ritual
# - Shows cooldown + streak in menu
# - Safe XP Hub integration
# - No signature changes
# -------------------------------------------------

import time
import random
from telebot import TeleBot, types

import bot.db as db
from bot.db import get_quests, record_quest

# -------------------------------------------------
# CONFIG
# -------------------------------------------------

GLOBAL_HOP_KEY = "hop_used_today"
HOP_STREAK_KEY = "hop_streak"

# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _utc_midnight_ts() -> int:
    now = int(time.time())
    return now - (now % 86400) + 86400

def _seconds_until_next_day() -> int:
    return max(0, _utc_midnight_ts() - int(time.time()))

def _format_hms(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"

def _safe_get_cd(user_id: int) -> dict:
    return db.get_cooldowns(user_id) or {}

def _streak_bonus_pct(streak: int) -> int:
    if streak <= 0:
        return 0
    return min(25, streak * 2)  # caps at +25%

# -------------------------------------------------
# UI
# -------------------------------------------------

def show_hop_ui(bot: TeleBot, chat_id: int, message_id: int | None = None):
    """
    ENTRY POINT
    Called from XP Hub:
        show_hop_ui(bot, chat_id, msg_id)
    """
    uid = chat_id  # private chat = user id

    quests = get_quests(uid)
    cooldowns = _safe_get_cd(uid)

    on_cooldown = quests.get(GLOBAL_HOP_KEY) == 1
    streak = int(cooldowns.get(HOP_STREAK_KEY, 0) or 0)
    bonus = _streak_bonus_pct(streak)

    if on_cooldown:
        remaining = _seconds_until_next_day()
        text = (
            "🐾 <b>HOP — ON COOLDOWN</b>\n\n"
            "The rift has closed for today.\n\n"
            f"🔥 Streak: <b>{streak} days</b> (+{bonus}%)\n"
            f"⏳ Next hop in: <b>{_format_hms(remaining)}</b>\n\n"
            "Return tomorrow to continue your ritual."
        )
    else:
        text = (
            "🐾 <b>HOP</b>\n\n"
            "Each day, the rift opens once.\n"
            "Those who return daily grow faster.\n\n"
            f"🔥 Current streak: <b>{streak} days</b> (+{bonus}%)\n\n"
            "👇 <b>Ready?</b>"
        )

    kb = types.InlineKeyboardMarkup(row_width=1)

    if not on_cooldown:
        kb.add(types.InlineKeyboardButton("🐾 Hop Now", callback_data="hop:go"))

    kb.add(types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="__xphub__:home"))

    if message_id:
        bot.edit_message_text(
            text,
            chat_id,
            message_id,
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        bot.send_message(
            chat_id,
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )

# -------------------------------------------------
# Callback handler (unchanged routing)
# -------------------------------------------------

def setup(bot: TeleBot):

    @bot.callback_query_handler(func=lambda c: c.data.startswith("hop:"))
    def hop_cb(call):
        bot.answer_callback_query(call.id)

        uid = call.from_user.id
        chat_id = call.message.chat.id
        msg_id = call.message.message_id

        action = call.data.split(":", 1)[1]

        # -------------------------
        # Execute Hop
        # -------------------------
        if action == "go":
            quests = get_quests(uid)
            if quests.get(GLOBAL_HOP_KEY) == 1:
                show_hop_ui(bot, chat_id, msg_id)
                return

            # --- roll XP ---
            base_xp = random.randint(15, 35)

            cooldowns = _safe_get_cd(uid)
            streak = int(cooldowns.get(HOP_STREAK_KEY, 0) or 0)
            bonus_pct = _streak_bonus_pct(streak)

            gained = int(round(base_xp * (1 + bonus_pct / 100)))

            # --- apply XP ---
            user = db.get_user(uid)
            new_total = int(user.get("xp_total", 0)) + gained

            db.update_user_xp(uid, {
                "xp_total": new_total
            })

            # --- mark hop used ---
            record_quest(uid, GLOBAL_HOP_KEY)

            cooldowns[HOP_STREAK_KEY] = streak + 1
            db.set_cooldowns(uid, cooldowns)

            # --- feedback ---
            text = (
                "✨ <b>HOP COMPLETE</b>\n\n"
                f"📈 XP gained: <b>{gained}</b>\n"
                f"🔥 Streak: <b>{streak + 1} days</b> (+{_streak_bonus_pct(streak + 1)}%)\n"
                "🧬 Evolution multipliers applied\n\n"
                "You feel your Grok growing stronger…"
            )

            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="__xphub__:home"))

            bot.edit_message_text(
                text,
                chat_id,
                msg_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
