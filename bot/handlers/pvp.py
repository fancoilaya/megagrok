# bot/handlers/pvp.py
# MegaGrok PvP Handler (Full Edition)
# Includes:
#  - Turn-by-turn PvP combat (anti-429)
#  - Target Selection UI
#  - Revenge Button
#  - Recommended Targets (Top 3)
#  - Random 6 Targets
#  - Search + Refresh
#  - ELO, XP, Shield, Display Name Support

import time
import random
from telebot import TeleBot, types

import bot.db as db
import services.fight_session_pvp as fight_session
from services.fight_session_battle import build_player_stats_from_user


# ---------------------------------------------
# CONFIG
# ---------------------------------------------
PVP_FREE_MODE = True
PVP_ELO_K = 32
PVP_MIN_STEAL_PERCENT = 0.07
PVP_MIN_STEAL_ABS = 20
PVP_SHIELD_SECONDS = 3 * 3600
UI_EDIT_THROTTLE_SECONDS = 1.0  # <= 1s between edits


# ---------------------------------------------
# UTILS
# ---------------------------------------------
def get_display_name(user):
    if not user:
        return "Unknown"
    if user.get("display_name"):
        return user["display_name"]
    if user.get("username"):
        return "@" + user["username"]
    return f"User{user.get('user_id')}"


def hp_bar(cur, maxhp, width=20):
    cur = max(0, int(cur))
    maxhp = max(1, int(maxhp))
    ratio = cur / maxhp
    full = int(width * ratio)
    return "▓" * full + "░" * (width - full)


def safe_edit(bot, sess, chat_id, msg_id, text, kb):
    now = time.time()
    last = getattr(sess, "_last_ui_edit", 0)
    if now - last < UI_EDIT_THROTTLE_SECONDS:
        return

    try:
        bot.edit_message_text(text, chat_id, msg_id, parse_mode="Markdown", reply_markup=kb)
        sess._last_ui_edit = time.time()
        fight_session.manager.save_session(sess)
        return

    except Exception as e:
        s = str(e).lower()
        if "message is not modified" in s:
            return
        if "too many requests" in s or "retry after" in s:
            sess._last_ui_edit = time.time()
            fight_session.manager.save_session(sess)
            return

        try:
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)
            sess._last_ui_edit = time.time()
            fight_session.manager.save_session(sess)
        except:
            sess._last_ui_edit = time.time()
            fight_session.manager.save_session(sess)


def calc_xp_steal(def_xp):
    return max(int(def_xp * PVP_MIN_STEAL_PERCENT), PVP_MIN_STEAL_ABS)


# ---------------------------------------------
# TARGET RECOMMENDATION ENGINE
# ---------------------------------------------
def get_recommended_targets(attacker_id, limit=3):

    attacker = db.get_user(attacker_id)
    if not attacker:
        return []

    atk_elo = attacker.get("elo_pvp", 1000)

    rows = db.cursor.execute(
        """
        SELECT user_id, display_name, username, elo_pvp, xp_total,
               pvp_fights_started, pvp_challenges_received
        FROM users
        WHERE user_id != ?
        """,
        (attacker_id,)
    ).fetchall()

    scored = []
    for uid, disp, uname, elo, xp, started, received in rows:

        if db.is_pvp_shielded(uid):
            continue

        if elo is None:
            elo = 1000

        elo_diff = abs(elo - atk_elo)
        activity = (started or 0) + (received or 0)
        reward = xp or 0

        # Weighted Score
        score = (
            (2000 - elo_diff) +
            (activity * 25) +
            (reward * 0.02)
        )

        name = disp or (f"@{uname}" if uname else f"User{uid}")
        scored.append((score, uid, name, elo))

    scored.sort(reverse=True)
    return scored[:limit]


# ---------------------------------------------
# BATTLE UI BUILDERS
# ---------------------------------------------
def build_caption(sess):
    a = sess.pvp_attacker or {}
    d = sess.pvp_defender or {}

    an = get_display_name(a)
    dn = get_display_name(d)

    a_max = a.get("current_hp", a.get("hp", 100))
    d_max = d.get("current_hp", d.get("hp", 100))

    lines = [
        f"⚔️ *PvP Raid:* {an} vs {dn}",
        "",
        f"{an}: {hp_bar(sess.attacker_hp, a_max, 20)} {sess.attacker_hp}/{a_max}",
        f"{dn}: {hp_bar(sess.defender_hp, d_max, 20)} {sess.defender_hp}/{d_max}",
        "",
        f"Turn: {sess.turn}",
        "",
    ]

    if sess.events:
        lines.append("*Recent actions:*")
        for ev in sess.events[:6]:
            actor = an if ev["actor"] == "attacker" else dn
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
        types.InlineKeyboardButton("▶ Auto", callback_data=f"pvp:act:auto:{uid}"),
        types.InlineKeyboardButton("❌ Forfeit", callback_data=f"pvp:act:forfeit:{uid}"),
    )
    return kb


