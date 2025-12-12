# bot/handlers/pvp.py
# PvP Menu handler for MegaGrokbot
# - /pvp main menu (Revenge, Recommended, Shielded, Browse (alphabetical), Help)
# - Browse is alphabetical, paginated (5 players / page)
# - Uses services.pvp_targets, services.pvp_stats, services.fight_session_pvp
# - Integrates with safe finalize fallback if your project has finalize_pvp
#
# Install: place file at bot/handlers/pvp.py, restart bot. Call setup(bot) from main if you register manually.

import time
from typing import List, Dict, Any, Optional
from telebot import TeleBot, types

# Services (top-level /services)
from services import pvp_targets
from services import pvp_stats
from services import fight_session_pvp as fight_session

# bot package helpers
import bot.db as db
from bot.handlers import pvp_ranking as ranking_module

# -------------------------
# Config
# -------------------------
BROWSE_PAGE_SIZE = 5  # user requested: option A (5 per page)
PVP_SHIELD_SECONDS = 3 * 3600
UI_EDIT_THROTTLE_SECONDS = 1.0
PVP_ELO_K = 32

# -------------------------
# Utilities
# -------------------------
def get_display_name_from_row(u: Dict[str, Any]) -> str:
    if not u:
        return "Unknown"
    disp = u.get("display_name")
    uname = u.get("username")
    if disp and str(disp).strip():
        return str(disp)
    if uname and str(uname).strip():
        return str(uname)
    uid = u.get("user_id") or u.get("id") or "?"
    return f"User{uid}"

def hp_bar(cur: int, maxhp: int, width: int = 20) -> str:
    cur = max(0, int(cur))
    maxhp = max(1, int(maxhp))
    filled = int((cur / maxhp) * width)
    return "▓" * filled + "░" * (width - filled)

def safe_call(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception:
        return None

# -------------------------
# Action keyboard (same as before: Heal replaces Auto)
# -------------------------
def _action_cb(action: str, token: str) -> str:
    return f"pvp:act:{action}:{token}"

def action_keyboard(sess) -> types.InlineKeyboardMarkup:
    sid = getattr(sess, "session_id", None) or str(getattr(sess, "attacker_id", ""))
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=_action_cb("attack", sid)),
        types.InlineKeyboardButton("🛡 Block", callback_data=_action_cb("block", sid)),
    )
    kb.add(
        types.InlineKeyboardButton("💨 Dodge", callback_data=_action_cb("dodge", sid)),
        types.InlineKeyboardButton("⚡ Charge", callback_data=_action_cb("charge", sid)),
    )
    kb.add(
        types.InlineKeyboardButton("💉 Heal (20%)", callback_data=_action_cb("heal", sid)),
        types.InlineKeyboardButton("❌ Forfeit", callback_data=_action_cb("forfeit", sid)),
    )
    return kb

