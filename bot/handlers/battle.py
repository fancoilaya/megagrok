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


def _hp_bar_with_numbers(current: int, maximum: int, width: int = 18) -> str:
    """
    Returns the bar plus the actual HP numbers (Style A).
    Example: ▓▓▓▓░░░ 63 / 110
    """
    if maximum <= 0:
        maximum = 1
    pct = max(0.0, min(1.0, float(current) / float(maximum)))
    fill = int(round(pct * width))
    bar = f"{'▓' * fill}{'░' * (width - fill)}"
    return f"{bar} {current} / {maximum}"


def _build_caption(session: fight_session.FightSession) -> str:
    """
    Keep the same visual style but:
    - Use Telegram username (or fallback 'User<id>')
    - Show HP bar + actual HP numbers
    - No 'recent moves' block
    """
    # Username stored in session.player["username"] at creation time (we ensure this)
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

    # No recent moves text included (user requested cleaner UI)

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
            try:
                return json.loads(row[0])
            except Exception:
                return {}
    except Exception:
        pass

    return {}


def _set_user_cooldowns(user_id: int, cooldowns: dict):
    try:
        payload = json.dumps(cooldowns)
        db.cursor.execute("UPDATE users SET cooldowns=? WHERE user_id=?", (payload, user_id))
        db.conn.commit()
    except Exception:
        pass


# =====================================================
# UI REFRESH — robust, saves session reliably
# =====================================================

def _refresh_ui(bot: TeleBot, sess: fight_session.FightSession, chat_id: int):
    """
    Delete previous UI message (best-effort) and send a fresh one.
    Crucially: save the session reference AFTER sending the new message so future callbacks can find it.
    """
    # 1) Attempt to delete old UI message (best-effort)
    try:
        last_meta = sess.to_dict().get("_last_sent_message", {})
        old_msg_id = last_meta.get("message_id")
        if old_msg_id:
            try:
                bot.delete_message(chat_id, old_msg_id)
            except Exception:
                # deletion might fail if message already removed or insufficient rights
                pass
    except Exception:
        pass

    # 2) Build and send new UI
    kb = _build_action_keyboard(sess)
    caption = _build_caption(sess)
    new_msg = bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=kb)

    # 3) Save the new pointer into the session store immediately
    try:
        sess_meta = sess.to_dict()
        sess_meta["_last_sent_message"] = {"chat_id": chat_id, "message_id": new_msg.message_id}
        fight_session.manager._sessions[str(sess.user_id)] = sess_meta
        fight_session.manager.save_session(sess)
    except Exception:
        # best-effort: if saving fails, session still exists in memory (manager), try to store minimal info
        try:
            fight_session.manager._sessions[str(sess.user_id)] = sess.to_dict()
            fight_session.manager.save_session(sess)
        except Exception:
            pass

    return new_msg


# =====================================================
# HANDLER REGISTRATION
# =====================================================

