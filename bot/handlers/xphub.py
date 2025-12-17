# bot/handlers/xphub.py
# XP Hub — Grow integrated cleanly (no fake commands)

from telebot import types, TeleBot
from bot.db import get_user
from bot.evolutions import get_evolution_for_level
from bot.handlers.growmygrok import show_grow_ui


# ======================================================
# Handler setup
# ======================================================

def setup(bot: TeleBot):

    @bot.message_handler(commands=["xphub"])
    def xphub_handler(message):
        text, markup = render_xp_hub(message.from_user.id)
        bot.send_message(
            message.chat.id,
            text,
            reply_markup=markup,
            parse_mode="HTML"
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("xphub:"))
    def xphub_callback_handler(call):
        action = call.data.split(":", 1)[1]
        chat_id = call.message.chat.id

        if action == "grow":
            show_grow_ui(bot, chat_id)
            return

        if action == "hop":
            bot.send_message(chat_id, "/hop")
            return

        if action == "battle":
            bot.send_message(chat_id, "/battle")
            return

        if action == "profile":
            bot.send_message(chat_id, "/profile")
            return


# ======================================================
# XP HUB RENDERING
# ======================================================

def render_xp_hub(user_id: int):
    user = get_user(user_id)
    if not user:
        return "❌ You do not have a Grok yet.", None

    level = int(user.get("level", 1))
    xp_current = int(user.get("xp_current", 0))
    xp_needed = int(user.get("xp_to_next_level", 100))

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
        "Choose your next move:"
    )

    return text, build_xp_hub_keyboard()


def build_xp_bar(current: int, maximum: int, length: int = 12):
    if maximum <= 0:
        return "▓" * length
    filled = int((current / maximum) * length)
    return "▓" * min(length, filled) + "░" * (length - min(length, filled))


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
