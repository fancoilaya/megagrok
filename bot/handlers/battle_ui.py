# bot/handlers/battle_ui.py
# -------------------------------------------------
# Battle UX — Delegates to existing battle system
# -------------------------------------------------

from telebot import TeleBot, types
import bot.mobs as mobs
from bot.handlers.battle import start_battle_from_ui

BATTLE_UI_PREFIX = "__battle_ui__:"


def render_battle_home(uid=None):
    text = (
        "⚔️ <b>TRAINING BATTLES</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Choose a tier, then an enemy.\n\n"
        "👇 <b>Select a tier:</b>"
    )

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🐀 Tier I", callback_data=f"{BATTLE_UI_PREFIX}tier:1"),
        types.InlineKeyboardButton("⚔️ Tier II", callback_data=f"{BATTLE_UI_PREFIX}tier:2"),
        types.InlineKeyboardButton("🔥 Tier III", callback_data=f"{BATTLE_UI_PREFIX}tier:3"),
        types.InlineKeyboardButton("👑 Tier IV", callback_data=f"{BATTLE_UI_PREFIX}tier:4"),
        types.InlineKeyboardButton("🐉 Tier V", callback_data=f"{BATTLE_UI_PREFIX}tier:5"),
    )
    kb.add(
        types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="__xphub__:home")
    )
    return text, kb


def render_mob_select(tier: int):
    mobs_list = mobs.list_mobs_by_tier(tier) or []

    text = f"👹 <b>TIER {tier}</b>\n\nSelect your enemy:"

    kb = types.InlineKeyboardMarkup(row_width=1)
    for mob in mobs_list:
        kb.add(
            types.InlineKeyboardButton(
                mob["name"],
                callback_data=f"{BATTLE_UI_PREFIX}mob:{tier}:{mob['name']}"
            )
        )

    kb.add(
        types.InlineKeyboardButton("⬅ Back", callback_data=f"{BATTLE_UI_PREFIX}home")
    )
    return text, kb


def setup(bot: TeleBot):

    @bot.callback_query_handler(func=lambda c: c.data == f"{BATTLE_UI_PREFIX}home")
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

    @bot.callback_query_handler(func=lambda c: c.data.startswith(f"{BATTLE_UI_PREFIX}tier:"))
    def battle_tier(call):
        tier = int(call.data.split(":")[-1])
        text, kb = render_mob_select(tier)
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="HTML"
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith(f"{BATTLE_UI_PREFIX}mob:"))
    def battle_mob(call):
        _, tier, mob_id = call.data.replace(f"{BATTLE_UI_PREFIX}mob:", "").split(":")
        start_battle_from_ui(
            bot=bot,
            uid=call.from_user.id,
            chat_id=call.message.chat.id,
            msg_id=call.message.message_id,
            tier=int(tier),
            mob_id=mob_id
        )
        bot.answer_callback_query(call.id)
