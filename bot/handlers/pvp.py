# bot/handlers/pvp.py
# MegaGrok PvP System – Fully Corrected Version
# Works with: db.py, fight_session.py (your uploaded versions)

import os
import time
import random
from telebot import TeleBot, types

import bot.db as db
import services.fight_session as fight_session


# ============================================================
# CONFIG
# ============================================================
PVP_FREE_MODE = os.getenv("PVP_FREE_MODE", "true").lower() == "true"
PVP_SHIELD_SECONDS = int(os.getenv("PVP_SHIELD_SECONDS", str(3 * 3600)))
PVP_MIN_STEAL_PERCENT = float(os.getenv("PVP_MIN_STEAL_PERCENT", "0.07"))
PVP_MIN_STEAL_ABS = int(os.getenv("PVP_MIN_STEAL_ABS", "20"))
PVP_ELO_K = int(os.getenv("PVP_ELO_K", "32"))
RESULT_BAR_WIDTH = 18


# ============================================================
# SAFE GIF
# ============================================================
try:
    from bot.utils import safe_send_gif
except:
    def safe_send_gif(bot, chat_id, file_path):
        pass


# ============================================================
# HELPERS
# ============================================================
def get_display_name(user):
    if not user:
        return "Unknown"
    if user.get("display_name"):
        return user["display_name"]
    if user.get("username"):
        return user["username"]
    return f"User{user.get('user_id')}"


def hp_bar(cur, maxhp, width=16):
    cur = max(0, int(cur))
    maxhp = max(1, int(maxhp))
    ratio = cur / maxhp
    full = int(width * ratio)
    return "▓" * full + "░" * (width - full)


def safe_edit_message(bot, chat_id, msg_id, text, kb):
    try:
        bot.edit_message_text(
            text,
            chat_id,
            msg_id,
            parse_mode="Markdown",
            reply_markup=kb
        )
    except Exception as e:
        if "message is not modified" in str(e):
            return
        print("safe_edit_message ERROR:", e)


def calc_xp_steal(def_xp):
    return max(int(def_xp * PVP_MIN_STEAL_PERCENT), PVP_MIN_STEAL_ABS)


def notify(bot, user_id, text):
    try:
        bot.send_message(user_id, text, parse_mode="Markdown")
    except:
        pass


# ============================================================
# BUILD CAPTION
# ============================================================
def build_caption(sess):
    a = sess.pvp_attacker
    d = sess.pvp_defender

    a_name = get_display_name(a)
    d_name = get_display_name(d)

    a_max = a.get("current_hp", a.get("hp", 100))
    d_max = d.get("current_hp", d.get("hp", 100))

    lines = [
        f"⚔️ *PvP Raid:* {a_name} vs {d_name}",
        "",
        f"{a_name}: {hp_bar(sess.attacker_hp, a_max, 20)}  {sess.attacker_hp}/{a_max}",
        f"{d_name}: {hp_bar(sess.defender_hp, d_max, 20)}  {sess.defender_hp}/{d_max}",
        "",
        f"Turn {sess.turn}",
        ""
    ]

    if sess.events:
        lines.append("*Recent events:*")
        for ev in sess.events[:5]:
            actor = a_name if ev["actor"] == "attacker" else d_name
            if ev["action"] == "attack":
                dmg = ev.get("damage", 0)
                note = ev.get("note", "")
                lines.append(f"• {actor} dealt {dmg} dmg {note}")
            else:
                lines.append(f"• {actor}: {ev['action']} {ev.get('note','')}")

    return "\n".join(lines)


# ============================================================
# ACTION KEYBOARD
# ============================================================
def action_keyboard(attacker_id, auto_mode):
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=f"pvp:act:attack:{attacker_id}"),
        types.InlineKeyboardButton("🛡 Block", callback_data=f"pvp:act:block:{attacker_id}"),
        types.InlineKeyboardButton("💨 Dodge", callback_data=f"pvp:act:dodge:{attacker_id}")
    )
    kb.add(types.InlineKeyboardButton("⚡ Charge", callback_data=f"pvp:act:charge:{attacker_id}"))
    kb.add(
        types.InlineKeyboardButton("▶ Auto" if not auto_mode else "⏸ Auto", callback_data=f"pvp:act:auto:{attacker_id}"),
        types.InlineKeyboardButton("❌ Forfeit", callback_data=f"pvp:act:forfeit:{attacker_id}")
    )
    return kb