# -------------------------
# Caption builder for active session
# -------------------------
def build_caption(sess) -> str:
    a = getattr(sess, "attacker", {}) or {}
    d = getattr(sess, "defender", {}) or {}
    a_name = get_display_name_from_row(a)
    d_name = get_display_name_from_row(d)
    a_hp = int(a.get("hp", a.get("max_hp", 100)))
    d_hp = int(d.get("hp", d.get("max_hp", 100)))
    a_max = int(a.get("max_hp", a.get("hp", 100)))
    d_max = int(d.get("max_hp", d.get("hp", 100)))

    lines: List[str] = [
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
            actor = a_name if ev.get("actor") == "attacker" else d_name
            action = ev.get("action", "")
            dmg = ev.get("damage")
            note = ev.get("note", "")
            if action == "attack" and dmg is not None:
                lines.append(f"• {actor} dealt {dmg} dmg {note}".strip())
            else:
                note_str = f" {note}" if note else ""
                lines.append(f"• {actor}: {action}{note_str}")
    return "\n".join(lines)

# -------------------------
# PvP finalize fallback (safe)
# -------------------------
def finalize_pvp_local(attacker_id: int, defender_id: int, sess) -> Dict[str, Any]:
    """
    Safe fallback: update XP/ELO and log pvp attack if your codebase
    doesn't provide finalize_pvp. Non-invasive and tolerant.
    """
    attacker = db.get_user(attacker_id) or {}
    defender = db.get_user(defender_id) or {}

    attacker_won = getattr(sess, "winner", "") == "attacker"

    xp_stolen = 0
    if attacker_won:
        def_xp = int(defender.get("xp_total", 0) or 0)
        xp_stolen = max(int(def_xp * 0.07), 20)
        try:
            cursor = getattr(db, "cursor", None)
            conn = getattr(db, "conn", None)
            if cursor:
                cursor.execute("UPDATE users SET xp_total = xp_total - ?, xp_current = xp_current - ? WHERE user_id = ?",
                               (xp_stolen, xp_stolen, defender_id))
                cursor.execute("UPDATE users SET xp_total = xp_total + ?, xp_current = xp_current + ? WHERE user_id = ?",
                               (xp_stolen, xp_stolen, attacker_id))
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
        # small penalty to attacker on loss
        atk_xp = int(attacker.get("xp_total", 0) or 0)
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

    # ELO update (simple)
    atk_elo = int(attacker.get("elo_pvp", 1000) or 1000)
    dfd_elo = int(defender.get("elo_pvp", 1000) or 1000)

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
            dmg = int(ev.get("damage") or 0)
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

# -------------------------
# Send result card
# -------------------------
def send_result_card(bot, sess, summary: Dict[str, Any]):
    attacker_id = getattr(sess, "attacker_id", None)
    defender_id = getattr(sess, "defender_id", None)
    attacker = db.get_user(attacker_id) or {}
    defender = db.get_user(defender_id) or {}
    a_name = get_display_name_from_row(attacker)
    d_name = get_display_name_from_row(defender)

    a_hp = summary.get("attacker_hp", sess.attacker.get("hp", 0))
    d_hp = summary.get("defender_hp", sess.defender.get("hp", 0))

    win = getattr(sess, "winner", "") == "attacker"
    card: List[str] = []
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
    except Exception:
        pass

# -------------------------
# Menu builders
# -------------------------
def menu_main_markup(user_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔥 Revenge", callback_data=f"pvp:menu:revenge:{user_id}"),
        types.InlineKeyboardButton("🎯 Recommended", callback_data=f"pvp:menu:recommended:{user_id}"),
    )
    kb.add(
        types.InlineKeyboardButton("🛡 Shielded", callback_data=f"pvp:menu:shielded:{user_id}"),
        types.InlineKeyboardButton("📜 Browse Players", callback_data=f"pvp:menu:browse:1:{user_id}"),
    )
    kb.add(types.InlineKeyboardButton("❓ PvP Help", callback_data=f"pvp:menu:help:{user_id}"))
    return kb

def markup_back(user_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))
    return kb

# -------------------------
# Browse helpers (alphabetical)
# -------------------------
def browse_page_from_all(all_users: List[Dict[str, Any]], page: int, page_size: int = BROWSE_PAGE_SIZE):
    total = len(all_users)
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, pages))
    start = (page - 1) * page_size
    end = start + page_size
    return all_users[start:end], page, pages

def build_browse_kb(page_users: List[Dict[str, Any]], page: int, pages: int, user_id: int):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for u in page_users:
        uid = int(u.get("user_id"))
        name = get_display_name_from_row(u)
        power = pvp_targets.calculate_power({"hp": u.get("hp", 100), "attack": u.get("attack", 10), "defense": u.get("defense", 5)})
        kb.add(types.InlineKeyboardButton(f"Attack {name} (Power {power})", callback_data=f"pvp:rec:{user_id}:{uid}"))
    # navigation
    nav_row = []
    if page > 1:
        nav_row.append(types.InlineKeyboardButton("⏮ Prev", callback_data=f"pvp:menu:browse:{page-1}:{user_id}"))
    if page < pages:
        nav_row.append(types.InlineKeyboardButton("Next ⏭", callback_data=f"pvp:menu:browse:{page+1}:{user_id}"))
    if nav_row:
        kb.add(*nav_row)
    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))
    return kb

