# bot/handlers/pvp.py  — patched, session_id-safe and backwards compatible
# Based on your original pvp.py (uploaded by you). :contentReference[oaicite:1]{index=1}
#
# Changes:
#  - Uses session_id in callback_data for NEW sessions (sid:<hex>)
#  - Fallback to legacy attacker_id keyed sessions if sid lookup fails
#  - Accessor helpers normalize old/new session shapes for safe reads/writes
#  - Preserves all original UX, DB operations, notifications, ELO/xp logic, and safe_edit throttling

import time
import random
from telebot import TeleBot, types

# PvP engine manager & classes (patched: session_id support)
import services.fight_session_pvp as fight_session
# Shared stat builder from PvE module
from services.fight_session_battle import build_player_stats_from_user

import bot.db as db

# include original file citation reference for traceability
# original file: :contentReference[oaicite:2]{index=2}

# CONFIG (unchanged)
PVP_FREE_MODE = True
PVP_ELO_K = 32
PVP_MIN_STEAL_PERCENT = 0.07
PVP_MIN_STEAL_ABS = 20
PVP_SHIELD_SECONDS = 3 * 3600
UI_EDIT_THROTTLE_SECONDS = 1.0  # <= 1 second between edits per session


# -------------------------
# Helpers (display + hp bar)
# -------------------------
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
    """
    Edit the message but respect per-session throttle and avoid fallback spam on 429.
    `sess` is the fight session object (PvP).
    """
    now = time.time()
    last = getattr(sess, "_last_ui_edit", 0)
    if now - last < UI_EDIT_THROTTLE_SECONDS:
        # skip edit to avoid hitting Telegram rate limits
        return

    try:
        bot.edit_message_text(
            text, chat_id, msg_id, parse_mode="Markdown", reply_markup=kb
        )
        sess._last_ui_edit = time.time()
        fight_session.manager.save_session(sess)
        return
    except Exception as e:
        s = str(e).lower()
        # if not modified — fine
        if "message is not modified" in s:
            return
        # if rate-limited — do not fallback to send_message (would cause more rate limits)
        if "too many requests" in s or "retry after" in s:
            # record last edit time to prevent retries for a bit
            sess._last_ui_edit = time.time()
            fight_session.manager.save_session(sess)
            return
        # fallback once when safe (other errors)
        try:
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)
            sess._last_ui_edit = time.time()
            fight_session.manager.save_session(sess)
        except Exception:
            # if even send fails, give up silently
            sess._last_ui_edit = time.time()
            fight_session.manager.save_session(sess)
            return


def calc_xp_steal(def_xp):
    return max(int(def_xp * PVP_MIN_STEAL_PERCENT), PVP_MIN_STEAL_ABS)


# -------------------------
# Session access helpers (normalize old/new session shapes)
# -------------------------
def _sess_attacker(sess):
    """
    Return attacker dict regardless of session shape.
    New session shape: sess.attacker (dict)
    Old session shape: sess.pvp_attacker (dict)
    """
    if hasattr(sess, "attacker") and isinstance(getattr(sess, "attacker"), dict):
        return sess.attacker
    return getattr(sess, "pvp_attacker", {}) or {}


def _sess_defender(sess):
    if hasattr(sess, "defender") and isinstance(getattr(sess, "defender"), dict):
        return sess.defender
    return getattr(sess, "pvp_defender", {}) or {}


def _sess_attacker_hp(sess):
    # prefer explicit numeric field if available
    if hasattr(sess, "attacker_hp"):
        return getattr(sess, "attacker_hp")
    # new shape: attacker dict holds 'hp' or runtime hp inside attacker['hp']
    a = _sess_attacker(sess)
    return a.get("hp") if isinstance(a.get("hp"), int) else a.get("current_hp", a.get("hp", 100))


def _sess_defender_hp(sess):
    if hasattr(sess, "defender_hp"):
        return getattr(sess, "defender_hp")
    d = _sess_defender(sess)
    return d.get("hp") if isinstance(d.get("hp"), int) else d.get("current_hp", d.get("hp", 100))


def _sess_set_attacker_hp(sess, value):
    # maintain compatibility: set numeric field if exists, else modify dict
    if hasattr(sess, "attacker_hp"):
        sess.attacker_hp = value
        return
    if hasattr(sess, "attacker") and isinstance(sess.attacker, dict):
        sess.attacker["hp"] = value
        return
    if hasattr(sess, "pvp_attacker") and isinstance(sess.pvp_attacker, dict):
        sess.pvp_attacker["hp"] = value
        return
    # fallback: set attribute
    setattr(sess, "attacker_hp", value)


