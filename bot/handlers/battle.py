# bot/handlers/battle.py (battle handler v7)
# Uses session_id-based callback_data for secure fight isolation.
# UX: edits the same message during the fight. When the fight ends,
# the battle message is edited to a final summary WITHOUT buttons and
# a separate Victory/Defeat message is sent. This closes the UX.

import time
from telebot import TeleBot, types
from typing import Optional

# PvE Engine (migrated manager supports sid lookups)
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

# -------------------------------------------------------------------
# Helper: callback_data builder
# format: battle:act:<action>:<sid>
# -------------------------------------------------------------------
def _cbdata(action: str, sid: str) -> str:
    return f"battle:act:{action}:{sid}"

# -------------------------------------------------------------------
# Setup bot handlers
# -------------------------------------------------------------------
def setup(bot: TeleBot):

    @bot.message_handler(commands=["battle"])
    def cmd_battle(message):
        kb = types.InlineKeyboardMarkup(row_width=2)
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
    # Tier selection
    # ------------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("battle:choose_tier"))
    def cb_choose_tier(call):
        try:
            _, _, tier_str = call.data.split(":")
            tier = int(tier_str)
        except Exception:
            return bot.answer_callback_query(call.id, "Invalid tier.")

        uid = call.from_user.id
        user = db.get_user(uid)
        if not user:
            return bot.answer_callback_query(call.id, "User not found.")

        mob = mobs.get_random_mob(tier)
        if not mob:
            return bot.answer_callback_query(call.id, "No mobs in this tier.")

        mob_stats = build_mob_stats_from_mob(mob)
        player_stats = build_player_stats_from_user(user)

        # Create session (manager will auto-generate session_id and persist both keys)
        sess = battle_manager.create_session(uid, player_stats, mob_stats)

        # store last message so subsequent edits target the same message
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
        except Exception:
            bot.send_message(call.message.chat.id, caption, reply_markup=kb, parse_mode="Markdown")

        bot.answer_callback_query(call.id)

    # ------------------------------------------------------------
    # Action callbacks (use sid)
    # ------------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("battle:act"))
    def cb_action(call):
        """
        callback_data expected: battle:act:<action>:<sid>
        We validate that call.from_user.id == session.user_id (owner-only PvE).
        """
        parts = call.data.split(":")
        if len(parts) != 4:
            return bot.answer_callback_query(call.id, "Invalid action format.")

        _, _, action, sid = parts

        # load session by sid (preferred)
        sess = battle_manager.load_session_by_sid(sid)
        # fallback: if sid missing, attempt to parse as int and load legacy session
        if not sess:
            try:
                legacy_uid = int(sid)
            except Exception:
                return bot.answer_callback_query(call.id, "Session not found.", show_alert=True)
            sess = battle_manager.load_session(legacy_uid)
            # while legacy sessions are supported, prefer to migrate them on next save

        if not sess:
            return bot.answer_callback_query(call.id, "Session missing or expired.", show_alert=True)

        # Strict owner-only validation (PvE)
        if call.from_user.id != sess.user_id:
            return bot.answer_callback_query(call.id, "❌ This is not your battle.", show_alert=True)

        # target message for edits
        chat_id = sess._last_msg["chat"] if sess._last_msg else call.message.chat.id
        msg_id = sess._last_msg["msg"] if sess._last_msg else None

        # SURRENDER
        if action == ACTION_SURRENDER:
            sess.ended = True
            sess.winner = "mob"
            battle_manager.save_session(sess)

            # finalize and cleanup
            _finalize_and_cleanup(bot, sess, chat_id)
            return bot.answer_callback_query(call.id, "You surrendered.")

        # AUTO toggle
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
                _finalize_and_cleanup(bot, sess, chat_id)
            else:
                caption = _build_caption(sess)
                kb = _build_keyboard(sess)
                _safe_edit(bot, chat_id, msg_id, caption, kb)

            return bot.answer_callback_query(call.id)

        # Validate normal actions
        if action not in {ACTION_ATTACK, ACTION_BLOCK, ACTION_DODGE, ACTION_CHARGE}:
            return bot.answer_callback_query(call.id, "Unknown action.", show_alert=True)

        sess.resolve_player_action(action)
        battle_manager.save_session(sess)

        if sess.ended:
            _finalize_and_cleanup(bot, sess, chat_id)
        else:
            caption = _build_caption(sess)
            kb = _build_keyboard(sess)
            _safe_edit(bot, chat_id, msg_id, caption, kb)

        return bot.answer_callback_query(call.id)

# -------------------------
# UI / helpers
# -------------------------
def _build_caption(sess: BattleSession) -> str:
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

def _build_keyboard(sess: BattleSession) -> types.InlineKeyboardMarkup:
    sid = getattr(sess, "session_id", None) or ""
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=_cbdata(ACTION_ATTACK, sid)),
        types.InlineKeyboardButton("🛡 Block", callback_data=_cbdata(ACTION_BLOCK, sid)),
    )
    kb.add(
        types.InlineKeyboardButton("💨 Dodge", callback_data=_cbdata(ACTION_DODGE, sid)),
        types.InlineKeyboardButton("⚡ Charge", callback_data=_cbdata(ACTION_CHARGE, sid)),
    )
    kb.add(
        types.InlineKeyboardButton(
            "▶ Auto" if not sess.auto_mode else "⏸ Auto",
            callback_data=_cbdata(ACTION_AUTO, sid)
        ),
        types.InlineKeyboardButton("❌ Surrender", callback_data=_cbdata(ACTION_SURRENDER, sid)),
    )
    return kb

def _hp_bar(cur: int, maxhp: int, width: int = 22) -> str:
    ratio = cur / maxhp if maxhp else 0
    full = int(ratio * width)
    return "▓" * full + "░" * (width - full)

def _safe_edit(bot: TeleBot, chat_id: int, msg_id: Optional[int], text: str, kb: Optional[types.InlineKeyboardMarkup]):
    try:
        if msg_id:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        # ignore "message is not modified"
        if "message is not modified" in str(e).lower():
            return
        try:
            bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass

# Finalize: edit battle message to summary (no buttons) and send final message, then cleanup session
def _finalize_and_cleanup(bot: TeleBot, sess: BattleSession, chat_id: int):
    # Edit the original battle message to final caption WITHOUT buttons (close UI)
    final_caption = _build_caption(sess) + "\n\n" + ("🏆 *VICTORY!* You defeated the enemy!" if sess.winner == "player" else "💀 *DEFEAT!* The enemy overpowered you.")
    # Try to edit original; if we lack msg id, just send final caption
    msg_id = sess._last_msg["msg"] if sess._last_msg else None
    try:
        if msg_id:
            bot.edit_message_text(final_caption, chat_id, msg_id, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, final_caption, parse_mode="Markdown")
    except Exception:
        try:
            bot.send_message(chat_id, final_caption, parse_mode="Markdown")
        except Exception:
            pass

    # Send a separate short result message
    if sess.winner == "player":
        bot.send_message(chat_id, "🏆 *VICTORY!* You defeated the enemy!", parse_mode="Markdown")
    else:
        bot.send_message(chat_id, "💀 *DEFEAT!* The enemy overpowered you.", parse_mode="Markdown")

    # Cleanup: remove session entries (by sid if available, else by user id)
    sid = getattr(sess, "session_id", None)
    if sid:
        battle_manager.end_session_by_sid(sid)
    else:
        battle_manager.end_session(sess.user_id)

