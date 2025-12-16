# bot/handlers/pvp.py
# (UPDATED with Revenge Fury, cleaned revenge UI, pvp:rev support, Cleanup Option C)

import time
from typing import List, Dict, Any, Optional
from telebot import TeleBot, types

# Services
from services import pvp_targets
from services import pvp_stats
from services import fight_session_pvp as fight_session

import bot.db as db
from bot.handlers import pvp_ranking as ranking_module

BROWSE_PAGE_SIZE = 5
PVP_SHIELD_SECONDS = 3 * 3600
UI_EDIT_THROTTLE_SECONDS = 1.0
PVP_ELO_K = 32


# -------------------------
# Utility Helpers
# -------------------------
def get_display_name_from_row(u: Dict[str, Any]) -> str:
    if not u:
        return "Unknown"
    disp = u.get("display_name")
    uname = u.get("username")
    if disp:
        return disp
    if uname:
        return uname
    return f"User{u.get('user_id','?')}"


def hp_bar(cur: int, maxhp: int, width: int = 20) -> str:
    cur = max(0, int(cur))
    maxhp = maxhp or 1
    filled = int((cur / maxhp) * width)
    return "▓" * filled + "░" * (width - filled)


def safe_call(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception:
        return None


# -------------------------
# Action Keyboard
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
# Caption Builder
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
        "",
    ]

    ev = sess.events[:6]
    if ev:
        lines.append("*Recent actions:*")
        for e in ev:
            actor = a_name if e["actor"] == "attacker" else d_name
            if e["action"] == "attack" and e.get("damage") is not None:
                lines.append(f"• {actor} dealt {e['damage']} dmg {e.get('note','')}".strip())
            else:
                note = f" {e.get('note','')}" if e.get("note") else ""
                lines.append(f"• {actor}: {e['action']}{note}")

    return "\n".join(lines)


# -------------------------
# Finalize PvP (Fallback)
# -------------------------
# (UNCHANGED – excluded here to save tokens)
# -------------------------
# send_result_card()
# (UNCHANGED)
# -------------------------
# menu_main_markup(), markup_back()
# (UNCHANGED)
# -------------------------

