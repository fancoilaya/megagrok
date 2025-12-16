# bot/handlers/pvp.py
# CLEAN PATCHED VERSION — stable + improved Stats & Help menus + tutorial launch in new message

import time
from typing import List, Dict, Any
from telebot import TeleBot, types

# Services
from services import pvp_targets
from services import pvp_stats
from services import fight_session_pvp as fight_session

import bot.db as db
from bot.handlers import pvp_ranking as ranking_module
from bot.handlers import pvp_tutorial  # for tutorial launch

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
    if u.get("display_name"):
        return u["display_name"]
    if u.get("username"):
        return u["username"]
    return f"User{u.get('user_id','?')}"


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
        ""
    ]

    for ev in sess.events[:6]:
        actor = a_name if ev["actor"] == "attacker" else d_name
        if ev["action"] == "attack":
            lines.append(f"• {actor} dealt {ev['damage']} dmg {ev.get('note','')}".strip())
        else:
            note = f" {ev.get('note','')}" if ev.get("note") else ""
            lines.append(f"• {actor}: {ev['action']}{note}")

    return "\n".join(lines)


# -------------------------
# Finalize PvP (fallback)
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

    def expected(a, b):
        return 1 / (1 + 10 ** ((b - a) / 400))

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
            tgt = "attacker" if ev["actor"] == "attacker" else "defender"
            best[tgt]["damage"] = max(best[tgt]["damage"], ev["damage"])

    return {
        "xp_stolen": xp_stolen,
        "elo_change": new_atk - atk_elo,
        "best_hits": best,
        "attacker_hp": sess.attacker.get("hp", 0),
        "defender_hp": sess.defender.get("hp", 0),
    }


# -------------------------
# Result Card
# -------------------------
def send_result_card(bot, sess, summary):
    att = db.get_user(sess.attacker_id) or {}
    dfd = db.get_user(sess.defender_id) or {}
    a_name = get_display_name_from_row(att)
    d_name = get_display_name_from_row(dfd)

    out = []

    if sess.winner == "attacker":
        out.append("🏆 *VICTORY!*")
        out.append(f"You defeated *{d_name}*")
        out.append(f"🎁 XP Stolen: +{summary['xp_stolen']}")
    else:
        out.append("💀 *DEFEAT*")
        out.append(f"You were repelled by *{d_name}*")
        out.append(f"📉 XP Lost: -{summary['xp_stolen']}")

    out.append(f"🏅 ELO Change: {summary['elo_change']:+d}")
    out.append("")
    out.append(f"❤️ {a_name}: {summary['attacker_hp']}")
    out.append(f"💀 {d_name}: {summary['defender_hp']}")
    out.append("")
    out.append("*Highlights:*")

    best = summary["best_hits"]
    if best["attacker"]["damage"]:
        out.append(f"💥 Your best hit: {best['attacker']['damage']}")
    if best["defender"]["damage"]:
        out.append(f"💢 Enemy best hit: {best['defender']['damage']}")

    bot.send_message(sess._last_msg["chat"], "\n".join(out), parse_mode="Markdown")


# -------------------------
# Stats Menu Helpers (Improved Layout)
# -------------------------
def stats_menu_markup(user_id: int):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📈 Your PvP Stats", callback_data=f"pvp:stats:me:{user_id}"))
    kb.add(types.InlineKeyboardButton("🏆 Top PvP Players", callback_data=f"pvp:stats:top:{user_id}"))
    kb.add(types.InlineKeyboardButton("🥇 Win/Loss Rankings", callback_data=f"pvp:stats:wins:{user_id}"))
    kb.add(types.InlineKeyboardButton("🎖 Rank Tier Info", callback_data=f"pvp:stats:ranks:{user_id}"))
    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))
    return kb


def build_user_stats_text(user_id: int) -> str:
    u = db.get_user(user_id)
    p = db.get_pvp_stats(user_id)

    rank, _ = ranking_module.elo_to_rank(int(u.get("elo_pvp", 1000)))

    return (
        f"📈 *Your PvP Stats* — {get_display_name_from_row(u)}\n\n"
        f"🏅 Rank: *{rank}* — ELO {u.get('elo_pvp', 1000)}\n"
        f"🏆 Wins: {p.get('wins',0)}   📉 Losses: {p.get('losses',0)}\n"
        f"⚔️ Fights Started: {p.get('started',0)}\n"
        f"🛡 Successful Defenses: {p.get('successful_def',0)}\n"
        f"❌ Failed Defenses: {p.get('failed_def',0)}\n"
    )


