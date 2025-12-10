# bot/handlers/pvp.py
# MegaGrok Async PvP System (Attacker vs AI defender)
# Requires: db.py, services/fight_session.py

import os
import time
import random
from telebot import types
from telebot import TeleBot

import db
from services import fight_session
from bot.utils import safe_send_gif   # optional, remove if not used

# ==========================================
# CONFIG
# ==========================================

PVP_FREE_MODE = os.getenv("PVP_FREE_MODE", "true").lower() == "true"
PVP_SHIELD_SECONDS = int(os.getenv("PVP_SHIELD_SECONDS", str(3 * 3600)))
PVP_MIN_STEAL_PERCENT = 0.07     # 7%
PVP_MIN_STEAL_ABS = 20           # min XP if attacker wins
PVP_ELO_K = 32                   # ranking sensitivity


# ==========================================
# VIP ACCESS CHECK (placeholder; free for now)
# ==========================================
def has_pvp_access(user_id: int) -> bool:
    if PVP_FREE_MODE:
        return True
    # Later:
    # return db.is_vip(user_id)
    return True


# ==========================================
# UTILITY
# ==========================================
def hp_bar(cur, maxhp, width=16):
    ratio = max(0, min(1, cur / maxhp))
    f = int(width * ratio)
    return "▓" * f + "░" * (width - f)


# ==========================================
# CAPTION BUILDER
# ==========================================
def build_caption(sess: fight_session.FightSession):
    a = sess.pvp_attacker
    d = sess.pvp_defender
    a_name = a.get("username", f"Player{sess.attacker_id}")
    d_name = d.get("username", f"Player{sess.defender_id}")

    a_max = a.get("current_hp", a.get("hp"))
    d_max = d.get("current_hp", d.get("hp"))

    lines = [
        f"⚔️ *PvP Raid:* {a_name} vs {d_name}",
        "",
        f"{a_name}: {hp_bar(sess.attacker_hp, a_max)}  {sess.attacker_hp}/{a_max}",
        f"{d_name}: {hp_bar(sess.defender_hp, d_max)}  {sess.defender_hp}/{d_max}",
        "",
        f"Turn: {sess.turn}",
        "",
    ]

    if sess.events:
        lines.append("*Recent actions:*")
        for ev in sess.events[:4]:
            if ev["action"] == "attack":
                lines.append(f"⚔️ {ev['actor']} dealt {ev['damage']} dmg {ev.get('note','')}")
            else:
                lines.append(f"{ev['actor']} — {ev['action']} {ev.get('note','')}")
    return "\n".join(lines)


# ==========================================
# KEYBOARD BUILDER
# ==========================================
def action_keyboard(attacker_id: int, auto_mode: bool):
    kb = types.InlineKeyboardMarkup(row_width=3)
    uid = attacker_id

    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=f"pvp:act:attack:{uid}"),
        types.InlineKeyboardButton("🛡 Block", callback_data=f"pvp:act:block:{uid}"),
        types.InlineKeyboardButton("💨 Dodge", callback_data=f"pvp:act:dodge:{uid}")
    )
    kb.add(
        types.InlineKeyboardButton("⚡ Charge", callback_data=f"pvp:act:charge:{uid}"),
    )
    kb.add(
        types.InlineKeyboardButton(
            "▶ Auto" if not auto_mode else "⏸ Auto",
            callback_data=f"pvp:act:auto:{uid}"
        ),
        types.InlineKeyboardButton("✖ Forfeit", callback_data=f"pvp:act:forfeit:{uid}")
    )
    return kb


# ==========================================
# XP STEAL CALC
# ==========================================
def calc_xp_steal(def_total_xp: int) -> int:
    amount = int(def_total_xp * PVP_MIN_STEAL_PERCENT)
    return max(amount, PVP_MIN_STEAL_ABS)


# ==========================================
# DEFENDER NOTIFICATION
# ==========================================
def notify(bot: TeleBot, user_id: int, msg: str):
    try:
        bot.send_message(user_id, msg, parse_mode="Markdown")
    except:
        pass


