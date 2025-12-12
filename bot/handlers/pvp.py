# bot/handlers/pvp.py
# Corrected PvP handler for your project layout.
# - Uses services.pvp_stats.build_pvp_stats
# - Uses services.pvp_targets.get_recommended_targets / get_revenge_targets
# - Uses services.fight_session_pvp.manager for sessions
# - Heal action implemented (20% max HP, one-use)
# - Safe finalize that updates XP/ELO and logs pvp attack

import time
import random
from telebot import TeleBot, types

# Services live at project root /services
from services import fight_session_pvp as fight_session
from services import pvp_targets
from services import pvp_stats

# bot package utilities
import bot.db as db
from bot.handlers import pvp_ranking as ranking_module

# CONFIG
PVP_ELO_K = 32
PVP_MIN_STEAL_PERCENT = 0.07
PVP_MIN_STEAL_ABS = 20
PVP_SHIELD_SECONDS = 3 * 3600
UI_EDIT_THROTTLE_SECONDS = 1.0

# Helper: display name
def get_display_name(u):
    if not u:
        return "Unknown"
    if u.get("display_name"):
        return u["display_name"]
    if u.get("username"):
        return str(u["username"])
    return f"User{u.get('user_id')}"

# Small HP bar util
def hp_bar(cur, maxhp, width=20):
    cur = max(0, int(cur))
    maxhp = max(1, int(maxhp))
    filled = int((cur / maxhp) * width)
    return "▓" * filled + "░" * (width - filled)

# Check access (placeholder)
def has_pvp_access(uid):
    # keep free for now; replace with db.is_vip if needed
    return True

# throttle-safe edit helper
def safe_edit(bot, sess, chat_id, msg_id, text, kb):
    now = time.time()
    last = getattr(sess, "_last_ui_edit", 0)
    if now - last < UI_EDIT_THROTTLE_SECONDS:
        return
    try:
        bot.edit_message_text(text, chat_id, msg_id, parse_mode="Markdown", reply_markup=kb)
        sess._last_ui_edit = time.time()
        fight_session.manager.save_session(sess)
    except Exception:
        try:
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)
            sess._last_ui_edit = time.time()
            fight_session.manager.save_session(sess)
        except:
            sess._last_ui_edit = time.time()
            fight_session.manager.save_session(sess)

# Action keyboard: Heal replaces Auto
def _cb(action, token):
    return f"pvp:act:{action}:{token}"

def action_keyboard(sess):
    sid = getattr(sess, "session_id", None)
    token = sid if sid else str(getattr(sess, "attacker_id", ""))
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=_cb("attack", token)),
        types.InlineKeyboardButton("🛡 Block", callback_data=_cb("block", token)),
    )
    kb.add(
        types.InlineKeyboardButton("💨 Dodge", callback_data=_cb("dodge", token)),
        types.InlineKeyboardButton("⚡ Charge", callback_data=_cb("charge", token)),
    )
    kb.add(
        types.InlineKeyboardButton("💉 Heal (20%)", callback_data=_cb("heal", token)),
        types.InlineKeyboardButton("❌ Forfeit", callback_data=_cb("forfeit", token)),
    )
    return kb

# Caption builder for the active UI
def build_caption(sess):
    a = getattr(sess, "attacker", {}) or {}
    d = getattr(sess, "defender", {}) or {}
    a_name = get_display_name(a)
    d_name = get_display_name(d)
    a_hp = int(a.get("hp", a.get("max_hp", 100)))
    d_hp = int(d.get("hp", d.get("max_hp", 100)))
    a_max = int(a.get("max_hp", a.get("hp", 100)))
    d_max = int(d.get("max_hp", d.get("hp", 100)))

    lines = [
        f"⚔️ *PvP Raid:* {a_name} vs {d_name}",
        "",
        f"{a_name}: {hp_bar(a_hp, a_max, 20)} {a_hp}/{a_max}",
        f"{d_name}: {hp_bar(d_hp, d_max, 20)} {d_hp}/{d_max}",
        "",
        f"Turn: {getattr(sess, 'turn', 1)}",
        ""
    ]

    evs = getattr(sess, "events", []) or []
    if evs:
        lines.append("*Recent actions:*")
        for ev in evs[:6]:
            actor = a_name if ev["actor"] == "attacker" else d_name
            if ev["action"] == "attack":
                note = (" " + ev.get("note", "").strip()) if ev.get("note") else ""
                lines.append(f"• {actor} dealt {ev['damage']} dmg{note}")
            else:
                lines.append(f"• {actor}: {ev['action']} {ev.get('note','')}")
    return "\n".join(lines)