# -------------------------
# Setup - register handlers
# -------------------------
def setup(bot: TeleBot):
    globals()["bot_instance"] = bot

    @bot.message_handler(commands=["pvp"])
    def cmd_pvp(message):
        user_id = message.from_user.id
        # optional: mark active
        try:
            safe_call(db.touch_last_active, user_id)
        except Exception:
            pass

        # Build main menu
        me = db.get_user(user_id) or {}
        elo = int(me.get("elo_pvp", 1000))
        rank_name, _ = ranking_module.elo_to_rank(elo)
        text = f"⚔️ *MEGAGROK PvP ARENA*\n\nWelcome, {get_display_name_from_row(me)}!\n\n📈 Rank: *{rank_name}* — ELO: *{elo}*\n\nChoose an option:"
        kb = menu_main_markup(user_id)
        bot.reply_to(message, text, parse_mode="Markdown", reply_markup=kb)

    # Panel callbacks
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:menu"))
    def cb_pvp_menu(call):
        parts = call.data.split(":")
        # format: pvp:menu:<sub>:<arg1>:<arg2?>
        if len(parts) < 4:
            return bot.answer_callback_query(call.id, "Invalid menu.")
        _, _, sub = parts[:3]
        # last part is always the user_id who initiated
        try:
            target_user_id = int(parts[-1])
        except:
            return bot.answer_callback_query(call.id, "Invalid menu user.")
        # ensure only owner can trigger their menu actions
        if call.from_user.id != target_user_id:
            return bot.answer_callback_query(call.id, "Not your PvP menu.", show_alert=True)

        if sub == "main":
            # show main menu
            me = db.get_user(target_user_id) or {}
            elo = int(me.get("elo_pvp", 1000))
            rank_name, _ = ranking_module.elo_to_rank(elo)
            text = f"⚔️ *MEGAGROK PvP ARENA*\n\nWelcome, {get_display_name_from_row(me)}!\n\n📈 Rank: *{rank_name}* — ELO: *{elo}*\n\nChoose an option:"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=menu_main_markup(target_user_id))
            return bot.answer_callback_query(call.id)

        elif sub == "revenge":
            revs = pvp_targets.get_revenge_targets(target_user_id) or []
            if not revs:
                text = "🔥 *Revenge Targets*\n\nNo recent attackers found."
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup_back(target_user_id))
                return bot.answer_callback_query(call.id)
            lines = ["🔥 *Revenge Targets*",""]
            for r in revs[:10]:
                name = r.get("display_name") or r.get("username") or f"User{r.get('user_id')}"
                since = int((time.time() - int(r.get("ts", time.time()))) // 3600)
                lines.append(f"• {name} — {since}h ago — {r.get('xp_stolen',0)} XP")
            text = "\n".join(lines)
            kb = types.InlineKeyboardMarkup(row_width=1)
            for r in revs[:8]:
                uid = int(r.get("user_id"))
                name = r.get("display_name") or r.get("username") or f"User{uid}"
                kb.add(types.InlineKeyboardButton(f"Revenge {name}", callback_data=f"pvp:rec:{target_user_id}:{uid}"))
            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{target_user_id}"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
            return bot.answer_callback_query(call.id)

        elif sub == "recommended":
            recs = pvp_targets.get_recommended_targets(target_user_id) or []
            if not recs:
                text = "🎯 *Recommended Targets*\n\nNo recommended players found."
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup_back(target_user_id))
                return bot.answer_callback_query(call.id)
            lines = ["🎯 *Recommended Targets*",""]
            for r in recs[:12]:
                name = r.get("display_name") or r.get("username") or f"User{r.get('user_id')}"
                lines.append(f"• {name} — Level {r.get('level',1)} — Power {r.get('power')} — {r.get('rank')}")
            text = "\n".join(lines)
            kb = types.InlineKeyboardMarkup(row_width=1)
            for r in recs[:8]:
                uid = int(r.get("user_id"))
                name = r.get("display_name") or r.get("username") or f"User{uid}"
                kb.add(types.InlineKeyboardButton(f"Attack {name} (Power {r.get('power')})", callback_data=f"pvp:rec:{target_user_id}:{uid}"))
            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{target_user_id}"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
            return bot.answer_callback_query(call.id)

        elif sub == "shielded":
            # pull all users and filter shielded
            all_users = safe_call(db.get_all_users) or []
            now = int(time.time())
            shielded = []
            for u in all_users:
                if int(u.get("pvp_shield_until", 0) or 0) > now:
                    shielded.append(u)
            if not shielded:
                text = "🛡 *Shielded Players*\n\nNo players are currently shielded."
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup_back(target_user_id))
                return bot.answer_callback_query(call.id)
            lines = ["🛡 *Shielded Players*",""]
            for s in shielded[:50]:
                name = get_display_name_from_row(s)
                until = int(s.get("pvp_shield_until", 0) or 0)
                rem = max(0, until - int(time.time()))
                hh = rem // 3600
                mm = (rem % 3600) // 60
                lines.append(f"• {name} — {hh}h {mm}m")
            text = "\n".join(lines)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup_back(target_user_id))
            return bot.answer_callback_query(call.id)

        elif sub == "browse":
            # format: pvp:menu:browse:<page>:<user_id>
            if len(parts) < 5:
                return bot.answer_callback_query(call.id, "Invalid browse.")
            try:
                page = int(parts[3])
            except:
                page = 1
            all_users = safe_call(db.get_all_users) or []
            # sort alphabetically by display_name or username
            def sort_key(u):
                name = (u.get("display_name") or u.get("username") or f"User{u.get('user_id')}").lower()
                return name
            all_users_sorted = sorted(all_users, key=sort_key)
            page_users, page, pages = browse_page_from_all(all_users_sorted, page, BROWSE_PAGE_SIZE)
            # build text
            lines = [f"📜 *Browse Players (A–Z)*", f"Page {page}/{pages}", ""]
            for u in page_users:
                name = get_display_name_from_row(u)
                lvl = int(u.get("level", 1))
                power = pvp_targets.calculate_power({"hp": u.get("hp", 100), "attack": u.get("attack", 10), "defense": u.get("defense", 5)})
                lines.append(f"• {name} — Level {lvl} — Power {power}")
            text = "\n".join(lines)
            kb = build_browse_kb(page_users, page, pages, target_user_id)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
            return bot.answer_callback_query(call.id)

        elif sub == "help":
            text = "❓ *PvP Help*\n\nChoose a help topic:"
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(types.InlineKeyboardButton("📘 How PvP Works", callback_data=f"pvp:help:how:{target_user_id}"))
            kb.add(types.InlineKeyboardButton("📜 PvP Commands", callback_data=f"pvp:help:commands:{target_user_id}"))
            kb.add(types.InlineKeyboardButton("🎓 PvP Tutorial", callback_data=f"pvp:help:tutorial:{target_user_id}"))
            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{target_user_id}"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
            return bot.answer_callback_query(call.id)

        else:
            return bot.answer_callback_query(call.id, "Unknown menu action.")

    # Help callbacks
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:help"))
    def cb_pvp_help(call):
        parts = call.data.split(":")
        if len(parts) < 4:
            return bot.answer_callback_query(call.id, "Invalid help action.")
        _, _, topic, uid_str = parts
        try:
            user_id = int(uid_str)
        except:
            return bot.answer_callback_query(call.id, "Invalid.")
        if call.from_user.id != user_id:
            return bot.answer_callback_query(call.id, "Not your help menu.", show_alert=True)
        if topic == "how":
            text = ("📘 *How PvP Works*\n\n"
                    "You can challenge other groks. Winning gives XP and ELO changes. "
                    "Use the menu to find revenge targets, recommended matches, or browse players.")
            kb = markup_back(user_id)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
            return bot.answer_callback_query(call.id)
        if topic == "commands":
            text = ("📜 *PvP Commands*\n\n"
                    "/pvp — Open PvP menu\n"
                    "/pvp @username — Start a duel immediately vs target\n"
                    "/pvp_help — detailed help\n"
                    "/pvp_commands — command list")
            kb = markup_back(user_id)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
            return bot.answer_callback_query(call.id)
        if topic == "tutorial":
            # call your tutorial handler if present (safe attempt)
            try:
                from bot.handlers import pvp_tutorial
                return pvp_tutorial.show_tutorial_for_user(bot, call.message, user_id)
            except Exception:
                text = "🎓 PvP Tutorial is not available."
                kb = markup_back(user_id)
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
                return bot.answer_callback_query(call.id)
        return bot.answer_callback_query(call.id, "Unknown help topic.")

    # Attack/recommendation callbacks (start duel)
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:rec") or c.data.startswith("pvp:rev") or c.data.startswith("pvp:find"))
    def cb_start_duel(call):
        parts = call.data.split(":")
        # pvp:rec:<attacker_id>:<defender_id>
        if len(parts) < 4:
            return bot.answer_callback_query(call.id, "Invalid action.")
        typ = parts[1]
        try:
            attacker_id = int(parts[2])
            defender_id = int(parts[3])
        except:
            return bot.answer_callback_query(call.id, "Invalid IDs.")
        if call.from_user.id != attacker_id:
            return bot.answer_callback_query(call.id, "Not your action.", show_alert=True)
        if db.is_pvp_shielded(defender_id):
            return bot.answer_callback_query(call.id, "That user is shielded.", show_alert=True)

        attacker = db.get_user(attacker_id) or {}
        defender = db.get_user(defender_id) or {}
        a_stats = pvp_stats.build_pvp_stats(attacker)
        d_stats = pvp_stats.build_pvp_stats(defender)
        a_stats["display_name"] = attacker.get("display_name"); a_stats["username"] = attacker.get("username")
        d_stats["display_name"] = defender.get("display_name"); d_stats["username"] = defender.get("username")

        sess = fight_session.manager.create_pvp_session(attacker_id, defender_id, a_stats, d_stats)
        sess.attacker["hp"] = a_stats.get("hp")
        sess.defender["hp"] = d_stats.get("hp")
        m = bot.send_message(call.message.chat.id, build_caption(sess), parse_mode="Markdown", reply_markup=action_keyboard(sess))
        sess._last_msg = {"chat": m.chat.id, "msg": m.message_id}
        sess._last_ui_edit = 0
        fight_session.manager.save_session(sess)

        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_challenges_received")
        bot.answer_callback_query(call.id, "Raid started!")
        return

    # Action handler in active session (attack, block, dodge, charge, heal, forfeit)
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:act"))
    def cb_pvp_action(call):
        try:
            _, _, action, token = call.data.split(":")
        except Exception:
            return bot.answer_callback_query(call.id, "Invalid action.")

        # load session by sid first, then by attacker id
        sess = fight_session.manager.load_session_by_sid(token)
        if not sess:
            try:
                sess = fight_session.manager.load_session(int(token))
            except Exception:
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
            # try external finalize
            try:
                from bot.handlers.pvp import finalize_pvp as ext_finalize
                summary = ext_finalize(attacker_id, sess.defender_id, sess)
            except Exception:
                summary = finalize_pvp_local(attacker_id, sess.defender_id, sess)
            send_result_card(bot, sess, summary)
            fight_session.manager.end_session_by_sid(getattr(sess, "session_id", ""))
            return bot.answer_callback_query(call.id, "You forfeited.")

        # execute action via fight engine
        sess.resolve_attacker_action(action)
        fight_session.manager.save_session(sess)

        if sess.ended:
            # finalize
            try:
                from bot.handlers.pvp import finalize_pvp as ext_finalize
                summary = ext_finalize(attacker_id, sess.defender_id, sess)
            except Exception:
                summary = finalize_pvp_local(attacker_id, sess.defender_id, sess)
            send_result_card(bot, sess, summary)
            fight_session.manager.end_session_by_sid(getattr(sess, "session_id", ""))
        else:
            # update UI
            try:
                # throttle edits to avoid hitting API limits
                now = time.time()
                last = getattr(sess, "_last_ui_edit", 0)
                if now - last >= UI_EDIT_THROTTLE_SECONDS:
                    bot.edit_message_text(build_caption(sess), chat_id, msg_id, parse_mode="Markdown", reply_markup=action_keyboard(sess))
                    sess._last_ui_edit = time.time()
                    fight_session.manager.save_session(sess)
            except Exception:
                # fallback: send a fresh message
                try:
                    bot.send_message(chat_id, build_caption(sess), parse_mode="Markdown", reply_markup=action_keyboard(sess))
                except:
                    pass

        bot.answer_callback_query(call.id)

# end of file
