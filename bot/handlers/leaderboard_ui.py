# bot/handlers/leaderboard_ui.py
# PvE Leaderboard UI — XP + Battle Performance

from telebot import TeleBot, types
from bot.db import get_top_users


def show_leaderboard_ui(bot: TeleBot, chat_id: int, message_id: int, uid: int):
    users = get_top_users(10)

    lines = []
    rank = 1

    for u in users:
        name = u.get("display_name") or u.get("username") or f"User{u['user_id']}"
        level = u.get("level", 1)
        xp = u.get("xp_total", 0)
        wins = u.get("wins", 0)
        rituals = u.get("rituals", 0)  # proxy for activity

        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"

        lines.append(
            f"{medal} <b>{name}</b> — Lv {level} | XP {xp} | W {wins}"
        )
        rank += 1

    text = (
        "🏆 <b>PvE LEADERBOARD</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        + "\n".join(lines)
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
