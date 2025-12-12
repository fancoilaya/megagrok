# bot/handlers/pvp.py — FINAL CLEAN VERSION WITH SESSION_ID + FULL USER IDENTITY + SAFE UI
# Combines your original PvP logic with:
# - Session ID isolation (prevents interference)
# - Backwards compatibility (old buttons still work)
# - Correct attacker/defender identity injection (fixes UserNone vs UserNone)
# - Clean UI updates & safe-edit throttling
# - Original XP/ELO/Shield logic preserved
# - Evolution-based stats (from fight_session_battle builder)
#
# Original file reference: pvp.py (uploaded by user) :contentReference[oaicite:0]{index=0}

import time
import random
from telebot import TeleBot, types

import services.fight_session_pvp as fight_session
from services.fight_session_battle import build_player_stats_from_user
import bot.db as db

# --- CONFIG ---
PVP_FREE_MODE = True
PVP_ELO_K = 32
PVP_MIN_STEAL_PERCENT = 0.07
PVP_MIN_STEAL_ABS = 20
PVP_SHIELD_SECONDS = 3 * 3600
UI_EDIT_THROTTLE_SECONDS = 1.0


# ============================================================
# GENERAL HELPERS
# ============================================================

def get_display_name(user):
    """Return user's display_name or username or fallback."""
    if not user:
        return "Unknown"
    if user.get("display_name"):
        return user["display_name"]
    if user.get("username"):
        return "@" + user["username"]
    return f"User{user.get('user_id')}"


def hp_bar(cur, maxhp, width=20):
    """Pretty HP bar."""
    cur = max(0, int(cur))
    maxhp = max(1, int(maxhp))
    filled = int((cur / maxhp) * width)
    return "▓" * filled + "░" * (width - filled)


def calc_xp_steal(def_xp):
    return max(int(def_xp * PVP_MIN_STEAL_PERCENT), PVP_MIN_STEAL_ABS)


def has_pvp_access(uid):
    if PVP_FREE_MODE:
        return True
    try:
        return db.is_vip(uid)
    except:
        return True


# ============================================================
# SAFE EDIT WRAPPER (KEEPS YOUR ANTI-RATE-LIMIT BEHAVIOR)
# ============================================================

def safe_edit(bot, sess, chat_id, msg_id, text, kb):
    now = time.time()
    last = getattr(sess, "_last_ui_edit", 0)
    if now - last < UI_EDIT_THROTTLE_SECONDS:
        return

    try:
        bot.edit_message_text(text, chat_id, msg_id,
                              parse_mode="Markdown",
                              reply_markup=kb)
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
            bot.send_message(chat_id, text,
                             parse_mode="Markdown",
                             reply_markup=kb)
            sess._last_ui_edit = time.time()
            fight_session.manager.save_session(sess)
        except:
            sess._last_ui_edit = time.time()
            fight_session.manager.save_session(sess)


# ============================================================
# SESSION ACCESS NORMALIZERS (COMPATIBLE WITH OLD + NEW FORMATS)
# ============================================================

def _sess_attacker(sess):
    return getattr(sess, "attacker", None) or getattr(sess, "pvp_attacker", {}) or {}


def _sess_defender(sess):
    return getattr(sess, "defender", None) or getattr(sess, "pvp_defender", {}) or {}


def _sess_attacker_id(sess):
    return getattr(sess, "attacker_id", getattr(sess, "pvp_attacker_id", None))


def _sess_defender_id(sess):
    return getattr(sess, "defender_id", getattr(sess, "pvp_defender_id", None))


def _sess_session_id(sess):
    return getattr(sess, "session_id", None)


def _sess_attacker_hp(sess):
    if hasattr(sess, "attacker_hp"):
        return sess.attacker_hp
    atk = _sess_attacker(sess)
    return atk.get("hp", 100)


def _sess_defender_hp(sess):
    if hasattr(sess, "defender_hp"):
        return sess.defender_hp
    d = _sess_defender(sess)
    return d.get("hp", 100)


def _sess_set_attacker_hp(sess, val):
    if hasattr(sess, "attacker_hp"):
        sess.attacker_hp = val
        return
    atk = _sess_attacker(sess)
    atk["hp"] = val


def _sess_set_defender_hp(sess, val):
    if hasattr(sess, "defender_hp"):
        sess.defender_hp = val
        return
    d = _sess_defender(sess)
    d["hp"] = val


# ============================================================
# CAPTION + KEYBOARD BUILDERS
# ============================================================

