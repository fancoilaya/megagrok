from telebot import types
from bot.db import get_user
from bot.evolutions import get_evolution_for_level
from bot.handlers import growmygrok, hop, battle


# ======================================================
# SETUP — REQUIRED BY YOUR HANDLER LOADER
# ======================================================

def setup(bot):
    bot.register_message_handler(
        cmd_xphub,
        commands=["xphub"]
    )

    bot.register_callback_query_handler(
        handle_xphub_callback,
        func=lambda call: call.data.startswith("xphub:")
    )


# ======================================================
# COMMAND HANDLER
# ======================================================

def cmd_xphub(message, bot):
    user_id = message.from_user.id
    chat_id = message.chat.id

    text, markup = render_xp_hub(user_id)
    bot.send_message(
        chat_id,
        text,
        reply_markup=markup,
        parse_mode="HTML"
    )


# ======================================================
# XP HUB RENDERING
# ======================================================

def render_xp_hub(user_id):
    user = get_user(user_id)
    if not user:
        return "❌ User not found.", None

    level = user["level"]
    xp = user["xp"]

    evo = get_evolution_for_level(level)
    next_xp = evo.get("next_xp", xp)

    xp_bar = build_xp_bar(xp, next_xp)

    text = (
        "🌌 <b>MEGAGROK XP HUB</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👾 <b>Form:</b> {evo['name']}\n"
        f"⚡ <b>Level:</b> {level}\n\n"
        f"<b>XP</b> {xp_bar}\n"
        f"{xp} / {next_xp}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎮 <b>ACTIONS</b>\n"
    )

    markup = build_xp_hub_keyboard()
    return text, markup


def build_xp_bar(current, maximum, length=12):
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


# ======================================================
# CALLBACK HANDLER
# ======================================================

def handle_xphub_callback(call, bot):
    action = call.data.split(":", 1)[1]
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    # Route to existing handlers (NO logic duplication)
    if action == "grow":
        growmygrok.handle_grow(call.message, bot)

    elif action == "hop":
        hop.handle_hop(call.message, bot)

    elif action == "battle":
        battle.start_battle(call.message, bot)

    elif action == "profile":
        bot.send_message(chat_id, "/profile")
        return

    # Refresh XP Hub
    text, markup = render_xp_hub(user_id)
    bot.edit_message_text(
        text,
        chat_id,
        message_id,
        reply_markup=markup,
        parse_mode="HTML"
    )