# Local finalize (safe fallback). Attempts to mirror your ELO/XP logic.
def finalize_pvp_local(attacker_id, defender_id, sess):
    """
    Called when a session ends. Updates DB: XP transfer, ELO, shields, logging.
    Returns summary dict for the result card.
    """
    attacker = db.get_user(attacker_id) or {}
    defender = db.get_user(defender_id) or {}

    # compute xp values
    atk_xp = attacker.get("xp_total", 0) or 0
    def_xp = defender.get("xp_total", 0) or 0

    attacker_won = getattr(sess, "winner", "") == "attacker"

    xp_stolen = 0
    if attacker_won:
        xp_stolen = max(int(def_xp * PVP_MIN_STEAL_PERCENT), PVP_MIN_STEAL_ABS)
        try:
            cursor = getattr(db, "cursor", None)
            conn = getattr(db, "conn", None)
            if cursor:
                cursor.execute(
                    "UPDATE users SET xp_total = xp_total - ?, xp_current = xp_current - ? WHERE user_id = ?",
                    (xp_stolen, xp_stolen, defender_id)
                )
                cursor.execute(
                    "UPDATE users SET xp_total = xp_total + ?, xp_current = xp_current + ? WHERE user_id = ?",
                    (xp_stolen, xp_stolen, attacker_id)
                )
                if conn:
                    conn.commit()
        except Exception:
            try:
                if conn:
                    conn.rollback()
            except:
                pass

        db.increment_pvp_field(attacker_id, "pvp_wins")
        db.increment_pvp_field(defender_id, "pvp_losses")
        db.set_pvp_shield(defender_id, int(time.time()) + PVP_SHIELD_SECONDS)

        db.log_pvp_attack(attacker_id, defender_id, xp_stolen, "win")
    else:
        penalty = max(1, int(atk_xp * 0.05))
        try:
            cursor = getattr(db, "cursor", None)
            conn = getattr(db, "conn", None)
            if cursor:
                cursor.execute("UPDATE users SET xp_total = xp_total - ?, xp_current = xp_current - ? WHERE user_id = ?",
                               (penalty, penalty, attacker_id))
                cursor.execute("UPDATE users SET xp_total = xp_total + ?, xp_current = xp_current + ? WHERE user_id = ?",
                               (penalty, penalty, defender_id))
                if conn:
                    conn.commit()
        except Exception:
            try:
                if conn:
                    conn.rollback()
            except:
                pass
        db.increment_pvp_field(attacker_id, "pvp_losses")
        db.increment_pvp_field(defender_id, "pvp_wins")
        db.log_pvp_attack(attacker_id, defender_id, 0, "fail")

    # ELO calculation
    atk_elo = attacker.get("elo_pvp", 1000) or 1000
    dfd_elo = defender.get("elo_pvp", 1000) or 1000

    def expected(a, b):
        return 1 / (1 + 10 ** ((b - a) / 400))

    E = expected(atk_elo, dfd_elo)
    if attacker_won:
        new_atk = atk_elo + int(PVP_ELO_K * (1 - E))
        new_dfd = dfd_elo - int(PVP_ELO_K * (1 - E))
    else:
        new_atk = atk_elo + int(PVP_ELO_K * (0 - E))
        new_dfd = dfd_elo - int(PVP_ELO_K * (0 - E))

    db.update_elo(attacker_id, new_atk)
    db.update_elo(defender_id, new_dfd)

    # best hits summary
    best = {"attacker": {"damage": 0}, "defender": {"damage": 0}}
    for ev in getattr(sess, "events", []) or []:
        if ev.get("action") == "attack":
            dmg = ev.get("damage", 0) or 0
            if ev.get("actor") == "attacker":
                best["attacker"]["damage"] = max(best["attacker"]["damage"], dmg)
            else:
                best["defender"]["damage"] = max(best["defender"]["damage"], dmg)

    return {
        "xp_stolen": xp_stolen,
        "elo_change": new_atk - atk_elo,
        "best_hits": best,
        "attacker_hp": int(sess.attacker.get("hp", 0)),
        "defender_hp": int(sess.defender.get("hp", 0)),
    }

