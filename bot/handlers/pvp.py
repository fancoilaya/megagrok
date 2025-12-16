# bot/handlers/pvp.py
# FINAL CLEAN VERSION — auto-registering, working, optimized

import time
from typing import List, Dict, Any
from telebot import TeleBot, types

# Services
from services import pvp_targets
from services import pvp_stats
from services import fight_session_pvp as fight_session

# Database
import bot.db as db
from bot.handlers import pvp_ranking as ranking_module


# -------------------------------------------
# CONFIG
# -------------------------------------------
BROWSE_PAGE_SIZE = 5
PVP_SHIELD_SECONDS = 3 * 3600
PVP_ELO_K = 32
UI_EDIT_THROTTLE_SECONDS = 1.0


# -------------------------------------------
# UTILITIES
# -------------------------------------------
def safe(fn, *a, **k):
    try:
        return fn(*a, **k)
    except:
        return None


def name_of(u: Dict[str, Any]) -> str:
    if not u:
        return "Unknown"
    return u.get("display_name") or u.get("username") or f"User{u.get('user_id')}"


def hp_bar(cur, maxhp, width=20):
    cur = max(0, int(cur))
    maxhp = max(1, int(maxhp))
    filled = int((cur / maxhp) * width)
    return "▓" * filled + "░" * (width - filled)


# -------------------------------------------
# SIMPLE / CLEAN MENUS
# -------------------------------------------
def menu_main_markup(user_id: int):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔥 Revenge", callback_data=f"pvp:menu:revenge:{user_id}"),
        types.InlineKeyboardButton("🎯 Recommended", callback_data=f"pvp:menu:recommended:{user_id}"),
    )
    kb.add(
        types.InlineKeyboardButton("🛡 Shielded", callback_data=f"pvp:menu:shielded:{user_id}"),
        types.InlineKeyboardButton("📜 Browse", callback_data=f"pvp:menu:browse:1:{user_id}"),
    )
    kb.add(
        types.InlineKeyboardButton("❓ Help", callback_data=f"pvp:menu:help:{user_id}"),
        types.InlineKeyboardButton("📊 Stats", callback_data=f"pvp:menu:stats:{user_id}")
    )
    return kb


def markup_back(user_id: int):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))
    return kb


# -------------------------------------------
# BROWSE HELPERS
# -------------------------------------------
def browse_page(all_users, page, size=BROWSE_PAGE_SIZE):
    total = len(all_users)
    pages = max(1, (total + size - 1) // size)
    page = max(1, min(page, pages))
    start = (page - 1) * size
    return all_users[start:start + size], page, pages


def browse_keyboard(users, page, pages, user_id):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for u in users:
        power = pvp_targets.calculate_power({
            "hp": u.get("hp", 100),
            "attack": u.get("attack", 10),
            "defense": u.get("defense", 5)
        })
        kb.add(types.InlineKeyboardButton(
            f"Attack {name_of(u)} (Power {power})",
            callback_data=f"pvp:rec:{user_id}:{u['user_id']}"
        ))
    row = []
    if page > 1:
        row.append(types.InlineKeyboardButton("⏮ Prev", callback_data=f"pvp:menu:browse:{page-1}:{user_id}"))
    if page < pages:
        row.append(types.InlineKeyboardButton("Next ⏭", callback_data=f"pvp:menu:browse:{page+1}:{user_id}"))
    if row:
        kb.add(*row)
    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))
    return kb


# -------------------------------------------
# CAPTION BUILDER (fight UI)
# -------------------------------------------
def build_caption(sess):
    a = sess.attacker
    d = sess.defender
    a_name = name_of(a)
    d_name = name_of(d)
    a_hp = int(a.get("hp", 100))
    d_hp = int(d.get("hp", 100))
    a_max = int(a.get("max_hp", a_hp))
    d_max = int(d.get("max_hp", d_hp))

    lines = [
        f"⚔️ *PvP Raid:* {a_name} vs {d_name}",
        "",
        f"{a_name}: {hp_bar(a_hp, a_max)} {a_hp}/{a_max}",
        f"{d_name}: {hp_bar(d_hp, d_max)} {d_hp}/{d_max}",
        "",
        f"Turn: {sess.turn}",
        ""
    ]

    if sess.events:
        lines.append("*Recent actions:*")
        for e in sess.events[:6]:
            who = a_name if e["actor"] == "attacker" else d_name
            if e["action"] == "attack":
                lines.append(f"• {who} dealt {e['damage']} dmg {e['note']}".strip())
            else:
                note = f" {e['note']}" if e["note"] else ""
                lines.append(f"• {who}: {e['action']}{note}")

    return "\n".join(lines)


