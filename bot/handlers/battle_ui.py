# bot/handlers/battle_ui.py
# -------------------------------------------------
# Battle UX — Step 1 (XP Hub integrated)
# Tier + Mob selection (NO battle execution yet)
# -------------------------------------------------

import time
from telebot import TeleBot, types

import bot.db as db
import bot.mobs as mobs

BATTLE_UI_PREFIX = "__battle_ui__:"
BATTLE_COOLDOWN_SECONDS = 12 * 3600  # 12 hours


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _fmt_time(sec: int) -> str:
    if sec <= 0:
        return "Ready"
    h = sec // 3600
    m = (sec % 3600) // 60
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def _cooldown_block(uid: int) -> str:
    cds = db.get_cooldowns(uid) or {}
    last_ts = int(cds.get("battle", 0) or 0)
    now = int(time.time())

    if not last_ts:
        return "⚔️ Battle cooldown: <b>Ready</b>\n"

    remaining = (last_ts + BATTLE_COOLDOWN_SECONDS) - now
    if remaining <= 0:
        return "⚔️ Battle cooldown: <b>Ready</b>\n"

    return f"⏳ Battle cooldown: <b>{_fmt_time(remaining)}</b>\n"


# -------------------------------------------------
# UI RENDERERS
# -------------------------------------------------

def render_battle_home(uid: int):
    text = (
        "⚔️ <b>TRAINING BATTLES</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Fight mobs to earn XP, evolve, and test your strength.\n\n"
        f"{_cooldown_block(uid)}\n"
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
    mob_list = mobs.get_mobs_by_tier(tier) or []

    text = (
        f"👹 <b>TIER {tier} — AVAILABLE MOBS</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{_cooldown_block(uid)}\n"
        "👇 <b>Select a mob:</b>"
    )

    kb = types.InlineKeyboardMarkup(row_width=1)

    for mob in mob_list:
        name = mob.get("name", "Unknown Mob")
        mob_id = mob.get("id") or name.lower().replace(" ", "_")
        kb.add(
            types.InlineKeyboardButton(
                f"⚔️ {name}",
                callback_data=f"{BATTLE_UI_PREFIX}mob:{tier}:{mob_id}"
            )
        )

    kb.add(
        types.InlineKeyboardButton("⬅️ Back to Tier Select", callback_data=f"{BATTLE_UI_PREFIX}home")
    )
    kb.add(
        types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="__xphub__:home")
    )

    return text, kb


# -------------------------------------------------
# HANDLERS
# -------------------------------------------------

def setup(bot: TeleBot):

    # ----------------------------
    # ENTER BATTLE UX
    # ----------------------------
    @bot.callback_query_handler(func=lambda c: c.data == f"{BATTLE_UI_PREFIX}home")
    def battle_home_cb(call):
        uid = call.from_user.id
        chat_id = call.message.chat.id
        msg_id = call.message.message_id

        text, kb = render_battle_home(uid)

        bot.edit_message_text(
            text,
            chat_id,
            msg_id,
            reply_markup=kb,
            parse_mode="HTML"
        )
        bot.answer_callback_query(call.id)

    # ----------------------------
    # TIER SELECT (FIXED)
    # ----------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith(f"{BATTLE_UI_PREFIX}tier:"))
    def battle_tier_cb(call):
        uid = call.from_user.id
        chat_id = call.message.chat.id
        msg_id = call.message.message_id

        try:
            tier_str = call.data.replace(f"{BATTLE_UI_PREFIX}tier:", "")
            tier = int(tier_str)
        except Exception:
            bot.answer_callback_query(call.id, "Invalid tier.")
            return

        text, kb = render_mob_select(uid, tier)

        bot.edit_message_text(
            text,
            chat_id,
            msg_id,
            reply_markup=kb,
            parse_mode="HTML"
        )
        bot.answer_callback_query(call.id)

    # ----------------------------
    # MOB SELECT (NO BATTLE YET)
    # ----------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith(f"{BATTLE_UI_PREFIX}mob:"))
    def battle_mob_cb(call):
        uid = call.from_user.id
        chat_id = call.message.chat.id
        msg_id = call.message.message_id

        payload = call.data.replace(f"{BATTLE_UI_PREFIX}mob:", "")
        tier, mob_id = payload.split(":", 1)

        text = (
            "⚔️ <b>BATTLE PREVIEW</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"Tier: <b>{tier}</b>\n"
            f"Mob: <b>{mob_id.replace('_', ' ').title()}</b>\n\n"
            "⚠️ Battle execution will be enabled in the next step."
        )

        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("⬅️ Back to Mobs", callback_data=f"{BATTLE_UI_PREFIX}tier:{tier}")
        )
        kb.add(
            types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="__xphub__:home")
        )

        bot.edit_message_text(
            text,
            chat_id,
            msg_id,
            reply_markup=kb,
            parse_mode="HTML"
        )
        bot.answer_callback_query(call.id)