def build_caption(sess):
    a = _sess_attacker(sess)
    d = _sess_defender(sess)

    a_name = get_display_name(a)
    d_name = get_display_name(d)

    a_max = a.get("hp", a.get("current_hp", 100))
    d_max = d.get("hp", d.get("current_hp", 100))

    a_hp = _sess_attacker_hp(sess)
    d_hp = _sess_defender_hp(sess)

    lines = [
        f"⚔️ *PvP Raid:* {a_name} vs {d_name}",
        "",
        f"{a_name}: {hp_bar(a_hp, a_max, 20)} {a_hp}/{a_max}",
        f"{d_name}: {hp_bar(d_hp, d_max, 20)} {d_hp}/{d_max}",
        "",
        f"Turn: {getattr(sess, 'turn', 1)}",
        "",
    ]

    if getattr(sess, "events", None):
        lines.append("*Recent actions:*")
        for ev in sess.events[:4]:
            actor = a_name if ev["actor"] == "attacker" else d_name
            if ev["action"] == "attack":
                lines.append(f"• {actor} dealt {ev['damage']} dmg {ev.get('note','')}")
            else:
                lines.append(f"• {actor}: {ev['action']}")

    return "\n".join(lines)


def _action_cb(action, token):
    return f"pvp:act:{action}:{token}"


def action_keyboard(sess):
    sid = _sess_session_id(sess)
    if sid:
        token = sid
    else:
        token = str(_sess_attacker_id(sess) or "")

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=_action_cb("attack", token)),
        types.InlineKeyboardButton("🛡 Block", callback_data=_action_cb("block", token)),
    )
    kb.add(
        types.InlineKeyboardButton("💨 Dodge", callback_data=_action_cb("dodge", token)),
        types.InlineKeyboardButton("⚡ Charge", callback_data=_action_cb("charge", token)),
    )
    kb.add(
        types.InlineKeyboardButton("▶ Auto", callback_data=_action_cb("auto", token)),
        types.InlineKeyboardButton("❌ Forfeit", callback_data=_action_cb("forfeit", token)),
    )
    return kb


# ============================================================
# FINALIZATION LOGIC — ELO, XP STEAL, SHIELD, RESULTS
# ============================================================

def finalize_pvp(bot, sess):
    atk_id = _sess_attacker_id(sess)
    dfd_id = _sess_defender_id(sess)

    attacker = db.get_user(atk_id) or {}
    defender = db.get_user(dfd_id) or {}

    atk_xp = attacker.get("xp_total", 0)
    dfd_xp = defender.get("xp_total", 0)

    attacker_won = (sess.winner == "attacker")

    # Best hits
    best = {"attacker": {"damage": 0}, "defender": {"damage": 0}}
    for ev in getattr(sess, "events", []):
        if ev["action"] == "attack":
            dmg = ev.get("damage", 0)
            if ev["actor"] == "attacker" and dmg > best["attacker"]["damage"]:
                best["attacker"] = {"damage": dmg}
            if ev["actor"] == "defender" and dmg > best["defender"]["damage"]:
                best["defender"] = {"damage": dmg}

    xp_stolen = 0

    if attacker_won:
        xp_stolen = calc_xp_steal(dfd_xp)

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

        try:
            db.increment_pvp_field(atk_id, "pvp_wins")
            db.increment_pvp_field(dfd_id, "pvp_losses")
        except:
            pass

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

        try:
            db.increment_pvp_field(atk_id, "pvp_losses")
            db.increment_pvp_field(dfd_id, "pvp_wins")
        except:
            pass

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

    # Defender Notification (best effort)
    atk_name = get_display_name(attacker)
    try:
        notify = bot_instance_for_pvp
    except:
        notify = None

    if notify:
        if attacker_won:
            msg = f"⚠️ You were raided by *{atk_name}*!\nXP stolen: {xp_stolen}"
        else:
            msg = f"🛡 Your AI defender repelled *{atk_name}*!"

        try:
            notify.send_message(dfd_id, msg, parse_mode="Markdown")
        except:
            pass

    return {
        "xp_stolen": xp_stolen,
        "elo_change": new_atk - atk_elo,
        "best_hits": best,
        "attacker_hp": _sess_attacker_hp(sess),
        "defender_hp": _sess_defender_hp(sess),
    }