# -------------------------------------------
# RESULT CARD
# -------------------------------------------
def send_result(bot, sess, summary):
    attacker = db.get_user(sess.attacker_id) or {}
    defender = db.get_user(sess.defender_id) or {}
    a_name = name_of(attacker)
    d_name = name_of(defender)

    a_hp = summary["attacker_hp"]
    d_hp = summary["defender_hp"]

    win = sess.winner == "attacker"

    card = []
    if win:
        card.append("🏆 *VICTORY!*")
        card.append(f"You defeated *{d_name}*")
        card.append(f"🎁 XP Stolen: +{summary['xp_stolen']}")
    else:
        card.append("💀 *DEFEAT*")
        card.append(f"You were repelled by *{d_name}*")
        card.append(f"📉 XP Lost: -{summary['xp_stolen']}")

    card.append(f"🏅 ELO Change: {summary['elo_change']:+d}")
    card.append("")
    card.append(f"❤️ {a_name}: {hp_bar(a_hp, a_hp, 12)} {a_hp}")
    card.append(f"💀 {d_name}: {hp_bar(d_hp, d_hp, 12)} {d_hp}")
    card.append("")
    card.append("*Highlights:*")

    best = summary["best_hits"]
    if best["attacker"]["damage"]:
        card.append(f"💥 Your best hit: {best['attacker']['damage']}")
    if best["defender"]["damage"]:
        card.append(f"💢 Enemy best hit: {best['defender']['damage']}")

    bot.send_message(sess._last_msg["chat"], "\n".join(card), parse_mode="Markdown")


# -------------------------------------------
# ACTION KEYBOARD
# -------------------------------------------
def action_keyboard(sess):
    sid = sess.session_id
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=f"pvp:act:attack:{sid}"),
        types.InlineKeyboardButton("🛡 Block", callback_data=f"pvp:act:block:{sid}")
    )
    kb.add(
        types.InlineKeyboardButton("💨 Dodge", callback_data=f"pvp:act:dodge:{sid}"),
        types.InlineKeyboardButton("⚡ Charge", callback_data=f"pvp:act:charge:{sid}")
    )
    kb.add(
        types.InlineKeyboardButton("💉 Heal", callback_data=f"pvp:act:heal:{sid}"),
        types.InlineKeyboardButton("❌ Forfeit", callback_data=f"pvp:act:forfeit:{sid}")
    )
    return kb


# -------------------------------------------
# /pvp ENTRY POINT
# -------------------------------------------
@bot_instance.message_handler(commands=["pvp"])
def cmd_pvp(message):
    user_id = message.from_user.id
    me = db.get_user(user_id) or {}
    elo = int(me.get("elo_pvp", 1000))
    rank_name, _ = ranking_module.elo_to_rank(elo)

    text = (
        "⚔️ *MEGAGROK PvP ARENA*\n\n"
        f"Welcome, {name_of(me)}!\n"
        f"📈 Rank: *{rank_name}* — ELO: *{elo}*\n\n"
        "Choose an option:"
    )

    bot_instance.reply_to(message, text, parse_mode="Markdown", reply_markup=menu_main_markup(user_id))


