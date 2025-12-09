# bot/battle.py
import os
import random
import time
import json
from telebot import types
from telebot import TeleBot

from services import fight_session
from bot.mobs import get_random_mob
from bot.db import (
    get_user,
    update_user_xp,
    record_quest,
)
import bot.db as db
from bot.utils import safe_send_gif
import bot.evolutions as evolutions
from bot.leaderboard_tracker import announce_leaderboard_if_changed

# Asset paths
ASSETS_BASE = "assets/gifs"
GIF_INTRO = os.path.join(ASSETS_BASE, "battle_intro.gif")
GIF_VICTORY = os.path.join(ASSETS_BASE, "victory.gif")
GIF_DEFEAT = os.path.join(ASSETS_BASE, "defeat.gif")

# Cooldown: 12 hours
BATTLE_COOLDOWN_SECONDS = 12 * 3600

# Auto mode burst processing
AUTO_BURST_TURNS = 4


# =========================================================
# UI ELEMENTS
# =========================================================

def _build_action_keyboard(session: fight_session.FightSession):
    kb = types.InlineKeyboardMarkup(row_width=3)
    uid = session.user_id

    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=f"battle:act:attack:{uid}"),
        types.InlineKeyboardButton("🛡 Block",  callback_data=f"battle:act:block:{uid}"),
        types.InlineKeyboardButton("💨 Dodge",  callback_data=f"battle:act:dodge:{uid}"),
        types.InlineKeyboardButton("⚡ Charge", callback_data=f"battle:act:charge:{uid}")
    )

    kb.add(
        types.InlineKeyboardButton("▶ Auto" if not session.auto_mode else "⏸ Auto",
                                   callback_data=f"battle:act:auto:{uid}"),
        types.InlineKeyboardButton("✖ Surrender",
                                   callback_data=f"battle:act:surrender:{uid}")
    )
    return kb


def _hp_bar_with_numbers(current, maximum, width=18):
    try:
        pct = max(0, min(1, float(current) / float(maximum)))
    except Exception:
        pct = 0
    fill = int(pct * width)
    bar = "▓" * fill + "░" * (width - fill)
    return f"{bar} {current} / {maximum}"


def _format_event_line(ev: dict) -> str:
    actor = ev.get("actor", "")
    action = ev.get("action", "")
    dmg = ev.get("damage", 0)
    dodged = ev.get("dodged", False)
    crit = ev.get("crit", False)
    note = ev.get("note", "")

    if action == "attack":
        if dodged:
            return f"⚔️ {actor} attacked — *dodged*"
        line = f"⚔️ {actor} attacked for {dmg} dmg"
        if crit:
            line += " (CRIT!)"
        if note:
            line += f" — {note}"
        return line

    if action == "charge":
        return f"⚡ {actor} charged. {note or ''}".strip()

    if action == "block":
        return f"🛡 {actor} defended. {note or ''}".strip()

    if action == "dodge":
        if dmg > 0:
            return f"💨 {actor} dodged & countered for {dmg}"
        return f"💨 {actor} attempted dodge. {note or ''}".strip()

    return f"{actor} did {action}. {note or ''}".strip()


def _build_caption(session: fight_session.FightSession):
    username = session.player.get("username", f"User{session.user_id}")
    mobname = session.mob.get("name", "Mob")

    p_max = int(session.player.get("current_hp", session.player.get("hp", 100)))
    m_max = int(session.mob.get("hp", session.mob.get("max_hp", 100)))

    lines = [
        f"⚔️ *Battle — {username} vs {mobname}*",
        "",
        f"{username}: {_hp_bar_with_numbers(session.player_hp, p_max)}",
        f"{mobname}:   {_hp_bar_with_numbers(session.mob_hp, m_max)}",
        "",
        f"Turn: {session.turn}",
        ""
    ]

    if session.events:
        lines.append("*Last actions:*")
        for ev in session.events[:4]:
            lines.append(_format_event_line(ev))

    return "\n".join(lines)


# =========================================================
# COOLDOWN HELPERS
# =========================================================

def _get_user_cooldowns(uid: int) -> dict:
    try:
        db._add_column_if_missing("cooldowns", "TEXT")
    except:
        pass

    try:
        db.cursor.execute("SELECT cooldowns FROM users WHERE user_id=?", (uid,))
        row = db.cursor.fetchone()
        if row and row[0]:
            return json.loads(row[0])
    except:
        pass
    return {}