# Send result card (simple format)
def send_result_card(bot, sess, summary):
    attacker_id = getattr(sess, "attacker_id", None)
    defender_id = getattr(sess, "defender_id", None)
    attacker = db.get_user(attacker_id) or {}
    defender = db.get_user(defender_id) or {}
    a_name = get_display_name(attacker)
    d_name = get_display_name(defender)

    a_hp = summary.get("attacker_hp", sess.attacker.get("hp", 0))
    d_hp = summary.get("defender_hp", sess.defender.get("hp", 0))

    win = getattr(sess, "winner", "") == "attacker"
    card = []
    if win:
        card.append("🏆 *VICTORY!*")
        card.append(f"You defeated *{d_name}*")
        card.append("")
        card.append(f"🎁 XP Stolen: +{summary.get('xp_stolen',0)}")
    else:
        card.append("💀 *DEFEAT*")
        card.append(f"You were repelled by *{d_name}*")
        card.append("")
        card.append(f"📉 XP Lost: -{summary.get('xp_stolen',0)}")

    card.append(f"🏅 ELO Change: {summary.get('elo_change',0):+d}")
    card.append("")
    card.append(f"❤️ {a_name}: {hp_bar(a_hp, attacker.get('hp', a_hp), 12)} {a_hp}/{attacker.get('hp', a_hp)}")
    card.append(f"💀 {d_name}: {hp_bar(d_hp, defender.get('hp', d_hp), 12)} {d_hp}/{defender.get('hp', d_hp)}")
    card.append("")
    card.append("*Highlights:*")
    best = summary.get("best_hits", {})
    if best.get("attacker", {}).get("damage"):
        card.append(f"💥 Your best hit: {best['attacker']['damage']} dmg")
    if best.get("defender", {}).get("damage"):
        card.append(f"💢 Enemy best hit: {best['defender']['damage']} dmg")

    chat = getattr(sess, "_last_msg", {}).get("chat", attacker_id)
    try:
        bot.send_message(chat, "\n".join(card), parse_mode="Markdown")
    except:
        pass

