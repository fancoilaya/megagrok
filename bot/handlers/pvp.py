# bot/handlers/pvp.py
# MegaGrok PvP Raid System (Final Corrected Version)
# Works with: services/fight_session_pvp.py + services/fight_session_battle (stat builder)
# Fully separated from PvE battle system.

import time
import random
from telebot import TeleBot, types

# ✔ PvP engine
import services.fight_session_pvp as fight_session

# ✔ Use SHARED stat builder from PvE engine (Option B)
from services.fight_session_battle import build_player_stats_from_user

# Database
import bot.db as db

try:
    from bot.utils import safe_send_gif
except:
    def safe_send_gif(bot, chat_id, x): pass


# ============================================================
# CONFIG
# ============================================================

PVP_FREE_MODE = True  # placeholder, replace with VIP toggle later
PVP_ELO_K = 32
PVP_MIN_STEAL_PERCENT = 0.07
PVP_MIN_STEAL_ABS = 20
RESULT_BAR_WIDTH = 18
PVP_SHIELD_SECONDS = 3 * 3600


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


def hp_bar(cur, maxhp, width=20):
    cur = max(0, int(cur))
    maxhp = max(1, int(maxhp))
    ratio = cur / maxhp
    full = int(width * ratio)
    return "▓" * full + "░" * (width - full)


def safe_edit(bot, chat_id, msg_id, text, kb):
    try:
        bot.edit_message_text(
            text,
            chat_id,
            msg_id,
            parse_mode="Markdown",
            reply_markup=kb,
        )
    except Exception as e:
        if "not modified" in str(e).lower():
            return
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)


def calc_xp_steal(def_xp):
    return max(int(def_xp * PVP_MIN_STEAL_PERCENT), PVP_MIN_STEAL_ABS)


# ============================================================
# CAPTION BUILDER
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
        f"{a_name}: {hp_bar(sess.attacker_hp, a_max, 20)} {sess.attacker_hp}/{a_max}",
        f"{d_name}: {hp_bar(sess.defender_hp, d_max, 20)} {sess.defender_hp}/{d_max}",
        "",
        f"Turn: {sess.turn}",
        ""
    ]

    if sess.events:
        lines.append("*Recent actions:*")
        for ev in sess.events[:6]:
            actor = a_name if ev["actor"] == "attacker" else d_name
            if ev["action"] == "attack":
                lines.append(f"• {actor} dealt {ev['damage']} dmg {ev.get('note','')}")
            else:
                lines.append(f"• {actor}: {ev['action']} {ev.get('note','')}")

    return "\n".join(lines)


def action_keyboard(sess):
    uid = sess.attacker_id
    kb = types.InlineKeyboardMarkup()

    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=f"pvp:act:attack:{uid}"),
        types.InlineKeyboardButton("🛡 Block", callback_data=f"pvp:act:block:{uid}"),
    )
    kb.add(
        types.InlineKeyboardButton("💨 Dodge", callback_data=f"pvp:act:dodge:{uid}"),
        types.InlineKeyboardButton("⚡ Charge", callback_data=f"pvp:act:charge:{uid}"),
    )
    kb.add(
        types.InlineKeyboardButton(
            "▶ Auto" if not sess.auto_mode else "⏸ Auto",
            callback_data=f"pvp:act:auto:{uid}"
        ),
        types.InlineKeyboardButton("❌ Forfeit", callback_data=f"pvp:act:forfeit:{uid}")
    )

    return kb


# ============================================================
# FINALIZE / RESULTS
# ============================================================

