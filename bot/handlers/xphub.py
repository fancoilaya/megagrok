# bot/handlers/xphub.py

from telebot import TeleBot, types
from bot.db import get_user
from bot.evolutions import get_evolution_for_level

from bot.handlers.growmygrok import show_grow_ui
from bot.handlers.hop import show_hop_ui
from bot.handlers.evolution_ui import show_evolution_ui
from bot.handlers.stats_ui import show_stats_ui
from bot.handlers.leaderboard_ui import show_leaderboard_ui


XP_PREFIX = "__xphub__:"  # unique namespace to avoid callback interception


def setup(bot: TeleBot):

    # ----------------------------
    # /xphub command
    # ----------------------------
    @bot.message_handler(commands=["xphub"])
    def hub_cmd(message):
        text, kb = render_hub(message.from_user.id)
        bot.send_message(
            message.chat.id,
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )

    # ----------------------------
    # XP Hub callbacks
    # ----------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith(XP_PREFIX))
    def hub_cb(call):
        # REQUIRED by Telegram (prevents loading spinner)
        bot.answer_callback_query(call.id)

        action = call.data.split(":", 1)[1]
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

        if action == "stats":
            show_stats_ui(bot, chat_id, msg_id, uid)
            return

        if action == "leaderboard":
            show_leaderboard_ui(bot, chat_id, msg_id, uid)
            return

        if action == "home":
            text, kb = render_hub(uid)
            bot.edit_message_text(
                text,
                chat_id,
                msg_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
            return

        if action == "battle":
            bot.send_message(chat_id, "/battle")
            return

        if action == "profile":
            bot.send_message(chat_id, "/profile")
            return


# ----------------------------
# XP Hub renderer
# ----------------------------
def render_hub(uid: int):
    user = get_user(uid)
    if not user:
        return "❌ No Grok found.", None

    level = user.get("level", 1)
    cur = user.get("xp_current", 0)
    nxt = user.get("xp_to_next_level", 100)

    evo = get_evolution_for_level(level)
    form_label = evo.get("name", "Unknown Grok")

    # XP progress bar (safe)
    filled = int((cur / nxt) * 12) if nxt > 0 else 0
    filled = max(0, min(12, filled))
    bar = "▓" * filled + "░" * (12 - filled)

    text = (
        "🌌 <b>MEGAGROK XP HUB</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👾 <b>Form:</b> {form_label}\n"
        f"⚡ <b>Level:</b> {level}\n\n"
        f"<b>XP</b> <code>{bar}</code>\n"
        f"{cur} / {nxt}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎮 <b>ACTIONS</b>"
    )

    kb = types.InlineKeyboardMarkup(row_width=2)

    kb.add(
        types.InlineKeyboardButton("🌱 Grow", callback_data=f"{XP_PREFIX}grow"),
        types.InlineKeyboardButton("🐾 Hop", callback_data=f"{XP_PREFIX}hop"),
    )

    kb.add(
        types.InlineKeyboardButton("⚔️ Battle", callback_data=f"{XP_PREFIX}battle"),
        types.InlineKeyboardButton("🧬 Evolution", callback_data=f"{XP_PREFIX}evolution"),
    )

    kb.add(
        types.InlineKeyboardButton("📊 Stats", callback_data=f"{XP_PREFIX}stats"),
        types.InlineKeyboardButton("🏆 Leaderboard", callback_data=f"{XP_PREFIX}leaderboard"),
    )

    kb.add(
        types.InlineKeyboardButton("👤 Profile", callback_data=f"{XP_PREFIX}profile"),
    )

    return text, kb
