# bot/handlers/leaderboard_ui.py
#
# Leaderboard UI glue:
# - Fetches data
# - Calls renderers
# - Handles Telegram message editing & buttons

from telebot import TeleBot, types

from bot.db import get_top_users, get_user
from bot.handlers.leaderboard_views import render_grok_evolution_leaderboard

NAV_PREFIX = "__nav__:"


def show_leaderboard_ui(
    bot: TeleBot,
    chat_id: int,
    message_id: int,
    uid: int
):
    # -------------------------------------------------
    # Fetch raw leaderboard data
    # -------------------------------------------------
    raw_users = get_top_users(limit=10)
    me = get_user(uid)

    # -------------------------------------------------
    # Map DB rows → view models
    # -------------------------------------------------
    top_users = []
    for u in raw_users:
        top_users.append({
            "display_name": (
                u.get("display_name")
                or u.get("username")
                or f"User{u['user_id']}"
            ),
            "level": u.get("level", 1),
            "xp_total": u.get("xp_total", 0),
            "evolution": u.get("evolution_name", "Unknown Form"),
        })

    # -------------------------------------------------
    # Current user context
    # -------------------------------------------------
    current_user = None
    if me:
        rank = None
        for idx, u in enumerate(raw_users, start=1):
            if u["user_id"] == uid:
                rank = idx
                break

        xp_to_top10 = None
        if rank and rank > 10:
            xp_to_top10 = max(
                0,
                raw_users[9]["xp_total"] - me.get("xp_total", 0)
            )

        current_user = {
            "rank": rank or "—",
            "level": me.get("level", 1),
            "xp_total": me.get("xp_total", 0),
            "xp_to_top10": xp_to_top10,
        }

    # -------------------------------------------------
    # Render leaderboard
    # -------------------------------------------------
    text = render_grok_evolution_leaderboard(top_users, current_user)

    # -------------------------------------------------
    # Navigation buttons
    # -------------------------------------------------
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(
            "🧠 Training Grounds",
            callback_data=f"{NAV_PREFIX}training"
        ),
        types.InlineKeyboardButton(
            "🔙 Back to Awaken",
            callback_data=f"{NAV_PREFIX}home"
        ),
    )

    # -------------------------------------------------
    # Edit message
    # -------------------------------------------------
    bot.edit_message_text(
        text,
        chat_id,
        message_id,
        reply_markup=kb,
        parse_mode="HTML"
    )