# ==========================================
# FINALIZE PVP RESULT
# ==========================================
def finalize_pvp(bot: TeleBot, sess: fight_session.FightSession):
    attacker_id = sess.attacker_id
    defender_id = sess.defender_id

    attacker = db.get_user(attacker_id)
    defender = db.get_user(defender_id)

    atk_xp_total = attacker.get("xp_total", 0)
    def_xp_total = defender.get("xp_total", 0)

    attacker_won = sess.winner == "attacker"

    # XP
    xp_stolen = 0
    if attacker_won:
        xp_stolen = calc_xp_steal(def_xp_total)
        db.cursor.execute(
            "UPDATE users SET xp_total = xp_total - ?, xp_current = xp_current - ? WHERE user_id=?",
            (xp_stolen, xp_stolen, defender_id)
        )
        db.cursor.execute(
            "UPDATE users SET xp_total = xp_total + ?, xp_current = xp_current + ? WHERE user_id=?",
            (xp_stolen, xp_stolen, attacker_id)
        )
        db.increment_pvp_field(attacker_id, "pvp_wins")
        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_losses")
        db.increment_pvp_field(defender_id, "pvp_fights_defended")

        # Apply shield
        shield_until = int(time.time()) + PVP_SHIELD_SECONDS
        db.set_pvp_shield(defender_id, shield_until)

    else:
        # attacker lost
        xp_penalty = max(1, int(atk_xp_total * 0.05))
        db.cursor.execute(
            "UPDATE users SET xp_total = xp_total - ?, xp_current = xp_current - ? WHERE user_id=?",
            (xp_penalty, xp_penalty, attacker_id)
        )
        db.cursor.execute(
            "UPDATE users SET xp_total = xp_total + ?, xp_current = xp_current + ? WHERE user_id=?",
            (xp_penalty, xp_penalty, defender_id)
        )
        db.increment_pvp_field(attacker_id, "pvp_losses")
        db.increment_pvp_field(defender_id, "pvp_wins")

    db.conn.commit()

    # ELO
    atk_elo = attacker.get("elo_pvp", 1000)
    def_elo = defender.get("elo_pvp", 1000)

    def expected(a, b):
        return 1 / (1 + 10 ** ((b - a) / 400))

    E = expected(atk_elo, def_elo)
    K = PVP_ELO_K

    if attacker_won:
        new_atk = int(round(atk_elo + K * (1 - E)))
        new_def = int(round(def_elo - K * (1 - E)))
    else:
        new_atk = int(round(atk_elo + K * (0 - E)))
        new_def = int(round(def_elo - K * (0 - E)))

    db.update_elo(attacker_id, new_atk)
    db.update_elo(defender_id, new_def)

    # Notify defender
    if attacker_won:
        notify(
            bot,
            defender_id,
            f"⚠️ You were raided by {attacker.get('username') or attacker_id}!\n"
            f"XP stolen: {xp_stolen}\n"
            f"ELO change: {new_def - def_elo}\n"
            f"Shield active for {PVP_SHIELD_SECONDS//3600}h."
        )
    else:
        notify(
            bot,
            defender_id,
            f"🛡 Your AI defender repelled {attacker.get('username') or attacker_id}!\n"
            f"ELO change: {new_def - def_elo}"
        )

    return {
        "winner": sess.winner,
        "xp_stolen": xp_stolen,
        "elo_attacker": new_atk - atk_elo,
        "elo_defender": new_def - def_elo
    }


