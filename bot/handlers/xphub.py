from telebot import types, TeleBot

from bot.db import get_user
from bot.evolutions import get_evolution_for_level
from bot.handlers import growmygrok, hop, battle


# ======================================================
# Handler setup (EXACT pattern used in growmygrok.py)
# ======================================================

def setup(bot: TeleBot):

    @bot.message_handler(commands=["xphub"])
    def xphub_handler(message):
        user_id = message.from_user.id
        chat_id = message.chat.id

        text, markup = render_xp_hub(user_id)
        bot.send_message(
            chat_id,
            text,
            reply_markup=markup,
            parse_mode="HTML"
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("xphub:"))
    def xphub_callback_handler(call):
        action = call.data.split(":", 1)[1]
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        if action == "grow":
            growmygrok.handle_grow(call.message)

        elif action == "hop":
            hop.handle_hop(call.message)

        elif action == "battle":
            battle.start_battle(call.message)

        elif action == "profile":
            bot.send_message(chat_id, "/profile")
            bot.answer_callback_query(call.id)
            return

        # Refresh XP Hub after action
        text, markup = render_xp_hub(user_id)
        bot.edit_message_text(
            text,
            chat_id,
            message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

        bot.answer_callback_query(call.id)


# ======================================================
# XP HUB RENDERING (READ-ONLY)
# ======================================================

def render_xp_hub(user_id: int):
    user = get_user(user_id)
    if not user:
        return "❌ User not found.", None

    level = user["level"]
    xp_current = user["xp_current"]
    xp_needed = user["xp_to_next_level"]

    evo = get_evolution_for_level(level)

    xp_bar = build_xp_bar(xp_current, xp_needed)

    text = (
        "🌌 <b>MEGAGROK XP HUB</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👾 <b>Form:</b> {evo['name']}\n"
        f"⚡ <b>Level:</b> {level}\n\n"
        f"<b>XP</b> {xp_bar}\n"
        f"{xp_current} / {xp_needed}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎮 <b>ACTIONS</b>\n"
    )

    markup = build_xp_hub_keyboard()
    return text, markup


def build_xp_bar(current: int, maximum: int, length: int = 12) -> str:
    if maximum <= 0:
        return "▓" * length

    filled = int((current / maximum) * length)
    filled = max(0, min(filled, length))

    return "▓" * filled + "░" * (length - filled)


def build_xp_hub_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)

    kb.add(
        types.InlineKeyboardButton("🌱 Grow", callback_data="xphub:grow"),
        types.InlineKeyboardButton("🐾 Hop", callback_data="xphub:hop"),
    )
    kb.add(
        types.InlineKeyboardButton("⚔️ Battle", callback_data="xphub:battle"),
        types.InlineKeyboardButton("👤 Profile", callback_data="xphub:profile"),
    )

    return kb