def setup(bot: TeleBot):

    @bot.message_handler(commands=["battle"])
    def battle_cmd(message):
        user_id = message.from_user.id

        # keep quick /fight daily behavior intact
        q = get_quests(user_id)
        if q.get("fight", 0) == 1:
            bot.reply_to(message, "⚔️ You already used your daily /fight. Use /battle for cinematic fights.")
            return

        # Cooldown check
        cooldowns = _get_user_cooldowns(user_id)
        last_ts = int(cooldowns.get("battle", 0))
        now = int(time.time())
        if last_ts and (now - last_ts < BATTLE_COOLDOWN_SECONDS):
            remain = BATTLE_COOLDOWN_SECONDS - (now - last_ts)
            hours = remain // 3600
            minutes = (remain % 3600) // 60
            bot.reply_to(message, f"⏳ You can battle again in {hours}h {minutes}m.")
            return

        # Pick mob and load user
        mob = random.choice(MOBS)
        user = get_user(user_id)

        # Determine username: use TG username if present, else fallback to "User<id>"
        username = (message.from_user.username and f"@{message.from_user.username}") or f"User{user_id}"

        # Ensure the session player's username is set to this, overriding any stale value
        player_stats = fight_session.build_player_stats_from_user(user, username_fallback=username)
        player_stats["username"] = username  # force username

        mob_stats = fight_session.build_mob_stats_from_mob(mob)

        # Play intro GIF (safe fallback)
        try:
            safe_send_gif(bot, message.chat.id, GIF_INTRO)
        except Exception:
            try:
                bot.send_message(message.chat.id, "⚔️ The battle begins!")
            except Exception:
                pass

        # Create and persist session
        sess = fight_session.manager.create_session(user_id, player_stats, mob_stats)

        # Immediately send UI (and save session pointer inside _refresh_ui)
        _refresh_ui(bot, sess, message.chat.id)

    # -------------------------
    # CALLBACK HANDLER
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("battle:"))
    def battle_callback(call: types.CallbackQuery):
        parts = call.data.split(":")
        if len(parts) < 4:
            bot.answer_callback_query(call.id, "Invalid action.")
            return

        _, _, action, owner = parts[:4]
        owner_id = int(owner)
        user_id = call.from_user.id

        if owner_id != user_id:
            bot.answer_callback_query(call.id, "This battle isn't yours. Start /battle to begin your own.", show_alert=True)
            return

        # Load session fresh from manager (session IO is saved on every UI refresh)
        sess = fight_session.manager.load_session(user_id)
        if not sess:
            # Provide clearer instruction instead of generic expired message
            bot.answer_callback_query(call.id, "Battle session expired or not found. Start /battle again.", show_alert=True)
            return

        chat_id = call.message.chat.id

        # Surrender
        if action == "surrender":
            sess.ended = True
            sess.winner = "mob"
            fight_session.manager.save_session(sess)

            # Delete UI and finalize
            try:
                last_meta = sess.to_dict().get("_last_sent_message", {})
                old_chat = last_meta.get("chat_id", chat_id)
                old_msg = last_meta.get("message_id")
                if old_msg:
                    try:
                        bot.delete_message(old_chat, old_msg)
                    except Exception:
                        pass
            except Exception:
                pass

            _finalize(bot, sess, chat_id)
            fight_session.manager.end_session(user_id)
            bot.answer_callback_query(call.id, "You surrendered.")
            return

        # Auto toggle
        if action == "auto":
            sess.auto_mode = not sess.auto_mode
            fight_session.manager.save_session(sess)
            bot.answer_callback_query(call.id, "Auto mode toggled.")

            if sess.auto_mode:
                # perform an immediate AI turn
                sess.resolve_auto_turn()
                fight_session.manager.save_session(sess)

            # refresh UI (delete old, send new, save pointer)
            _refresh_ui(bot, sess, chat_id)

            # If fight ended due to auto turn
            if sess.ended:
                _finalize(bot, sess, chat_id)
                fight_session.manager.end_session(user_id)
            return

        # Normal actions mapping
        ACTION_MAP = {
            "attack": fight_session.ACTION_ATTACK,
            "block":  fight_session.ACTION_BLOCK,
            "dodge":  fight_session.ACTION_DODGE,
            "charge": fight_session.ACTION_CHARGE
        }

        if action not in ACTION_MAP:
            bot.answer_callback_query(call.id, "Unknown action.")
            return

        # Resolve the player's chosen action
        sess.resolve_player_action(ACTION_MAP[action])
        fight_session.manager.save_session(sess)

        # Refresh UI (delete old, send new, save pointer)
        _refresh_ui(bot, sess, chat_id)

        bot.answer_callback_query(call.id, "Action performed.")

        # If battle ended, finalize result
        if sess.ended:
            _finalize(bot, sess, chat_id)
            fight_session.manager.end_session(user_id)


# =====================================================
# FINAL XP + SUMMARY HANDLING
# =====================================================

def _finalize(bot: TeleBot, sess: fight_session.FightSession, fallback_chat_id: int = None):
    """
    Finalize XP, record quest, apply cooldown, and send final summary.
    """

    user_id = sess.user_id
    user = get_user(user_id)
    mob = sess.mob

    # XP calc (same as your /fight)
    base_xp = random.randint(int(mob.get("min_xp", 10)), int(mob.get("max_xp", 25)))
    lvl = user.get("level", 1)
    evo_mult = evolutions.get_xp_multiplier_for_level(lvl) * float(user.get("evolution_multiplier", 1.0))
    effective_xp = int(round(base_xp * evo_mult))

    # Update XP & level progression
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

    # Set cooldown timestamp
    cooldowns = _get_user_cooldowns(user_id)
    cooldowns["battle"] = int(time.time())
    _set_user_cooldowns(user_id, cooldowns)

    # Choose chat_id: prefer the session saved pointer, fallback to provided chat id
    chat_id = sess.to_dict().get("_last_sent_message", {}).get("chat_id") or fallback_chat_id

    # Send final cinematic GIF (best-effort)
    try:
        if chat_id:
            if sess.winner == "player" and os.path.exists(GIF_VICTORY):
                safe_send_gif(bot, chat_id, GIF_VICTORY)
            elif sess.winner == "mob" and os.path.exists(GIF_DEFEAT):
                safe_send_gif(bot, chat_id, GIF_DEFEAT)
    except Exception:
        pass

    # Build summary text
    lines = []
    if sess.winner == "player":
        lines.append("🎉 *VICTORY!*")
    elif sess.winner == "mob":
        lines.append("☠️ *DEFEAT!*")
    else:
        lines.append("⚔️ *DRAW!*")

    lines.append(f"Enemy: *{mob.get('name')}*")
    lines.append(f"🎁 XP gained: +{effective_xp}")

    if leveled_up:
        lines.append("🎉 *LEVEL UP!* Your MegaGrok grows stronger!")

    lines.append("⏳ Next /battle available in 12 hours.")

    try:
        if chat_id:
            bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")
    except Exception:
        # If even final send fails, ignore (best-effort)
        pass