# -------------------------------------------
# MENU CALLBACK HANDLER
# -------------------------------------------
@bot_instance.callback_query_handler(func=lambda c: c.data.startswith("pvp:menu"))
def cb_pvp_menu(call):
    parts = call.data.split(":")
    sub = parts[2]
    user_id = int(parts[-1])

    if call.from_user.id != user_id:
        return bot_instance.answer_callback_query(call.id, "Not your menu.", show_alert=True)

    # MAIN PANEL
    if sub == "main":
        u = db.get_user(user_id)
        elo = int(u.get("elo_pvp", 1000))
        rank, _ = ranking_module.elo_to_rank(elo)
        text = (
            "⚔️ *MEGAGROK PvP ARENA*\n\n"
            f"Welcome, {name_of(u)}!\n"
            f"📈 Rank: *{rank}* — ELO: *{elo}*\n\n"
            "Choose an option:"
        )
        return bot_instance.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                              parse_mode="Markdown", reply_markup=menu_main_markup(user_id))

    # REVENGE
    if sub == "revenge":
        revs = pvp_targets.get_revenge_targets(user_id)
        if not revs:
            txt = "🔥 *Revenge Targets*\n\nNo recent attackers."
            return bot_instance.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                                                  parse_mode="Markdown", reply_markup=markup_back(user_id))

        lines = ["🔥 *Revenge Targets*",""]
        kb = types.InlineKeyboardMarkup(row_width=1)

        for r in revs[:5]:
            lines.append(f"• {r['display_name']} | {r['time_ago']} | +{r['xp_stolen']} XP stolen")
            kb.add(types.InlineKeyboardButton(
                f"Revenge {r['display_name']}",
                callback_data=f"pvp:rev:{user_id}:{r['user_id']}"
            ))

        kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))

        return bot_instance.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id,
                                              parse_mode="Markdown", reply_markup=kb)

    # RECOMMENDED
    if sub == "recommended":
        recs = pvp_targets.get_recommended_targets(user_id)
        if not recs:
            txt = "🎯 *Recommended Targets*\n\nNone found."
            return bot_instance.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                                                  parse_mode="Markdown", reply_markup=markup_back(user_id))

        lines = ["🎯 *Recommended Targets*",""]
        kb = types.InlineKeyboardMarkup(row_width=1)

        for r in recs:
            lines.append(f"• {r['display_name']} — Lv {r['level']} — Power {r['power']} — {r['rank']}")
            kb.add(types.InlineKeyboardButton(
                f"Attack {r['display_name']}",
                callback_data=f"pvp:rec:{user_id}:{r['user_id']}"
            ))

        kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))

        return bot_instance.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id,
                                              parse_mode="Markdown", reply_markup=kb)

    # SHIELDED
    if sub == "shielded":
        now = int(time.time())
        all_users = safe(db.get_all_users) or []
        shielded = [u for u in all_users if int(u.get("pvp_shield_until", 0)) > now]

        if not shielded:
            txt = "🛡 *Shielded Players*\n\nNo shielded players."
            return bot_instance.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                                                  parse_mode="Markdown", reply_markup=markup_back(user_id))

        lines = ["🛡 *Shielded Players*",""]
        for u in shielded:
            rem = int(u["pvp_shield_until"]) - now
            hh = rem // 3600
            mm = (rem % 3600)//60
            lines.append(f"• {name_of(u)} — {hh}h {mm}m")

        return bot_instance.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id,
                                              parse_mode="Markdown", reply_markup=markup_back(user_id))

    # BROWSE
    if sub == "browse":
        page = int(parts[3])
        all_users = safe(db.get_all_users) or []

        all_users.sort(key=lambda u: (name_of(u).lower()))
        page_users, page, pages = browse_page(all_users, page)

        lines = [f"📜 *Browse Players* Page {page}/{pages}",""]
        for u in page_users:
            power = pvp_targets.calculate_power({
                "hp": u.get("hp", 100),
                "attack": u.get("attack", 10),
                "defense": u.get("defense", 5),
            })
            lines.append(f"• {name_of(u)} — Lv {u.get('level',1)} — Power {power}")

        return bot_instance.edit_message_text("\n".join(lines),
                                              call.message.chat.id,
                                              call.message.message_id,
                                              parse_mode="Markdown",
                                              reply_markup=browse_keyboard(page_users, page, pages, user_id))

    # HELP
    if sub == "help":
        text = "❓ *PvP Help*\n\nUse /pvp to open the arena.\nChoose Recommended or Revenge to fight smarter."
        return bot_instance.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                              parse_mode="Markdown", reply_markup=markup_back(user_id))

    # STATS
    if sub == "stats":
        u = db.get_user(user_id)
        p = db.get_pvp_stats(user_id)
        rank, _ = ranking_module.elo_to_rank(int(u.get("elo_pvp", 1000)))

        text = (
            f"📊 *Your PvP Stats* — {name_of(u)}\n\n"
            f"🏅 Rank: {rank} — ELO {u.get('elo_pvp', 1000)}\n"
            f"🏆 Wins: {p.get('wins',0)}   📉 Losses: {p.get('losses',0)}\n"
            f"🛡 Successful Def: {p.get('successful_def',0)}\n"
            f"⚔️ Fights Started: {p.get('started',0)}"
        )

        return bot_instance.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                              parse_mode="Markdown", reply_markup=markup_back(user_id))


