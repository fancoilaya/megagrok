# bot/handlers/battle.py
import os
import random
import time
import json
from telebot import types
from telebot import TeleBot

from services import fight_session
from bot.mobs import MOBS
from bot.db import (
    get_user,
    update_user_xp,
    record_quest,
    increment_win
)
import bot.db as db
from bot.utils import safe_send_gif
import bot.evolutions as evolutions

# Assets folder
ASSETS_BASE = "assets/gifs"
GIF_INTRO = os.path.join(ASSETS_BASE, "battle_intro.gif")
GIF_VICTORY = os.path.join(ASSETS_BASE, "victory.gif")
GIF_DEFEAT = os.path.join(ASSETS_BASE, "defeat.gif")

# Cooldown
BATTLE_COOLDOWN_SECONDS = 12 * 3600  # 12 hours


# =====================================================
# INTERNAL HELPERS
# =====================================================

def _build_action_keyboard(session: fight_session.FightSession) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=3)
    uid = session.user_id
    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=f"battle:act:attack:{uid}"),
        types.InlineKeyboardButton("🛡 Block",  callback_data=f"battle:act:block:{uid}"),
        types.InlineKeyboardButton("💨 Dodge",  callback_data=f"battle:act:dodge:{uid}"),
        types.InlineKeyboardButton("⚡ Charge", callback_data=f"battle:act:charge:{uid}"),
    )
    kb.add(
        types.InlineKeyboardButton("▶ Auto" if not session.auto_mode else "⏸ Auto",
                                   callback_data=f"battle:act:auto:{uid}"),
        types.InlineKeyboardButton("✖ Surrender",
                                   callback_data=f"battle:act:surrender:{uid}")
    )
    return kb


def _hp_bar_with_numbers(current: int, maximum: int, width: int = 18) -> str:
    pct = max(0.0, min(1.0, float(current) / float(maximum)))
    fill = int(round(pct * width))
    bar = f"{'▓' * fill}{'░' * (width - fill)}"
    return f"{bar} {current} / {maximum}"


def _build_caption(session: fight_session.FightSession) -> str:
    p_name = session.player.get("username", f"User{session.user_id}")
    m_name = session.mob.get("name", "Mob")

    p_max = int(session.player.get("current_hp", session.player.get("hp", 100)))
    m_max = int(session.mob.get("hp", session.mob.get("max_hp", 100)))

    caption = (
        f"⚔️ *Battle — {p_name} vs {m_name}*\n\n"
        f"{p_name}: {_hp_bar_with_numbers(session.player_hp, p_max)}\n"
        f"{m_name}: {_hp_bar_with_numbers(session.mob_hp, m_max)}\n\n"
        f"Turn: {session.turn}\n"
    )

    return caption


def _get_user_cooldowns(user_id: int) -> dict:
    try:
        db._add_column_if_missing("cooldowns", "TEXT")
    except Exception:
        pass

    try:
        db.cursor.execute("SELECT cooldowns FROM users WHERE user_id=?", (user_id,))
        row = db.cursor.fetchone()
        if row and row[0]:
            return json.loads(row[0])
    except Exception:
        pass

    return {}


def _set_user_cooldowns(user_id: int, cooldowns: dict):
    try:
        payload = json.dumps(cooldowns)
        db.cursor.execute("UPDATE users SET cooldowns=? WHERE user_id=?", (payload, user_id))
        db.conn.commit()
    except:
        pass


# =====================================================
# UI REFRESH — delete old message and send new one
# =====================================================

def _refresh_ui(bot: TeleBot, sess: fight_session.FightSession, chat_id: int):
    # Delete previous UI
    try:
        last_meta = sess.to_dict().get("_last_sent_message", {})
        old_msg = last_meta.get("message_id")
        if old_msg:
            try:
                bot.delete_message(chat_id, old_msg)
            except:
                pass
    except:
        pass

    # Send new UI
    kb = _build_action_keyboard(sess)
    caption = _build_caption(sess)
    new_msg = bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=kb)

    # Save new pointer
    meta = sess.to_dict()
    meta["_last_sent_message"] = {"chat_id": chat_id, "message_id": new_msg.message_id}
    fight_session.manager._sessions[str(sess.user_id)] = meta
    fight_session.manager.save_session(sess)

    return new_msg


# =====================================================
# HANDLER REGISTRATION
# =====================================================

