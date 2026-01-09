# bot/handlers/battle_ui.py
# =========================================================
# WORKING Battle UX (no fragile Telegram features)
# =========================================================

import time
from telebot import TeleBot, types

import bot.db as db
import bot.mobs as mobs
from bot.handlers.battle import start_battle_from_ui

BATTLE_UI_PREFIX = "__battle_ui__:"
BATTLE_COOLDOWN_SECONDS = 12 * 3600


# ---------------------------------------------------------
# Cooldown display
# ---------------------------------------------------------

def battle_cooldown_text(uid: int) -> str:
    cds = db.get_cooldowns(uid) or {}
    last_ts = int(cds.get("battle", 0) or 0)
    now = int(time.time())

    if not last_ts:
        return "⏳ Cooldown: Ready"

    remaining = (last_ts + BATTLE_COOLDOWN_SECONDS) - now
    if remaining <= 0:
        return "⏳ Cooldown: Ready"

    h = remaining // 3600
    m = (remaining % 3600) // 60
    return f"⏳ Cooldown: {h}h {m}m"


# ---------------------------------------------------------
# UI Renders
# ---------------------------------------------------------

def render_battle_home(uid: int):
    text = (
        "⚔️ <b>TRAINING BATTLES</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{battle_cooldown_text(uid)}\n\n"
        "Select a tier:\n"
    )

    kb = types.InlineKeyboardMarkup(row_width=2)
    for i in range(1, 6):
        kb.add(
            types.InlineKeyboardButton(
                f"Tier {i}",
                callback_data=f"{BATTLE_UI_PREFIX}tier:{i}"
            )
        )

    kb.add(
        types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="__xphub__:home")
    )

    return text, kb


def render_mob_select(uid: int, tier: int):
    mobs_list = mobs.list_mobs_by_tier(tier) or []

    text = (
        f"👹 <b>Tier {tier}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{battle_cooldown_text(uid)}\n\n"
        "Select a mob:\n"
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
        types.InlineKeyboardButton("⬅ Back", callback_data=f"{BATTLE_UI_PREFIX}home")
    )

    return text, kb


# ---------------------------------------------------------
# Handlers
# ---------------------------------------------------------

def setup(bot: TeleBot):

    @bot.callback_query_handler(func=lambda c: c.data == f"{BATTLE_UI_PREFIX}home")
    def battle_home(call):
        text, kb = render_battle_home(call.from_user.id)
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
        text, kb = render_mob_select(call.from_user.id, tier)
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
        _, tier, mob_name = call.data.replace(
            f"{BATTLE_UI_PREFIX}mob:", ""
        ).split(":")

        start_battle_from_ui(
            bot=bot,
            uid=call.from_user.id,
            chat_id=call.message.chat.id,
            msg_id=call.message.message_id,
            tier=int(tier),
            mob_id=mob_name
        )

        bot.answer_callback_query(call.id)
