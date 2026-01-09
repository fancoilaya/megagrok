# bot/handlers/battle_ui.py
# =========================================================
# Battle UI — Tier selection only
# Mirrors /battle behavior inside the UI
# =========================================================

from telebot import TeleBot, types
from bot.handlers.battle import start_battle_from_ui

BATTLE_UI_PREFIX = "__battle_ui__"


def render_battle_home(uid:int):
    text = (
        "⚔️ <b>TRAINING BATTLES</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Choose a tier.\n"
        "A random enemy from that tier will appear.\n\n"
        "👇 <b>Select a tier:</b>"
    )

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🐀 Tier I", callback_data=f"{BATTLE_UI_PREFIX}:tier:1"),
        types.InlineKeyboardButton("⚔️ Tier II", callback_data=f"{BATTLE_UI_PREFIX}:tier:2"),
    )
    kb.add(
        types.InlineKeyboardButton("🔥 Tier III", callback_data=f"{BATTLE_UI_PREFIX}:tier:3"),
        types.InlineKeyboardButton("👑 Tier IV", callback_data=f"{BATTLE_UI_PREFIX}:tier:4"),
    )
    kb.add(
        types.InlineKeyboardButton("🐉 Tier V", callback_data=f"{BATTLE_UI_PREFIX}:tier:5"),
    )
    kb.add(
        types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="__xphub__:home")
    )

    return text, kb


def setup(bot: TeleBot):

    # -----------------------------------------------------
    # Open Battle UI
    # -----------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == f"{BATTLE_UI_PREFIX}:home")
    def battle_home(call):
        text, kb = render_battle_home()
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="HTML"
        )
        bot.answer_callback_query(call.id)

    # -----------------------------------------------------
    # Tier selected → start battle (random mob)
    # -----------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith(f"{BATTLE_UI_PREFIX}:tier:"))
    def battle_start(call):
        try:
            tier = int(call.data.split(":")[-1])
        except Exception:
            bot.answer_callback_query(call.id, "Invalid tier.", show_alert=True)
            return

        # IMPORTANT:
        # mob_id=None → battle.py will pick a random mob
        start_battle_from_ui(
            bot=bot,
            uid=call.from_user.id,
            chat_id=call.message.chat.id,
            msg_id=call.message.message_id,
            tier=tier,
            mob_id=None
        )

        # Answer callback ONLY here (final handler)
        bot.answer_callback_query(call.id)