def build_top_pvp_text(limit=10) -> str:
    rows = db.get_top_pvp(limit)
    text = ["🏆 *Top PvP Players*",""]
    for r in rows:
        text.append(f"{r['rank']}. {r['name']} — ELO {r['elo']} ({r['wins']}W/{r['losses']}L)")
    return "\n".join(text)


def build_wins_ranking_text(limit=10) -> str:
    all_users = safe_call(db.get_all_users) or []
    sorted_users = sorted(all_users, key=lambda u: int(u.get("pvp_wins", 0)), reverse=True)
    out = ["🥇 *Win/Loss Rankings*",""]
    rank = 1
    for u in sorted_users[:limit]:
        out.append(f"{rank}. {get_display_name_from_row(u)} — {u.get('pvp_wins',0)}W / {u.get('pvp_losses',0)}L")
        rank += 1
    return "\n".join(out)


def build_rank_info_text(user_id: int) -> str:
    u = db.get_user(user_id)
    elo = int(u.get("elo_pvp", 1000))
    rank, _ = ranking_module.elo_to_rank(elo)

    return (
        "🎖 *Rank Tier Information*\n\n"
        "🥉 Bronze: 0–999\n"
        "🥈 Silver: 1000–1299\n"
        "🥇 Gold: 1300–1499\n"
        "💎 Diamond: 1500+\n\n"
        f"Your Rank: *{rank}* — ELO {elo}"
    )


# -------------------------
# Help Menu
# -------------------------
def help_menu_markup(user_id: int):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📘 How PvP Works", callback_data=f"pvp:help:how:{user_id}"))
    kb.add(types.InlineKeyboardButton("📜 PvP Commands", callback_data=f"pvp:help:commands:{user_id}"))
    kb.add(types.InlineKeyboardButton("🎓 PvP Tutorial", callback_data=f"pvp:help:tutorial:{user_id}"))
    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))
    return kb


def help_text_how():
    return (
        "📘 *How PvP Works*\n\n"
        "• Choose opponents via Recommended, Browse, or Revenge.\n"
        "• Win battles to gain XP and ELO.\n"
        "• Losing costs XP.\n"
        "• Shield protects players from being attacked repeatedly.\n"
    )


def help_text_commands():
    return (
        "📜 *PvP Commands*\n\n"
        "/pvp — Open menu\n"
        "/pvp @user — Challenge user\n"
        "/pvp_help — Full help\n"
        "/pvp_commands — Command list\n"
        "/pvp_tutorial — Step-by-step tutorial\n"
    )