# ---------------------------------------------
# RESULT CARD
# ---------------------------------------------
def finalize_pvp(bot, sess):

    atk_id = sess.attacker_id
    dfd_id = sess.defender_id

    attacker = db.get_user(atk_id) or {}
    defender = db.get_user(dfd_id) or {}

    atk_xp = attacker.get("xp_total", 0)
    dfd_xp = defender.get("xp_total", 0)

    attacker_won = sess.winner == "attacker"
    xp_stolen = 0

    best = {"attacker": {"damage": 0}, "defender": {"damage": 0}}

    for ev in sess.events:
        if ev["action"] == "attack":
            if ev["actor"] == "attacker" and ev["damage"] > best["attacker"]["damage"]:
                best["attacker"] = {"damage": ev["damage"], "turn": ev["turn"]}
            if ev["actor"] == "defender" and ev["damage"] > best["defender"]["damage"]:
                best["defender"] = {"damage": ev["damage"], "turn": ev["turn"]}

    if attacker_won:
        xp_stolen = max(int(dfd_xp * PVP_MIN_STEAL_PERCENT), PVP_MIN_STEAL_ABS)

        try:
            db.cursor.execute(
                "UPDATE users SET xp_total = xp_total - ?, xp_current = xp_current - ? WHERE user_id = ?",
                (xp_stolen, xp_stolen, dfd_id)
            )
            db.cursor.execute(
                "UPDATE users SET xp_total = xp_total + ?, xp_current = xp_current + ? WHERE user_id = ?",
                (xp_stolen, xp_stolen, atk_id)
            )
            db.conn.commit()
        except:
            pass

        db.increment_pvp_field(atk_id, "pvp_wins")
        db.increment_pvp_field(dfd_id, "pvp_losses")

        # Apply Revenge Marker
        try:
            db.set_last_attacker(dfd_id, atk_id)
        except:
            pass

        # Apply Shield
        try:
            db.set_pvp_shield(dfd_id, int(time.time()) + PVP_SHIELD_SECONDS)
        except:
            pass

    else:
        penalty = max(1, int(atk_xp * 0.05))
        try:
            db.cursor.execute(
                "UPDATE users SET xp_total = xp_total - ?, xp_current = xp_current - ? WHERE user_id = ?",
                (penalty, penalty, atk_id)
            )
            db.cursor.execute(
                "UPDATE users SET xp_total = xp_total + ?, xp_current = xp_current + ? WHERE user_id = ?",
                (penalty, penalty, dfd_id)
            )
            db.conn.commit()
        except:
            pass

        db.increment_pvp_field(atk_id, "pvp_losses")
        db.increment_pvp_field(dfd_id, "pvp_wins")

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

    try:
        db.update_elo(atk_id, new_atk)
        db.update_elo(dfd_id, new_dfd)
    except:
        pass

    return {
        "xp_stolen": xp_stolen,
        "elo_change": new_atk - atk_elo,
        "best_hits": best,
        "attacker_hp": sess.attacker_hp,
        "defender_hp": sess.defender_hp,
    }


def send_result_card(bot, sess, summary):
    attacker = db.get_user(sess.attacker_id) or {}
    defender = db.get_user(sess.defender_id) or {}

    an = get_display_name(attacker)
    dn = get_display_name(defender)

    chat_id = sess._last_msg.get("chat", sess.attacker_id)

    title = "🏆 *VICTORY!*" if sess.winner == "attacker" else "💀 *DEFEAT*"
    subtitle = f"You defeated *{dn}*" if sess.winner == "attacker" else f"You were repelled by *{dn}*"

    xp_line = (
        f"🎁 *XP Stolen:* +{summary['xp_stolen']}"
        if sess.winner == "attacker"
        else f"📉 *XP Lost:* -{summary['xp_stolen']}"
    )
    elo_line = f"🏅 ELO Change: {summary['elo_change']:+d}"

    card = [
        title,
        subtitle,
        "",
        f"{xp_line}    {elo_line}",
        "",
        f"❤️ {an}: {summary['attacker_hp']}",
        f"💀 {dn}: {summary['defender_hp']}",
        "",
        "*Highlights:*",
    ]

    if summary["best_hits"]["attacker"]["damage"]:
        card.append(f"💥 Your best hit: {summary['best_hits']['attacker']['damage']} dmg")
    if summary["best_hits"]["defender"]["damage"]:
        card.append(f"💢 Enemy best hit: {summary['best_hits']['defender']['damage']} dmg")

    bot.send_message(chat_id, "\n".join(card), parse_mode="Markdown")