# ============================================================
# FINALIZE PVP (XP/ELO/SHIELD)
# ============================================================
def finalize_pvp(bot, sess):
    attacker_id = sess.attacker_id
    defender_id = sess.defender_id

    atk = db.get_user(attacker_id)
    dfd = db.get_user(defender_id)

    atk_xp = atk.get("xp_total", 0)
    dfd_xp = dfd.get("xp_total", 0)

    attacker_won = sess.winner == "attacker"
    xp_stolen = 0

    # best hits
    best_hits = {"attacker": {"damage": 0}, "defender": {"damage": 0}}

    for ev in sess.events:
        if ev["action"] == "attack":
            dmg = ev["damage"]
            if ev["actor"] == "attacker" and dmg > best_hits["attacker"]["damage"]:
                best_hits["attacker"] = {"damage": dmg, "turn": ev["turn"]}
            if ev["actor"] == "defender" and dmg > best_hits["defender"]["damage"]:
                best_hits["defender"] = {"damage": dmg, "turn": ev["turn"]}

    if attacker_won:
        xp_stolen = calc_xp_steal(dfd_xp)

        db.cursor.execute("UPDATE users SET xp_total=xp_total-?, xp_current=xp_current-? WHERE user_id=?",
                          (xp_stolen, xp_stolen, defender_id))
        db.cursor.execute("UPDATE users SET xp_total=xp_total+?, xp_current=xp_current+? WHERE user_id=?",
                          (xp_stolen, xp_stolen, attacker_id))

        db.increment_pvp_field(attacker_id, "pvp_wins")
        db.increment_pvp_field(defender_id, "pvp_losses")

        db.set_pvp_shield(defender_id, int(time.time()) + PVP_SHIELD_SECONDS)

    else:
        penalty = max(1, int(atk_xp * 0.05))

        db.cursor.execute("UPDATE users SET xp_total=xp_total-?, xp_current=xp_current-? WHERE user_id=?",
                          (penalty, penalty, attacker_id))
        db.cursor.execute("UPDATE users SET xp_total=xp_total+?, xp_current=xp_current+? WHERE user_id=?",
                          (penalty, penalty, defender_id))

        db.increment_pvp_field(attacker_id, "pvp_losses")
        db.increment_pvp_field(defender_id, "pvp_wins")

    db.conn.commit()

    # ELO
    atk_elo = atk.get("elo_pvp", 1000)
    dfd_elo = dfd.get("elo_pvp", 1000)

    def expected(a, b):
        return 1 / (1 + 10 ** ((b - a) / 400)))

    E = expected(atk_elo, dfd_elo)

    if attacker_won:
        new_atk = atk_elo + int(PVP_ELO_K * (1 - E))
        new_dfd = dfd_elo - int(PVP_ELO_K * (1 - E))
    else:
        new_atk = atk_elo + int(PVP_ELO_K * (0 - E))
        new_dfd = dfd_elo - int(PVP_ELO_K * (0 - E))

    db.update_elo(attacker_id, new_atk)
    db.update_elo(defender_id, new_dfd)

    # notify defender
    a_name = get_display_name(atk)

    if attacker_won:
        notify(bot, defender_id, f"⚠️ You were raided by *{a_name}*!\nXP lost: {xp_stolen}\nELO change: {new_dfd - dfd_elo}\n🛡 Shield active!")
    else:
        notify(bot, defender_id, f"🛡 Your AI defender repelled *{a_name}*!\nELO change: {new_dfd - dfd_elo}")

    return {
        "winner": sess.winner,
        "xp_stolen": xp_stolen,
        "elo_attacker": new_atk - atk_elo,
        "elo_defender": new_dfd - dfd_elo,
        "attacker_hp": sess.attacker_hp,
        "defender_hp": sess.defender_hp,
        "best_hits": best_hits
    }