def send_result_card(bot, sess, summary):
    attacker = db.get_user(_sess_attacker_id(sess)) or {}
    defender = db.get_user(_sess_defender_id(sess)) or {}

    a_name = get_display_name(attacker)
    d_name = get_display_name(defender)

    msg_info = getattr(sess, "_last_msg", {}) or {}
    chat = msg_info.get("chat", _sess_attacker_id(sess))

    a_hp = summary["attacker_hp"]
    d_hp = summary["defender_hp"]

    a_max = attacker.get("current_hp", attacker.get("hp", 100))
    d_max = defender.get("current_hp", defender.get("hp", 100))

    win = (sess.winner == "attacker")

    card = [
        "🏆 *VICTORY!*" if win else "💀 *DEFEAT*",
        f"You defeated *{d_name}*" if win else f"You were repelled by *{d_name}*",
        "",
        f"🎁 XP Stolen: +{summary['xp_stolen']}" if win else f"📉 XP Lost: -{summary['xp_stolen']}",
        f"🏅 ELO Change: {summary['elo_change']:+d}",
        "",
        f"❤️ {a_name}: {hp_bar(a_hp, a_max, 12)} {a_hp}/{a_max}",
        f"💀 {d_name}: {hp_bar(d_hp, d_max, 12)} {d_hp}/{d_max}",
        "",
        "*Highlights:*",
    ]

    best = summary["best_hits"]
    if best["attacker"]["damage"]:
        card.append(f"💥 Your best hit: {best['attacker']['damage']} dmg")
    if best["defender"]["damage"]:
        card.append(f"💢 Enemy best hit: {best['defender']['damage']} dmg")

    try:
        bot.send_message(chat, "\n".join(card), parse_mode="Markdown")
    except:
        pass


# ============================================================
# MAIN SETUP — COMMAND + CALLBACKS (FULL, CLEAN, SAFE)
# ============================================================