# -------------------------------------------
# DUEL START CALLBACK
# -------------------------------------------
@bot_instance.callback_query_handler(func=lambda c: c.data.startswith("pvp:rec") or c.data.startswith("pvp:rev"))
def cb_start_duel(call):
    parts = call.data.split(":")
    typ = parts[1]
    attacker_id = int(parts[2])
    defender_id = int(parts[3])

    if call.from_user.id != attacker_id:
        return bot_instance.answer_callback_query(call.id, "Not your action.", show_alert=True)

    if db.is_pvp_shielded(defender_id):
        return bot_instance.answer_callback_query(call.id, "Target is shielded.", show_alert=True)

    # Remove old menu UI
    try:
        bot_instance.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except:
        pass

    attacker = db.get_user(attacker_id)
    defender = db.get_user(defender_id)

    a_stats = pvp_stats.build_pvp_stats(attacker)
    d_stats = pvp_stats.build_pvp_stats(defender)

    is_revenge = (typ == "rev")

    sess = fight_session.manager.create_pvp_session(
        attacker_id, defender_id, a_stats, d_stats, revenge_fury=is_revenge
    )

    if is_revenge:
        pvp_targets.clear_revenge_for(attacker_id, defender_id)

    m = bot_instance.send_message(
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

    return bot_instance.answer_callback_query(call.id, "Raid started!")


# -------------------------------------------
# ACTION HANDLER (turns)
# -------------------------------------------
@bot_instance.callback_query_handler(func=lambda c: c.data.startswith("pvp:act"))
def cb_turn(call):
    parts = call.data.split(":")
    if len(parts) != 4:
        return bot_instance.answer_callback_query(call.id, "Invalid action.")

    _, _, action, token = parts

    sess = fight_session.manager.load_session_by_sid(token)
    if not sess:
        return bot_instance.answer_callback_query(call.id, "Session expired.", show_alert=True)

    if call.from_user.id != sess.attacker_id:
        return bot_instance.answer_callback_query(call.id, "Not your raid.", show_alert=True)

    chat_id = sess._last_msg["chat"]
    msg_id = sess._last_msg["msg"]

    # FORFEIT
    if action == "forfeit":
        sess.ended = True
        sess.winner = "defender"
        fight_session.manager.save_session(sess)

        try:
            from bot.handlers.pvp import finalize_pvp as ext_final
            summary = ext_final(sess.attacker_id, sess.defender_id, sess)
        except:
            summary = fight_session.finalize_local(sess.attacker_id, sess.defender_id, sess)

        send_result(bot_instance, sess, summary)
        try: bot_instance.delete_message(chat_id, msg_id)
        except: pass

        fight_session.manager.end_session_by_sid(sess.session_id)
        return bot_instance.answer_callback_query(call.id)

    # NORMAL TURN
    sess.resolve_attacker_action(action)
    fight_session.manager.save_session(sess)

    # END?
    if sess.ended:
        try:
            from bot.handlers.pvp import finalize_pvp as ext_final
            summary = ext_final(sess.attacker_id, sess.defender_id, sess)
        except:
            summary = fight_session.finalize_local(sess.attacker_id, sess.defender_id, sess)

        send_result(bot_instance, sess, summary)
        try: bot_instance.delete_message(chat_id, msg_id)
        except: pass

        fight_session.manager.end_session_by_sid(sess.session_id)
        return bot_instance.answer_callback_query(call.id)

    # UPDATE UI
    now = time.time()
    if now - sess._last_ui_edit >= UI_EDIT_THROTTLE_SECONDS:
        try:
            bot_instance.edit_message_text(
                build_caption(sess),
                chat_id,
                msg_id,
                parse_mode="Markdown",
                reply_markup=action_keyboard(sess)
            )
        except:
            bot_instance.send_message(
                chat_id,
                build_caption(sess),
                parse_mode="Markdown",
                reply_markup=action_keyboard(sess)
            )
        sess._last_ui_edit = now
        fight_session.manager.save_session(sess)

    return bot_instance.answer_callback_query(call.id)

# END FILE