# -------------------------
# Setup
# -------------------------
def setup(bot: TeleBot):
    globals()["bot_instance"] = bot

    # /pvp command
    @bot.message_handler(commands=["pvp"])
    def cmd_pvp(message):
        user_id = message.from_user.id
        me = db.get_user(user_id) or {}
        rank, _ = ranking_module.elo_to_rank(int(me.get("elo_pvp", 1000)))

        text = (
            "⚔️ *MEGAGROK PvP ARENA*\n\n"
            f"Welcome, {get_display_name_from_row(me)}!\n\n"
            f"📈 Rank: *{rank}* — ELO: *{me.get('elo_pvp',1000)}*\n\n"
            "Choose an option:"
        )

        bot.reply_to(message, text, parse_mode="Markdown",
                     reply_markup=menu_main_markup(user_id))

    # MENU HANDLER
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:menu"))
    def cb_pvp_menu(call):
        parts = call.data.split(":")
        _, _, sub = parts[:3]
        user_id = int(parts[-1])

        if call.from_user.id != user_id:
            return bot.answer_callback_query(call.id, "Not your menu.", show_alert=True)

        # MAIN MENU
        if sub == "main":
            u = db.get_user(user_id) or {}
            rank, _ = ranking_module.elo_to_rank(int(u.get("elo_pvp", 1000)))

            text = (
                "⚔️ *MEGAGROK PvP ARENA*\n\n"
                f"Welcome, {get_display_name_from_row(u)}!\n\n"
                f"📈 Rank: *{rank}* — ELO: *{u.get('elo_pvp',1000)}*\n\n"
                "Choose an option:"
            )

            bot.edit_message_text(
                text, call.message.chat.id, call.message.message_id,
                parse_mode="Markdown", reply_markup=menu_main_markup(user_id)
            )
            return bot.answer_callback_query(call.id)

        # REVENGE TARGETS
        elif sub == "revenge":
            revs = pvp_targets.get_revenge_targets(user_id)
            if not revs:
                bot.edit_message_text(
                    "🔥 *Revenge Targets*\n\nNo recent attackers.",
                    call.message.chat.id, call.message.message_id,
                    parse_mode="Markdown", reply_markup=markup_back(user_id)
                )
                return bot.answer_callback_query(call.id)

            lines = ["🔥 *Revenge Targets*",""]
            kb = types.InlineKeyboardMarkup(row_width=1)

            for r in revs:
                lines.append(
                    f"• {r['display_name']} | {r['time_ago']} | +{r['xp_stolen']} XP"
                )
                kb.add(types.InlineKeyboardButton(
                    f"Revenge {r['display_name']}",
                    callback_data=f"pvp:rev:{user_id}:{r['user_id']}"
                ))

            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))

            bot.edit_message_text(
                "\n".join(lines), call.message.chat.id, call.message.message_id,
                parse_mode="Markdown", reply_markup=kb
            )
            return bot.answer_callback_query(call.id)

        # RECOMMENDED TARGETS
        elif sub == "recommended":
            recs = pvp_targets.get_recommended_targets(user_id)
            if not recs:
                bot.edit_message_text(
                    "🎯 *Recommended Targets*\n\nNo recommended players.",
                    call.message.chat.id, call.message.message_id,
                    parse_mode="Markdown", reply_markup=markup_back(user_id)
                )
                return bot.answer_callback_query(call.id)

            lines = ["🎯 *Recommended Targets*",""]
            kb = types.InlineKeyboardMarkup()

            for r in recs:
                lines.append(
                    f"• {r['display_name']} — Level {r['level']} — Power {r['power']} — {r['rank']}"
                )
                kb.add(types.InlineKeyboardButton(
                    f"Attack {r['display_name']} (Power {r['power']})",
                    callback_data=f"pvp:rec:{user_id}:{r['user_id']}"
                ))

            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))

            bot.edit_message_text(
                "\n".join(lines), call.message.chat.id, call.message.message_id,
                parse_mode="Markdown", reply_markup=kb
            )
            return bot.answer_callback_query(call.id)

        # SHIELDED PLAYERS
        elif sub == "shielded":
            now = int(time.time())
            allu = safe_call(db.get_all_users) or []
            shielded = [u for u in allu if int(u.get("pvp_shield_until", 0)) > now]

            if not shielded:
                bot.edit_message_text(
                    "🛡 *Shielded Players*\n\nNone are shielded.",
                    call.message.chat.id, call.message.message_id,
                    parse_mode="Markdown", reply_markup=markup_back(user_id)
                )
                return bot.answer_callback_query(call.id)

            lines = ["🛡 *Shielded Players*",""]
            for u in shielded:
                rem = int(u["pvp_shield_until"]) - now
                hh = rem // 3600
                mm = (rem % 3600)//60
                lines.append(f"• {get_display_name_from_row(u)} — {hh}h {mm}m")

            bot.edit_message_text(
                "\n".join(lines), call.message.chat.id, call.message.message_id,
                parse_mode="Markdown", reply_markup=markup_back(user_id)
            )
            return bot.answer_callback_query(call.id)

        # BROWSE USERS
        elif sub == "browse":
            page = int(parts[3])
            all_users = safe_call(db.get_all_users) or []
            all_users.sort(key=lambda u: get_display_name_from_row(u).lower())

            page_users, page, pages = browse_page_from_all(all_users, page)

            lines = [f"📜 *Browse Players* {page}/{pages}", ""]
            for u in page_users:
                pw = pvp_targets.calculate_power({
                    "hp": u.get("hp", 100),
                    "attack": u.get("attack", 10),
                    "defense": u.get("defense", 5)
                })
                lines.append(f"• {get_display_name_from_row(u)} — Level {u.get('level',1)} — Power {pw}")

            bot.edit_message_text(
                "\n".join(lines), call.message.chat.id, call.message.message_id,
                parse_mode="Markdown",
                reply_markup=build_browse_kb(page_users, page, pages, user_id)
            )
            return bot.answer_callback_query(call.id)

        # HELP MENU
        elif sub == "help":
            bot.edit_message_text(
                "❓ *PvP Help*\n\nChoose a topic:",
                call.message.chat.id, call.message.message_id,
                parse_mode="Markdown", reply_markup=help_menu_markup(user_id)
            )
            return bot.answer_callback_query(call.id)

        # STATS MENU
        elif sub == "stats":
            bot.edit_message_text(
                "📊 *PvP Stats & Leaderboards*\n\nChoose a category:",
                call.message.chat.id, call.message.message_id,
                parse_mode="Markdown", reply_markup=stats_menu_markup(user_id)
            )
            return bot.answer_callback_query(call.id)

        return bot.answer_callback_query(call.id)

    # -------------------------
    # HELP CALLBACKS
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:help"))
    def cb_help(call):
        parts = call.data.split(":")
        _, _, topic, user_id_str = parts
        user_id = int(user_id_str)

        if call.from_user.id != user_id:
            return bot.answer_callback_query(call.id, "Not your menu.", show_alert=True)

        if topic == "how":
            bot.edit_message_text(
                help_text_how(),
                call.message.chat.id, call.message.message_id,
                parse_mode="Markdown", reply_markup=help_menu_markup(user_id)
            )
        elif topic == "commands":
            bot.edit_message_text(
                help_text_commands(),
                call.message.chat.id, call.message.message_id,
                parse_mode="Markdown", reply_markup=help_menu_markup(user_id)
            )
        elif topic == "tutorial":
            # START TUTORIAL IN NEW MESSAGE
            pvp_tutorial.show_tutorial_for_user(bot, call.message, user_id)
        else:
            bot.answer_callback_query(call.id, "Unknown help topic.")
            return

        return bot.answer_callback_query(call.id)

    # -------------------------
    # STATS CALLBACKS
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:stats"))
    def cb_stats(call):
        parts = call.data.split(":")
        _, _, stat_type, user_id_str = parts
        user_id = int(user_id_str)

        if call.from_user.id != user_id:
            return bot.answer_callback_query(call.id, "Not your menu.", show_alert=True)

        if stat_type == "me":
            text = build_user_stats_text(user_id)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=stats_menu_markup(user_id))

        elif stat_type == "top":
            text = build_top_pvp_text(10)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=stats_menu_markup(user_id))

        elif stat_type == "wins":
            text = build_wins_ranking_text(10)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=stats_menu_markup(user_id))

        elif stat_type == "ranks":
            text = build_rank_info_text(user_id)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=stats_menu_markup(user_id))

        return bot.answer_callback_query(call.id)

    # -------------------------
    # DUEL START
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:rec") or c.data.startswith("pvp:rev"))
    def cb_start_duel(call):
        parts = call.data.split(":")
        typ = parts[1]
        attacker_id = int(parts[2])
        defender_id = int(parts[3])

        if call.from_user.id != attacker_id:
            return bot.answer_callback_query(call.id, "Not your action.", show_alert=True)
        if db.is_pvp_shielded(defender_id):
            return bot.answer_callback_query(call.id, "Target is shielded.", show_alert=True)

        # Close menu UI
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except:
            pass

        attacker = db.get_user(attacker_id)
        defender = db.get_user(defender_id)

        a_stats = pvp_stats.build_pvp_stats(attacker)
        d_stats = pvp_stats.build_pvp_stats(defender)

        is_revenge = (typ == "rev")

        sess = fight_session.manager.create_pvp_session(
            attacker_id,
            defender_id,
            a_stats,
            d_stats,
            revenge_fury=is_revenge
        )

        if is_revenge:
            pvp_targets.clear_revenge_for(attacker_id, defender_id)

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

        bot.answer_callback_query(call.id)
        return

    # -------------------------
    # ACTION HANDLER
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

            try: bot.delete_message(chat_id, msg_id)
            except: pass

            fight_session.manager.end_session_by_sid(sess.session_id)
            return bot.answer_callback_query(call.id)

        # NORMAL ACTION
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

            try: bot.delete_message(chat_id, msg_id)
            except: pass

            fight_session.manager.end_session_by_sid(sess.session_id)
            return bot.answer_callback_query(call.id)

        # UI UPDATE
        now = time.time()
        if now - sess._last_ui_edit >= UI_EDIT_THROTTLE_SECONDS:
            try:
                bot.edit_message_text(
                    build_caption(sess),
                    chat_id,
                    msg_id,
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

# END OF FILE