def setup(bot: TeleBot):
    globals()["bot_instance"] = bot

    # -------------------------
    # /pvp entry point
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
        bot.reply_to(message, text, parse_mode="Markdown", reply_markup=menu_main_markup(user_id))


    # -------------------------
    # MENU CALLBACKS
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:menu"))
    def cb_pvp_menu(call):
        parts = call.data.split(":")
        _, _, sub = parts[:3]
        target_user_id = int(parts[-1])

        if call.from_user.id != target_user_id:
            return bot.answer_callback_query(call.id, "Not your PvP menu.", show_alert=True)

        # ---------- MAIN ----------
        if sub == "main":
            me = db.get_user(target_user_id) or {}
            elo = int(me.get("elo_pvp", 1000))
            rank_name, _ = ranking_module.elo_to_rank(elo)
            text = (
                "⚔️ *MEGAGROK PvP ARENA*\n\n"
                f"Welcome, {get_display_name_from_row(me)}!\n\n"
                f"📈 Rank: *{rank_name}* — ELO: *{elo}*\n\n"
                "Choose an option:"
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=menu_main_markup(target_user_id))
            return bot.answer_callback_query(call.id)

        # ---------- REVENGE PANEL ----------
        if sub == "revenge":
            revs = pvp_targets.get_revenge_targets(target_user_id)
            if not revs:
                text = "🔥 *Revenge Targets*\n\nNo recent attackers found."
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                      parse_mode="Markdown", reply_markup=markup_back(target_user_id))
                return bot.answer_callback_query(call.id)

            lines = ["🔥 *Revenge Targets*",""]
            for r in revs:
                name = r["display_name"]
                time_ago = r["time_ago"]
                xp = r["xp_stolen"]
                lines.append(f"• {name} | {time_ago} | +{xp} XP stolen")

            kb = types.InlineKeyboardMarkup(row_width=1)
            for r in revs:
                kb.add(types.InlineKeyboardButton(
                    f"Revenge {r['display_name']}",
                    callback_data=f"pvp:rev:{target_user_id}:{r['user_id']}"
                ))

            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{target_user_id}"))

            bot.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=kb)
            return bot.answer_callback_query(call.id)

        # ---------- RECOMMENDED ----------
        if sub == "recommended":
            recs = pvp_targets.get_recommended_targets(target_user_id)
            if not recs:
                bot.edit_message_text(
                    "🎯 *Recommended Targets*\n\nNo recommended players found.",
                    call.message.chat.id, call.message.message_id,
                    parse_mode="Markdown", reply_markup=markup_back(target_user_id)
                )
                return bot.answer_callback_query(call.id)

            lines = ["🎯 *Recommended Targets*",""]
            for r in recs:
                lines.append(
                    f"• {r['display_name']} — Level {r['level']} — Power {r['power']} — {r['rank']}"
                )

            kb = types.InlineKeyboardMarkup(row_width=1)
            for r in recs:
                kb.add(types.InlineKeyboardButton(
                    f"Attack {r['display_name']} (Power {r['power']})",
                    callback_data=f"pvp:rec:{target_user_id}:{r['user_id']}"
                ))

            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{target_user_id}"))

            bot.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=kb)
            return bot.answer_callback_query(call.id)

        # ---------- SHIELDED ----------
        if sub == "shielded":
            all_users = safe_call(db.get_all_users) or []
            now = int(time.time())
            shielded = [u for u in all_users if int(u.get("pvp_shield_until", 0)) > now]

            if not shielded:
                bot.edit_message_text(
                    "🛡 *Shielded Players*\n\nNo players are currently shielded.",
                    call.message.chat.id, call.message.message_id,
                    parse_mode="Markdown", reply_markup=markup_back(target_user_id)
                )
                return bot.answer_callback_query(call.id)

            lines = ["🛡 *Shielded Players*",""]
            for u in shielded:
                rem = max(0, int(u["pvp_shield_until"]) - int(time.time()))
                hh = rem // 3600
                mm = (rem % 3600) // 60
                lines.append(f"• {get_display_name_from_row(u)} — {hh}h {mm}m remaining")

            bot.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=markup_back(target_user_id))
            return bot.answer_callback_query(call.id)

        # ---------- BROWSE ----------
        if sub == "browse":
            try:
                page = int(parts[3])
            except:
                page = 1

            all_users = safe_call(db.get_all_users) or []
            all_users_sorted = sorted(
                all_users,
                key=lambda u: (u.get("display_name") or u.get("username") or f"User{u.get('user_id')}").lower()
            )

            page_users, page, pages = browse_page_from_all(all_users_sorted, page, BROWSE_PAGE_SIZE)

            lines = [f"📜 *Browse Players (A–Z)*", f"Page {page}/{pages}",""]
            for u in page_users:
                power = pvp_targets.calculate_power({
                    "hp": u.get("hp", 100),
                    "attack": u.get("attack", 10),
                    "defense": u.get("defense", 5)
                })
                lines.append(f"• {get_display_name_from_row(u)} — Level {u.get('level',1)} — Power {power}")

            bot.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=build_browse_kb(page_users, page, pages, target_user_id))
            return bot.answer_callback_query(call.id)

        # ---------- HELP ----------
        if sub == "help":
            text = "❓ *PvP Help*\n\nChoose a help topic:"
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(types.InlineKeyboardButton("📘 How PvP Works", callback_data=f"pvp:help:how:{target_user_id}"))
            kb.add(types.InlineKeyboardButton("📜 PvP Commands", callback_data=f"pvp:help:commands:{target_user_id}"))
            kb.add(types.InlineKeyboardButton("🎓 PvP Tutorial", callback_data=f"pvp:help:tutorial:{target_user_id}"))
            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{target_user_id}"))

            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=kb)
            return bot.answer_callback_query(call.id)

        # ---------- STATS ----------
        if sub == "stats":
            text = "📊 *PvP Stats & Leaderboards*\n\nChoose a category:"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=stats_menu_markup(target_user_id))
            return bot.answer_callback_query(call.id)

        # fallback
        return bot.answer_callback_query(call.id, "Unknown menu action")


    # -------------------------
    # HELP CALLBACKS
    # (UNCHANGED)
    # -------------------------

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:help"))
    def cb_pvp_help(call):
        # unchanged help logic…
        pass  # OMITTED FOR BREVITY (same as your file)


    # -------------------------
    # STATS CALLBACKS
    # (UNCHANGED)
    # -------------------------

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:stats"))
    def cb_pvp_stats(call):
        # unchanged stats logic…
        pass  # OMITTED FOR BREVITY (same as your file)


    # -------------------------
    # START DUEL CALLBACK
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:rec") or c.data.startswith("pvp:rev"))
    def cb_start_duel(call):
        parts = call.data.split(":")
        typ = parts[1]           # "rec" or "rev"
        attacker_id = int(parts[2])
        defender_id = int(parts[3])

        if call.from_user.id != attacker_id:
            return bot.answer_callback_query(call.id, "Not your action.", show_alert=True)

        if db.is_pvp_shielded(defender_id):
            return bot.answer_callback_query(call.id, "That user is shielded.", show_alert=True)

        # ---------- DETECT REVENGE MODE ----------
        is_revenge = (typ == "rev")

        # ---------- REMOVE OLD MENU UI ----------
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except:
            pass

        # Build fighter stats
        attacker = db.get_user(attacker_id) or {}
        defender = db.get_user(defender_id) or {}
        a_stats = pvp_stats.build_pvp_stats(attacker)
        d_stats = pvp_stats.build_pvp_stats(defender)

        a_stats["display_name"] = attacker.get("display_name") or attacker.get("username")
        d_stats["display_name"] = defender.get("display_name") or defender.get("username")

        # ---------- CREATE SESSION WITH FURY FLAG ----------
        sess = fight_session.manager.create_pvp_session(
            attacker_id,
            defender_id,
            a_stats,
            d_stats,
            revenge_fury=is_revenge
        )

        # Clear revenge logs once revenge attack begins
        if is_revenge:
            pvp_targets.clear_revenge_for(attacker_id, defender_id)

        # Start fight UI
        m = bot.send_message(
            call.message.chat.id,
            build_caption(sess),
            parse_mode="Markdown",
            reply_markup=action_keyboard(sess)
        )

        sess._last_msg = {"chat": m.chat.id, "msg": m.message_id}
        sess._last_ui_edit = 0
        fight_session.manager.save_session(sess)

        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_challenges_received")

        return bot.answer_callback_query(call.id, "Raid started!")


    # -------------------------
    # ACTION CALLBACKS (fight turns)
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:act"))
    def cb_pvp_action(call):
        try:
            _, _, action, token = call.data.split(":")
        except:
            return bot.answer_callback_query(call.id, "Invalid action.")

        sess = fight_session.manager.load_session_by_sid(token) or \
               fight_session.manager.load_session(int(token))

        if not sess:
            return bot.answer_callback_query(call.id, "Session expired.", show_alert=True)

        if call.from_user.id != sess.attacker_id:
            return bot.answer_callback_query(call.id, "Not your raid.", show_alert=True)

        chat_id = sess._last_msg["chat"]
        msg_id = sess._last_msg["msg"]

        # ---------- FORFEIT ----------
        if action == "forfeit":
            sess.ended = True
            sess.winner = "defender"
            fight_session.manager.save_session(sess)

            # finalize
            try:
                from bot.handlers.pvp import finalize_pvp as ext_finalize
                summary = ext_finalize(sess.attacker_id, sess.defender_id, sess)
            except:
                summary = finalize_pvp_local(sess.attacker_id, sess.defender_id, sess)

            send_result_card(bot, sess, summary)

            # ---------- CLEAN UP FIGHT UI ----------
            try:
                bot.delete_message(chat_id, msg_id)
            except:
                pass

            fight_session.manager.end_session_by_sid(sess.session_id)
            return bot.answer_callback_query(call.id, "You forfeited.")

        # ---------- NORMAL TURN ----------
        sess.resolve_attacker_action(action)
        fight_session.manager.save_session(sess)

        # ---------- FIGHT END ----------
        if sess.ended:
            try:
                from bot.handlers.pvp import finalize_pvp as ext_finalize
                summary = ext_finalize(sess.attacker_id, sess.defender_id, sess)
            except:
                summary = finalize_pvp_local(sess.attacker_id, sess.defender_id, sess)

            send_result_card(bot, sess, summary)

            # ---------- CLEANUP UI ----------
            try:
                bot.delete_message(chat_id, msg_id)
            except:
                pass

            fight_session.manager.end_session_by_sid(sess.session_id)
            return bot.answer_callback_query(call.id)

        # ---------- UPDATE UI ----------
        now = time.time()
        if now - sess._last_ui_edit >= UI_EDIT_THROTTLE_SECONDS:
            try:
                bot.edit_message_text(
                    build_caption(sess),
                    chat_id, msg_id,
                    parse_mode="Markdown",
                    reply_markup=action_keyboard(sess)
                )
                sess._last_ui_edit = now
                fight_session.manager.save_session(sess)
            except:
                try:
                    bot.send_message(
                        chat_id,
                        build_caption(sess),
                        parse_mode="Markdown",
                        reply_markup=action_keyboard(sess)
                    )
                except:
                    pass

        return bot.answer_callback_query(call.id)

# end of file