def setup(bot: TeleBot):

    @bot.message_handler(commands=["battle"])
    def battle_cmd(message):
        user_id = message.from_user.id

        # Cooldown only (NO quest fight check!)
        cooldowns = _get_user_cooldowns(user_id)
        last = int(cooldowns.get("battle", 0))
        now = int(time.time())

        if last and (now - last < BATTLE_COOLDOWN_SECONDS):
            rem = BATTLE_COOLDOWN_SECONDS - (now - last)
            bot.reply_to(message, f"⏳ Next battle in {rem//3600}h {(rem%3600)//60}m.")
            return

        # Load player + mob
        mob = random.choice(MOBS)
        user = get_user(user_id)

        username = (message.from_user.username and f"@{message.from_user.username}") or f"User{user_id}"

        player_stats = fight_session.build_player_stats_from_user(user, username_fallback=username)
        player_stats["username"] = username  # enforce TG username

        mob_stats = fight_session.build_mob_stats_from_mob(mob)

        # Intro GIF
        try:
            safe_send_gif(bot, message.chat.id, GIF_INTRO)
        except:
            bot.send_message(message.chat.id, "⚔️ The battle begins!")

        # Create session
        sess = fight_session.manager.create_session(user_id, player_stats, mob_stats)

        # Initial UI
        _refresh_ui(bot, sess, message.chat.id)

    # -------------------------
    # CALLBACK HANDLER
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("battle:"))
    def battle_callback(call):
        parts = call.data.split(":")
        _, _, action, owner = parts[:4]
        owner_id = int(owner)

        if call.from_user.id != owner_id:
            bot.answer_callback_query(call.id, "Not your battle!", show_alert=True)
            return

        sess = fight_session.manager.load_session(owner_id)
        if not sess:
            bot.answer_callback_query(call.id, "Battle expired. Start /battle again.", show_alert=True)
            return

        chat_id = call.message.chat.id

        # ----- SURRENDER -----
        if action == "surrender":
            sess.ended = True
            sess.winner = "mob"
            fight_session.manager.save_session(sess)

            _refresh_ui(bot, sess, chat_id)
            _finalize(bot, sess, chat_id)
            fight_session.manager.end_session(owner_id)
            bot.answer_callback_query(call.id, "You surrendered.")
            return

        # ----- AUTO MODE -----
        if action == "auto":
            sess.auto_mode = not sess.auto_mode
            fight_session.manager.save_session(sess)
            bot.answer_callback_query(call.id, "Auto toggled.")

            if sess.auto_mode:
                sess.resolve_auto_turn()
                fight_session.manager.save_session(sess)

            _refresh_ui(bot, sess, chat_id)

            if sess.ended:
                _finalize(bot, sess, chat_id)
                fight_session.manager.end_session(owner_id)
            return

        # ----- NORMAL ACTION -----
        ACTIONS = {
            "attack": fight_session.ACTION_ATTACK,
            "block":  fight_session.ACTION_BLOCK,
            "dodge":  fight_session.ACTION_DODGE,
            "charge": fight_session.ACTION_CHARGE
        }

        if action not in ACTIONS:
            bot.answer_callback_query(call.id, "Unknown action.")
            return

        sess.resolve_player_action(ACTIONS[action])
        fight_session.manager.save_session(sess)

        _refresh_ui(bot, sess, chat_id)
        bot.answer_callback_query(call.id, "Action performed.")

        if sess.ended:
            _finalize(bot, sess, chat_id)
            fight_session.manager.end_session(owner_id)


# =====================================================
# FINAL XP + SUMMARY
# =====================================================

def _finalize(bot: TeleBot, sess: fight_session.FightSession, chat_id: int):

    user_id = sess.user_id
    user = get_user(user_id)
    mob = sess.mob

    # XP calc
    base_xp = random.randint(mob.get("min_xp", 10), mob.get("max_xp", 25))
    lvl = user["level"]
    evo_mult = evolutions.get_xp_multiplier_for_level(lvl) * float(user.get("evolution_multiplier", 1.0))
    effective_xp = int(base_xp * evo_mult)

    xp_total = user["xp_total"] + effective_xp
    cur = user["xp_current"] + effective_xp
    xp_to_next = user["xp_to_next_level"]
    curve = user["level_curve_factor"]

    leveled = False
    while cur >= xp_to_next:
        cur -= xp_to_next
        lvl += 1
        xp_to_next = int(xp_to_next * curve)
        leveled = True

    update_user_xp(user_id, dict(
        xp_total=xp_total,
        xp_current=cur,
        xp_to_next_level=xp_to_next,
        level=lvl
    ))

    if sess.winner == "player":
        increment_win(user_id)

    # IMPORTANT: battle quest key = "battle"
    record_quest(user_id, "battle")

    # Apply cooldown
    cooldowns = _get_user_cooldowns(user_id)
    cooldowns["battle"] = int(time.time())
    _set_user_cooldowns(user_id, cooldowns)

    # Finale GIF
    try:
        if sess.winner == "player" and os.path.exists(GIF_VICTORY):
            safe_send_gif(bot, chat_id, GIF_VICTORY)
        elif sess.winner == "mob" and os.path.exists(GIF_DEFEAT):
            safe_send_gif(bot, chat_id, GIF_DEFEAT)
    except:
        pass

    # Summary text
    txt = []

    if sess.winner == "player":
        txt.append("🎉 *VICTORY!*")
    elif sess.winner == "mob":
        txt.append("☠️ *DEFEAT!*")
    else:
        txt.append("⚔️ *DRAW!*")

    txt.append(f"🎁 XP gained: +{effective_xp}")

    if leveled:
        txt.append("🎉 *LEVEL UP!* Your MegaGrok grows stronger!")

    txt.append("⏳ Next /battle available in 12 hours.")

    bot.send_message(chat_id, "\n".join(txt), parse_mode="Markdown")
