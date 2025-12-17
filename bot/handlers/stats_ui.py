# bot/handlers/stats_ui.py
# Stats UI — Player Progress Page (Read-only, PvE focused)

from telebot import TeleBot, types
from bot.db import get_user
from bot.evolutions import get_evolution_for_level


def show_stats_ui(bot: TeleBot, chat_id: int, message_id: int, uid: int):
    user = get_user(uid)
    if not user:
        bot.edit_message_text(
            "❌ No Grok data found.",
            chat_id,
            message_id
        )
        return

    level = user.get("level", 1)
    xp_total = user.get("xp_total", 0)
    xp_current = user.get("xp_current", 0)
    xp_next = user.get("xp_to_next_level", 100)

    evo = get_evolution_for_level(level)
    evo_name = evo.get("name", "Unknown Grok")

    wins = user.get("wins", 0)
    mobs = user.get("mobs_defeated", 0)
    losses = max(0, mobs - wins)

    text = (
        "📊 <b>YOUR GROK STATS</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🧬 <b>PROGRESSION</b>\n"
        f"Form: <b>{evo_name}</b>\n"
        f"Level: <b>{level}</b>\n"
        f"Total XP: <b>{xp_total}</b>\n"
        f"XP to next level: <b>{max(0, xp_next - xp_current)}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⚔️ <b>PvE COMBAT</b>\n"
        f"Battles: <b>{mobs}</b>\n"
        f"Wins: <b>{wins}</b>\n"
        f"Losses: <b>{losses}</b>\n"
    )

    kb = types.InlineKeyboardMarkup()
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
