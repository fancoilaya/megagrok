# MegaGrok Async PvP System — v3 Cinematic Result Card
# Place in: bot/handlers/pvp.py
# Requires: bot/db.py, services/fight_session.py

import os
import time
import random
from typing import Optional, Dict, Any
from telebot import TeleBot, types

# Correct project imports
import bot.db as db
import services.fight_session as fight_session

# Optional GIF utility (fallback safe noop)
try:
    from bot.utils import safe_send_gif
except Exception:
    def safe_send_gif(bot, chat_id, path): 
        return None


# -------------------------
# Config (env overrides)
# -------------------------
PVP_FREE_MODE = os.getenv("PVP_FREE_MODE", "true").lower() == "true"
PVP_SHIELD_SECONDS = int(os.getenv("PVP_SHIELD_SECONDS", str(3 * 3600)))
PVP_MIN_STEAL_PERCENT = float(os.getenv("PVP_MIN_STEAL_PERCENT", "0.07"))
PVP_MIN_STEAL_ABS = int(os.getenv("PVP_MIN_STEAL_ABS", "20"))
PVP_ELO_K = int(os.getenv("PVP_ELO_K", "32"))
RESULT_BAR_WIDTH = int(os.getenv("RESULT_BAR_WIDTH", "18"))


# -------------------------
# Helpers
# -------------------------
def get_display_name(user: Dict[str, Any]) -> str:
    """Prefer display_name, then username, then fallback."""
    if not user:
        return "Unknown"
    dn = user.get("display_name")
    if dn and str(dn).strip():
        return str(dn).strip()
    un = user.get("username")
    if un and str(un).strip():
        return str(un).strip()
    uid = user.get("user_id") or user.get("id") or "?"
    return f"User{uid}"


def hp_bar(cur: int, maxhp: int, width: int = 16) -> str:
    cur = max(0, int(cur))
    maxhp = max(1, int(maxhp))
    ratio = cur / maxhp
    f = int(round(width * ratio))
    return "▓" * f + "░" * (width - f)


def safe_edit_message(bot: TeleBot, chat_id: int, msg_id: int, text: str, reply_markup):
    """Edit message but suppress Telegram 'message is not modified' 400 error."""
    try:
        bot.edit_message_text(text, chat_id, msg_id, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception as e:
        s = str(e)
        if "message is not modified" in s:
            return
        # Print other exceptions for debugging
        print("safe_edit_message ERROR:", e)


def calc_xp_steal(def_total_xp: int) -> int:
    amt = int(def_total_xp * PVP_MIN_STEAL_PERCENT)
    return max(amt, PVP_MIN_STEAL_ABS)


# -------------------------
# Caption / UI builders
# -------------------------
def build_caption(sess: fight_session.FightSession) -> str:
    """Build the main battle caption (shown in the chat)."""
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
        f"Turn: {sess.turn}",
        ""
    ]

    # Recent actions (most recent first)
    if getattr(sess, "events", None):
        lines.append("*Recent actions:*")
        for ev in sess.events[:6]:
            actor_label = a_name if ev.get("actor") == "attacker" else d_name if ev.get("actor") == "defender" else ev.get("actor", "")
            if ev.get("action") == "attack":
                dmg = ev.get("damage", 0)
                note = ev.get("note") or ""
                lines.append(f"⚔️ {actor_label} dealt {dmg} dmg {note}")
            else:
                lines.append(f"{actor_label} — {ev.get('action')} {ev.get('note','')}")
    return "\n".join(lines)


def action_keyboard(attacker_id: int, auto_mode: bool) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=f"pvp:act:attack:{attacker_id}"),
        types.InlineKeyboardButton("🛡 Block", callback_data=f"pvp:act:block:{attacker_id}"),
        types.InlineKeyboardButton("💨 Dodge", callback_data=f"pvp:act:dodge:{attacker_id}")
    )
    kb.add(types.InlineKeyboardButton("⚡ Charge", callback_data=f"pvp:act:charge:{attacker_id}"))
    kb.add(
        types.InlineKeyboardButton("▶ Auto" if not auto_mode else "⏸ Auto", callback_data=f"pvp:act:auto:{attacker_id}"),
        types.InlineKeyboardButton("✖ Forfeit", callback_data=f"pvp:act:forfeit:{attacker_id}")
    )
    return kb