def _set_user_cooldowns(uid: int, cooldowns: dict):
    try:
        payload = json.dumps(cooldowns)
        db.cursor.execute("UPDATE users SET cooldowns=? WHERE user_id=?", (payload, uid))
        db.conn.commit()
    except:
        pass


# =========================================================
# REFRESH BATTLE UI
# =========================================================

def _refresh_ui(bot: TeleBot, sess: fight_session.FightSession, chat_id: int):
    uid = sess.user_id

    try:
        store = fight_session.manager._sessions.get(str(uid), {})
        last = store.get("_last_sent_message", {})
        old_chat = last.get("chat_id")
        old_msg = last.get("message_id")
        if old_chat and old_msg:
            try:
                bot.delete_message(old_chat, old_msg)
            except:
                pass
    except:
        pass

    kb = _build_action_keyboard(sess)
    caption = _build_caption(sess)

    new_msg = bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=kb)

    sess_dict = sess.to_dict()
    old_store = fight_session.manager._sessions.get(str(uid), {})

    for k, v in old_store.items():
        if k not in sess_dict:
            sess_dict[k] = v

    sess_dict["_last_sent_message"] = {
        "chat_id": chat_id,
        "message_id": new_msg.message_id
    }

    fight_session.manager._sessions[str(uid)] = sess_dict
    fight_session.manager.save_session(sess)

    return new_msg


# =========================================================
# TIER SELECTION
# =========================================================

def _tier_selection_keyboard():
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
        types.InlineKeyboardButton("🐉 Tier 5 — Legendary", callback_data="battle:choose_tier:5"),
    )
    return kb


# =========================================================
# BATTLE SETUP
# =========================================================

def setup(bot: TeleBot):

    @bot.message_handler(commands=["battle"])
    def battle_cmd(message):
        uid = message.from_user.id

        cd = _get_user_cooldowns(uid)
        last = int(cd.get("battle", 0))
        now = int(time.time())

        if last and now - last < BATTLE_COOLDOWN_SECONDS:
            remain = BATTLE_COOLDOWN_SECONDS - (now - last)
            bot.reply_to(message, f"⏳ Next /battle in: {remain//3600}h {(remain%3600)//60}m")
            return

        bot.send_message(message.chat.id, "Choose your opponent tier:", reply_markup=_tier_selection_keyboard())

    # ---- SAFE battle start ----

    def _start_battle_for_tier(bot, owner_id: int, chat_id: int, tier: int):
        user = get_user(owner_id)
        mob = get_random_mob(tier=tier)

        if not mob:
            bot.send_message(chat_id, "⚠ No mobs found for this tier.")
            return

        username = user.get("username", f"User{owner_id}")
        if username:
            username = f"@{username}"

        player_stats = fight_session.build_player_stats_from_user(user, username_fallback=username)
        mob_stats = fight_session.build_mob_stats_from_mob(mob)

        # Intro text
        intro_text = mob.get("intro")
        if intro_text:
            bot.send_message(chat_id, intro_text)

        # Show mob GIF if exists
        mob_gif = mob.get("gif")
        if mob_gif and os.path.exists(mob_gif):
            safe_send_gif(bot, chat_id, mob_gif)
        else:
            safe_send_gif(bot, chat_id, GIF_INTRO)

        # Delay needed so keyboard doesn't get dropped after GIF
        time.sleep(0.15)

        sess = fight_session.manager.create_session(owner_id, player_stats, mob_stats)

        _refresh_ui(bot, sess, chat_id)

    # ------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("battle:choose_tier:"))
    def choose_tier_handler(call: types.CallbackQuery):
        tier = int(call.data.split(":")[2])
        owner_id = call.from_user.id
        chat_id = call.message.chat.id

        _start_battle_for_tier(bot, owner_id, chat_id, tier)

        bot.answer_callback_query(call.id, f"Starting Tier {tier} battle.")

    # ------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("battle:act:"))
    def battle_action(call: types.CallbackQuery):
        _, _, action, owner_str = call.data.split(":")
        chat_id = call.message.chat.id

        try:
            owner = int(owner_str)
        except:
            bot.answer_callback_query(call.id, "Invalid owner.", show_alert=True)
            return

        if call.from_user.id != owner:
            bot.answer_callback_query(call.id, "Not your battle!", show_alert=True)
            return

        sess = fight_session.manager.load_session(owner)
        if not sess:
            bot.answer_callback_query(call.id, "Battle expired.", show_alert=True)
            return

        # ---------- SURRENDER ----------
        if action == "surrender":
            sess.ended = True
            sess.winner = "mob"
            fight_session.manager.save_session(sess)

            _refresh_ui(bot, sess, chat_id)
            _finalize(bot, sess, chat_id)
            fight_session.manager.end_session(owner)
            bot.answer_callback_query(call.id, "You surrendered.")
            return

        # ---------- AUTO MODE ----------
        if action == "auto":
            sess.auto_mode = not sess.auto_mode
            fight_session.manager.save_session(sess)
            bot.answer_callback_query(call.id, "Auto toggled.")

            if sess.auto_mode:
                for _ in range(AUTO_BURST_TURNS):
                    if sess.ended:
                        break
                    sess.resolve_auto_turn()
                    fight_session.manager.save_session(sess)

            _refresh_ui(bot, sess, chat_id)

            if sess.ended:
                _finalize(bot, sess, chat_id)
                fight_session.manager.end_session(owner)

            return

        # ---------- NORMAL ACTION ----------
        ACTIONS = {
            "attack": fight_session.ACTION_ATTACK,
            "block":  fight_session.ACTION_BLOCK,
            "dodge":  fight_session.ACTION_DODGE,
            "charge": fight_session.ACTION_CHARGE
        }

        if action not in ACTIONS:
            bot.answer_callback_query(call.id, "Invalid action.")
            return

        sess.resolve_player_action(ACTIONS[action])
        fight_session.manager.save_session(sess)

        _refresh_ui(bot, sess, chat_id)
        bot.answer_callback_query(call.id, "Action performed")

        if sess.auto_mode and not sess.ended:
            for _ in range(AUTO_BURST_TURNS):
                if sess.ended:
                    break
                sess.resolve_auto_turn()
                fight_session.manager.save_session(sess)
            _refresh_ui(bot, sess, chat_id)

        if sess.ended:
            _finalize(bot, sess, chat_id)
            fight_session.manager.end_session(owner)


