# bot/handlers/pvp.py
# CLEAN PATCHED VERSION — keeps your system EXACTLY, adds new features

import time
from typing import List, Dict, Any, Optional
from telebot import TeleBot, types

# Services
from services import pvp_targets
from services import pvp_stats
from services import fight_session_pvp as fight_session

import bot.db as db
from bot.handlers import pvp_ranking as ranking_module

# -------------------------
# Config
# -------------------------
BROWSE_PAGE_SIZE = 5
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
# UI for actions
# -------------------------
def _action_cb(action: str, token: str) -> str:
    return f"pvp:act:{action}:{token}"

def action_keyboard(sess) -> types.InlineKeyboardMarkup:
    sid = getattr(sess, "session_id") or str(sess.attacker_id)
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
# Caption builder
# -------------------------
def build_caption(sess) -> str:
    a = sess.attacker
    d = sess.defender
    a_name = get_display_name_from_row(a)
    d_name = get_display_name_from_row(d)
    a_hp = int(a.get("hp", a.get("max_hp", 100)))
    d_hp = int(d.get("hp", d.get("max_hp", 100)))
    a_max = int(a.get("max_hp", 100))
    d_max = int(d.get("max_hp", 100))

    lines = [
        f"⚔️ *PvP Raid:* {a_name} vs {d_name}",
        "",
        f"{a_name}: {hp_bar(a_hp, a_max)} {a_hp}/{a_max}",
        f"{d_name}: {hp_bar(d_hp, d_max)} {d_hp}/{d_max}",
        "",
        f"Turn: {sess.turn}",
        ""
    ]

    evs = sess.events[:6]
    if evs:
        lines.append("*Recent actions:*")
        for ev in evs:
            who = a_name if ev["actor"] == "attacker" else d_name
            if ev["action"] == "attack":
                lines.append(f"• {who} dealt {ev['damage']} dmg {ev.get('note','')}".strip())
            else:
                note = f" {ev.get('note', '')}" if ev.get("note") else ""
                lines.append(f"• {who}: {ev['action']}{note}")

    return "\n".join(lines)

# -------------------------
# Finalize fallback (unchanged)
# -------------------------
def finalize_pvp_local(att_id, def_id, sess):
    attacker = db.get_user(att_id) or {}
    defender = db.get_user(def_id) or {}
    attacker_won = sess.winner == "attacker"
    xp_stolen = 0

    if attacker_won:
        def_xp = int(defender.get("xp_total", 0))
        xp_stolen = max(int(def_xp * 0.07), 20)
        db.log_pvp_attack(att_id, def_id, xp_stolen, "win")
        db.set_pvp_shield(def_id, int(time.time()) + PVP_SHIELD_SECONDS)
        db.increment_pvp_field(att_id, "pvp_wins")
        db.increment_pvp_field(def_id, "pvp_losses")
    else:
        db.log_pvp_attack(att_id, def_id, 0, "fail")
        db.increment_pvp_field(att_id, "pvp_losses")
        db.increment_pvp_field(def_id, "pvp_wins")

    atk_elo = int(attacker.get("elo_pvp", 1000))
    def_elo = int(defender.get("elo_pvp", 1000))
    def expected(a, b): return 1 / (1 + 10 ** ((b - a) / 400))
    E = expected(atk_elo, def_elo)
    if attacker_won:
        new_atk = atk_elo + int(PVP_ELO_K * (1 - E))
        new_def = def_elo - int(PVP_ELO_K * (1 - E))
    else:
        new_atk = atk_elo + int(PVP_ELO_K * (0 - E))
        new_def = def_elo - int(PVP_ELO_K * (0 - E))

    db.update_elo(att_id, new_atk)
    db.update_elo(def_id, new_def)

    best = {"attacker": {"damage": 0}, "defender": {"damage": 0}}
    for ev in sess.events:
        if ev["action"] == "attack":
            if ev["actor"] == "attacker":
                best["attacker"]["damage"] = max(best["attacker"]["damage"], ev["damage"])
            else:
                best["defender"]["damage"] = max(best["defender"]["damage"], ev["damage"])

    return {
        "xp_stolen": xp_stolen,
        "elo_change": new_atk - atk_elo,
        "best_hits": best,
        "attacker_hp": sess.attacker.get("hp", 0),
        "defender_hp": sess.defender.get("hp", 0),
    }

