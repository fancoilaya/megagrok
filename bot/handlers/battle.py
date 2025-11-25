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
import bot.db as db  # access raw DB for cooldown storage
from bot.utils import safe_send_gif
import bot.evolutions as evolutions

# Assets folder
ASSETS_BASE = "assets/gifs"
GIF_INTRO = os.path.join(ASSETS_BASE, "battle_intro.gif")
GIF_VICTORY = os.path.join(ASSETS_BASE, "victory.gif")
GIF_DEFEAT = os.path.join(ASSETS_BASE, "defeat.gif")

# Cooldown config
BATTLE_COOLDOWN_SECONDS = 12 * 3600  # 12 hours


# -------------------------------------
# INTERNAL HELPERS
# -------------------------------------

def _build_action_keyboard(session: fight_session.FightSession) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=3)
    b_attack = types.InlineKeyboardButton("🗡 Attack", callback_data=f"battle:act:attack:{session.user_id}")
    b_block = types.InlineKeyboardButton("🛡 Block", callback_data=f"battle:act:block:{session.user_id}")
    b_dodge = types.InlineKeyboardButton("💨 Dodge", callback_data=f"battle:act:dodge:{session.user_id}")
    b_charge = types.InlineKeyboardButton("⚡ Charge", callback_data=f"battle:act:charge:{session.user_id}")
    b_auto = types.InlineKeyboardButton(("▶ Auto" if not session.auto_mode else "⏸ Auto"),
                                        callback_data=f"battle:act:auto:{session.user_id}")
    b_quit = types.InlineKeyboardButton("✖ Surrender", callback_data=f"battle:act:surrender:{session.user_id}")

    kb.add(b_attack, b_block, b_dodge, b_charge)
    kb.add(b_auto, b_quit)
    return kb


def _hp_bar(current: int, maximum: int, width: int = 18) -> str:
    pct = max(0.0, min(1.0, float(current) / float(maximum)))
    fill = int(round(pct * width))
    return f"{'▓' * fill}{'░' * (width - fill)} {int(pct * 100)}%"


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
            dmg = e.get("damage")
            if e.get("dodged"):
                caption += f"- {actor} {action} — dodged\n"
            else:
                caption += f"- {actor} {action} — {dmg} dmg\n"

    return caption


def _get_user_cooldowns(user_id: int) -> dict:
    """Load cooldown JSON field from DB."""
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


def _delete_previous_ui(bot: TeleBot, sess: fight_session.FightSession):
    """Delete previously-sent UI message."""
    try:
        last_meta = sess.to_dict().get("_last_sent_message", {})
        chat_id = last_meta.get("chat_id")
        msg_id = last_meta.get("message_id")
        if chat_id and msg_id:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception:
                pass
    except Exception:
        pass


# -------------------------------------
# PRIMARY HANDLER REGISTRATION
# -------------------------------------

