# bot/handlers/battle.py
# Corrected to work with services.fight_session_battle
# Fully compatible with your existing UI and mob tier system.

import time
from telebot import TeleBot, types

# ✔ Correct imports for new PvE engine
from services.fight_session_battle import (
    manager as battle_manager,
    BattleSession,
    ACTION_ATTACK,
    ACTION_BLOCK,
    ACTION_DODGE,
    ACTION_CHARGE,
    ACTION_AUTO,
    ACTION_SURRENDER,
    build_player_stats_from_user,
    build_mob_stats_from_mob,
)

import bot.db as db
import mobs


def setup(bot: TeleBot):
    # ============================
    # /battle command
    # ============================
    @bot.message_handler(commands=["battle"])
    def cmd_battle(message):
        uid = message.from_user.id

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Tier 1", callback_data="battle:choose_tier:1"))
        kb.add(types.InlineKeyboardButton("Tier 2", callback_data="battle:choose_tier:2"))
        kb.add(types.InlineKeyboardButton("Tier 3", callback_data="battle:choose_tier:3"))
        kb.add(types.InlineKeyboardButton("Tier 4", callback_data="battle:choose_tier:4"))

        bot.reply_to(
            message,
            "⚔️ *Choose your battle tier:*",
            reply_markup=kb,
            parse_mode="Markdown",
        )

    # ============================
    # Tier selection callback
    # ============================
    @bot.callback_query_handler(func=lambda c: c.data.startswith("battle:choose_tier"))
    def cb_choose_tier(call):
        try:
            _, _, tier_str = call.data.split(":")
            tier = int(tier_str)
        except:
            bot.answer_callback_query(call.id, "Invalid tier.")
            return

        user_id = call.from_user.id
        user = db.get_user(user_id)
        if not user:
            bot.answer_callback_query(call.id, "User not found in DB.")
            return

        # choose mob from mobs.py
        mob = mobs.get_random_mob_from_tier(tier)
        mob_stats = build_mob_stats_from_mob(mob)

        # build player stats
        player_stats = build_player_stats_from_user(user)

        # create PvE session
        sess = battle_manager.create_session(user_id, player_stats, mob_stats)
        sess._last_msg = {"chat": call.message.chat.id, "msg": call.message.message_id}
        battle_manager.save_session(sess)

        # send battle UI
        caption = _build_battle_caption(sess)
        kb = _build_action_keyboard(sess)

        try:
            bot.edit_message_text(
                caption,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb,
                parse_mode="Markdown",
            )
        except:
            bot.send_message(
                call.message.chat.id,
                caption,
                reply_markup=kb,
                parse_mode="Markdown",
            )

        bot.answer_callback_query(call.id)

    # ============================
    # Action callbacks
    # ============================
    @bot.callback_query_handler(func=lambda c: c.data.startswith("battle:act"))
    def cb_action(call):
        try:
            _, _, action, uid_str = call.data.split(":")
            uid = int(uid_str)
        except:
            bot.answer_callback_query(call.id, "Invalid action.")
            return

        if call.from_user.id != uid:
            bot.answer_callback_query(call.id, "Not your battle.", show_alert=True)
            return

        sess = battle_manager.load_session(uid)
        if not sess or sess.ended:
            bot.answer_callback_query(call.id, "Battle ended or missing.")
            return

        chat_id = sess._last_msg["chat"]
        msg_id = sess._last_msg["msg"]

        # Surrender
        if action == ACTION_SURRENDER:
            sess.ended = True
            sess.winner = "mob"
            battle_manager.save_session(sess)
            _finalize(bot, sess, chat_id)
            battle_manager.end_session(uid)
            bot.answer_callback_query(call.id, "You surrendered.")
            return

        # Auto toggle
        if action == ACTION_AUTO:
            sess.auto_mode = not sess.auto_mode
            battle_manager.save_session(sess)

            if sess.auto_mode:
                # Run immediate rounds for snappy feel
                for _ in range(4):
                    if sess.ended:
                        break
                    sess.resolve_auto_turn()
                    battle_manager.save_session(sess)

            if sess.ended:
                _finalize(bot, sess, chat_id)
                battle_manager.end_session(uid)
            else:
                caption = _build_battle_caption(sess)
                kb = _build_action_keyboard(sess)
                _safe_edit(bot, chat_id, msg_id, caption, kb)

            bot.answer_callback_query(call.id)
            return

        # Normal actions
        sess.resolve_player_action(action)
        battle_manager.save_session(sess)

        if sess.ended:
            _finalize(bot, sess, chat_id)
            battle_manager.end_session(uid)
        else:
            caption = _build_battle_caption(sess)
            kb = _build_action_keyboard(sess)
            _safe_edit(bot, chat_id, msg_id, caption, kb)

        bot.answer_callback_query(call.id)