# ============================================================
# RESULT CARD
# ============================================================
def send_pvp_result_card(bot, sess, summary):
    attacker = db.get_user(sess.attacker_id)
    defender = db.get_user(sess.defender_id)

    a_name = get_display_name(attacker)
    d_name = get_display_name(defender)

    # MUST use correct chat:
    last_msg = sess._last_msg
    chat_id = last_msg["chat"] if last_msg else sess.attacker_id

    # XP progress
    cur = attacker.get("xp_current", 0)
    nxt = attacker.get("xp_to_next_level", attacker.get("xp_needed", 100))
    ratio = 0 if nxt == 0 else min(1.0, max(0.0, cur / nxt))
    xp_bar = "▓" * int(RESULT_BAR_WIDTH * ratio) + "░" * (RESULT_BAR_WIDTH - int(RESULT_BAR_WIDTH * ratio))

    # HP bars
    atk_hp = summary["attacker_hp"]
    dfd_hp = summary["defender_hp"]
    atk_max = attacker.get("current_hp", attacker.get("hp", 100))
    dfd_max = defender.get("current_hp", defender.get("hp", 100))

    atk_bar = hp_bar(atk_hp, atk_max, 12)
    dfd_bar = hp_bar(dfd_hp, dfd_max, 12)

    atk_best = summary["best_hits"]["attacker"]
    dfd_best = summary["best_hits"]["defender"]

    if summary["winner"] == "attacker":
        title = "🏆 *VICTORY!*"
        subtitle = f"You defeated *{d_name}*"
        xp_line = f"🎁 XP stolen: +{summary['xp_stolen']}"
        elo_line = f"ELO: {summary['elo_attacker']:+d}"
    else:
        title = "💀 *DEFEAT*"
        subtitle = f"You were repelled by *{d_name}*"
        xp_line = f"📉 XP lost: -{summary['xp_stolen']}"
        elo_line = f"ELO: {summary['elo_attacker']:+d}"

    shield_line = ""
    try:
        su = db.get_pvp_shield_until(sess.defender_id)
        if su:
            hours = max(0, int((su - time.time()) / 3600))
            shield_line = f"🛡 Shield active for {hours}h"
    except:
        pass

    text = (
        f"{title}\n"
        f"{subtitle}\n\n"
        f"{xp_line}    {elo_line}\n\n"
        f"❤️ {a_name}: {atk_bar} {atk_hp}/{atk_max}\n"
        f"💀 {d_name}: {dfd_bar} {dfd_hp}/{dfd_max}\n\n"
    )

    if atk_best["damage"]:
        text += f"💥 Your best hit: {atk_best['damage']} dmg\n"
    if dfd_best["damage"]:
        text += f"💢 Enemy best hit: {dfd_best['damage']} dmg\n"

    text += (
        f"\n🔥 Level {attacker.get('level',1)}\n"
        f"📊 Progress: {xp_bar} {int(ratio*100)}%\n"
        f"⬆ XP needed: {max(0, nxt - cur)}\n"
    )

    if shield_line:
        text += f"\n{shield_line}"

    bot.send_message(chat_id, text, parse_mode="Markdown")


