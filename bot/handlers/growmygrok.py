# bot/handlers/growmygrok.py
# -------------------------------------------
# Grow My Grok — Risk-based XP progression
# Clean UI + cooldown + safe navigation
# -------------------------------------------

import time
import random
from telebot import TeleBot, types

import bot.db as db

# -------------------------------------------
# CONFIG
# -------------------------------------------

GLOBAL_GROW_COOLDOWN = 45 * 60  # 45 minutes

# -------------------------------------------
# HELPERS
# -------------------------------------------

def _now() -> int:
    return int(time.time())


def _load_cd(uid: int) -> dict:
    return db.get_cooldowns(uid)


def _save_cd(uid: int, cd: dict):
    db.set_cooldowns(uid, cd)


def _cooldown_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton(
            "🔄 Refresh",
            callback_data="grow:refresh"
        ),
        types.InlineKeyboardButton(
            "🔙 Back to XP Hub",
            callback_data="__xphub__:home"
        )
    )
    return kb


# -------------------------------------------
# GROW MODES
# -------------------------------------------

MODE_DESCRIPTIONS = {
    "train": (
        "🛠️ <b>Train — Low Risk</b>\n"
        "• Small, guaranteed XP\n"
        "• Safe progression\n"
        "• No penalties"
    ),
    "forage": (
        "🍃 <b>Forage — Medium Risk</b>\n"
        "• Higher XP potential\n"
        "• Chance of failure"
    ),
    "gamble": (
        "🎲 <b>Gamble — High Risk</b>\n"
        "• Massive XP if successful\n"
        "• Chance to lose XP"
    ),
}

BUTTON_LABELS = {
    "train": "🛠️ Train — Low Risk",
    "forage": "🍃 Forage — Medium Risk",
    "gamble": "🎲 Gamble — High Risk",
}


# -------------------------------------------
# MAIN UI
# -------------------------------------------

def show_grow_ui(bot: TeleBot, chat_id: int, message_id: int, uid: int):
    cd = _load_cd(uid)
    last = cd.get("grow_last_action", 0)
    now = _now()

    # ---------------------------
    # COOLDOWN GATE
    # ---------------------------
    if last and now - last < GLOBAL_GROW_COOLDOWN:
        left = GLOBAL_GROW_COOLDOWN - (now - last)
        m, s = divmod(left, 60)

        bot.edit_message_text(
            f"⏳ <b>Grow is on cooldown</b>\n\n"
            f"⏱️ {m}m {s}s remaining",
            chat_id,
            message_id,
            reply_markup=_cooldown_keyboard(),
            parse_mode="HTML"
        )
        return

    # ---------------------------
    # NORMAL GROW UI
    # ---------------------------
    text = (
        "🌱 <b>Choose how to grow your Grok</b>\n\n"
        f"{MODE_DESCRIPTIONS['train']}\n\n"
        f"{MODE_DESCRIPTIONS['forage']}\n\n"
        f"{MODE_DESCRIPTIONS['gamble']}\n\n"
        "👇 <b>Select an option:</b>"
    )

    kb = types.InlineKeyboardMarkup(row_width=1)

    for mode in ("train", "forage", "gamble"):
        kb.add(
            types.InlineKeyboardButton(
                BUTTON_LABELS[mode],
                callback_data=f"grow:{mode}"
            )
        )

    # Back button (ALWAYS present)
    kb.add(
        types.InlineKeyboardButton(
            "🔙 Back to XP Hub",
            callback_data="__xphub__:home"
        )
    )

    bot.edit_message_text(
        text,
        chat_id,
        message_id,
        reply_markup=kb,
        parse_mode="HTML"
    )


# -------------------------------------------
# CALLBACK HANDLER
# -------------------------------------------

def setup(bot: TeleBot):

    @bot.callback_query_handler(func=lambda c: c.data.startswith("grow:"))
    def cb_grow(call):
        uid = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        action = call.data.split(":", 1)[1]

        bot.answer_callback_query(call.id)

        # ---------------------------
        # REFRESH
        # ---------------------------
        if action == "refresh":
            show_grow_ui(bot, chat_id, message_id, uid)
            return

        # ---------------------------
        # COOLDOWN CHECK
        # ---------------------------
        cd = _load_cd(uid)
        last = cd.get("grow_last_action", 0)
        now = _now()

        if last and now - last < GLOBAL_GROW_COOLDOWN:
            show_grow_ui(bot, chat_id, message_id, uid)
            return

        # ---------------------------
        # XP CALCULATION
        # ---------------------------
        user = db.get_user(uid)
        xp = 0
        note = ""

        if action == "train":
            xp = random.randint(5, 9)
            note = "Steady training pays off."

        elif action == "forage":
            if random.random() < 0.65:
                xp = random.randint(10, 18)
                note = "You found rich resources!"
            else:
                xp = 0
                note = "Nothing useful was found."

        elif action == "gamble":
            roll = random.random()
            if roll < 0.35:
                xp = random.randint(20, 35)
                note = "Big win! Fortune favors the bold."
            else:
                xp = -random.randint(5, 12)
                note = "Disaster! You lost some XP."

        # ---------------------------
        # APPLY XP
        # ---------------------------
        new_xp = max(0, int(user.get("xp_current", 0)) + xp)
        total_xp = int(user.get("xp_total", 0)) + max(0, xp)

        db.update_user_xp(uid, {
            "xp_current": new_xp,
            "xp_total": total_xp
        })

        # ---------------------------
        # SET COOLDOWN
        # ---------------------------
        cd["grow_last_action"] = now
        _save_cd(uid, cd)

        # ---------------------------
        # RESULT UI
        # ---------------------------
        sign = "+" if xp >= 0 else ""
        text = (
            "🌱 <b>Growth Result</b>\n\n"
            f"✨ XP Change: <b>{sign}{xp}</b>\n"
            f"🧠 {note}\n\n"
            "⏳ Grow is now on cooldown."
        )

        kb = _cooldown_keyboard()

        bot.edit_message_text(
            text,
            chat_id,
            message_id,
            reply_markup=kb,
            parse_mode="HTML"
        )
