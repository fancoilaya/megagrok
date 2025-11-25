# bot/battle.py
import os
import random
import time
from telebot import types
from services import fight_session
from bot import evolutions  # your module
from bot.mobs import MOBS
from bot.db import (
    get_user,
    update_user_xp,
    get_quests,
    record_quest,
    increment_win
)
from bot.utils import safe_send_gif  # helper you already have for sending gifs
from telebot import TeleBot

# NOTE: this file expects your main TeleBot instance variable `bot` to be available globally
# If you register handlers via register_handlers(bot) in commands.py you can import this module
# and call register functions or execute inline registration here if you prefer.

# Asset paths (adjust to your layout)
ASSETS_BASE = "assets/gifs"
GIF_INTRO = os.path.join(ASSETS_BASE, "battle_intro.gif")
GIF_ATTACK = os.path.join(ASSETS_BASE, "attack.gif")
GIF_DODGE = os.path.join(ASSETS_BASE, "dodge.gif")
GIF_CRIT = os.path.join(ASSETS_BASE, "crit.gif")
GIF_BLOCK = os.path.join(ASSETS_BASE, "block.gif")
GIF_MOB_ATTACK = os.path.join(ASSETS_BASE, "mob_attack.gif")
GIF_VICTORY = os.path.join(ASSETS_BASE, "victory.gif")
GIF_DEFEAT = os.path.join(ASSETS_BASE, "defeat.gif")
GIF_AUTO = os.path.join(ASSETS_BASE, "auto.gif")

# Inline keyboard builder
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

# Small helper to render HP bars
def _hp_bar(current: int, maximum: int, width: int = 18) -> str:
    pct = max(0.0, min(1.0, float(current) / float(maximum) if maximum > 0 else 0.0))
    fill = int(round(pct * width))
    bar = "▓" * fill + "░" * (width - fill)
    return f"{bar} {int(pct*100)}%"

# Small helper to format the fight summary/caption
def _build_caption(session: fight_session.FightSession) -> str:
    player_name = session.player.get("username", "You")
    mob_name = session.mob.get("name", "Mob")
    caption = (
        f"⚔️ *Battle — {player_name} vs {mob_name}*\n\n"
        f"{player_name}: {_hp_bar(session.player_hp, session.player.get('current_hp', session.player.get('hp', 100)))}\n"
        f"{mob_name}: {_hp_bar(session.mob_hp, session.mob.get('hp', session.mob.get('max_hp', 100)))}\n\n"
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

# -----------------------
# /battle command handler
# -----------------------
def register_battle_handlers(bot: TeleBot):
    @bot.message_handler(commands=['battle'])
    def battle_cmd(message):
        user_id = message.from_user.id
        q = get_quests(user_id)
        if q.get("fight", 0) == 1:
            bot.reply_to(message, "⚔️ You already fought today (quick mode). Use /battle when you want the cinematic mode.")
            return

        mob = random.choice(MOBS)
        user = get_user(user_id)

        player_stats = fight_session.build_player_stats_from_user(user, username_fallback=user.get("username", message.from_user.username or "You"))
        mob_stats = fight_session.build_mob_stats_from_mob(mob)
        sess = fight_session.manager.create_session(user_id, player_stats, mob_stats)

        kb = _build_action_keyboard(sess)
        caption = _build_caption(sess)
        try:
            if os.path.exists(GIF_INTRO):
                # use safe_send_gif helper where available (keeps your file-size/format handling centralized)
                safe_send_gif(bot, message.chat.id, GIF_INTRO, caption=caption, reply_markup=kb)
                # safe_send_gif should return the sent message object or you can fallback
                # For compatibility we fetch last message id if needed - but safe_send_gif implementation will vary
                sent = None
            else:
                sent = bot.send_message(message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            sent = bot.send_message(message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)

        # store message pointer if available (best-effort)
        if sent:
            sess_meta = sess.to_dict()
            sess_meta["_last_sent_message"] = {"chat_id": message.chat.id, "message_id": getattr(sent, "message_id", None)}
            fight_session.manager._sessions[str(sess.user_id)] = sess_meta
            fight_session.manager.save_session(sess)
        else:
            # best-effort store without message id
            fight_session.manager.save_session(sess)

    # Callback handler registered inside same function so it has bot in scope
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

        if act == "surrender":
            sess.ended = True
            sess.winner = "mob"
            fight_session.manager.save_session(sess)
            bot.answer_callback_query(call.id, "You surrendered.")
            _finalize_session_rewards(bot, sess, defeated=True)
            fight_session.manager.end_session(owner_id)
            return

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

        step_result = sess.resolve_player_action(chosen_action)
        fight_session.manager.save_session(sess)

        # update the message (caption & keyboard). We try to edit caption; if GIFs are used and editing fails we fallback to sending a new animation/message.
        try:
            last_meta = sess.to_dict().get("_last_sent_message", {})
            chat_id = last_meta.get("chat_id")
            msg_id = last_meta.get("message_id")
            kb = _build_action_keyboard(sess)
            caption = _build_caption(sess)
            # attempt to edit caption (works if the message has caption)
            if chat_id and msg_id:
                try:
                    bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=caption, parse_mode="Markdown", reply_markup=kb)
                except Exception:
                    # fallback: send a new caption/message
                    bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=kb)
            else:
                bot.send_message(call.message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            pass

        bot.answer_callback_query(call.id, "Action performed.")

        if getattr(sess, "ended", False):
            _edit_session_message(bot, sess)
            _finalize_session_rewards(bot, sess, defeated=(sess.winner != "player"))
            fight_session.manager.end_session(owner_id)
            return


# -----------------------
# Helpers for finalizing rewards
# -----------------------
def _finalize_session_rewards(bot: TeleBot, sess: fight_session.FightSession, defeated: bool = False):
    """
    Apply XP and other rewards using your existing flow (keeps behavior identical to /fight).
    """
    user_id = sess.user_id
    user = get_user(user_id)
    mob = sess.mob
    base_xp = random.randint(int(mob.get("min_xp", 10)), int(mob.get("max_xp", 25)))
    level = user.get("level", 1)
    tier_mult = evolutions.get_xp_multiplier_for_level(level)
    user_mult = float(user.get("evolution_multiplier", 1.0))
    evo_mult = tier_mult * user_mult
    effective_xp = int(round(base_xp * evo_mult))

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

    # send final cinematic (best-effort)
    try:
        last_meta = sess.to_dict().get("_last_sent_message", {})
        chat_id = last_meta.get("chat_id")
        if sess.winner == "player" and os.path.exists(GIF_VICTORY):
            safe_send_gif(bot, chat_id, GIF_VICTORY, caption=_build_caption(sess) + f"\n\n🎉 You gained +{effective_xp} XP!")
        elif sess.winner == "mob" and os.path.exists(GIF_DEFEAT):
            safe_send_gif(bot, chat_id, GIF_DEFEAT, caption=_build_caption(sess) + f"\n\nYou gained +{effective_xp} XP.")
        else:
            if chat_id:
                bot.send_message(chat_id, _build_caption(sess) + f"\n\nYou gained +{effective_xp} XP.", parse_mode="Markdown")
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
        bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=_build_caption(sess), parse_mode="Markdown", reply_markup=kb)
    except Exception:
        pass