# ============================================================================
# UI HELPERS
# ============================================================================

def _build_battle_caption(sess: BattleSession) -> str:
    hp_player = max(0, sess.player_hp)
    hp_mob = max(0, sess.mob_hp)

    bar_player = _hp_bar(hp_player, sess.player.get("hp", 100))
    bar_mob = _hp_bar(hp_mob, sess.mob.get("hp", 100))

    lines = [
        f"⚔️ *Battle vs {sess.mob.get('name','Mob')}*",
        "",
        f"🧍 You:   {bar_player}  {hp_player}/{sess.player.get('hp',100)}",
        f"👹 Enemy: {bar_mob}  {hp_mob}/{sess.mob.get('hp',100)}",
        "",
        f"Turn: {sess.turn}",
        "",
    ]

    if sess.events:
        lines.append("*Last actions:*")
        for ev in sess.events[:5]:
            actor = "You" if ev["actor"] == "player" else sess.mob.get("name", "Mob")
            if ev["action"] == "attack":
                lines.append(f"• {actor} dealt {ev['damage']} dmg {ev.get('note','')}")
            else:
                lines.append(f"• {actor}: {ev['action']} {ev.get('note','')}")

    return "\n".join(lines)


def _build_action_keyboard(sess: BattleSession):
    kb = types.InlineKeyboardMarkup()
    row1 = [
        types.InlineKeyboardButton("🗡 Attack", callback_data=f"battle:act:{ACTION_ATTACK}:{sess.user_id}"),
        types.InlineKeyboardButton("🛡 Block",  callback_data=f"battle:act:{ACTION_BLOCK}:{sess.user_id}"),
    ]
    row2 = [
        types.InlineKeyboardButton("💨 Dodge", callback_data=f"battle:act:{ACTION_DODGE}:{sess.user_id}"),
        types.InlineKeyboardButton("⚡ Charge", callback_data=f"battle:act:{ACTION_CHARGE}:{sess.user_id}"),
    ]
    row3 = [
        types.InlineKeyboardButton("▶ Auto" if not sess.auto_mode else "⏸ Auto",
                                   callback_data=f"battle:act:{ACTION_AUTO}:{sess.user_id}"),
        types.InlineKeyboardButton("❌ Surrender", callback_data=f"battle:act:{ACTION_SURRENDER}:{sess.user_id}")
    ]
    kb.add(*row1)
    kb.add(*row2)
    kb.add(*row3)
    return kb


def _finalize(bot: TeleBot, sess: BattleSession, chat_id: int):
    if sess.winner == "player":
        bot.send_message(chat_id, "🏆 *Victory!* You defeated the enemy.", parse_mode="Markdown")
    else:
        bot.send_message(chat_id, "💀 *Defeat!* The enemy has overpowered you.", parse_mode="Markdown")


def _hp_bar(cur, maxhp, width: int = 20):
    ratio = cur / maxhp if maxhp else 0
    full = int(ratio * width)
    return "▓" * full + "░" * (width - full)


def _safe_edit(bot: TeleBot, chat_id: int, msg_id: int, text: str, kb):
    try:
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        if "message is not modified" in str(e):
            return
        bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")