# -------------------------
# Finalize logic
# -------------------------
def finalize_pvp(bot: TeleBot, sess: fight_session.FightSession) -> Dict[str, Any]:
    """
    Apply XP/ELO/shield changes and return summary dict.
    summary contains:
      winner: "attacker" or "defender"
      xp_stolen: int
      elo_attacker: delta
      elo_defender: delta
      attacker_hp: int (final)
      defender_hp: int (final)
      highlights: dict (best_hits etc)
    """
    attacker_id = sess.attacker_id
    defender_id = sess.defender_id

    attacker = db.get_user(attacker_id) or {}
    defender = db.get_user(defender_id) or {}

    atk_xp = attacker.get("xp_total", 0)
    def_xp = defender.get("xp_total", 0)

    attacker_won = (sess.winner == "attacker")
    xp_stolen = 0

    # compute highlights from session events
    best_hits = {"attacker": {"damage": 0, "turn": None}, "defender": {"damage": 0, "turn": None}}
    for ev in getattr(sess, "events", []) or []:
        if ev.get("action") == "attack":
            dmg = ev.get("damage", 0)
            who = ev.get("actor")
            if who == "attacker" and dmg > best_hits["attacker"]["damage"]:
                best_hits["attacker"] = {"damage": dmg, "turn": ev.get("turn")}
            if who == "defender" and dmg > best_hits["defender"]["damage"]:
                best_hits["defender"] = {"damage": dmg, "turn": ev.get("turn")}

    if attacker_won:
        xp_stolen = calc_xp_steal(def_xp)
        # transfer XP
        db.cursor.execute("UPDATE users SET xp_total = xp_total - ?, xp_current = xp_current - ? WHERE user_id=?",
                          (xp_stolen, xp_stolen, defender_id))
        db.cursor.execute("UPDATE users SET xp_total = xp_total + ?, xp_current = xp_current + ? WHERE user_id=?",
                          (xp_stolen, xp_stolen, attacker_id))
        db.increment_pvp_field(attacker_id, "pvp_wins")
        db.increment_pvp_field(defender_id, "pvp_losses")
        # shield defender
        db.set_pvp_shield(defender_id, int(time.time()) + PVP_SHIELD_SECONDS)
    else:
        penalty = max(1, int(atk_xp * 0.05))
        db.cursor.execute("UPDATE users SET xp_total = xp_total - ?, xp_current = xp_current - ? WHERE user_id=?",
                          (penalty, penalty, attacker_id))
        db.cursor.execute("UPDATE users SET xp_total = xp_total + ?, xp_current = xp_current + ? WHERE user_id=?",
                          (penalty, penalty, defender_id))
        db.increment_pvp_field(attacker_id, "pvp_losses")
        db.increment_pvp_field(defender_id, "pvp_wins")

    db.conn.commit()

    # ELO adjustments
    atk_elo = attacker.get("elo_pvp", 1000)
    def_elo = defender.get("elo_pvp", 1000)

    def expected(a, b): return 1 / (1 + 10 ** ((b - a) / 400))

    E = expected(atk_elo, def_elo)
    if attacker_won:
        new_atk = int(round(atk_elo + PVP_ELO_K * (1 - E)))
        new_def = int(round(def_elo - PVP_ELO_K * (1 - E)))
    else:
        new_atk = int(round(atk_elo + PVP_ELO_K * (0 - E)))
        new_def = int(round(def_elo - PVP_ELO_K * (0 - E)))

    db.update_elo(attacker_id, new_atk)
    db.update_elo(defender_id, new_def)

    # Refresh user objects
    attacker = db.get_user(attacker_id) or attacker
    defender = db.get_user(defender_id) or defender

    # Notify defender
    a_name = get_display_name(attacker)
    if attacker_won:
        notify_msg = (f"⚠️ You were raided by *{a_name}*!\n"
                      f"XP stolen: {xp_stolen}\n"
                      f"ELO change: {new_def - def_elo}\n"
                      f"Shield active for {PVP_SHIELD_SECONDS//3600}h.")
    else:
        notify_msg = (f"🛡 Your AI defender repelled *{a_name}*!\n"
                      f"ELO change: {new_def - def_elo}")

    notify(bot, defender_id, notify_msg)

    return {
        "winner": sess.winner,
        "xp_stolen": xp_stolen,
        "elo_attacker": new_atk - atk_elo,
        "elo_defender": new_def - def_elo,
        "attacker_hp": sess.attacker_hp,
        "defender_hp": sess.defender_hp,
        "best_hits": best_hits
    }


def notify(bot: TeleBot, user_id: int, text: str):
    try:
        bot.send_message(user_id, text, parse_mode="Markdown")
    except Exception:
        pass


