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
    get_quests,
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
        types.InlineKeyboardButton("▶ Auto" if not session.auto_mode else "⏸ Auto", callback_data=f"battle:act:auto:{uid}"),
        types.InlineKeyboardButton("✖ Surrender", callback_data=f"battle:act:surrender:{uid}")
    )
    return kb


def _hp_bar(current: int, maximum: int, width: int = 18) -> str:
    pct = max(0.0, min(1.0, float(current) / float(maximum)))
    fill = int(round(pct * width))
    return f"{'▓' * fill}{'░' * (width - fill)} {int(pct * 100)}%"


def _build_caption(session: fight_session.FightSession) -> str:
    p_name = session.player.get("username", "You")
    m_name = session.mob.get("name", "Mob")

    p_max = int(session.player.get("current_hp", session.player.get("hp", 100)))
    m_max = int(session.mob.get("hp", session.mob.get("max_hp", 100)))

    caption = (
        f"⚔️ *Battle — {p_name} vs {m_name}*\n\n"
        f"{p_name}: {_hp_bar(session.player_hp, p_max)}\n"
        f"{m_name}: {_hp_bar(session.mob_hp, m_max)}\n\n"
        f"Turn: {session.turn}\n"
    )

    if session.events:
        caption += "\n*Recent moves:*\n"
        for e in session.events[-4:]:
            actor = e["actor"]
            action = e["action"]
            dmg = e.get("damage", 0)
            if e.get("dodged"):
                caption += f"- {actor} {action} — dodged\n"
            else:
                caption += f"- {actor} {action} — {dmg} dmg\n"

    return caption


def _get_user_cooldowns(user_id: int) -> dict:
    try:
        db._add_column_if_missing("cooldowns", "TEXT")
    except:
        pass

    try:
        db.cursor.execute("SELECT cooldowns FROM users WHERE user_id=?", (user_id,))
        row = db.cursor.fetchone()
        if row and row[0]:
            return json.loads(row[0])
    except:
        pass

    return {}


def _set_user_cooldowns(user_id: int, cooldowns: dict):
    try:
        payload = json.dumps(cooldowns)
        db.cursor.execute("UPDATE users SET cooldowns=? WHERE user_id=?", (payload, user_id))
        db.conn.commit()
    except:
        pass


# ⭐ NEW — GUARANTEED UI REFRESH (DELETE OLD FRAME)
def _refresh_ui(bot, sess, chat_id):
    # Delete old UI (best effort)
    try:
        last_meta = sess.to_dict().get("_last_sent_message", {})
        old_id = last_meta.get("message_id")
        if old_id:
            bot.delete_message(chat_id, old_id)
    except:
        pass

    # Create new UI
    kb = _build_action_keyboard(sess)
    caption = _build_caption(sess)

    new_msg = bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=kb)

    # Save new pointer
    meta = sess.to_dict()
    meta["_last_sent_message"] = {"chat_id": chat_id, "message_id": new_msg.message_id}
    fight_session.manager._sessions[str(sess.user_id)] = meta
    fight_session.manager.save_session(sess)


# =====================================================
# HANDLER REGISTRATION
# =====================================================