# =========================================================
# FINALIZE BATTLE
# =========================================================

def _finalize(bot: TeleBot, sess: fight_session.FightSession, chat_id: int):
    user_id = sess.user_id
    user = get_user(user_id)
    mob = sess.mob

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

    update_user_xp(
        user_id,
        {"xp_total": xp_total, "xp_current": cur, "xp_to_next_level": xp_to_next, "level": lvl}
    )

    # Leaderboard
    try:
        announce_leaderboard_if_changed(bot)
    except:
        pass

    try:
        record_quest(user_id, "battle")
    except:
        pass

    try:
        cd = _get_user_cooldowns(user_id)
        cd["battle"] = int(time.time())
        _set_user_cooldowns(user_id, cd)
    except:
        pass

    # Delete UI
    try:
        last = sess.to_dict().get("_last_sent_message", {})
        bot.delete_message(last.get("chat_id"), last.get("message_id"))
    except:
        pass

    # Show ending GIF
    try:
        if sess.winner == "player":
            if os.path.exists(GIF_VICTORY):
                safe_send_gif(bot, chat_id, GIF_VICTORY)
        elif sess.winner == "mob":
            if os.path.exists(GIF_DEFEAT):
                safe_send_gif(bot, chat_id, GIF_DEFEAT)
    except:
        pass

    msg = []

    if sess.winner == "player":
        msg.append(f"🎉 *{mob.get('win_text', 'VICTORY!')}*")
    elif sess.winner == "mob":
        msg.append(f"☠️ *{mob.get('lose_text', 'DEFEAT!')}*")
    else:
        msg.append("⚔️ *DRAW!*")

    msg.append(f"🎁 XP gained: +{effective_xp}")

    if leveled:
        msg.append("🎉 *LEVEL UP!* Your MegaGrok grows stronger!")

    msg.append("⏳ Next /battle in 12 hours.")

    bot.send_message(chat_id, "\n".join(msg), parse_mode="Markdown")