def finalize_pvp(bot, sess):
    atk_id = sess.attacker_id
    dfd_id = sess.defender_id

    attacker = db.get_user(atk_id)
    defender = db.get_user(dfd_id)

    atk_xp = attacker.get("xp_total", 0)
    dfd_xp = defender.get("xp_total", 0)

    attacker_won = sess.winner == "attacker"

    xp_stolen = 0

    # Highlights
    best = {"attacker": {"damage": 0}, "defender": {"damage": 0}}
    for ev in sess.events:
        if ev["action"] == "attack" and ev["damage"] > 0:
            if ev["actor"] == "attacker" and ev["damage"] > best["attacker"]["damage"]:
                best["attacker"] = {"damage": ev["damage"], "turn": ev["turn"]}
            if ev["actor"] == "defender" and ev["damage"] > best["defender"]["damage"]:
                best["defender"] = {"damage": ev["damage"], "turn": ev["turn"]}

    if attacker_won:
        xp_stolen = calc_xp_steal(dfd_xp)

        db.cursor.execute(
            "UPDATE users SET xp_total=xp_total-?, xp_current=xp_current-? WHERE user_id=?",
            (xp_stolen, xp_stolen, dfd_id)
        )
        db.cursor.execute(
            "UPDATE users SET xp_total=xp_total+?, xp_current=xp_current+? WHERE user_id=?",
            (xp_stolen, xp_stolen, atk_id)
        )

        db.increment_pvp_field(atk_id, "pvp_wins")
        db.increment_pvp_field(dfd_id, "pvp_losses")

        db.set_pvp_shield(dfd_id, int(time.time()) + PVP_SHIELD_SECONDS)

    else:
        penalty = max(1, int(atk_xp * 0.05))

        db.cursor.execute(
            "UPDATE users SET xp_total=xp_total-?, xp_current=xp_current-? WHERE user_id=?",
            (penalty, penalty, atk_id)
        )
        db.cursor.execute(
            "UPDATE users SET xp_total=xp_total+?, xp_current=xp_current+? WHERE user_id=?",
            (penalty, penalty, dfd_id)
        )

        db.increment_pvp_field(atk_id, "pvp_losses")
        db.increment_pvp_field(dfd_id, "pvp_wins")

    db.conn.commit()

    # ELO update
    atk_elo = attacker.get("elo_pvp", 1000)
    dfd_elo = defender.get("elo_pvp", 1000)

    def expected(a, b):
        return 1 / (1 + 10 ** ((b - a) / 400))

    E = expected(atk_elo, dfd_elo)
    if attacker_won:
        new_atk = atk_elo + int(PVP_ELO_K * (1 - E))
        new_dfd = dfd_elo - int(PVP_ELO_K * (1 - E))
    else:
        new_atk = atk_elo + int(PVP_ELO_K * (0 - E))
        new_dfd = dfd_elo - int(PVP_ELO_K * (0 - E))

    db.update_elo(atk_id, new_atk)
    db.update_elo(dfd_id, new_dfd)

    # Notify defender
    atk_name = get_display_name(attacker)
    if attacker_won:
        notify_msg = (
            f"⚠️ You were raided by *{atk_name}*!\n"
            f"XP stolen: {xp_stolen}\n"
            f"ELO change: {new_dfd - dfd_elo}\n"
            f"🛡 Shield active."
        )
    else:
        notify_msg = (
            f"🛡 Your AI defender repelled *{atk_name}*!\n"
            f"ELO change: {new_dfd - dfd_elo}"
        )

    _notify(bot, dfd_id, notify_msg)

    return {
        "xp_stolen": xp_stolen,
        "elo_change": new_atk - atk_elo,
        "best_hits": best,
        "attacker_hp": sess.attacker_hp,
        "defender_hp": sess.defender_hp,
    }


def _notify(bot, uid, text):
    try:
        bot.send_message(uid, text, parse_mode="Markdown")
    except:
        pass


# ============================================================
# RESULT CARD
# ============================================================

def send_result_card(bot, sess, summary):
    attacker = db.get_user(sess.attacker_id)
    defender = db.get_user(sess.defender_id)

    a_name = get_display_name(attacker)
    d_name = get_display_name(defender)

    msg_info = sess._last_msg or {}
    chat_id = msg_info.get("chat", sess.attacker_id)

    a_hp = summary["attacker_hp"]
    d_hp = summary["defender_hp"]

    a_max = attacker.get("current_hp", attacker.get("hp", 100))
    d_max = defender.get("current_hp", defender.get("hp", 100))

    best = summary["best_hits"]

    win = sess.winner == "attacker"

    title = "🏆 *VICTORY!*" if win else "💀 *DEFEAT*"
    subtitle = f"You defeated *{d_name}*" if win else f"You were repelled by *{d_name}*"

    xp_line = (
        f"🎁 *XP Stolen:* +{summary['xp_stolen']}"
        if win else
        f"📉 *XP Lost:* -{summary['xp_stolen']}"
    )
    elo_line = f"🏅 ELO Change: {summary['elo_change']:+d}"

    card = [
        title,
        subtitle,
        "",
        f"{xp_line}    {elo_line}",
        "",
        f"❤️ {a_name}: {hp_bar(a_hp, a_max, 12)}  {a_hp}/{a_max}",
        f"💀 {d_name}: {hp_bar(d_hp, d_max, 12)}  {d_hp}/{d_max}",
        "",
        "*Highlights:*",
    ]

    if best["attacker"]["damage"]:
        card.append(f"💥 Your best hit: {best['attacker']['damage']} dmg")
    if best["defender"]["damage"]:
        card.append(f"💢 Enemy best hit: {best['defender']['damage']} dmg")

    bot.send_message(chat_id, "\n".join(card), parse_mode="Markdown")


# ============================================================
# PVP ACCESS
# ============================================================

def has_pvp_access(uid):
    if PVP_FREE_MODE:
        return True
    try:
        return db.is_vip(uid)
    except:
        return True


# ============================================================
# MAIN SETUP
# ============================================================