# ==========================================
# PvP START COMMAND — /attack
# ==========================================
def setup(bot: TeleBot):

    @bot.message_handler(commands=["attack"])
    def cmd_attack(message):
        attacker_id = message.from_user.id

        if not has_pvp_access(attacker_id):
            bot.reply_to(message, "🔒 PvP is VIP-only. Unlock by verifying your wallet.")
            return

        # determine target
        defender_id = None

        # 1 — reply target
        if message.reply_to_message:
            defender_id = message.reply_to_message.from_user.id

        # 2 — argument-based
        else:
            parts = message.text.split()
            if len(parts) <= 1:
                bot.reply_to(message, "Usage: /attack <name/@username> or reply to a user.")
                return

            query = parts[1].strip()

            # username?
            if query.startswith("@"):
                found = db.get_user_by_username(query)
                if found:
                    defender_id = found[0]
                else:
                    bot.reply_to(message, "User not found.")
                    return

            else:
                # fuzzy name search
                matches = db.search_users_by_name(query)
                if len(matches) == 0:
                    bot.reply_to(message, "No matching users.")
                    return
                elif len(matches) == 1:
                    defender_id = matches[0][0]
                else:
                    # show choice list
                    kb = types.InlineKeyboardMarkup()
                    for uid, uname, disp in matches:
                        label = disp or uname or f"User{uid}"
                        kb.add(types.InlineKeyboardButton(label, callback_data=f"pvp_select:{attacker_id}:{uid}"))
                    bot.reply_to(message, "Multiple matches found — choose:", reply_markup=kb)
                    return

        # validation
        if defender_id is None:
            bot.reply_to(message, "Could not determine target.")
            return

        if defender_id == attacker_id:
            bot.reply_to(message, "You cannot attack yourself.")
            return

        if db.is_pvp_shielded(defender_id):
            bot.reply_to(message, "🛡 Target is shielded from raids.")
            return

        # load players
        attacker = db.get_user(attacker_id)
        defender = db.get_user(defender_id)

        attacker_stats = fight_session.build_player_stats_from_user(attacker)
        defender_stats = fight_session.build_player_stats_from_user(defender)

        # start session
        sess = fight_session.manager.create_pvp_session(
            attacker_id, attacker_stats, defender_id, defender_stats
        )

        # attacker started raid
        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_challenges_received")

        caption = build_caption(sess)
        kb = action_keyboard(attacker_id, sess.auto_mode)

        try:
            safe_send_gif(bot, message.chat.id, "assets/gifs/pvp_intro.gif")
        except:
            pass

        m = bot.send_message(message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)

        # save message pointer
        store = fight_session.manager._sessions.get(str(attacker_id), {})
        store["_last_msg"] = {"chat": message.chat.id, "msg": m.message_id}
        fight_session.manager._sessions[str(attacker_id)] = store
        fight_session.manager.save_session(sess)


    # ==========================================
    # fuzzy selection callback
    # ==========================================
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp_select:"))
    def cb_select(call):
        _, attacker_str, target_str = call.data.split(":")
        attacker_id = int(attacker_str)
        defender_id = int(target_str)

        attacker = db.get_user(attacker_id)
        defender = db.get_user(defender_id)

        attacker_stats = fight_session.build_player_stats_from_user(attacker)
        defender_stats = fight_session.build_player_stats_from_user(defender)

        sess = fight_session.manager.create_pvp_session(
            attacker_id, attacker_stats, defender_id, defender_stats
        )

        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_challenges_received")

        caption = build_caption(sess)
        kb = action_keyboard(attacker_id, sess.auto_mode)

        m = bot.send_message(call.message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)

        store = fight_session.manager._sessions.get(str(attacker_id), {})
        store["_last_msg"] = {"chat": call.message.chat.id, "msg": m.message_id}
        fight_session.manager._sessions[str(attacker_id)] = store
        fight_session.manager.save_session(sess)

        bot.answer_callback_query(call.id, "Raid started!")


    # ==========================================
    # ACTION CALLBACKS
    # ==========================================
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:act:"))
    def cb_action(call: types.CallbackQuery):
        parts = call.data.split(":")
        _, _, action, attacker_str = parts
        attacker_id = int(attacker_str)

        if call.from_user.id != attacker_id:
            bot.answer_callback_query(call.id, "Not your raid.", show_alert=True)
            return

        sess = fight_session.manager.load_session(attacker_id)
        if not sess:
            bot.answer_callback_query(call.id, "Raid expired.", show_alert=True)
            return

        chat_id = call.message.chat.id

        # FORFEIT
        if action == "forfeit":
            sess.ended = True
            sess.winner = "defender"
            fight_session.manager.save_session(sess)

            finalize_pvp(bot, sess)
            fight_session.manager.end_session(attacker_id)

            bot.edit_message_text("❌ You forfeited the raid.", chat_id, call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        # AUTO toggle
        if action == "auto":
            sess.auto_mode = not sess.auto_mode
            fight_session.manager.save_session(sess)

            if sess.auto_mode:
                # burst several auto-turns
                for _ in range(4):
                    if sess.ended:
                        break
                    sess.resolve_auto_attacker_turn()
                    fight_session.manager.save_session(sess)

            # refresh UI
            caption = build_caption(sess)
            kb = action_keyboard(attacker_id, sess.auto_mode)
            bot.edit_message_text(caption, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=kb)

            if sess.ended:
                finalize_pvp(bot, sess)
                fight_session.manager.end_session(attacker_id)

            bot.answer_callback_query(call.id)
            return

        # NORMAL ACTIONS
        mapping = {
            "attack": "attack",
            "block": "block",
            "dodge": "dodge",
            "charge": "charge",
        }

        if action not in mapping:
            bot.answer_callback_query(call.id, "Invalid action.")
            return

        sess.resolve_attacker_action(mapping[action])
        fight_session.manager.save_session(sess)

        # refresh UI
        caption = build_caption(sess)
        kb = action_keyboard(attacker_id, sess.auto_mode)
        bot.edit_message_text(caption, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=kb)

        bot.answer_callback_query(call.id)

        if sess.ended:
            finalize_pvp(bot, sess)
            fight_session.manager.end_session(attacker_id)


    # ==========================================
    # PvP LEADERBOARD
    # ==========================================
    @bot.message_handler(commands=["pvp_top"])
    def cmd_pvp_top(message):
        top = db.get_top_pvp(10)
        if not top:
            bot.reply_to(message, "No PvP data yet.")
            return

        lines = ["🏆 *Top PvP Players*"]
        for row in top:
            name = row["name"]
            elo = row["elo"]
            w = row["wins"]
            l = row["losses"]
            lines.append(f"{row['rank']}. {name} — {elo} ELO ({w}W/{l}L)")

        bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")


    # ==========================================
    # PERSONAL PVP STATS
    # ==========================================
    @bot.message_handler(commands=["pvp_stats"])
    def cmd_pvp_stats(message):
        uid = message.from_user.id
        stats = db.get_pvp_stats(uid)

        msg = (
            f"📊 *Your PvP Stats*\n"
            f"ELO: {stats['elo']}\n"
            f"Wins: {stats['wins']}\n"
            f"Losses: {stats['losses']}\n"
            f"Raids Started: {stats['started']}\n"
            f"Defended: {stats['defended']}\n"
            f"Challenges Received: {stats['challenges']}\n"
            f"Shield until: {time.ctime(stats['shield_until'])}"
        )
        bot.reply_to(message, msg, parse_mode="Markdown")