# -------------------------
# Result card
# -------------------------
def send_result_card(bot, sess, summary):
    att = db.get_user(sess.attacker_id) or {}
    dfd = db.get_user(sess.defender_id) or {}
    a_name = get_display_name_from_row(att)
    d_name = get_display_name_from_row(dfd)

    a_hp = summary["attacker_hp"]
    d_hp = summary["defender_hp"]

    win = sess.winner == "attacker"

    out = []
    if win:
        out.append("🏆 *VICTORY!*")
        out.append(f"You defeated *{d_name}*")
        out.append(f"🎁 XP Stolen: +{summary['xp_stolen']}")
    else:
        out.append("💀 *DEFEAT*")
        out.append(f"You were repelled by *{d_name}*")
        out.append(f"📉 XP Lost: -{summary['xp_stolen']}")

    out.append(f"🏅 ELO Change: {summary['elo_change']:+d}")
    out.append("")
    out.append(f"❤️ {a_name}: {a_hp}")
    out.append(f"💀 {d_name}: {d_hp}")
    out.append("")

    best = summary["best_hits"]
    out.append("*Highlights:*")
    if best["attacker"]["damage"]:
        out.append(f"💥 Your best hit: {best['attacker']['damage']}")
    if best["defender"]["damage"]:
        out.append(f"💢 Enemy best hit: {best['defender']['damage']}")

    bot.send_message(sess._last_msg["chat"], "\n".join(out), parse_mode="Markdown")