def _sess_set_defender_hp(sess, value):
    if hasattr(sess, "defender_hp"):
        sess.defender_hp = value
        return
    if hasattr(sess, "defender") and isinstance(sess.defender, dict):
        sess.defender["hp"] = value
        return
    if hasattr(sess, "pvp_defender") and isinstance(sess.pvp_defender, dict):
        sess.pvp_defender["hp"] = value
        return
    setattr(sess, "defender_hp", value)


def _sess_attacker_id(sess):
    return getattr(sess, "attacker_id", getattr(sess, "pvp_attacker_id", None))


def _sess_defender_id(sess):
    return getattr(sess, "defender_id", getattr(sess, "pvp_defender_id", None))


def _sess_session_id(sess):
    # return session_id if present (new sessions), else None
    return getattr(sess, "session_id", None)


# -------------------------
# Caption + keyboard builders (preserve original layout)
# -------------------------
def build_caption(sess):
    a = _sess_attacker(sess) or {}
    d = _sess_defender(sess) or {}

    a_name = get_display_name(a)
    d_name = get_display_name(d)

    a_max = a.get("current_hp", a.get("hp", 100))
    d_max = d.get("current_hp", d.get("hp", 100))

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
        # keep original behavior but show fewer to avoid spam (match your PvE clean UX)
        for ev in sess.events[:6]:
            actor = a_name if ev["actor"] == "attacker" else d_name
            if ev["action"] == "attack":
                lines.append(f"• {actor} dealt {ev['damage']} dmg {ev.get('note','')}")
            else:
                lines.append(f"• {actor}: {ev['action']} {ev.get('note','')}")
    return "\n".join(lines)


def _action_cb(action: str, sid_or_attacker: str) -> str:
    """
    Build callback_data for actions. For new sessions we pass session_id; legacy attacker numeric ids still supported.
    Format: pvp:act:<action>:<token>
    """
    return f"pvp:act:{action}:{sid_or_attacker}"


def action_keyboard(sess):
    # prefer session_id for new sessions
    sid = _sess_session_id(sess) or ""
    token = sid if sid else str(_sess_attacker_id(sess) or "")
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=_action_cb("attack", token)),
        types.InlineKeyboardButton("🛡 Block", callback_data=_action_cb("block", token)),
    )
    kb.add(
        types.InlineKeyboardButton("💨 Dodge", callback_data=_action_cb("dodge", token)),
        types.InlineKeyboardButton("⚡ Charge", callback_data=_action_cb("charge", token)),
    )
    # NOTE: Auto executes one automatic attacker turn (same as original)
    kb.add(
        types.InlineKeyboardButton("▶ Auto", callback_data=_action_cb("auto", token)),
        types.InlineKeyboardButton("❌ Forfeit", callback_data=_action_cb("forfeit", token)),
    )
    return kb


# -------------------------
# finalize_pvp and send_result_card (preserve original logic)
# -------------------------
def finalize_pvp(bot, sess):
    atk_id = _sess_attacker_id(sess)
    dfd_id = _sess_defender_id(sess)

    attacker = db.get_user(atk_id) or {}
    defender = db.get_user(dfd_id) or {}

    atk_xp = attacker.get("xp_total", 0)
    dfd_xp = defender.get("xp_total", 0)

    attacker_won = getattr(sess, "winner", "") == "attacker"
    xp_stolen = 0

    best = {"attacker": {"damage": 0}, "defender": {"damage": 0}}
    for ev in getattr(sess, "events", []):
        if ev["action"] == "attack" and ev.get("damage", 0) > 0:
            if ev["actor"] == "attacker" and ev["damage"] > best["attacker"]["damage"]:
                best["attacker"] = {"damage": ev["damage"], "turn": ev["turn"]}
            if ev["actor"] == "defender" and ev["damage"] > best["defender"]["damage"]:
                best["defender"] = {"damage": ev["damage"], "turn": ev["turn"]}

    if attacker_won:
        xp_stolen = calc_xp_steal(dfd_xp)
        try:
            db.cursor.execute(
                "UPDATE users SET xp_total = xp_total - ?, xp_current = xp_current - ? WHERE user_id = ?",
                (xp_stolen, xp_stolen, dfd_id),
            )
            db.cursor.execute(
                "UPDATE users SET xp_total = xp_total + ?, xp_current = xp_current + ? WHERE user_id = ?",
                (xp_stolen, xp_stolen, atk_id),
            )
            db.conn.commit()
        except Exception:
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
                (penalty, penalty, atk_id),
            )
            db.cursor.execute(
                "UPDATE users SET xp_total = xp_total + ?, xp_current = xp_current + ? WHERE user_id = ?",
                (penalty, penalty, dfd_id),
            )
            db.conn.commit()
        except:
            pass

        try:
            db.increment_pvp_field(atk_id, "pvp_losses")
            db.increment_pvp_field(dfd_id, "pvp_wins")
        except:
            pass

    # ELO update (original formula preserved)
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

    # Notify defender (best-effort)
    atk_name = get_display_name(attacker)
    if attacker_won:
        notify_msg = (
            f"⚠️ You were raided by *{atk_name}*!\n"
            f"XP stolen: {xp_stolen}\n"
            f"ELO change: {new_dfd - dfd_elo}\n"
        )
    else:
        notify_msg = (
            f"🛡 Your AI defender repelled *{atk_name}*!\n"
            f"ELO change: {new_dfd - dfd_elo}\n"
        )

    try:
        bot = globals().get("bot_instance_for_pvp")
        if bot:
            bot.send_message(dfd_id, notify_msg, parse_mode="Markdown")
    except:
        pass

    # Prepare a simple summary dictionary like original returned structure
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

    msg_info = getattr(sess, "_last_msg", None) or {}
    chat_id = msg_info.get("chat", _sess_attacker_id(sess))

    a_hp = summary["attacker_hp"]
    d_hp = summary["defender_hp"]

    a_max = attacker.get("current_hp", attacker.get("hp", 100))
    d_max = defender.get("current_hp", defender.get("hp", 100))

    best = summary["best_hits"]

    win = getattr(sess, "winner", "") == "attacker"

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

    try:
        bot.send_message(chat_id, "\n".join(card), parse_mode="Markdown")
    except:
        pass