# --------------------------------------------------------------
# TARGET SELECTION UI
# --------------------------------------------------------------
def show_random_targets(bot, chat_id, attacker_id):

    kb = types.InlineKeyboardMarkup()

    # --------------------------------
    # REVENGE Button
    # --------------------------------
    last_att = db.get_last_attacker(attacker_id)
    if last_att:
        user = db.get_user(last_att)
        if user and not db.is_pvp_shielded(last_att):
            name = get_display_name(user)
            elo = user.get("elo_pvp", 1000)
            kb.add(
                types.InlineKeyboardButton(
                    f"🔥 Revenge: {name} — {elo} ELO",
                    callback_data=f"pvp_pick:{attacker_id}:{last_att}"
                )
            )

    # --------------------------------
    # TOP 3 RECOMMENDED TARGETS
    # --------------------------------
    recommended = get_recommended_targets(attacker_id, limit=3)
    if recommended:
        kb.add(types.InlineKeyboardButton("🔥 Recommended Targets:", callback_data="noop"))

        for score, uid, name, elo in recommended:
            kb.add(
                types.InlineKeyboardButton(
                    f"{name} — {elo} ELO",
                    callback_data=f"pvp_pick:{attacker_id}:{uid}"
                )
            )

        kb.add(types.InlineKeyboardButton(" ", callback_data="noop"))

    # --------------------------------
    # RANDOM 6 TARGETS
    # --------------------------------
    rows = db.cursor.execute(
        """
        SELECT user_id, display_name, username, elo_pvp
        FROM users
        WHERE user_id != ?
        ORDER BY RANDOM()
        LIMIT 50
        """,
        (attacker_id,)
    ).fetchall()

    candidates = [
        row for row in rows
        if not db.is_pvp_shielded(row[0])
    ][:6]

    if candidates:
        kb.add(types.InlineKeyboardButton("🎯 Targets:", callback_data="noop"))

    for uid, disp, uname, elo in candidates:
        name = disp or (f"@{uname}" if uname else f"User{uid}")
        kb.add(
            types.InlineKeyboardButton(
                f"{name} — {elo} ELO",
                callback_data=f"pvp_pick:{attacker_id}:{uid}"
            )
        )

    kb.add(
        types.InlineKeyboardButton("🔄 Refresh", callback_data=f"pvp_refresh:{attacker_id}"),
        types.InlineKeyboardButton("🔍 Search", callback_data=f"pvp_search:{attacker_id}")
    )

    bot.send_message(
        chat_id,
        "⚔️ *Choose a player to raid:*",
        parse_mode="Markdown",
        reply_markup=kb
    )


# --------------------------------------------------------------
# STANDARD ATTACK (fallback)
# --------------------------------------------------------------
def process_standard_attack(bot, message):
    """
    Your original /attack logic goes here.
    Used when:
    - user replies to someone
    - user types /attack <name>
    - recommended target button
    - revenge button
    """

    attacker_id = message.from_user.id

    # Determine defender
    parts = message.text.split()
    defender_id = None

    # From reply
    if message.reply_to_message:
        defender_id = message.reply_to_message.from_user.id

    # From text
    elif len(parts) > 1:
        q = parts[1]
        if q.startswith("@"):
            row = db.get_user_by_username(q)
            if row:
                defender_id = row[0] if isinstance(row, (list, tuple)) else row
        else:
            matches = db.search_users_by_name(q)
            if not matches:
                return bot.reply_to(message, "No matching users.")
            if len(matches) == 1:
                defender_id = matches[0][0]
            else:
                kb = types.InlineKeyboardMarkup()
                for uid, uname, disp in matches:
                    label = disp or uname or f"User{uid}"
                    kb.add(types.InlineKeyboardButton(
                        label, callback_data=f"pvp_pick:{attacker_id}:{uid}"
                    ))
                bot.reply_to(message, "Multiple matches:", reply_markup=kb)
                return

    if defender_id is None:
        return bot.reply_to(message, "Couldn't identify target.")

    if defender_id == attacker_id:
        return bot.reply_to(message, "You cannot attack yourself.")

    if db.is_pvp_shielded(defender_id):
        return bot.reply_to(message, "🛡 User is shielded.")

    attacker = db.get_user(attacker_id) or {}
    defender = db.get_user(defender_id) or {}

    a_stats = build_player_stats_from_user(attacker)
    d_stats = build_player_stats_from_user(defender)

    sess = fight_session.manager.create_pvp_session(attacker_id, a_stats, defender_id, d_stats)

    caption = build_caption(sess)
    kb = action_keyboard(sess)

    m = bot.send_message(
        message.chat.id,
        caption,
        parse_mode="Markdown",
        reply_markup=kb
    )

    sess._last_msg = {"chat": message.chat.id, "msg": m.message_id}
    sess._last_ui_edit = 0
    fight_session.manager.save_session(sess)

    db.increment_pvp_field(attacker_id, "pvp_fights_started")
    db.increment_pvp_field(defender_id, "pvp_challenges_received")


