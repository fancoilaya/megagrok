# bot/handlers/hop.py
# -------------------------------------------------
# Hop — Daily XP Ritual (FINAL FIXED VERSION)
# -------------------------------------------------

import time
import random
from telebot import TeleBot, types

import bot.db as db

# -------------------------------------------------
# CONFIG
# -------------------------------------------------

HOP_NEXT_TS = "hop_next_ts"
HOP_STREAK_KEY = "hop_streak"
HOP_PREFIX = "__hop__:"

# -------------------------------------------------
# TIME HELPERS
# -------------------------------------------------

def _utc_midnight_ts() -> int:
    now = int(time.time())
    return now - (now % 86400) + 86400

def _seconds_until(ts: int) -> int:
    return max(0, ts - int(time.time()))

def _format_hms(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"

# -------------------------------------------------
# COOLDOWN HELPERS
# -------------------------------------------------

def _load_cd(uid: int) -> dict:
    try:
        cd = db.get_cooldowns(uid)
        return cd if isinstance(cd, dict) else {}
    except Exception:
        return {}

def _save_cd(uid: int, cd: dict):
    try:
        db.set_cooldowns(uid, cd)
    except Exception:
        pass

def _streak_bonus_pct(streak: int) -> int:
    return min(25, max(0, streak * 2))

# -------------------------------------------------
# UI
# -------------------------------------------------

def show_hop_ui(
    bot: TeleBot,
    chat_id: int,
    message_id: int | None,
    uid: int
):
    """
    Renders Hop UI.
    uid MUST be explicitly passed (never infer from chat_id).
    """

    cd = _load_cd(uid)
    next_ts = int(cd.get(HOP_NEXT_TS, 0) or 0)
    streak = int(cd.get(HOP_STREAK_KEY, 0) or 0)

    now = int(time.time())
    on_cooldown = now < next_ts
    bonus = _streak_bonus_pct(streak)

    if on_cooldown:
        remaining = _seconds_until(next_ts)
        text = (
            "🐾 <b>HOP</b>\n\n"
            "Each day, the rift opens once.\n"
            "Those who return daily grow faster.\n\n"
            f"🔥 Current streak: <b>{streak} days</b> (+{bonus}%)\n"
            f"⏳ Next hop in: <b>{_format_hms(remaining)}</b>\n\n"
            "Return tomorrow to continue the ritual."
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
        kb.add(
            types.InlineKeyboardButton(
                "🐾 Hop Now",
                callback_data=f"{HOP_PREFIX}go"
            )
        )

    kb.add(
        types.InlineKeyboardButton(
            "🔙 Back to XP Hub",
            callback_data="__xphub__:home"
        )
    )

    try:
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
    except Exception as e:
        if "message is not modified" in str(e):
            return
        raise

# -------------------------------------------------
# HANDLERS
# -------------------------------------------------

def setup(bot: TeleBot):

    # ----------------------------
    # /hop COMMAND
    # ----------------------------
    @bot.message_handler(commands=["hop"])
    def hop_cmd(message):
        chat_id = message.chat.id
        uid = message.from_user.id

        sent = bot.send_message(chat_id, "🐾 Opening the rift…")
        show_hop_ui(bot, chat_id, sent.message_id, uid)

    # ----------------------------
    # HOP CALLBACKS (NAMESPACED)
    # ----------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith(HOP_PREFIX))
    def hop_cb(call):
        bot.answer_callback_query(call.id)

        uid = call.from_user.id
        chat_id = call.message.chat.id
        msg_id = call.message.message_id

        action = call.data.split(":", 1)[1]

        cd = _load_cd(uid)
        next_ts = int(cd.get(HOP_NEXT_TS, 0) or 0)
        streak = int(cd.get(HOP_STREAK_KEY, 0) or 0)

        now = int(time.time())

        if action == "go":
            if now < next_ts:
                show_hop_ui(bot, chat_id, msg_id, uid)
                return

            # XP roll
            base_xp = random.randint(15, 35)
            bonus_pct = _streak_bonus_pct(streak)
            gained = int(round(base_xp * (1 + bonus_pct / 100)))

            user = db.get_user(uid)
            db.update_user_xp(uid, {
                "xp_total": int(user.get("xp_total", 0)) + gained
            })

            # Update cooldown + streak
            cd[HOP_STREAK_KEY] = streak + 1
            cd[HOP_NEXT_TS] = _utc_midnight_ts()
            _save_cd(uid, cd)

            text = (
                "✨ <b>HOP COMPLETE</b>\n\n"
                f"📈 XP gained: <b>{gained}</b>\n"
                f"🔥 Streak: <b>{streak + 1} days</b> (+{_streak_bonus_pct(streak + 1)}%)\n"
                "🧬 Evolution multipliers applied\n\n"
                "You feel your Grok growing stronger…"
            )

            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(
                types.InlineKeyboardButton(
                    "🔙 Back to XP Hub",
                    callback_data="__xphub__:home"
                )
            )

            try:
                bot.edit_message_text(
                    text,
                    chat_id,
                    msg_id,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            except Exception as e:
                if "message is not modified" in str(e):
                    return
                raise