def has_pvp_access(uid):
    if PVP_FREE_MODE:
        return True
    try:
        return db.is_vip(uid)
    except:
        return True


# -------------------------
# Setup handler — preserve your flows, but use sid where possible
# -------------------------
def setup(bot: TeleBot):
    # store bot in module globals for notifications
    globals()["bot_instance_for_pvp"] = bot

    @bot.message_handler(commands=["attack"])
    def cmd_attack(message):
        attacker_id = message.from_user.id
        if not has_pvp_access(attacker_id):
            bot.reply_to(message, "🔒 PvP requires VIP.")
            return

        # determine defender
        defender_id = None
        if message.reply_to_message:
            defender_id = message.reply_to_message.from_user.id
        else:
            parts = message.text.split()
            if len(parts) == 1:
                return bot.reply_to(message, "Reply to someone or use `/attack <name>`", parse_mode="Markdown")
            q = parts[1].strip()
            if q.startswith("@"):
                row = db.get_user_by_username(q)
                if not row:
                    return bot.reply_to(message, "User not found.")
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
                        # legacy callbacks used attacker_id; we keep that for selection buttons (safe)
                        kb.add(types.InlineKeyboardButton(label, callback_data=f"pvp_select:{attacker_id}:{uid}"))
                    bot.reply_to(message, "Multiple matches:", reply_markup=kb)
                    return

        if defender_id is None:
            return bot.reply_to(message, "Could not identify target.")
        if defender_id == attacker_id:
            return bot.reply_to(message, "You cannot attack yourself.")
        if db.is_pvp_shielded(defender_id):
            return bot.reply_to(message, "🛡 User is shielded.")

        attacker = db.get_user(attacker_id) or {}
        defender = db.get_user(defender_id) or {}

        a_stats = build_player_stats_from_user(attacker)
        d_stats = build_player_stats_from_user(defender)

        # Create session via manager (manager now persists both legacy and sid keys)
        sess = fight_session.manager.create_pvp_session(attacker_id, defender_id, a_stats, d_stats)

        # Immediately populate runtime HP fields for compatibility if manager didn't set attacker_hp/defender_hp directly
        # New manager populates attacker/defender dicts; ensure we also set legacy-friendly attributes
        try:
            sess.attacker_hp = _sess_attacker_hp(sess)
            sess.defender_hp = _sess_defender_hp(sess)
        except Exception:
            pass

        caption = build_caption(sess)
        kb = action_keyboard(sess)
        m = bot.send_message(message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)
        sess._last_msg = {"chat": message.chat.id, "msg": m.message_id}
        sess._last_ui_edit = 0
        fight_session.manager.save_session(sess)

        try:
            db.increment_pvp_field(attacker_id, "pvp_fights_started")
            db.increment_pvp_field(defender_id, "pvp_challenges_received")
        except:
            pass

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp_select"))
    def cb_pvp_select(call):
        try:
            _, att, dfd = call.data.split(":")
            attacker_id = int(att); defender_id = int(dfd)
        except:
            return bot.answer_callback_query(call.id, "Invalid selection.")

        attacker = db.get_user(attacker_id) or {}
        defender = db.get_user(defender_id) or {}
        a_stats = build_player_stats_from_user(attacker)
        d_stats = build_player_stats_from_user(defender)

        # create session (legacy selection flow — manager will persist sid as well)
        sess = fight_session.manager.create_pvp_session(attacker_id, defender_id, a_stats, d_stats)

        try:
            sess.attacker_hp = _sess_attacker_hp(sess)
            sess.defender_hp = _sess_defender_hp(sess)
        except:
            pass

        caption = build_caption(sess)
        kb = action_keyboard(sess)
        m = bot.send_message(call.message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)
        sess._last_msg = {"chat": call.message.chat.id, "msg": m.message_id}
        sess._last_ui_edit = 0
        fight_session.manager.save_session(sess)
        try:
            db.increment_pvp_field(attacker_id, "pvp_fights_started")
            db.increment_pvp_field(defender_id, "pvp_challenges_received")
        except:
            pass
        bot.answer_callback_query(call.id, "Raid started!")

    # ACTION handler — supports both sid-based tokens and legacy attacker id tokens.
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:act"))
    def cb_pvp_action(call):
        parts = call.data.split(":")
        if len(parts) != 4:
            return bot.answer_callback_query(call.id, "Invalid.")

        _, _, action, token = parts

        # Try to load by sid first
        sess = None
        if token:
            sess = fight_session.manager.load_session_by_sid(token)
        if not sess:
            # fallback: maybe token is legacy numeric attacker id
            try:
                legacy_attacker = int(token)
                sess = fight_session.manager.load_session(legacy_attacker)
            except:
                sess = None

        if not sess:
            return bot.answer_callback_query(call.id, "Session not found.", show_alert=True)

        attacker_id = _sess_attacker_id(sess)
        # owner-only enforcement: only attacker can press attacker buttons
        if call.from_user.id != attacker_id:
            return bot.answer_callback_query(call.id, "Not your raid.", show_alert=True)

        # Ensure runtime hp fields exist for old clients that expect attacker_hp/defender_hp attributes
        try:
            # sync dicts -> numeric attrs for legacy downstream logic
            sess.attacker_hp = _sess_attacker_hp(sess)
            sess.defender_hp = _sess_defender_hp(sess)
        except:
            pass

        chat_id = sess._last_msg.get("chat") if getattr(sess, "_last_msg", None) else None
        msg_id = sess._last_msg.get("msg") if getattr(sess, "_last_msg", None) else None

        # Forfeit
        if action == "forfeit":
            sess.ended = True
            sess.winner = "defender"
            fight_session.manager.save_session(sess)
            summary = finalize_pvp(bot, sess)
            send_result_card(bot, sess, summary)
            # cleanup by sid if present
            sid = _sess_session_id(sess)
            if sid:
                fight_session.manager.end_session_by_sid(sid)
            else:
                fight_session.manager.end_session(attacker_id)
            return bot.answer_callback_query(call.id, "You forfeited.")

        # AUTO — perform ONE automatic attacker turn
        if action == "auto":
            # original logic called resolve_auto_attacker_turn — check for method on session
            if hasattr(sess, "resolve_auto_attacker_turn"):
                sess.resolve_auto_attacker_turn()
            else:
                # fallback: resolve one attacker action (attack)
                if hasattr(sess, "resolve_attacker_action"):
                    sess.resolve_attacker_action("attack")
            fight_session.manager.save_session(sess)

            if getattr(sess, "ended", False):
                summary = finalize_pvp(bot, sess)
                send_result_card(bot, sess, summary)
                sid = _sess_session_id(sess)
                if sid:
                    fight_session.manager.end_session_by_sid(sid)
                else:
                    fight_session.manager.end_session(attacker_id)
            else:
                caption = build_caption(sess)
                kb = action_keyboard(sess)
                safe_edit(bot, sess, chat_id, msg_id, caption, kb)

            return bot.answer_callback_query(call.id)

        # STANDARD ACTION (attack / block / dodge / charge)
        # Use session's resolve_attacker_action if available
        if hasattr(sess, "resolve_attacker_action"):
            sess.resolve_attacker_action(action)
        else:
            # fallback naive resolution: attacker deals attack minus defender defense
            try:
                a = _sess_attacker(sess)
                d = _sess_defender(sess)
                dmg = max(1, int(a.get("attack", 10)) - int(d.get("defense", 0)))
                # apply to defender hp
                new_d_hp = _sess_defender_hp(sess) - dmg
                _sess_set_defender_hp(sess, new_d_hp)
                # log event
                if hasattr(sess, "log"):
                    sess.log("attacker", "attack", dmg)
            except Exception:
                pass

        fight_session.manager.save_session(sess)

        if getattr(sess, "ended", False):
            summary = finalize_pvp(bot, sess)
            send_result_card(bot, sess, summary)
            sid = _sess_session_id(sess)
            if sid:
                fight_session.manager.end_session_by_sid(sid)
            else:
                fight_session.manager.end_session(attacker_id)
        else:
            caption = build_caption(sess)
            kb = action_keyboard(sess)
            safe_edit(bot, sess, chat_id, msg_id, caption, kb)

        bot.answer_callback_query(call.id)