def setup(bot: TeleBot):
    # store reference for notifications
    globals()["bot_instance_for_pvp"] = bot

    # --------------------------------------------------------
    # /attack — attacker initiates raid
    # --------------------------------------------------------
    @bot.message_handler(commands=["attack"])
    def cmd_attack(message):
        attacker_id = message.from_user.id
        if not has_pvp_access(attacker_id):
            return bot.reply_to(message, "🔒 PvP requires VIP.")

        # who is defender?
        defender_id = None
        if message.reply_to_message:
            defender_id = message.reply_to_message.from_user.id
        else:
            parts = message.text.split()
            if len(parts) == 1:
                return bot.reply_to(message, "Reply to someone or `/attack @name`")
            q = parts[1].strip()
            if q.startswith("@"):
                row = db.get_user_by_username(q)
                if not row:
                    return bot.reply_to(message, "User not found.")
                defender_id = row[0]
            else:
                candidates = db.search_users_by_name(q)
                if not candidates:
                    return bot.reply_to(message, "No users matched.")
                if len(candidates) == 1:
                    defender_id = candidates[0][0]
                else:
                    kb = types.InlineKeyboardMarkup()
                    for uid, uname, disp in candidates:
                        label = disp or uname or f"User{uid}"
                        kb.add(types.InlineKeyboardButton(label,
                            callback_data=f"pvp_select:{attacker_id}:{uid}"))
                    return bot.reply_to(message, "Multiple matches:", reply_markup=kb)

        if defender_id is None:
            return bot.reply_to(message, "Target not found.")
        if defender_id == attacker_id:
            return bot.reply_to(message, "You cannot attack yourself.")
        if db.is_pvp_shielded(defender_id):
            return bot.reply_to(message, "🛡 That user is shielded.")

        attacker = db.get_user(attacker_id) or {}
        defender = db.get_user(defender_id) or {}

        # Build stats + inject identity  (THIS FIXES UserNone ISSUE)
        a_stats = build_player_stats_from_user(attacker)
        d_stats = build_player_stats_from_user(defender)

        a_stats["user_id"] = attacker_id
        a_stats["username"] = attacker.get("username")
        a_stats["display_name"] = attacker.get("display_name")

        d_stats["user_id"] = defender_id
        d_stats["username"] = defender.get("username")
        d_stats["display_name"] = defender.get("display_name")

        # Create session
        sess = fight_session.manager.create_pvp_session(attacker_id, defender_id, a_stats, d_stats)
        sess.attacker_hp = a_stats["hp"]
        sess.defender_hp = d_stats["hp"]

        caption = build_caption(sess)
        kb = action_keyboard(sess)
        m = bot.send_message(message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)

        sess._last_msg = {"chat": m.chat.id, "msg": m.message_id}
        sess._last_ui_edit = 0
        fight_session.manager.save_session(sess)

        try:
            db.increment_pvp_field(attacker_id, "pvp_fights_started")
            db.increment_pvp_field(defender_id, "pvp_challenges_received")
        except:
            pass

    # --------------------------------------------------------
    # If user selected a defender from search list
    # --------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp_select"))
    def cb_pvp_select(call):
        try:
            _, att, dfd = call.data.split(":")
            attacker_id = int(att)
            defender_id = int(dfd)
        except:
            return bot.answer_callback_query(call.id, "Invalid selection.")

        attacker = db.get_user(attacker_id) or {}
        defender = db.get_user(defender_id) or {}

        a_stats = build_player_stats_from_user(attacker)
        d_stats = build_player_stats_from_user(defender)

        a_stats["user_id"] = attacker_id
        a_stats["username"] = attacker.get("username")
        a_stats["display_name"] = attacker.get("display_name")

        d_stats["user_id"] = defender_id
        d_stats["username"] = defender.get("username")
        d_stats["display_name"] = defender.get("display_name")

        sess = fight_session.manager.create_pvp_session(attacker_id, defender_id, a_stats, d_stats)
        sess.attacker_hp = a_stats["hp"]
        sess.defender_hp = d_stats["hp"]

        caption = build_caption(sess)
        kb = action_keyboard(sess)
        m = bot.send_message(call.message.chat.id, caption,
                             parse_mode="Markdown", reply_markup=kb)

        sess._last_msg = {"chat": m.chat.id, "msg": m.message_id}
        sess._last_ui_edit = 0
        fight_session.manager.save_session(sess)

        try:
            db.increment_pvp_field(attacker_id, "pvp_fights_started")
            db.increment_pvp_field(defender_id, "pvp_challenges_received")
        except:
            pass

        bot.answer_callback_query(call.id, "Raid started!")

    # --------------------------------------------------------
    # PvP ACTION HANDLER (attack/block/dodge/charge/auto/forfeit)
    # Supports both session_id callbacks AND old attacker_id callbacks
    # --------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:act"))
    def cb_pvp_action(call):
        parts = call.data.split(":")
        if len(parts) != 4:
            return bot.answer_callback_query(call.id, "Invalid.")

        _, _, action, token = parts

        # 1) Try session_id
        sess = fight_session.manager.load_session_by_sid(token)

        # 2) Fallback to legacy attacker-id callback
        if not sess:
            try:
                sess = fight_session.manager.load_session(int(token))
            except:
                sess = None

        if not sess:
            return bot.answer_callback_query(call.id, "Session expired.", show_alert=True)

        attacker_id = _sess_attacker_id(sess)

        # Owner-only enforcement
        if call.from_user.id != attacker_id:
            return bot.answer_callback_query(call.id, "Not your raid.", show_alert=True)

        chat_id = sess._last_msg.get("chat")
        msg_id = sess._last_msg.get("msg")

        # ACTION: Forfeit
        if action == "forfeit":
            sess.ended = True
            sess.winner = "defender"
            fight_session.manager.save_session(sess)

            summary = finalize_pvp(bot, sess)
            send_result_card(bot, sess, summary)

            sid = _sess_session_id(sess)
            if sid:
                fight_session.manager.end_session_by_sid(sid)
            else:
                fight_session.manager.end_session(attacker_id)

            return bot.answer_callback_query(call.id, "You forfeited.")

        # ACTION: Auto (perform 1 auto turn)
        if action == "auto":
            if hasattr(sess, "resolve_auto_attacker_turn"):
                sess.resolve_auto_attacker_turn()
            elif hasattr(sess, "resolve_attacker_action"):
                sess.resolve_attacker_action("attack")

            fight_session.manager.save_session(sess)

            if sess.ended:
                summary = finalize_pvp(bot, sess)
                send_result_card(bot, sess, summary)
                sid = _sess_session_id(sess)
                if sid:
                    fight_session.manager.end_session_by_sid(sid)
                else:
                    fight_session.manager.end_session(attacker_id)
            else:
                safe_edit(bot, sess, chat_id, msg_id,
                          build_caption(sess), action_keyboard(sess))

            return bot.answer_callback_query(call.id)

        # STANDARD ACTION (attack/block/dodge/charge)
        if hasattr(sess, "resolve_attacker_action"):
            sess.resolve_attacker_action(action)
        else:
            # fallback conservative behavior
            atk = _sess_attacker(sess)
            dfd = _sess_defender(sess)
            dmg = max(1, int(atk.get("attack", 10)) - int(dfd.get("defense", 0)))
            _sess_set_defender_hp(sess, _sess_defender_hp(sess) - dmg)
            if hasattr(sess, "log"):
                sess.log("attacker", "attack", dmg)

        fight_session.manager.save_session(sess)

        if sess.ended:
            summary = finalize_pvp(bot, sess)
            send_result_card(bot, sess, summary)

            sid = _sess_session_id(sess)
            if sid:
                fight_session.manager.end_session_by_sid(sid)
            else:
                fight_session.manager.end_session(attacker_id)

        else:
            safe_edit(bot, sess, chat_id, msg_id,
                      build_caption(sess), action_keyboard(sess))

        bot.answer_callback_query(call.id)