def setup(bot: TeleBot):

    # -------------------------
    # /battle command
    # -------------------------
    @bot.message_handler(commands=["battle"])
    def battle_cmd(message):
        user_id = message.from_user.id

        # Prevent conflict with daily quick fight
        q = get_quests(user_id)
        if q.get("fight", 0) == 1:
            bot.reply_to(message, "⚔️ You already used your daily /fight. Use /battle instead.")
            return

        # Cooldown
        cooldowns = _get_user_cooldowns(user_id)
        last_ts = int(cooldowns.get("battle", 0))
        now = int(time.time())

        if last_ts and (now - last_ts < BATTLE_COOLDOWN_SECONDS):
            remain = BATTLE_COOLDOWN_SECONDS - (now - last_ts)
            bot.reply_to(message, f"⏳ You must wait {remain//3600}h {(remain%3600)//60}m.")
            return

        # Pick mob
        mob = random.choice(MOBS)
        user = get_user(user_id)

        # Intro animation
        try:
            safe_send_gif(bot, message.chat.id, GIF_INTRO)
        except:
            bot.send_message(message.chat.id, "⚔️ The battle begins!")

        # Create session
        player_stats = fight_session.build_player_stats_from_user(
            user,
            username_fallback=message.from_user.username or "You"
        )
        mob_stats = fight_session.build_mob_stats_from_mob(mob)
        sess = fight_session.manager.create_session(user_id, player_stats, mob_stats)

        # Send first UI
        _refresh_ui(bot, sess, message.chat.id)

    # -------------------------
    # CALLBACK HANDLER
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("battle:"))
    def battle_callback(call):
        parts = call.data.split(":")
        _, _, action, owner = parts
        owner_id = int(owner)
        user_id = call.from_user.id

        if owner_id != user_id:
            bot.answer_callback_query(call.id, "Not your battle!", show_alert=True)
            return

        sess = fight_session.manager.load_session(user_id)
        if not sess:
            bot.answer_callback_query(call.id, "Session expired.", show_alert=True)
            return

        chat_id = call.message.chat.id

        # --- SURRENDER ---
        if action == "surrender":
            sess.ended = True
            sess.winner = "mob"
            fight_session.manager.save_session(sess)

            _refresh_ui(bot, sess, chat_id)  # cleanup
            _finalize(bot, sess)
            fight_session.manager.end_session(user_id)
            bot.answer_callback_query(call.id, "You surrendered.")
            return

        # --- AUTO MODE ---
        if action == "auto":
            sess.auto_mode = not sess.auto_mode
            fight_session.manager.save_session(sess)
            bot.answer_callback_query(call.id, "Auto toggled.")

            # Auto turn immediately
            if sess.auto_mode:
                sess.resolve_auto_turn()
                fight_session.manager.save_session(sess)

            _refresh_ui(bot, sess, chat_id)

            if sess.ended:
                _finalize(bot, sess)
                fight_session.manager.end_session(user_id)
            return

        # --- NORMAL ACTIONS ---
        ACTION_MAP = {
            "attack": fight_session.ACTION_ATTACK,
            "block":  fight_session.ACTION_BLOCK,
            "dodge":  fight_session.ACTION_DODGE,
            "charge": fight_session.ACTION_CHARGE
        }

        if action not in ACTION_MAP:
            bot.answer_callback_query(call.id, "Invalid action.")
            return

        sess.resolve_player_action(ACTION_MAP[action])
        fight_session.manager.save_session(sess)

        _refresh_ui(bot, sess, chat_id)
        bot.answer_callback_query(call.id, "Action performed.")

        # End of battle?
        if sess.ended:
            _finalize(bot, sess)
            fight_session.manager.end_session(user_id)


# =====================================================
# FINAL XP + SUMMARY HANDLING
# =====================================================

def _finalize(bot: TeleBot, sess: fight_session.FightSession):
    user_id = sess.user_id
    user = get_user(user_id)
    mob = sess.mob

    # XP calc (same as /fight)
    base_xp = random.randint(mob.get("min_xp", 10), mob.get("max_xp", 25))
    lvl = user["level"]
    evo_mult = evolutions.get_xp_multiplier_for_level(lvl) * float(user.get("evolution_multiplier", 1.0))
    effective_xp = int(base_xp * evo_mult)

    xp_total = user["xp_total"] + effective_xp
    cur = user["xp_current"] + effective_xp
    xp_to_next = user["xp_to_next_level"]
    curve = user["level_curve_factor"]
    leveled_up = False

    while cur >= xp_to_next:
        cur -= xp_to_next
        lvl += 1
        xp_to_next = int(xp_to_next * curve)
        leveled_up = True

    update_user_xp(user_id, {
        "xp_total": xp_total,
        "xp_current": cur,
        "xp_to_next_level": xp_to_next,
        "level": lvl
    })

    if sess.winner == "player":
        increment_win(user_id)

    record_quest(user_id, "fight")

    # Apply cooldown
    cooldowns = _get_user_cooldowns(user_id)
    cooldowns["battle"] = int(time.time())
    _set_user_cooldowns(user_id, cooldowns)

    # Summary output
    chat_id = sess.to_dict().get("_last_sent_message", {}).get("chat_id")

    # Final GIF
    try:
        if sess.winner == "player" and os.path.exists(GIF_VICTORY):
            safe_send_gif(bot, chat_id, GIF_VICTORY)
        elif sess.winner == "mob" and os.path.exists(GIF_DEFEAT):
            safe_send_gif(bot, chat_id, GIF_DEFEAT)
    except:
        pass

    # Final message
    msg = []
    if sess.winner == "player":
        msg.append("🎉 *VICTORY!*")
    elif sess.winner == "mob":
        msg.append("☠️ *DEFEAT!*")
    else:
        msg.append("⚔️ *DRAW!*")

    msg.append(f"🎁 XP Gained: +{effective_xp}")

    if leveled_up:
        msg.append("🎉 *LEVEL UP!* Your MegaGrok grows stronger!")

    msg.append("⏳ Next /battle available in 12 hours.")

    bot.send_message(chat_id, "\n".join(msg), parse_mode="Markdown")