def setup(bot: TeleBot):

    # ------------------------------------------------------------
    # /attack
    # ------------------------------------------------------------
    @bot.message_handler(commands=["attack"])
    def cmd_attack(message):
        attacker_id = message.from_user.id

        if not has_pvp_access(attacker_id):
            bot.reply_to(message, "🔒 PvP requires VIP.")
            return

        defender_id = None

        # reply target
        if message.reply_to_message:
            defender_id = message.reply_to_message.from_user.id

        else:
            parts = message.text.split()
            if len(parts) == 1:
                return bot.reply_to(
                    message,
                    "Reply to someone or use `/attack <name>`",
                    parse_mode="Markdown",
                )

            q = parts[1].strip()

            if q.startswith("@"):
                row = db.get_user_by_username(q)
                if not row:
                    bot.reply_to(message, "User not found.")
                    return
                defender_id = row[0] if isinstance(row, (list, tuple)) else row
            else:
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
                    bot.reply_to(message, "Multiple matches:", reply_markup=kb)
                    return

        if defender_id is None:
            bot.reply_to(message, "Could not identify target.")
            return

        if defender_id == attacker_id:
            bot.reply_to(message, "You cannot attack yourself.")
            return

        if db.is_pvp_shielded(defender_id):
            bot.reply_to(message, "🛡 User is shielded.")
            return

        attacker = db.get_user(attacker_id)
        defender = db.get_user(defender_id)

        a_stats = build_player_stats_from_user(attacker)
        d_stats = build_player_stats_from_user(defender)

        sess = fight_session.manager.create_pvp_session(attacker_id, a_stats, defender_id, d_stats)

        caption = build_caption(sess)
        kb = action_keyboard(sess)

        m = bot.send_message(message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)
        sess._last_msg = {"chat": message.chat.id, "msg": m.message_id}
        fight_session.manager.save_session(sess)

        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_challenges_received")

    # ------------------------------------------------------------
    # name selection callback
    # ------------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp_select"))
    def cb_pvp_select(call):
        _, att, dfd = call.data.split(":")
        attacker_id = int(att)
        defender_id = int(dfd)

        attacker = db.get_user(attacker_id)
        defender = db.get_user(defender_id)

        a_stats = build_player_stats_from_user(attacker)
        d_stats = build_player_stats_from_user(defender)

        sess = fight_session.manager.create_pvp_session(attacker_id, a_stats, defender_id, d_stats)

        caption = build_caption(sess)
        kb = action_keyboard(sess)

        m = bot.send_message(call.message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)
        sess._last_msg = {"chat": call.message.chat.id, "msg": m.message_id}
        fight_session.manager.save_session(sess)

        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_challenges_received")

        bot.answer_callback_query(call.id, "Raid started!")

    # ------------------------------------------------------------
    # action callback
    # ------------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:act"))
    def cb_pvp_action(call):
        try:
            _, _, action, attacker_str = call.data.split(":")
            attacker_id = int(attacker_str)
        except:
            return bot.answer_callback_query(call.id, "Invalid.")

        if call.from_user.id != attacker_id:
            return bot.answer_callback_query(call.id, "Not your raid.", show_alert=True)

        sess = fight_session.manager.load_session(attacker_id)
        if not sess:
            return bot.answer_callback_query(call.id, "Session not found.", show_alert=True)

        chat_id = sess._last_msg["chat"]
        msg_id = sess._last_msg["msg"]

        # FORFEIT
        if action == "forfeit":
            sess.ended = True
            sess.winner = "defender"
            fight_session.manager.save_session(sess)

            summary = finalize_pvp(bot, sess)
            send_result_card(bot, sess, summary)

            fight_session.manager.end_session(attacker_id)
            bot.answer_callback_query(call.id, "You forfeited.")
            return

        # AUTO
        if action == "auto":
            sess.auto_mode = not sess.auto_mode
            fight_session.manager.save_session(sess)

            if sess.auto_mode:
                for _ in range(4):
                    if sess.ended:
                        break
                    sess.resolve_auto_attacker_turn()
                    fight_session.manager.save_session(sess)

            if sess.ended:
                summary = finalize_pvp(bot, sess)
                send_result_card(bot, sess, summary)
                fight_session.manager.end_session(attacker_id)
            else:
                caption = build_caption(sess)
                kb = action_keyboard(sess)
                safe_edit(bot, chat_id, msg_id, caption, kb)

            bot.answer_callback_query(call.id)
            return

        # STANDARD ACTION
        sess.resolve_attacker_action(action)
        fight_session.manager.save_session(sess)

        if sess.ended:
            summary = finalize_pvp(bot, sess)
            send_result_card(bot, sess, summary)
            fight_session.manager.end_session(attacker_id)
        else:
            caption = build_caption(sess)
            kb = action_keyboard(sess)
            safe_edit(bot, chat_id, msg_id, caption, kb)

        bot.answer_callback_query(call.id)