# --------------------------------------------------------------
# CALLBACKS
# --------------------------------------------------------------
def setup(bot: TeleBot):

    globals()["bot_instance_for_pvp"] = bot

    # --------------------------
    # Main command
    # --------------------------
    @bot.message_handler(commands=["attack"])
    def cmd_attack(message):
        attacker_id = message.from_user.id

        if not PVP_FREE_MODE and not db.is_vip(attacker_id):
            return bot.reply_to(message, "🔒 PvP requires VIP.")

        # If reply or argument → standard flow
        parts = message.text.split()
        if message.reply_to_message or len(parts) > 1:
            return process_standard_attack(bot, message)

        # Otherwise → show target menu
        return show_random_targets(bot, message.chat.id, attacker_id)

    # --------------------------
    # Pick a target from UI
    # --------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp_pick"))
    def cb_pvp_pick(call):
        _, att, dfd = call.data.split(":")
        attacker_id = int(att)
        defender_id = int(dfd)

        if call.from_user.id != attacker_id:
            return bot.answer_callback_query(call.id, "Not your menu.", show_alert=True)

        msg = call.message
        msg.text = f"/attack {defender_id}"
        bot.answer_callback_query(call.id)
        return process_standard_attack(bot, msg)

    # --------------------------
    # Refresh the list
    # --------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp_refresh"))
    def cb_pvp_refresh(call):
        _, att = call.data.split(":")
        attacker_id = int(att)

        if call.from_user.id != attacker_id:
            return bot.answer_callback_query(call.id, "Not your menu.", show_alert=True)

        bot.answer_callback_query(call.id)
        return show_random_targets(bot, call.message.chat.id, attacker_id)

    # --------------------------
    # Search Helper
    # --------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp_search"))
    def cb_pvp_search(call):
        _, att = call.data.split(":")
        attacker_id = int(att)

        if call.from_user.id != attacker_id:
            return bot.answer_callback_query(call.id, "Not your menu.", show_alert=True)

        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "🔍 *Search PvP target:* Use `/attack <name>` or mention.\nExample: `/attack grok`",
            parse_mode="Markdown"
        )

    # --------------------------
    # Combat actions
    # --------------------------
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
            return bot.answer_callback_query(call.id, "Session missing.")

        chat_id = sess._last_msg["chat"]
        msg_id = sess._last_msg["msg"]

        # Forfeit
        if action == "forfeit":
            sess.ended = True
            sess.winner = "defender"
            fight_session.manager.save_session(sess)

            summary = finalize_pvp(bot, sess)
            send_result_card(bot, sess, summary)

            fight_session.manager.end_session(attacker_id)
            return bot.answer_callback_query(call.id, "You forfeited.")

        # AUTO (single turn)
        if action == "auto":
            sess.resolve_auto_attacker_turn()
            fight_session.manager.save_session(sess)

            if sess.ended:
                summary = finalize_pvp(bot, sess)
                send_result_card(bot, sess, summary)
                fight_session.manager.end_session(attacker_id)
            else:
                safe_edit(bot, sess, chat_id, msg_id, build_caption(sess), action_keyboard(sess))

            return bot.answer_callback_query(call.id)

        # Normal action
        sess.resolve_attacker_action(action)
        fight_session.manager.save_session(sess)

        if sess.ended:
            summary = finalize_pvp(bot, sess)
            send_result_card(bot, sess, summary)
            fight_session.manager.end_session(attacker_id)
        else:
            safe_edit(bot, sess, chat_id, msg_id, build_caption(sess), action_keyboard(sess))

        bot.answer_callback_query(call.id)