# ============================================================
# PVP SETUP
# ============================================================
def setup(bot: TeleBot):

    # ---------------------------
    # /attack
    # ---------------------------
    @bot.message_handler(commands=["attack"])
    def cmd_attack(message):
        attacker_id = message.from_user.id

        if not has_pvp_access(attacker_id):
            bot.reply_to(message, "🔒 PvP requires VIP.")
            return

        defender_id = None

        # reply mode
        if message.reply_to_message:
            defender_id = message.reply_to_message.from_user.id

        # parse argument
        else:
            parts = message.text.split()
            if len(parts) <= 1:
                return show_target_menu(bot, message)

            q = parts[1].strip()

            # username
            if q.startswith("@"):
                row = db.get_user_by_username(q)
                if not row:
                    bot.reply_to(message, "User not found.")
                    return
                defender_id = row[0] if isinstance(row, (list, tuple)) else row
            else:
                # fuzzy name
                matches = db.search_users_by_name(q)
                if not matches:
                    bot.reply_to(message, "No matching users.")
                    return
                if len(matches) == 1:
                    defender_id = matches[0][0]
                else:
                    kb = types.InlineKeyboardMarkup()
                    for uid, uname, disp in matches:
                        label = disp or uname or f"User{uid}"
                        kb.add(types.InlineKeyboardButton(label, callback_data=f"pvp_select:{attacker_id}:{uid}"))
                    bot.reply_to(message, "Multiple matches found:", reply_markup=kb)
                    return

        if defender_id is None:
            bot.reply_to(message, "Target not found.")
            return

        if defender_id == attacker_id:
            bot.reply_to(message, "You cannot attack yourself.")
            return

        if db.is_pvp_shielded(defender_id):
            bot.reply_to(message, "🛡 Target is shielded.")
            return

        # Build stats
        attacker = db.get_user(attacker_id)
        defender = db.get_user(defender_id)

        a_stats = fight_session.build_player_stats_from_user(attacker)
        d_stats = fight_session.build_player_stats_from_user(defender)

        sess = fight_session.manager.create_pvp_session(attacker_id, a_stats, defender_id, d_stats)

        caption = build_caption(sess)
        kb = action_keyboard(attacker_id, sess.auto_mode)

        try:
            safe_send_gif(bot, message.chat.id, "assets/gifs/pvp_intro.gif")
        except:
            pass

        m = bot.send_message(message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)

        # FIXED: store correct message location
        sess._last_msg = {"chat": message.chat.id, "msg": m.message_id}
        fight_session.manager.save_session(sess)

        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_challenges_received")


    # ---------------------------
    # Target menu helper
    # ---------------------------
    def show_target_menu(bot, message):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Reply Attack", callback_data="pvp_menu:reply"))
        kb.add(types.InlineKeyboardButton("Search Name", callback_data="pvp_menu:search_name"))
        kb.add(types.InlineKeyboardButton("Search Username", callback_data="pvp_menu:search_username"))
        kb.add(types.InlineKeyboardButton("PvP Top", callback_data="pvp_menu:top"))
        kb.add(types.InlineKeyboardButton("Cancel", callback_data="pvp_menu:cancel"))
        bot.reply_to(message, "⚔️ How do you want to select your opponent?", reply_markup=kb)


    # ---------------------------
    # Menu callbacks
    # ---------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp_menu"))
    def cb_menu(call):
        act = call.data.split(":")[1]
        if act == "cancel":
            bot.answer_callback_query(call.id, "Cancelled.")
            return
        if act == "reply":
            bot.answer_callback_query(call.id, "Reply to a message and use /attack")
            return
        if act == "search_name":
            bot.answer_callback_query(call.id, "Use: /attack <name>")
            return
        if act == "search_username":
            bot.answer_callback_query(call.id, "Use: /attack @username")
            return
        if act == "top":
            bot.answer_callback_query(call.id, "Use /pvp_top")
            return


    # ---------------------------
    # Name selection callback
    # ---------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp_select"))
    def cb_select(call):
        _, att, dfd = call.data.split(":")
        attacker_id = int(att)
        defender_id = int(dfd)

        attacker = db.get_user(attacker_id)
        defender = db.get_user(defender_id)

        a_stats = fight_session.build_player_stats_from_user(attacker)
        d_stats = fight_session.build_player_stats_from_user(defender)

        sess = fight_session.manager.create_pvp_session(attacker_id, a_stats, defender_id, d_stats)

        caption = build_caption(sess)
        kb = action_keyboard(attacker_id, sess.auto_mode)

        m = bot.send_message(call.message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)

        sess._last_msg = {"chat": call.message.chat.id, "msg": m.message_id}
        fight_session.manager.save_session(sess)

        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_challenges_received")

        bot.answer_callback_query(call.id, "Raid started!")


    # ---------------------------
    # ACTION CALLBACKS
    # ---------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:act"))
    def cb_action(call):
        _, _, action, attacker_id = call.data.split(":")
        attacker_id = int(attacker_id)

        if call.from_user.id != attacker_id:
            bot.answer_callback_query(call.id, "Not your fight.", show_alert=True)
            return

        sess = fight_session.manager.load_session(attacker_id)
        if not sess:
            bot.answer_callback_query(call.id, "Session expired.", show_alert=True)
            return

        chat_id = sess._last_msg["chat"]
        msg_id = sess._last_msg["msg"]

        # FORFEIT
        if action == "forfeit":
            sess.ended = True
            sess.winner = "defender"
            fight_session.manager.save_session(sess)

            summary = finalize_pvp(bot, sess)
            send_pvp_result_card(bot, sess, summary)

            fight_session.manager.end_session(attacker_id)

            try:
                bot.edit_message_text("❌ You forfeited the raid.", chat_id, msg_id)
            except:
                pass

            bot.answer_callback_query(call.id)
            return

        # AUTO MODE
        if action == "auto":
            sess.auto_mode = not sess.auto_mode
            fight_session.manager.save_session(sess)

            if sess.auto_mode:
                for _ in range(4):
                    if sess.ended:
                        break
                    sess.resolve_auto_attacker_turn()
                    fight_session.manager.save_session(sess)

            caption = build_caption(sess)
            kb = action_keyboard(attacker_id, sess.auto_mode)
            safe_edit_message(bot, chat_id, msg_id, caption, kb)

            if sess.ended:
                summary = finalize_pvp(bot, sess)
                send_pvp_result_card(bot, sess, summary)
                fight_session.manager.end_session(attacker_id)

            bot.answer_callback_query(call.id)
            return

        # STANDARD ACTIONS
        sess.resolve_attacker_action(action)
        fight_session.manager.save_session(sess)

        caption = build_caption(sess)
        kb = action_keyboard(attacker_id, sess.auto_mode)
        safe_edit_message(bot, chat_id, msg_id, caption, kb)

        bot.answer_callback_query(call.id)

        if sess.ended:
            summary = finalize_pvp(bot, sess)
            send_pvp_result_card(bot, sess, summary)
            fight_session.manager.end_session(attacker_id)


    # ---------------------------
    # /pvp_top
    # ---------------------------
    @bot.message_handler(commands=["pvp_top"])
    def cmd_pvp_top(message):
        top = db.get_top_pvp(10)
        if not top:
            bot.reply_to(message, "No PvP stats yet.")
            return

        lines = ["🏆 *Top PvP Players:*"]
        for row in top:
            nm = row.get("display_name") or row.get("username") or f"User{row['id']}"
            lines.append(f"{row['rank']}. {nm} — {row['elo']} ELO ({row['wins']}W/{row['losses']}L)")

        bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")


    # ---------------------------
    # /pvp_stats
    # ---------------------------
    @bot.message_handler(commands=["pvp_stats"])
    def cmd_pvp_stats(message):
        uid = message.from_user.id
        stats = db.get_pvp_stats(uid)

        if not stats:
            bot.reply_to(message, "No stats found.")
            return

        shield_until = stats.get("shield_until", 0)
        if shield_until:
            stxt = time.ctime(shield_until)
        else:
            stxt = "None"

        msg = (
            f"📊 *PvP Stats*\n"
            f"ELO: {stats['elo']}\n"
            f"Wins: {stats['wins']}\n"
            f"Losses: {stats['losses']}\n"
            f"Raids started: {stats['started']}\n"
            f"Defended: {stats['defended']}\n"
            f"Challenges received: {stats['challenges']}\n"
            f"🛡 Shield until: {stxt}"
        )

        bot.reply_to(message, msg, parse_mode="Markdown")


# ============================================================
# ACCESS CHECK
# ============================================================
def has_pvp_access(user_id):
    if PVP_FREE_MODE:
        return True
    try:
        return db.is_vip(user_id)
    except:
        return True
