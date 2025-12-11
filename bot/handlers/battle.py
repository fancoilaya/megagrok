# bot/handlers/battle.py
# MegaGrok PvE Battle Handler — XP + Level System Edition
# Includes:
#  - Proper mob naming
#  - XP rewards & level-up detection
#  - Post-battle result card
#  - GrowMyGrok-style progress bar
#  - Anti-429 safety for UI edits

import time
from telebot import TeleBot, types

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

BATTLE_COOLDOWN_SECONDS = 12 * 3600  # 12 hours between battles


# ============================================================
# Helpers
# ============================================================

def _hp_bar(cur, maxhp, width=22):
    ratio = cur / maxhp if maxhp else 0
    full = int(ratio * width)
    return "▓" * full + "░" * (width - full)


def _progress_bar(current, total, width=22):
    pct = current / total if total else 0
    full = int(pct * width)
    bar = "▓" * full + "░" * (width - full)
    pct_display = int(pct * 100)
    return bar, pct_display


def _safe_edit(bot, chat_id, msg_id, text, kb):
    """Prevents 429 spam and unnecessary edits."""
    try:
        bot.edit_message_text(
            text,
            chat_id,
            msg_id,
            reply_markup=kb,
            parse_mode="Markdown"
        )
    except Exception as e:
        s = str(e).lower()
        if "message is not modified" in s:
            return
        if "too many requests" in s:
            return
        try:
            bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")
        except:
            return


# ============================================================
# Caption builder
# ============================================================

def _build_caption(sess: BattleSession):
    mob_name = sess.mob.get("name", "Mob")

    hp_p = max(0, sess.player_hp)
    hp_m = max(0, sess.mob_hp)

    max_p = sess.player.get("hp", 100)
    max_m = sess.mob.get("hp", 100)

    bar_p = _hp_bar(hp_p, max_p)
    bar_m = _hp_bar(hp_m, max_m)

    lines = [
        f"⚔️ *Battle vs {mob_name}*",
        "",
        f"🧍 You:   {bar_p} {hp_p}/{max_p}",
        f"👹 {mob_name}: {bar_m} {hp_m}/{max_m}",
        "",
        f"Turn: {sess.turn}",
        "",
    ]

    if sess.events:
        lines.append("*Recent actions:*")
        for ev in sess.events[:5]:
            actor = "You" if ev["actor"] == "player" else mob_name
            if ev["action"] == "attack":
                lines.append(f"• {actor} dealt {ev['damage']} dmg {ev.get('note','')}")
            else:
                lines.append(f"• {actor}: {ev['action']} {ev.get('note','')}")
    return "\n".join(lines)


# ============================================================
# Keyboard builder
# ============================================================

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
        types.InlineKeyboardButton(
            "❌ Surrender",
            callback_data=f"battle:act:{ACTION_SURRENDER}:{uid}"
        ),
    )
    return kb


# ============================================================
# XP + Level System Finalization
# ============================================================

def _finalize(bot, sess: BattleSession, chat_id: int):
    uid = sess.user_id

    # Load fresh user
    user = db.get_user(uid)
    xp_total = user.get("xp_total", 0)
    lvl = user.get("level", 1)

    mob_name = sess.mob.get("name", "Enemy")
    mob_tier = sess.mob.get("tier", 1)

    # XP reward rules — you can tune these
    base_xp = 15 + (mob_tier * 10)
    victory = sess.winner == "player"
    xp_gain = base_xp if victory else max(1, base_xp // 3)

    new_xp = xp_total + xp_gain
    db.update_xp(uid, xp_gain)

    # Level requirements
    xp_needed = db.xp_needed_for_level(lvl)

    leveled_up = False
    if new_xp >= xp_needed:
        lvl += 1
        leveled_up = True
        db.update_level(uid, lvl)

    # XP for next level (re-check for next level requirement)
    xp_next = db.xp_needed_for_level(lvl)

    bar, pct = _progress_bar(new_xp, xp_next)

    # Cooldown
    next_cooldown = db.time_until_next_battle(uid)

    cd_text = (
        f"Next /battle in {next_cooldown}"
        if next_cooldown
        else "You can battle again!"
    )

    # Build final message
    title = "🏆 *VICTORY!*" if victory else "💀 *DEFEAT!*"

    text = (
        f"{title}\n"
        f"You defeated *{mob_name}*\n\n"
        f"🎁 *XP gained:* +{xp_gain}\n"
        f"🎚 *Level:* {lvl}\n"
        f"{bar} {pct}% ({new_xp}/{xp_next})\n\n"
        f"⏳ {cd_text}"
    )

    if leveled_up:
        text = (
            f"🎉 *LEVEL UP!*\n"
            f"You advanced to *Level {lvl}*! 🔥\n\n"
            f"{text}"
        )

    bot.send_message(chat_id, text, parse_mode="Markdown")


# ============================================================
# Setup command handlers
# ============================================================

def setup(bot: TeleBot):

    # ------------------------
    # /battle
    # ------------------------
    @bot.message_handler(commands=["battle"])
    def cmd_battle(message):

        uid = message.from_user.id

        if not db.can_start_battle(uid):
            remaining = db.time_until_next_battle(uid)
            return bot.reply_to(
                message,
                f"⏳ You must wait *{remaining}* before battling again.",
                parse_mode="Markdown"
            )

        # Choose tier UI
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

    # ------------------------
    # Pick tier callback
    # ------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("battle:choose_tier"))
    def cb_choose_tier(call):

        try:
            _, _, tier_str = call.data.split(":")
            tier = int(tier_str)
        except:
            return bot.answer_callback_query(call.id, "Invalid tier.")

        uid = call.from_user.id
        user = db.get_user(uid)

        # Pick mob properly
        mob = mobs.get_random_mob(tier)
        mob_stats = build_mob_stats_from_mob(mob)
        mob_stats["name"] = mob["name"]
        mob_stats["tier"] = mob["tier"]

        player_stats = build_player_stats_from_user(user)

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

    # ------------------------
    # Player actions
    # ------------------------
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
            return bot.answer_callback_query(call.id, "Session ended.")

        chat_id = sess._last_msg["chat"]
        msg_id = sess._last_msg["msg"]

        # ================
        # SURRENDER
        # ================
        if action == ACTION_SURRENDER:
            sess.ended = True
            sess.winner = "mob"
            battle_manager.save_session(sess)
            _finalize(bot, sess, chat_id)
            battle_manager.end_session(uid)
            return bot.answer_callback_query(call.id)

        # ================
        # AUTO (safe)
        # ================
        if action == ACTION_AUTO:
            sess.auto_mode = not sess.auto_mode
            battle_manager.save_session(sess)

            if sess.auto_mode:
                for _ in range(3):
                    if sess.ended:
                        break
                    sess.resolve_auto_turn()
                    battle_manager.save_session(sess)

            if sess.ended:
                _finalize(bot, sess, chat_id)
                battle_manager.end_session(uid)
            else:
                _safe_edit(bot, chat_id, msg_id, _build_caption(sess), _build_keyboard(sess))

            return bot.answer_callback_query(call.id)

        # ================
        # NORMAL ACTIONS
        # ================
        sess.resolve_player_action(action)
        battle_manager.save_session(sess)

        if sess.ended:
            _finalize(bot, sess, chat_id)
            battle_manager.end_session(uid)
        else:
            _safe_edit(bot, chat_id, msg_id, _build_caption(sess), _build_keyboard(sess))

        bot.answer_callback_query(call.id)
