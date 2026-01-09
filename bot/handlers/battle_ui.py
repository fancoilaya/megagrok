# bot/handlers/battle_ui.py
# -------------------------------------------------
# Battle UX — Tier & Mob selection with cooldown display
# -------------------------------------------------

import time
from telebot import TeleBot, types

import bot.db as db
import bot.mobs as mobs
from bot.handlers.battle import start_battle_from_ui

BATTLE_UI_PREFIX = "__battle_ui__:"
BATTLE_COOLDOWN_SECONDS = 12 * 3600


# -------------------------------------------------
# Cooldown helper (DISPLAY ONLY)
# -------------------------------------------------

def _battle_cooldown_text(uid: int) -> str:
    cds = db.get_cooldowns(uid) or {}
    last_ts = int(cds.get("battle", 0) or 0)
    now = int(time.time())

    if not last_ts:
        return "⏳ <b>Cooldown:</b> Ready"

    remaining = (last_ts + BATTLE_COOLDOWN_SECONDS) - now
    if remaining <= 0:
        return "⏳ <b>Cooldown:</b> Ready"

    mins = remaining // 60
    hours = mins // 60
    mins = mins % 60
    return f"⏳ <b>Cooldown:</b> {hours}h {mins}m"


# -------------------------------------------------
# UI renderers
# -------------------------------------------------

def render_battle_home(uid: int):
    cooldown_text = _battle_cooldown_text(uid)

    text = (
        "⚔️ <b>TRAINING BATTLES</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{cooldown_text}\n\n"
        "Choose a tier, then an enemy.\n\n"
        "👇 <b>Select a tier:</b>"
    )

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🐀 Tier I", callback_data=f"{BATTLE_UI_PREFIX}tier:1"),
        types.InlineKeyboardButton("⚔️ Tier II", callback_data=f"{BATTLE_UI_PREFIX}tier:2"),
    )
    kb.add(
        types.InlineKeyboardButton("🔥 Tier III", callback_data=f"{BATTLE_UI_PREFIX}tier:3"),
        types.InlineKeyboardButton("👑 Tier IV", callback_data=f"{BATTLE_UI_PREFIX}tier:4"),
    )
    kb.add(
        types.InlineKeyboardButton("🐉 Tier V", callback_data=f"{BATTLE_UI_PREFIX}tier:5"),
    )
    kb.add(
        types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="__xphub__:home")
    )

    return text, kb


def render_mob_select(uid: int, tier: int):
    mobs_list = mobs.list_mobs_by_tier(tier) or []
    cooldown_text = _battle_cooldown_text(uid)

    text = (
        f"👹 <b>TIER {tier}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{cooldown_text}\n\n"
        "Select your enemy:"
    )

    kb = types.InlineKeyboardMarkup(row_width=1)
    for mob in mobs_list:
        kb.add(
            types.InlineKeyboardButton(
                mob["name"],
                callback_data=f"{BATTLE_UI_PREFIX}mob:{tier}:{mob['name']}"
            )
        )

    kb.add(
        types.InlineKeyboardButton("⬅ Back to Tiers", callback_data=f"{BATTLE_UI_PREFIX}home")
    )

    return text, kb


# -------------------------------------------------
# Handlers
# -------------------------------------------------

def setup(bot: TeleBot):

    @bot.callback_query_handler(func=lambda c: c.data == f"{BATTLE_UI_PREFIX}home")
    def battle_home(call):
        uid = call.from_user.id
        text, kb = render_battle_home(uid)
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
        uid = call.from_user.id
        tier = int(call.data.split(":")[-1])
        text, kb = render_mob_select(uid, tier)
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
        uid = call.from_user.id
        _, tier, mob_name = call.data.replace(
            f"{BATTLE_UI_PREFIX}mob:", ""
        ).split(":")

        start_battle_from_ui(
            bot=bot,
            uid=uid,
            chat_id=call.message.chat.id,
            msg_id=call.message.message_id,
            tier=int(tier),
            mob_id=mob_name
        )

        bot.answer_callback_query(call.id)
