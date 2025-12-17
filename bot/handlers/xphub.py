# bot/handlers/xphub.py

from telebot import TeleBot, types
from bot.db import get_user
from bot.evolutions import get_evolution_for_level
from bot.handlers.growmygrok import show_grow_ui
from bot.handlers.hop import show_hop_ui
from bot.handlers.evolution_ui import show_evolution_ui


def setup(bot: TeleBot):

    @bot.message_handler(commands=["xphub"])
    def hub_cmd(message):
        text, kb = render_hub(message.from_user.id)
        bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("xphub:"))
    def hub_cb(call):
        action = call.data.split(":")[1]
        chat_id = call.message.chat.id
        msg_id = call.message.message_id
        uid = call.from_user.id

        if action == "grow":
            show_grow_ui(bot, chat_id, msg_id)
            return

        if action == "hop":
            show_hop_ui(bot, chat_id, msg_id)
            return

        if action == "evolution":
            show_evolution_ui(bot, chat_id, msg_id, uid)
            return

        if action == "home":
            text, kb = render_hub(uid)
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb, parse_mode="HTML")
            return

        if action == "battle":
            bot.send_message(chat_id, "/battle")
            return

        if action == "profile":
            bot.send_message(chat_id, "/profile")
            return


def render_hub(uid: int):
    user = get_user(uid)
    if not user:
        return "❌ No Grok found.", None

    level = user["level"]
    cur = user["xp_current"]
    nxt = user["xp_to_next_level"]
    evo = get_evolution_for_level(level)

    filled = int((cur / nxt) * 12)
    bar = "▓" * filled + "░" * (12 - filled)

    text = (
        "🌌 <b>MEGAGROK XP HUB</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👾 <b>Form:</b> {evo['name']}\n"
        f"⚡ <b>Level:</b> {level}\n\n"
        f"<b>XP</b> <code>{bar}</code>\n"
        f"{cur} / {nxt}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎮 <b>ACTIONS</b>"
    )

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🌱 Grow", callback_data="xphub:grow"),
        types.InlineKeyboardButton("🐾 Hop", callback_data="xphub:hop"),
    )
    kb.add(
        types.InlineKeyboardButton("⚔️ Battle", callback_data="xphub:battle"),
        types.InlineKeyboardButton("🧬 Evolution", callback_data="xphub:evolution"),
    )
    kb.add(
        types.InlineKeyboardButton("👤 Profile", callback_data="xphub:profile"),
    )

    return text, kb
