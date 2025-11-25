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
import bot.db as db  # access to cursor/conn and migration helper
from bot.utils import safe_send_gif
import bot.evolutions as evolutions

# Assets folder (use assets/gifs/ as agreed)
ASSETS_BASE = "assets/gifs"
GIF_INTRO = os.path.join(ASSETS_BASE, "battle_intro.gif")
GIF_VICTORY = os.path.join(ASSETS_BASE, "victory.gif")
GIF_DEFEAT = os.path.join(ASSETS_BASE, "defeat.gif")

# Cooldown config
BATTLE_COOLDOWN_SECONDS = 12 * 3600  # 12 hours

# Inline keyboard builder (for the editable UI message)
def _build_action_keyboard(session: fight_session.FightSession) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=3)
    b_attack = types.InlineKeyboardButton("🗡 Attack", callback_data=f"battle:act:attack:{session.user_id}")
    b_block = types.InlineKeyboardButton("🛡 Block", callback_data=f"battle:act:block:{session.user_id}")
    b_dodge = types.InlineKeyboardButton("💨 Dodge", callback_data=f"battle:act:dodge:{session.user_id}")
    b_charge = types.InlineKeyboardButton("⚡ Charge", callback_data=f"battle:act:charge:{session.user_id}")
    b_auto = types.InlineKeyboardButton(("▶ Auto" if not session.auto_mode else "⏸ Auto"), callback_data=f"battle:act:auto:{session.user_id}")
    b_quit = types.InlineKeyboardButton("✖ Surrender", callback_data=f"battle:act:surrender:{session.user_id}")
    kb.add(b_attack, b_block, b_dodge, b_charge)
    kb.add(b_auto, b_quit)
    return kb

def _hp_bar(current: int, maximum: int, width: int = 18) -> str:
    pct = max(0.0, min(1.0, float(current) / float(maximum) if maximum > 0 else 0.0))
    fill = int(round(pct * width))
    bar = "▓" * fill + "░" * (width - fill)
    return f"{bar} {int(pct*100)}%"

def _build_caption(session: fight_session.FightSession) -> str:
    player_name = session.player.get("username", "You")
    mob_name = session.mob.get("name", "Mob")
    player_max = int(session.player.get("current_hp", session.player.get("hp", 100)))
    mob_max = int(session.mob.get("hp", session.mob.get("max_hp", 100)))
    caption = (
        f"⚔️ *Battle — {player_name} vs {mob_name}*\n\n"
        f"{player_name}: {_hp_bar(session.player_hp, player_max)}\n"
        f"{mob_name}: {_hp_bar(session.mob_hp, mob_max)}\n\n"
        f"Turn: {session.turn}\n"
    )
    if session.events:
        caption += "\n*Recent moves:*\n"
        for e in session.events[-4:]:
            actor = e.get("actor")
            action = e.get("action")
            dmg = e.get("damage", 0)
            if e.get("dodged"):
                caption += f"- {actor} {action} — dodged\n"
            else:
                caption += f"- {actor} {action} — {dmg} dmg\n"
    return caption

# Helper: read cooldowns JSON for a user (returns dict)
def _get_user_cooldowns(user_id: int) -> dict:
    # ensure column exists (safe migration helper exists in db.py)
    try:
        db._add_column_if_missing("cooldowns", "TEXT")
    except Exception:
        # if helper missing or fails, proceed silently (best-effort)
        pass

    try:
        db.cursor.execute("SELECT cooldowns FROM users WHERE user_id = ?", (user_id,))
        row = db.cursor.fetchone()
        if row and row[0]:
            try:
                return json.loads(row[0])
            except Exception:
                return {}
    except Exception:
        pass
    return {}

# Helper: write cooldowns JSON for a user
def _set_user_cooldowns(user_id: int, cooldowns: dict) -> None:
    try:
        payload = json.dumps(cooldowns)
        db.cursor.execute("UPDATE users SET cooldowns = ? WHERE user_id = ?", (payload, user_id))
        db.conn.commit()
    except Exception:
        # best-effort — do not crash bot on DB write errors
        pass