# ------------------------
# SETUP - register handlers
# ------------------------
def setup(bot: TeleBot):
    globals()["bot_instance"] = bot

    @bot.message_handler(commands=["pvp"])
    def cmd_pvp(message):
        attacker_id = message.from_user.id
        # mark active (optional)
        try:
            db.touch_last_active(attacker_id)
        except Exception:
            pass

        if not has_pvp_access(attacker_id):
            return bot.reply_to(message, "🔒 PvP requires VIP.")

        parts = message.text.strip().split()
        # direct target provided -> immediate duel
        if len(parts) > 1:
            q = parts[1].strip()
            defender_id = None
            if q.startswith("@"):
                row = db.get_user_by_username(q)
                if not row:
                    return bot.reply_to(message, "User not found.")
                # get_user_by_username returns tuple in this db; handle both
                if isinstance(row, tuple) or isinstance(row, list):
                    defender_id = row[0]
                elif isinstance(row, dict):
                    defender_id = row.get("user_id")
            else:
                matches = db.search_users_by_name(q)
                if not matches:
                    return bot.reply_to(message, "No matches found.")
                defender_id = matches[0][0]

            if not defender_id:
                return bot.reply_to(message, "Could not find target.")

            if defender_id == attacker_id:
                return bot.reply_to(message, "You cannot attack yourself.")
            if db.is_pvp_shielded(defender_id):
                return bot.reply_to(message, "That user is shielded.")

            attacker = db.get_user(attacker_id) or {}
            defender = db.get_user(defender_id) or {}

            a_stats = pvp_stats.build_pvp_stats(attacker)
            d_stats = pvp_stats.build_pvp_stats(defender)

            # ensure identity fields included
            a_stats["username"] = attacker.get("username"); a_stats["display_name"] = attacker.get("display_name")
            d_stats["username"] = defender.get("username"); d_stats["display_name"] = defender.get("display_name")

            sess = fight_session.manager.create_pvp_session(attacker_id, defender_id, a_stats, d_stats)
            sess.attacker["hp"] = a_stats["hp"]
            sess.defender["hp"] = d_stats["hp"]
            m = bot.send_message(message.chat.id, build_caption(sess), parse_mode="Markdown", reply_markup=action_keyboard(sess))
            sess._last_msg = {"chat": m.chat.id, "msg": m.message_id}
            sess._last_ui_edit = 0
            fight_session.manager.save_session(sess)

            db.increment_pvp_field(attacker_id, "pvp_fights_started")
            db.increment_pvp_field(defender_id, "pvp_challenges_received")
            return

        # No args -> show Arena panel (recommended + revenge)
        recs = pvp_targets.get_recommended_targets(attacker_id)
        revenge = pvp_targets.get_revenge_targets(attacker_id)
        me = db.get_user(attacker_id) or {}
        elo = int(me.get("elo_pvp", 1000))
        rank_name, _ = ranking_module.elo_to_rank(elo)

        lines = ["⚔️ *MEGAGROK PvP ARENA*", ""]
        if revenge:
            lines.append("🔥 *Revenge Targets:*")
            for r in revenge[:5]:
                name = r.get("display_name") or r.get("username") or f"User{r.get('user_id')}"
                ago = int((time.time() - int(r.get("ts", time.time()))) // 3600)
                lines.append(f"• {name} — {ago}h ago — {r.get('xp_stolen',0)} XP")
            lines.append("")
        if recs:
            lines.append("🎯 *Recommended Targets:*")
            for r in recs[:6]:
                name = r.get("display_name") or r.get("username") or f"User{r.get('user_id')}"
                lines.append(f"• {name} — Level {r.get('level',1)} — Power {r.get('power')} — {r.get('rank')}")
            lines.append("")
        lines.append(f"📈 Rank: *{rank_name}* — ELO: *{elo}*")
        text = "\n".join(lines)

        kb = types.InlineKeyboardMarkup(row_width=1)
        for r in (revenge or [])[:5]:
            uid = int(r.get("user_id"))
            label = f"Revenge {r.get('display_name') or r.get('username') or uid}"
            kb.add(types.InlineKeyboardButton(label, callback_data=f"pvp:rev:{attacker_id}:{uid}"))
        for r in (recs or [])[:6]:
            uid = int(r.get("user_id"))
            label = f"Attack {r.get('display_name') or r.get('username') or uid}  (Power {r.get('power')})"
            kb.add(types.InlineKeyboardButton(label, callback_data=f"pvp:rec:{attacker_id}:{uid}"))

        kb.add(types.InlineKeyboardButton("🎲 Random fair match", callback_data=f"pvp:find:{attacker_id}"))

        bot.reply_to(message, text, parse_mode="Markdown", reply_markup=kb)

    # panel selection callback
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:rec") or c.data.startswith("pvp:rev") or c.data.startswith("pvp:find"))
    def cb_pvp_panel(call):
        parts = call.data.split(":")
        if parts[0] != "pvp":
            return
        typ = parts[1]
        try:
            attacker_id = int(parts[2])
        except:
            return bot.answer_callback_query(call.id, "Invalid.")
        if call.from_user.id != attacker_id:
            return bot.answer_callback_query(call.id, "Not your arena.", show_alert=True)

        if typ in ("rec", "rev"):
            defender_id = int(parts[3])
        elif typ == "find":
            recs = pvp_targets.get_recommended_targets(attacker_id)
            if not recs:
                return bot.answer_callback_query(call.id, "No targets available.")
            defender_id = recs[0]["user_id"]
        else:
            return bot.answer_callback_query(call.id, "Invalid selection.")

        if db.is_pvp_shielded(defender_id):
            return bot.answer_callback_query(call.id, "That user is shielded.", show_alert=True)

        attacker = db.get_user(attacker_id) or {}
        defender = db.get_user(defender_id) or {}
        a_stats = pvp_stats.build_pvp_stats(attacker)
        d_stats = pvp_stats.build_pvp_stats(defender)
        a_stats["username"] = attacker.get("username"); a_stats["display_name"] = attacker.get("display_name")
        d_stats["username"] = defender.get("username"); d_stats["display_name"] = defender.get("display_name")

        sess = fight_session.manager.create_pvp_session(attacker_id, defender_id, a_stats, d_stats)
        sess.attacker["hp"] = a_stats["hp"]
        sess.defender["hp"] = d_stats["hp"]
        m = bot.send_message(call.message.chat.id, build_caption(sess), parse_mode="Markdown", reply_markup=action_keyboard(sess))
        sess._last_msg = {"chat": m.chat.id, "msg": m.message_id}
        sess._last_ui_edit = 0
        fight_session.manager.save_session(sess)

        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_challenges_received")
        bot.answer_callback_query(call.id, "Raid started!")

    # action handler
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:act"))
    def cb_pvp_action(call):
        try:
            _, _, action, token = call.data.split(":")
        except Exception:
            return bot.answer_callback_query(call.id, "Invalid action.")

        # load by sid first
        sess = fight_session.manager.load_session_by_sid(token)
        if not sess:
            try:
                sess = fight_session.manager.load_session(int(token))
            except:
                sess = None
        if not sess:
            return bot.answer_callback_query(call.id, "Session expired.", show_alert=True)

        attacker_id = getattr(sess, "attacker_id", None)
        if call.from_user.id != attacker_id:
            return bot.answer_callback_query(call.id, "Not your raid.", show_alert=True)

        chat_id = sess._last_msg.get("chat"); msg_id = sess._last_msg.get("msg")

        if action == "forfeit":
            sess.ended = True; sess.winner = "defender"
            fight_session.manager.save_session(sess)
            try:
                summary = finalize_pvp_local(attacker_id, sess.defender_id, sess)
            except Exception:
                summary = {}
            try:
                send_result_card(bot, sess, summary)
            except:
                pass
            fight_session.manager.end_session_by_sid(getattr(sess, "session_id", ""))
            return bot.answer_callback_query(call.id, "You forfeited.")

        # execute action (heal included)
        sess.resolve_attacker_action(action)
        fight_session.manager.save_session(sess)

        if sess.ended:
            # try to call any existing finalize_pvp in your codebase first (to keep your custom logic)
            try:
                # import may succeed if you kept a finalize in another module
                from bot.handlers.pvp import finalize_pvp as ext_finalize
                summary = ext_finalize(attacker_id, sess.defender_id, sess)
            except Exception:
                # fallback local finalize
                summary = finalize_pvp_local(attacker_id, sess.defender_id, sess)
            send_result_card(bot, sess, summary)
            fight_session.manager.end_session_by_sid(getattr(sess, "session_id", ""))
        else:
            safe_edit(bot, sess, chat_id, msg_id, build_caption(sess), action_keyboard(sess))

        bot.answer_callback_query(call.id)

# When the module is imported, call setup(bot) from main to register handlers.