def setup(bot: TeleBot):

    # ---------------------
    # /battle
    # ---------------------
    @bot.message_handler(commands=['battle'])
    def battle_cmd(message):
        user_id = message.from_user.id

        # Prevent conflict with quick fight
        q = get_quests(user_id)
        if q.get("fight", 0) == 1:
            bot.reply_to(message,
                         "⚔️ You already used your daily /fight.\n"
                         "Use /battle for the cinematic mode.")
            return

        # Cooldown check
        cooldowns = _get_user_cooldowns(user_id)
        last_battle_ts = int(cooldowns.get("battle", 0))
        now = int(time.time())

        if last_battle_ts and (now - last_battle_ts < BATTLE_COOLDOWN_SECONDS):
            remain = BATTLE_COOLDOWN_SECONDS - (now - last_battle_ts)
            hours = remain // 3600
            minutes = (remain % 3600) // 60
            bot.reply_to(message,
                         f"⏳ You can battle again in {hours}h {minutes}m.")
            return

        # Load player + mob
        mob = random.choice(MOBS)
        user = get_user(user_id)

        # Play intro GIF or fallback
        try:
            safe_send_gif(bot, message.chat.id, GIF_INTRO)
        except Exception:
            pass

        # Create fight session
        player_stats = fight_session.build_player_stats_from_user(
            user,
            username_fallback=message.from_user.username or "You"
        )
        mob_stats = fight_session.build_mob_stats_from_mob(mob)

        sess = fight_session.manager.create_session(user_id, player_stats, mob_stats)

        # Send first UI card
        kb = _build_action_keyboard(sess)
        caption = _build_caption(sess)

        sent = bot.send_message(message.chat.id, caption,
                                parse_mode="Markdown",
                                reply_markup=kb)

        sess_data = sess.to_dict()
        sess_data["_last_sent_message"] = {
            "chat_id": message.chat.id,
            "message_id": sent.message_id
        }
        fight_session.manager._sessions[str(user_id)] = sess_data
        fight_session.manager.save_session(sess)

    # ---------------------
    # CALLBACKS
    # ---------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("battle:"))
    def battle_callback(call: types.CallbackQuery):
        _, _, action, owner = call.data.split(":")
        owner_id = int(owner)
        user_id = call.from_user.id

        if owner_id != user_id:
            bot.answer_callback_query(call.id,
                                      "This is not your battle.",
                                      show_alert=True)
            return

        sess = fight_session.manager.load_session(user_id)
        if not sess:
            bot.answer_callback_query(call.id,
                                      "Battle session expired.",
                                      show_alert=True)
            return

        # SURRENDER
        if action == "surrender":
            sess.ended = True
            sess.winner = "mob"
            fight_session.manager.save_session(sess)

            _delete_previous_ui(bot, sess)
            _finalize_session_rewards(bot, sess)
            fight_session.manager.end_session(user_id)
            bot.answer_callback_query(call.id, "You surrendered.")
            return

        # AUTO MODE TOGGLE
        if action == "auto":
            sess.auto_mode = not sess.auto_mode
            fight_session.manager.save_session(sess)
            bot.answer_callback_query(call.id, "Auto toggled.")

            # Auto performs an immediate turn
            if sess.auto_mode:
                sess.resolve_auto_turn()
                fight_session.manager.save_session(sess)

            # UI refresh
            _delete_previous_ui(bot, sess)
            kb = _build_action_keyboard(sess)
            caption = _build_caption(sess)
            new_msg = bot.send_message(call.message.chat.id,
                                       caption,
                                       parse_mode="Markdown",
                                       reply_markup=kb)

            sess_data = sess.to_dict()
            sess_data["_last_sent_message"] = {
                "chat_id": call.message.chat.id,
                "message_id": new_msg.message_id
            }
            fight_session.manager._sessions[str(user_id)] = sess_data
            fight_session.manager.save_session(sess)

            # End fight?
            if sess.ended:
                _finalize_session_rewards(bot, sess)
                fight_session.manager.end_session(user_id)

            return

        # NORMAL ACTIONS
        ACTION_MAP = {
            "attack": fight_session.ACTION_ATTACK,
            "block": fight_session.ACTION_BLOCK,
            "dodge": fight_session.ACTION_DODGE,
            "charge": fight_session.ACTION_CHARGE
        }

        chosen_action = ACTION_MAP.get(action)
        if not chosen_action:
            bot.answer_callback_query(call.id, "Unknown action.")
            return

        # Resolve turn
        sess.resolve_player_action(chosen_action)
        fight_session.manager.save_session(sess)

        # Refresh UI
        _delete_previous_ui(bot, sess)
        kb = _build_action_keyboard(sess)
        caption = _build_caption(sess)
        new_msg = bot.send_message(call.message.chat.id,
                                   caption,
                                   parse_mode="Markdown",
                                   reply_markup=kb)

        sess_data = sess.to_dict()
        sess_data["_last_sent_message"] = {
            "chat_id": call.message.chat.id,
            "message_id": new_msg.message_id
        }
        fight_session.manager._sessions[str(user_id)] = sess_data
        fight_session.manager.save_session(sess)

        bot.answer_callback_query(call.id, "Action performed.")

        # End of fight?
        if sess.ended:
            _finalize_session_rewards(bot, sess)
            fight_session.manager.end_session(user_id)


# -------------------------------------
# FINAL XP + SUMMARY HANDLING
# -------------------------------------
def _finalize_session_rewards(bot: TeleBot, sess: fight_session.FightSession):
    user_id = sess.user_id
    user = get_user(user_id)
    mob = sess.mob

    # XP calculation identical to your /fight logic
    base_xp = random.randint(mob.get("min_xp", 10), mob.get("max_xp", 25))
    level = user.get("level", 1)
    tier_mult = evolutions.get_xp_multiplier_for_level(level)
    user_mult = float(user.get("evolution_multiplier", 1.0))
    evo_mult = tier_mult * user_mult

    effective_xp = int(round(base_xp * evo_mult))

    # Level progression
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

    # Apply cooldown
    cooldowns = _get_user_cooldowns(user_id)
    cooldowns["battle"] = int(time.time())
    _set_user_cooldowns(user_id, cooldowns)

    # Final message
    try:
        last_meta = sess.to_dict().get("_last_sent_message", {})
        chat_id = last_meta.get("chat_id")

        if sess.winner == "player" and os.path.exists(GIF_VICTORY):
            safe_send_gif(bot, chat_id, GIF_VICTORY)
        elif sess.winner == "mob" and os.path.exists(GIF_DEFEAT):
            safe_send_gif(bot, chat_id, GIF_DEFEAT)

        text = []
        if sess.winner == "player":
            text.append("🎉 *Victory!*")
        elif sess.winner == "mob":
            text.append("☠️ *Defeat!*")
        else:
            text.append("⚔️ *Draw!*")

        text.append(f"Enemy: *{mob.get('name')}*")
        text.append(f"🎁 XP gained: +{effective_xp}")

        if leveled_up:
            text.append("🎉 *LEVEL UP!* Your MegaGrok evolves further.")

        text.append("⏳ Next /battle available in 12 hours.")

        bot.send_message(chat_id,
                         "\n".join(text),
                         parse_mode="Markdown")

    except Exception:
        pass
