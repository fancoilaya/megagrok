# bot/handlers/battle.py
# MegaGrok — PvE Battle Handler (Final Corrected Version)
# Fully compatible with fight_session_battle.py and mobs.py (Tier 1–5)

import time
from telebot import TeleBot, types

# PvE Engine
from services.fight_session_battle import (
    manager as battle_manager,
    BattleSession,
    build_player_stats_from_user,
    build_mob_stats_from_mob,
    ACTION_ATTACK,
    ACTION_BLOCK,
    ACTION_DODGE,
    ACTION_CHARGE,
    ACTION_AUTO,
    ACTION_SURRENDER,
)

import bot.db as db
import bot.mobs as mobs


# ============================================================
# MAIN SETUP
# ============================================================
def setup(bot: TeleBot):

    # ------------------------------------------------------------
    # /battle — show Tier selection
    # ------------------------------------------------------------
    @bot.message_handler(commands=["battle"])
    def cmd_battle(message):

        kb = types.InlineKeyboardMarkup(row_width=2)

        # Match your screenshot UI layout:
        kb.add(
            types.InlineKeyboardButton("🐀 Tier 1 — Common", callback_data="battle:choose_tier:1"),
            types.InlineKeyboardButton("⚔️ Tier 2 — Uncommon", callback_data="battle:choose_tier:2"),
        )
        kb.add(
            types.InlineKeyboardButton("🔥 Tier 3 — Rare", callback_data="battle:choose_tier:3"),
            types.InlineKeyboardButton("👑 Tier 4 — Epic", callback_data="battle:choose_tier:4"),
        )
        kb.add(
            types.InlineKeyboardButton("🐉 Tier 5 — Legendary", callback_data="battle:choose_tier:5")
        )

        bot.reply_to(
            message,
            "⚔️ *Choose your opponent tier:*",
            reply_markup=kb,
            parse_mode="Markdown",
        )

    # ------------------------------------------------------------
    # TIER SELECT CALLBACK
    # ------------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("battle:choose_tier"))
    def cb_choose_tier(call):

        try:
            _, _, tier_str = call.data.split(":")
            tier = int(tier_str)
        except:
            return bot.answer_callback_query(call.id, "Invalid tier.")

        uid = call.from_user.id
        user = db.get_user(uid)
        if not user:
            return bot.answer_callback_query(call.id, "User not found.")

        # ✔ Use your real mobs.py function
        mob = mobs.get_random_mob(tier)
        if not mob:
            return bot.answer_callback_query(call.id, "No mobs in this tier.")

        mob_stats = build_mob_stats_from_mob(mob)
        player_stats = build_player_stats_from_user(user)

        # Create session
        sess = battle_manager.create_session(uid, player_stats, mob_stats)
        sess._last_msg = {"chat": call.message.chat.id, "msg": call.message.message_id}
        battle_manager.save_session(sess)

        caption = _build_caption(sess)
        kb = _build_keyboard(sess)

        try:
            bot.edit_message_text(
                caption,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb,
                parse_mode="Markdown",
            )
        except:
            bot.send_message(call.message.chat.id, caption, reply_markup=kb, parse_mode="Markdown")

        bot.answer_callback_query(call.id)

    # ------------------------------------------------------------
    # ACTION CALLBACKS
    # ------------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("battle:act"))
    def cb_action(call):

        try:
            _, _, action, uid_str = call.data.split(":")
            uid = int(uid_str)
        except:
            return bot.answer_callback_query(call.id, "Invalid action.")

        if call.from_user.id != uid:
            return bot.answer_callback_query(call.id, "Not your battle!", show_alert=True)

        sess = battle_manager.load_session(uid)
        if not sess:
            return bot.answer_callback_query(call.id, "Session missing.")

        chat_id = sess._last_msg["chat"]
        msg_id = sess._last_msg["msg"]

        # SURRENDER
        if action == ACTION_SURRENDER:
            sess.ended = True
            sess.winner = "mob"
            battle_manager.save_session(sess)

            _finalize(bot, sess, chat_id)
            battle_manager.end_session(uid)
            return bot.answer_callback_query(call.id, "You surrendered.")

        # AUTO MODE
        if action == ACTION_AUTO:
            sess.auto_mode = not sess.auto_mode
            battle_manager.save_session(sess)

            if sess.auto_mode:
                for _ in range(4):
                    if sess.ended:
                        break
                    sess.resolve_auto_turn()
                    battle_manager.save_session(sess)

            if sess.ended:
                _finalize(bot, sess, chat_id)
                battle_manager.end_session(uid)
            else:
                caption = _build_caption(sess)
                kb = _build_keyboard(sess)
                _safe_edit(bot, chat_id, msg_id, caption, kb)

            return bot.answer_callback_query(call.id)

        # NORMAL ACTION
        sess.resolve_player_action(action)
        battle_manager.save_session(sess)

        if sess.ended:
            _finalize(bot, sess, chat_id)
            battle_manager.end_session(uid)
        else:
            caption = _build_caption(sess)
            kb = _build_keyboard(sess)
            _safe_edit(bot, chat_id, msg_id, caption, kb)

        bot.answer_callback_query(call.id)