# -------------------------
# Setup - register handlers
# -------------------------
def setup(bot: TeleBot):

    # -------------------------
    # /pvp menu
    # -------------------------
    @bot.message_handler(commands=["pvp"])
    def cmd_pvp(message):
        user_id = message.from_user.id
        me = db.get_user(user_id) or {}
        elo = int(me.get("elo_pvp", 1000))
        rank_name, _ = ranking_module.elo_to_rank(elo)

        text = (
            "⚔️ *MEGAGROK PvP ARENA*\n\n"
            f"Welcome, {get_display_name_from_row(me)}!\n\n"
            f"📈 Rank: *{rank_name}* — ELO: *{elo}*\n\n"
            "Choose an option:"
        )

        bot.reply_to(message, text, parse_mode="Markdown",
                     reply_markup=menu_main_markup(user_id))

    # -------------------------
    # MENU callbacks
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:menu"))
    def cb_pvp_menu(call):
        parts = call.data.split(":")
        _, _, sub = parts[:3]
        try:
            user_id = int(parts[-1])
        except:
            return bot.answer_callback_query(call.id, "Invalid menu user.")

        if call.from_user.id != user_id:
            return bot.answer_callback_query(call.id, "Not your menu.", show_alert=True)

        # MAIN
        if sub == "main":
            me = db.get_user(user_id) or {}
            elo = int(me.get("elo_pvp", 1000))
            rank_name, _ = ranking_module.elo_to_rank(elo)
            text = (
                "⚔️ *MEGAGROK PvP ARENA*\n\n"
                f"Welcome, {get_display_name_from_row(me)}!\n\n"
                f"📈 Rank: *{rank_name}* — ELO: *{elo}*\n\n"
                "Choose an option:"
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=menu_main_markup(user_id))
            return bot.answer_callback_query(call.id)

        # REVENGE
        elif sub == "revenge":
            revs = pvp_targets.get_revenge_targets(user_id)
            if not revs:
                txt = "🔥 *Revenge Targets*\n\nNo recent attackers."
                bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                                      parse_mode="Markdown", reply_markup=markup_back(user_id))
                return bot.answer_callback_query(call.id)

            lines = ["🔥 *Revenge Targets*",""]
            kb = types.InlineKeyboardMarkup(row_width=1)

            for r in revs:
                lines.append(f"• {r['display_name']} | {r['time_ago']} | +{r['xp_stolen']} XP stolen")
                kb.add(
                    types.InlineKeyboardButton(
                        f"Revenge {r['display_name']}",
                        callback_data=f"pvp:rev:{user_id}:{r['user_id']}"
                    )
                )

            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))

            bot.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=kb)
            return bot.answer_callback_query(call.id)

        # RECOMMENDED
        elif sub == "recommended":
            recs = pvp_targets.get_recommended_targets(user_id)
            if not recs:
                txt = "🎯 *Recommended Targets*\n\nNo recommended players."
                bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                                      parse_mode="Markdown", reply_markup=markup_back(user_id))
                return bot.answer_callback_query(call.id)

            lines = ["🎯 *Recommended Targets*",""]
            kb = types.InlineKeyboardMarkup(row_width=1)

            for r in recs:
                lines.append(
                    f"• {r['display_name']} — Level {r['level']} — Power {r['power']} — {r['rank']}"
                )
                kb.add(
                    types.InlineKeyboardButton(
                        f"Attack {r['display_name']} (Power {r['power']})",
                        callback_data=f"pvp:rec:{user_id}:{r['user_id']}"
                    )
                )

            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))
            bot.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=kb)
            return bot.answer_callback_query(call.id)

        # SHIELDED
        elif sub == "shielded":
            now = int(time.time())
            all_users = safe_call(db.get_all_users) or []
            shielded = [u for u in all_users if int(u.get("pvp_shield_until", 0)) > now]

            if not shielded:
                txt = "🛡 *Shielded Players*\n\nNone are shielded."
                bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                                      parse_mode="Markdown",
                                      reply_markup=markup_back(user_id))
                return bot.answer_callback_query(call.id)

            lines = ["🛡 *Shielded Players*",""]
            for u in shielded:
                rem = int(u["pvp_shield_until"]) - now
                hh = rem // 3600
                mm = (rem % 3600)//60
                lines.append(f"• {get_display_name_from_row(u)} — {hh}h {mm}m")

            bot.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown",
                                  reply_markup=markup_back(user_id))
            return bot.answer_callback_query(call.id)

        # BROWSE
        elif sub == "browse":
            page = int(parts[3])
            all_users = safe_call(db.get_all_users) or []
            all_users.sort(key=lambda u: get_display_name_from_row(u).lower())

            page_users, page, pages = browse_page_from_all(all_users, page)
            lines = [f"📜 *Browse Players* {page}/{pages}",""]

            for u in page_users:
                power = pvp_targets.calculate_power({
                    "hp": u.get("hp", 100),
                    "attack": u.get("attack", 10),
                    "defense": u.get("defense", 5)
                })
                lines.append(f"• {get_display_name_from_row(u)} — Level {u.get('level',1)} — Power {power}")

            bot.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown",
                                  reply_markup=build_browse_kb(page_users, page, pages, user_id))
            return bot.answer_callback_query(call.id)

        # HELP
        elif sub == "help":
            text = (
                "❓ *PvP Help*\n\n"
                "• Recommended: Players close to your level & power\n"
                "• Revenge: Fight back attackers\n"
                "• Shielded: Players under protection\n"
                "• Stats: Wins, losses, rank\n"
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=markup_back(user_id))
            return bot.answer_callback_query(call.id)

        # STATS
        elif sub == "stats":
            txt = build_user_stats_text(user_id)
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=markup_back(user_id))
            return bot.answer_callback_query(call.id)

        return bot.answer_callback_query(call.id)

    # -------------------------
    # DUEL START (rec / rev)
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:rec") or c.data.startswith("pvp:rev"))
    def cb_start_duel(call):
        parts = call.data.split(":")
        typ = parts[1]          # rec or rev
        attacker_id = int(parts[2])
        defender_id = int(parts[3])

        if call.from_user.id != attacker_id:
            return bot.answer_callback_query(call.id, "Not your action.", show_alert=True)
        if db.is_pvp_shielded(defender_id):
            return bot.answer_callback_query(call.id, "Target is shielded.", show_alert=True)

        # Collapse the menu UI
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except:
            pass

        attacker = db.get_user(attacker_id)
        defender = db.get_user(defender_id)
        a_stats = pvp_stats.build_pvp_stats(attacker)
        d_stats = pvp_stats.build_pvp_stats(defender)

        is_revenge = (typ == "rev")

        # Create session WITH fury flag
        sess = fight_session.manager.create_pvp_session(
            attacker_id,
            defender_id,
            a_stats,
            d_stats,
            revenge_fury=is_revenge  # <--- new flag
        )

        if is_revenge:
            # Clear revenge logs once revenge begins
            pvp_targets.clear_revenge_for(attacker_id, defender_id)

        m = bot.send_message(
            call.message.chat.id,
            build_caption(sess),
            parse_mode="Markdown",
            reply_markup=action_keyboard(sess),
        )

        sess._last_msg = {"chat": m.chat.id, "msg": m.message_id}
        sess._last_ui_edit = 0
        fight_session.manager.save_session(sess)

        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_challenges_received")

        return bot.answer_callback_query(call.id, "Raid started!")

    # -------------------------
    # ACTION handler
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:act"))
    def cb_pvp_action(call):
        try:
            _, _, action, token = call.data.split(":")
        except:
            return bot.answer_callback_query(call.id, "Invalid action.")

        sess = fight_session.manager.load_session_by_sid(token)
        if not sess:
            try:
                sess = fight_session.manager.load_session(int(token))
            except:
                sess = None

        if not sess:
            return bot.answer_callback_query(call.id, "Session expired.", show_alert=True)

        if call.from_user.id != sess.attacker_id:
            return bot.answer_callback_query(call.id, "Not your raid.", show_alert=True)

        chat_id = sess._last_msg["chat"]
        msg_id = sess._last_msg["msg"]

        # FORFEIT
        if action == "forfeit":
            sess.ended = True
            sess.winner = "defender"
            fight_session.manager.save_session(sess)

            try:
                from bot.handlers.pvp import finalize_pvp as ext_finalize
                summary = ext_finalize(sess.attacker_id, sess.defender_id, sess)
            except:
                summary = finalize_pvp_local(sess.attacker_id, sess.defender_id, sess)

            send_result_card(bot, sess, summary)

            # Cleanup UI
            try: bot.delete_message(chat_id, msg_id)
            except: pass

            fight_session.manager.end_session_by_sid(sess.session_id)
            return bot.answer_callback_query(call.id)

        # NORMAL TURN
        sess.resolve_attacker_action(action)
        fight_session.manager.save_session(sess)

        # END?
        if sess.ended:
            try:
                from bot.handlers.pvp import finalize_pvp as ext_finalize
                summary = ext_finalize(sess.attacker_id, sess.defender_id, sess)
            except:
                summary = finalize_pvp_local(sess.attacker_id, sess.defender_id, sess)

            send_result_card(bot, sess, summary)

            # Cleanup UI
            try: bot.delete_message(chat_id, msg_id)
            except: pass

            fight_session.manager.end_session_by_sid(sess.session_id)
            return bot.answer_callback_query(call.id)

        # UPDATE UI
        now = time.time()
        if now - sess._last_ui_edit >= UI_EDIT_THROTTLE_SECONDS:
            try:
                bot.edit_message_text(
                    build_caption(sess),
                    chat_id,
                    msg_id,
                    parse_mode="Markdown",
                    reply_markup=action_keyboard(sess),
                )
                sess._last_ui_edit = now
                fight_session.manager.save_session(sess)
            except:
                try:
                    bot.send_message(
                        chat_id,
                        build_caption(sess),
                        parse_mode="Markdown",
                        reply_markup=action_keyboard(sess),
                    )
                except:
                    pass

        return bot.answer_callback_query(call.id)

# end of file