# Handler registration entrypoint (main.py loads handlers via setup(bot))
def setup(bot: TeleBot):
    @bot.message_handler(commands=['battle'])
    def battle_cmd(message):
        user_id = message.from_user.id

        # Quick block if user used quick /fight today (keeps daily quest logic intact)
        q = get_quests(user_id)
        if q.get("fight", 0) == 1:
            bot.reply_to(message, "⚔️ You already fought today (quick mode). Use /battle for cinematic fights.")
            return

        # Check 12-hour cooldown using cooldowns JSON column
        cooldowns = _get_user_cooldowns(user_id)
        last_battle_ts = int(cooldowns.get("battle", 0))
        now = int(time.time())
        if last_battle_ts and now - last_battle_ts < BATTLE_COOLDOWN_SECONDS:
            remain = BATTLE_COOLDOWN_SECONDS - (now - last_battle_ts)
            hours = remain // 3600
            minutes = (remain % 3600) // 60
            bot.reply_to(message, f"⏳ You must wait {hours}h {minutes}m before starting another /battle.")
            return

        # Choose mob & load user
        mob = random.choice(MOBS)
        user = get_user(user_id)

        # Play intro GIF (safe_send_gif returns None which is OK)
        try:
            safe_send_gif(bot, message.chat.id, GIF_INTRO)
        except Exception:
            # ignore GIF errors; continue to UI
            pass

        # Create session
        player_stats = fight_session.build_player_stats_from_user(user, username_fallback=user.get("username", message.from_user.username or "You"))
        mob_stats = fight_session.build_mob_stats_from_mob(mob)
        sess = fight_session.manager.create_session(user_id, player_stats, mob_stats)

        # Send an editable UI message (text + buttons) — we store and edit this one
        kb = _build_action_keyboard(sess)
        caption = _build_caption(sess)
        sent = bot.send_message(message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)

        # store message pointer in session for future edits
        sess_meta = sess.to_dict()
        sess_meta["_last_sent_message"] = {"chat_id": message.chat.id, "message_id": getattr(sent, "message_id", None)}
        fight_session.manager._sessions[str(sess.user_id)] = sess_meta
        fight_session.manager.save_session(sess)

    # Callback handler
    @bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("battle:"))
    def battle_callback(call: types.CallbackQuery):
        parts = call.data.split(":")
        if len(parts) < 4:
            bot.answer_callback_query(call.id, "Invalid action.")
            return

        _, _, act, owner = parts[:4]
        owner_id = int(owner)
        user_id = call.from_user.id

        if user_id != owner_id:
            bot.answer_callback_query(call.id, "This battle isn't yours. Start your own /battle.", show_alert=True)
            return

        sess = fight_session.manager.load_session(owner_id)
        if not sess:
            bot.answer_callback_query(call.id, "Session expired or not found. Start /battle again.", show_alert=True)
            return

        # Surrender
        if act == "surrender":
            sess.ended = True
            sess.winner = "mob"
            fight_session.manager.save_session(sess)
            bot.answer_callback_query(call.id, "You surrendered.")
            _finalize_session_rewards(bot, sess)
            fight_session.manager.end_session(owner_id)
            return

        # Auto toggle
        if act == "auto":
            sess.auto_mode = not sess.auto_mode
            fight_session.manager.save_session(sess)
            bot.answer_callback_query(call.id, "Auto mode toggled.")
            if sess.auto_mode:
                res = sess.resolve_auto_turn()
                fight_session.manager.save_session(sess)
                _edit_session_message(bot, sess)
                if getattr(sess, "ended", False):
                    _finalize_session_rewards(bot, sess)
                    fight_session.manager.end_session(owner_id)
            else:
                _edit_session_message(bot, sess)
            return

        action_map = {
            "attack": fight_session.ACTION_ATTACK,
            "block": fight_session.ACTION_BLOCK,
            "dodge": fight_session.ACTION_DODGE,
            "charge": fight_session.ACTION_CHARGE
        }
        chosen_action = action_map.get(act)
        if not chosen_action:
            bot.answer_callback_query(call.id, "Unknown action.")
            return

        # Run one turn
        step_result = sess.resolve_player_action(chosen_action)
        fight_session.manager.save_session(sess)

        # Update editable UI message (we always edit the text message we created earlier)
        try:
            last_meta = sess.to_dict().get("_last_sent_message", {})
            chat_id = last_meta.get("chat_id")
            msg_id = last_meta.get("message_id")
            kb = _build_action_keyboard(sess)
            caption = _build_caption(sess)
            if chat_id and msg_id:
                try:
                    bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=caption, parse_mode="Markdown", reply_markup=kb)
                except Exception:
                    # fallback to sending a new message if edit fails
                    new_msg = bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=kb)
                    sess_meta = sess.to_dict()
                    sess_meta["_last_sent_message"] = {"chat_id": chat_id, "message_id": getattr(new_msg, "message_id", None)}
                    fight_session.manager._sessions[str(sess.user_id)] = sess_meta
                    fight_session.manager.save_session(sess)
            else:
                bot.send_message(call.message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            pass

        bot.answer_callback_query(call.id, "Action performed.")

        if getattr(sess, "ended", False):
            _edit_session_message(bot, sess)
            _finalize_session_rewards(bot, sess)
            fight_session.manager.end_session(owner_id)
            return


# -----------------------
# Rewards finalization (keeps your existing XP rules)
# -----------------------
def _finalize_session_rewards(bot: TeleBot, sess: fight_session.FightSession):
    user_id = sess.user_id
    user = get_user(user_id)
    mob = sess.mob

    base_xp = random.randint(int(mob.get("min_xp", 10)), int(mob.get("max_xp", 25)))
    level = user.get("level", 1)
    tier_mult = evolutions.get_xp_multiplier_for_level(level)
    user_mult = float(user.get("evolution_multiplier", 1.0))
    evo_mult = tier_mult * user_mult
    effective_xp = int(round(base_xp * evo_mult))

    # Update XP exactly like your /fight command
    xp_total = user["xp_total"] + effective_xp
    cur = user["xp_current"] + effective_xp
    xp_to_next = user["xp_to_next_level"]
    level = user["level"]
    curve = user["level_curve_factor"]
    leveled_up = False
    while cur >= xp_to_next:
        cur -= xp_to_next
        level += 1
        xp_to_next = int(xp_to_next * curve)
        leveled_up = True

    update_user_xp(
        user_id,
        {
            "xp_total": xp_total,
            "xp_current": cur,
            "xp_to_next_level": xp_to_next,
            "level": level
        }
    )

    if sess.winner == "player":
        increment_win(user_id)
    record_quest(user_id, "fight")

    # Set cooldown timestamp (12-hour cooldown)
    cooldowns = _get_user_cooldowns(user_id)
    cooldowns["battle"] = int(time.time())
    _set_user_cooldowns(user_id, cooldowns)

    # Play final cinematic GIF (best-effort) and send final summary
    try:
        last_meta = sess.to_dict().get("_last_sent_message", {})
        chat_id = last_meta.get("chat_id")
        if sess.winner == "player" and os.path.exists(GIF_VICTORY):
            safe_send_gif(bot, chat_id, GIF_VICTORY)
        elif sess.winner == "mob" and os.path.exists(GIF_DEFEAT):
            safe_send_gif(bot, chat_id, GIF_DEFEAT)
        # send final text summary
        if chat_id:
            final_caption = _build_caption(sess) + f"\n\n🎁 You gained +{effective_xp} XP!"
            bot.send_message(chat_id, final_caption, parse_mode="Markdown")
    except Exception:
        pass

def _edit_session_message(bot: TeleBot, sess: fight_session.FightSession):
    try:
        last_meta = sess.to_dict().get("_last_sent_message", {})
        chat_id = last_meta.get("chat_id")
        msg_id = last_meta.get("message_id")
        if not chat_id or not msg_id:
            return
        kb = _build_action_keyboard(sess)
        bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=_build_caption(sess), parse_mode="Markdown", reply_markup=kb)
    except Exception:
        pass