# ============================================================
# UI BUILDER FUNCTIONS
# ============================================================

def _build_caption(sess: BattleSession):
    hp_p = max(0, sess.player_hp)
    hp_m = max(0, sess.mob_hp)

    max_p = sess.player.get("hp", 100)
    max_m = sess.mob.get("hp", 100)

    bar_p = _hp_bar(hp_p, max_p)
    bar_m = _hp_bar(hp_m, max_m)

    lines = [
        f"⚔️ *Battle vs {sess.mob.get('name','Mob')}*",
        "",
        f"🧍 You:   {bar_p} {hp_p}/{max_p}",
        f"👹 Enemy: {bar_m} {hp_m}/{max_m}",
        "",
        f"Turn: {sess.turn}",
        "",
    ]

    if sess.events:
        lines.append("*Recent actions:*")
        for ev in sess.events[:5]:
            actor = "You" if ev["actor"] == "player" else sess.mob.get("name", "Mob")
            if ev["action"] == "attack":
                lines.append(f"• {actor} dealt {ev['damage']} dmg {ev.get('note','')}")
            else:
                lines.append(f"• {actor}: {ev['action']} {ev.get('note','')}")

    return "\n".join(lines)


def _build_keyboard(sess: BattleSession):
    uid = sess.user_id
    kb = types.InlineKeyboardMarkup()

    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=f"battle:act:{ACTION_ATTACK}:{uid}"),
        types.InlineKeyboardButton("🛡 Block", callback_data=f"battle:act:{ACTION_BLOCK}:{uid}"),
    )
    kb.add(
        types.InlineKeyboardButton("💨 Dodge", callback_data=f"battle:act:{ACTION_DODGE}:{uid}"),
        types.InlineKeyboardButton("⚡ Charge", callback_data=f"battle:act:{ACTION_CHARGE}:{uid}"),
    )
    kb.add(
        types.InlineKeyboardButton(
            "▶ Auto" if not sess.auto_mode else "⏸ Auto",
            callback_data=f"battle:act:{ACTION_AUTO}:{uid}"
        ),
        types.InlineKeyboardButton("❌ Surrender", callback_data=f"battle:act:{ACTION_SURRENDER}:{uid}"),
    )

    return kb


def _hp_bar(cur, maxhp, width=22):
    ratio = cur / maxhp if maxhp else 0
    full = int(ratio * width)
    return "▓" * full + "░" * (width - full)


def _safe_edit(bot, chat_id, msg_id, text, kb):
    try:
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        if "message is not modified" in str(e).lower():
            return
        bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")


# ============================================================
# FINAL SUMMARY
# ============================================================

def _finalize(bot, sess: BattleSession, chat_id: int):

    if sess.winner == "player":
        bot.send_message(
            chat_id,
            "🏆 *VICTORY!*\nYou defeated the enemy!",
            parse_mode="Markdown",
        )
    else:
        bot.send_message(
            chat_id,
            "💀 *DEFEAT!*\nThe enemy has overpowered you.",
            parse_mode="Markdown",
        )