# -------------------------
# Cinematic result card
# -------------------------
def send_pvp_result_card(bot: TeleBot, sess: fight_session.FightSession, summary: Dict[str, Any]):
    """Send a cinematic result message to the chat after finalize_pvp has run."""
    attacker = db.get_user(sess.attacker_id) or {}
    defender = db.get_user(sess.defender_id) or {}

    a_name = get_display_name(attacker)
    d_name = get_display_name(defender)

    # Where to send result: use last message pointer if available
    last = getattr(sess, "_last_msg", None) or fight_session.manager._sessions.get(str(sess.attacker_id), {}).get("_last_msg")
    if last and isinstance(last, dict):
        chat_id = last.get("chat")
    else:
        chat_id = getattr(sess, "chat_id", None)

    # Attacker stats (post-update)
    cur_xp = attacker.get("xp_current", 0)
    total_xp = attacker.get("xp_total", 0)
    lvl = attacker.get("level", 1)
    xp_to_next = attacker.get("xp_to_next_level", max(1, attacker.get("xp_needed", 100)))
    # compute progress ratio safely
    ratio = 0.0
    try:
        ratio = min(1.0, max(0.0, cur_xp / xp_to_next)) if xp_to_next else 0.0
    except Exception:
        ratio = 0.0

    xp_bar = "▓" * int(round(RESULT_BAR_WIDTH * ratio)) + "░" * (RESULT_BAR_WIDTH - int(round(RESULT_BAR_WIDTH * ratio)))

    # HP bars & highlights
    atk_hp = summary.get("attacker_hp", 0)
    def_hp = summary.get("defender_hp", 0)
    a_max = attacker.get("current_hp", attacker.get("hp", 100))
    d_max = defender.get("current_hp", defender.get("hp", 100))
    atk_hp_bar = hp_bar(atk_hp, a_max, 12)
    def_hp_bar = hp_bar(def_hp, d_max, 12)

    best_hits = summary.get("best_hits", {})
    atk_best = best_hits.get("attacker", {}) or {}
    def_best = best_hits.get("defender", {}) or {}

    shield_text = ""
    if summary["winner"] == "attacker":
        shield_until = db.get_pvp_shield_until(sess.defender_id) if hasattr(db, "get_pvp_shield_until") else None
        if shield_until:
            hours = max(0, int((shield_until - time.time()) // 3600))
            shield_text = f"🛡 Opponent shielded for {hours}h"
        else:
            shield_text = f"🛡 Opponent shield active"

    # Compose cinematic card
    if summary["winner"] == "attacker":
        title = "🏆 *VICTORY!*"
        subtitle = f"You defeated *{d_name}*"
        xp_line = f"🎁 *XP Stolen:* +{summary.get('xp_stolen', 0)}"
        elo_line = f"🏅 *ELO Change:* {summary.get('elo_attacker', 0):+d}"
    else:
        title = "💀 *DEFEAT*"
        subtitle = f"You were repelled by *{d_name}*"
        xp_line = f"📉 *XP Lost:* -{summary.get('xp_stolen', 0)}"
        elo_line = f"🏅 *ELO Change:* {summary.get('elo_attacker', 0):+d}"

    highlights = []
    if atk_best.get("damage"):
        highlights.append(f"💥 Your biggest hit: {atk_best['damage']} dmg (turn {atk_best.get('turn')})")
    if def_best.get("damage"):
        highlights.append(f"💢 Opponent biggest hit: {def_best['damage']} dmg (turn {def_best.get('turn')})")

    recap_lines = []
    recap_lines.append(title)
    recap_lines.append(subtitle)
    recap_lines.append("")
    recap_lines.append(f"{xp_line}     {elo_line}")
    recap_lines.append("")
    recap_lines.append(f"❤️ HP — {a_name}: {atk_hp_bar} {atk_hp}/{a_max}")
    recap_lines.append(f"💀 HP — {d_name}: {def_hp_bar} {def_hp}/{d_max}")
    recap_lines.append("")
    if highlights:
        recap_lines.append("*Battle highlights:*")
        for h in highlights:
            recap_lines.append(f"• {h}")
    recap_lines.append("")
    recap_lines.append(f"🔥 *Level:* {lvl}")
    recap_lines.append(f"📊 *Progress:* {xp_bar}  {int(ratio * 100)}%")
    recap_lines.append(f"⬆ XP to next: {max(0, int(xp_to_next - cur_xp))}")
    if shield_text:
        recap_lines.append("")
        recap_lines.append(shield_text)

    card_text = "\n".join(recap_lines)

    # Send card message (if chat_id known)
    try:
        if chat_id:
            bot.send_message(chat_id, card_text, parse_mode="Markdown")
        else:
            # fallback: DM attacker
            bot.send_message(sess.attacker_id, card_text, parse_mode="Markdown")
    except Exception as e:
        print("send_pvp_result_card error:", e)


# -------------------------
# Command /attack + callbacks
# -------------------------
def setup(bot: TeleBot):

    @bot.message_handler(commands=["attack"])
    def cmd_attack(message):
        attacker_id = message.from_user.id

        # VIP gating
        if not has_pvp_access(attacker_id):
            bot.reply_to(message, "🔒 PvP is currently VIP-only.")
            return

        defender_id = None

        # If the command is a reply, target that user
        if message.reply_to_message:
            defender_id = message.reply_to_message.from_user.id
        else:
            parts = message.text.split()
            if len(parts) <= 1:
                return show_target_menu(bot, message)
            query = parts[1].strip()
            # By @username
            if query.startswith("@"):
                found = None
                try:
                    found = db.get_user_by_username(query)
                except Exception:
                    # some db functions return tuple vs id — attempt both
                    found = db.get_user_by_username(query)
                # normalize
                if not found:
                    bot.reply_to(message, "User not found.")
                    return
                # if get_user_by_username returns row or (id, ...), handle
                if isinstance(found, (list, tuple)):
                    defender_id = found[0]
                else:
                    defender_id = found
            else:
                # Fuzzy name search
                matches = db.search_users_by_name(query)
                if not matches:
                    bot.reply_to(message, "No matching users found.")
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
            bot.reply_to(message, "Could not determine target.")
            return
        if defender_id == attacker_id:
            bot.reply_to(message, "You cannot attack yourself.")
            return
        if db.is_pvp_shielded(defender_id):
            bot.reply_to(message, "🛡 Target is shielded from raids.")
            return

        # Build player stats and start session
        attacker = db.get_user(attacker_id) or {}
        defender = db.get_user(defender_id) or {}

        a_stats = fight_session.build_player_stats_from_user(attacker)
        d_stats = fight_session.build_player_stats_from_user(defender)

        sess = fight_session.manager.create_pvp_session(attacker_id, a_stats, defender_id, d_stats)

        # Track message pointer for result card
        try:
            caption = build_caption(sess)
            kb = action_keyboard(attacker_id, sess.auto_mode)
            try:
                safe_send_gif(bot, message.chat.id, "assets/gifs/pvp_intro.gif")
            except:
                pass
            m = bot.send_message(message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)
            store = fight_session.manager._sessions.get(str(attacker_id), {})
            store["_last_msg"] = {"chat": message.chat.id, "msg": m.message_id}
            fight_session.manager._sessions[str(attacker_id)] = store
        except Exception as e:
            print("cmd_attack send error:", e)

        fight_session.manager.save_session(sess)
        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_challenges_received")


    # Target menu (Option B)
    def show_target_menu(bot: TeleBot, message):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Reply Attack", callback_data="pvp_menu:reply"))
        kb.add(types.InlineKeyboardButton("Search Name", callback_data="pvp_menu:search_name"))
        kb.add(types.InlineKeyboardButton("Search Username", callback_data="pvp_menu:search_username"))
        kb.add(types.InlineKeyboardButton("PvP Top", callback_data="pvp_menu:top"))
        kb.add(types.InlineKeyboardButton("Cancel", callback_data="pvp_menu:cancel"))
        bot.reply_to(message, "⚔️ *PvP Attack Options*\nChoose how to select your opponent:", parse_mode="Markdown", reply_markup=kb)


    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp_menu"))
    def cb_pvp_menu(call: types.CallbackQuery):
        act = call.data.split(":")[1]
        if act == "cancel":
            bot.answer_callback_query(call.id, "Cancelled.")
            return
        if act == "reply":
            bot.answer_callback_query(call.id, "Reply to a user's message and use /attack")
            return
        if act == "search_name":
            bot.answer_callback_query(call.id, "Use: /attack <name>")
            return
        if act == "search_username":
            bot.answer_callback_query(call.id, "Use: /attack @username")
            return
        if act == "top":
            bot.answer_callback_query(call.id, "Use /pvp_top and press Attack")
            return


    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp_select:"))
    def cb_pvp_select(call: types.CallbackQuery):
        try:
            _, attacker_str, defender_str = call.data.split(":")
            attacker_id = int(attacker_str)
            defender_id = int(defender_str)
        except Exception:
            bot.answer_callback_query(call.id, "Invalid selection.")
            return

        attacker = db.get_user(attacker_id) or {}
        defender = db.get_user(defender_id) or {}
        a_stats = fight_session.build_player_stats_from_user(attacker)
        d_stats = fight_session.build_player_stats_from_user(defender)
        sess = fight_session.manager.create_pvp_session(attacker_id, a_stats, defender_id, d_stats)

        caption = build_caption(sess)
        kb = action_keyboard(attacker_id, sess.auto_mode)
        m = bot.send_message(call.message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)
        store = fight_session.manager._sessions.get(str(attacker_id), {})
        store["_last_msg"] = {"chat": call.message.chat.id, "msg": m.message_id}
        fight_session.manager._sessions[str(attacker_id)] = store
        fight_session.manager.save_session(sess)
        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_challenges_received")
        bot.answer_callback_query(call.id, "Raid started!")


    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:act"))
    def cb_pvp_action(call: types.CallbackQuery):
        parts = call.data.split(":")
        if len(parts) < 4:
            bot.answer_callback_query(call.id, "Bad action.")
            return
        _, _, action, attacker_str = parts
        attacker_id = int(attacker_str)

        # Ensure only attacker can control their raid UI
        if call.from_user.id != attacker_id:
            bot.answer_callback_query(call.id, "Not your raid.", show_alert=True)
            return

        sess = fight_session.manager.load_session(attacker_id)
        if not sess:
            bot.answer_callback_query(call.id, "Raid session not found or expired.", show_alert=True)
            return

        chat_id = call.message.chat.id
        msg_id = call.message.message_id

        # Forfeit handling
        if action == "forfeit":
            sess.ended = True
            sess.winner = "defender"
            fight_session.manager.save_session(sess)
            summary = finalize_pvp(bot, sess)
            # send cinematic card
            send_pvp_result_card(bot, sess, summary)
            fight_session.manager.end_session(attacker_id)
            try:
                bot.edit_message_text("❌ You forfeited the raid.", chat_id, msg_id)
            except Exception:
                pass
            bot.answer_callback_query(call.id, "You forfeited the raid.")
            return

        # Auto mode toggle
        if action == "auto":
            sess.auto_mode = not sess.auto_mode
            fight_session.manager.save_session(sess)
            if sess.auto_mode:
                # run a few auto turns immediately for UX responsiveness
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

        # Normal actions
        if action not in ("attack", "block", "dodge", "charge"):
            bot.answer_callback_query(call.id, "Invalid action.")
            return

        # Resolve action through fight_session
        try:
            sess.resolve_attacker_action(action)
            fight_session.manager.save_session(sess)
        except Exception as e:
            print("resolve_attacker_action error:", e)

        caption = build_caption(sess)
        kb = action_keyboard(attacker_id, sess.auto_mode)
        safe_edit_message(bot, chat_id, msg_id, caption, kb)
        bot.answer_callback_query(call.id)

        if sess.ended:
            summary = finalize_pvp(bot, sess)
            send_pvp_result_card(bot, sess, summary)
            fight_session.manager.end_session(attacker_id)


    # Leaderboard and stats
    @bot.message_handler(commands=["pvp_top"])
    def cmd_pvp_top(message):
        top = db.get_top_pvp(10)
        if not top:
            bot.reply_to(message, "No PvP activity yet.")
            return
        lines = ["🏆 *Top PvP Players*"]
        for r in top:
            # db.get_top_pvp should return dict-like rows with name, elo, wins, losses, rank
            name = r.get("name") or r.get("display_name") or r.get("username") or f"User{r.get('user_id')}"
            lines.append(f"{r.get('rank')}. {name} — {r.get('elo')} ELO ({r.get('wins',0)}W/{r.get('losses',0)}L)")
        bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")


    @bot.message_handler(commands=["pvp_stats"])
    def cmd_pvp_stats(message):
        uid = message.from_user.id
        stats = db.get_pvp_stats(uid)
        if not stats:
            bot.reply_to(message, "No PvP stats found for you.")
            return
        shield_until = stats.get("shield_until", 0)
        shield_text = time.ctime(shield_until) if shield_until else "None"
        msg = (
            f"📊 *Your PvP Stats*\n"
            f"ELO: {stats.get('elo')}\n"
            f"Wins: {stats.get('wins')}\n"
            f"Losses: {stats.get('losses')}\n"
            f"Raids started: {stats.get('started')}\n"
            f"Defended: {stats.get('defended')}\n"
            f"Challenges received: {stats.get('challenges')}\n"
            f"Shield until: {shield_text}"
        )
        bot.reply_to(message, msg, parse_mode="Markdown")


# -------------------------
# Access utility & finishes
# -------------------------
def has_pvp_access(user_id: int) -> bool:
    # placeholder gating, use Redis/VIP later
    if PVP_FREE_MODE:
        return True
    # if db.has_vip is available, prefer that
    try:
        return db.is_vip(user_id)
    except Exception:
        return True
