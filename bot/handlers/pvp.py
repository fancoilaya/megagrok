# bot/handlers/pvp.py
# Stable PvP module with: PvP Menu, Help Menu, Stats Menu, Tutorial Launcher

import time
from typing import Dict, Any, List
from telebot import TeleBot, types

# Services
from services import pvp_targets
from services import pvp_stats
from services import fight_session_pvp as fight_session

import bot.db as db
from bot.handlers import pvp_ranking as ranking_module

# -------------------------
# CONFIG
# -------------------------
BROWSE_PAGE_SIZE = 5
PVP_SHIELD_SECONDS = 3 * 3600
UI_EDIT_THROTTLE_SECONDS = 1.0
PVP_ELO_K = 32


# -------------------------
# Utility
# -------------------------
def get_display_name(u: Dict[str, Any]) -> str:
    if not u:
        return "Unknown"
    if u.get("display_name"):
        return u["display_name"]
    if u.get("username"):
        return u["username"]
    return f"User{u.get('user_id','?')}"


def hp_bar(cur, maxhp, width=20):
    cur = max(0, int(cur))
    maxhp = max(1, int(maxhp))
    filled = int((cur / maxhp) * width)
    return "▓" * filled + "░" * (width - filled)


def safe_call(fn, *a, **k):
    try:
        return fn(*a, **k)
    except:
        return None


# -------------------------
# Action buttons
# -------------------------
def _act(action, token):
    return f"pvp:act:{action}:{token}"


def action_keyboard(sess):
    sid = getattr(sess, "session_id") or str(sess.attacker_id)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=_act("attack", sid)),
        types.InlineKeyboardButton("🛡 Block", callback_data=_act("block", sid)),
    )
    kb.add(
        types.InlineKeyboardButton("💨 Dodge", callback_data=_act("dodge", sid)),
        types.InlineKeyboardButton("⚡ Charge", callback_data=_act("charge", sid)),
    )
    kb.add(
        types.InlineKeyboardButton("💉 Heal (20%)", callback_data=_act("heal", sid)),
        types.InlineKeyboardButton("❌ Forfeit", callback_data=_act("forfeit", sid)),
    )
    return kb


# -------------------------
# Caption Builder
# -------------------------
def build_caption(sess):
    a = sess.attacker
    d = sess.defender
    an = get_display_name(a)
    dn = get_display_name(d)
    a_hp = int(a.get("hp", a.get("max_hp", 100)))
    d_hp = int(d.get("hp", d.get("max_hp", 100)))
    a_m = int(a.get("max_hp", 100))
    d_m = int(d.get("max_hp", 100))

    lines = [
        f"⚔️ *PvP Raid:* {an} vs {dn}",
        "",
        f"{an}: {hp_bar(a_hp, a_m)} {a_hp}/{a_m}",
        f"{dn}: {hp_bar(d_hp, d_m)} {d_hp}/{d_m}",
        "",
        f"Turn: {sess.turn}",
        "",
    ]

    for ev in sess.events[:6]:
        actor = an if ev["actor"] == "attacker" else dn
        if ev["action"] == "attack":
            lines.append(f"• {actor} dealt {ev['damage']} dmg {ev.get('note','')}".strip())
        else:
            note = f" {ev.get('note','')}" if ev.get('note') else ""
            lines.append(f"• {actor}: {ev['action']}{note}")

    return "\n".join(lines)


# -------------------------
# Finalize PvP
# -------------------------
def finalize_pvp_local(att_id, def_id, sess):
    at = db.get_user(att_id) or {}
    de = db.get_user(def_id) or {}
    win = sess.winner == "attacker"
    xp_stolen = 0

    if win:
        dx = int(de.get("xp_total", 0))
        xp_stolen = max(int(dx * 0.07), 20)
        db.log_pvp_attack(att_id, def_id, xp_stolen, "win")
        db.set_pvp_shield(def_id, int(time.time()) + PVP_SHIELD_SECONDS)
        db.increment_pvp_field(att_id, "pvp_wins")
        db.increment_pvp_field(def_id, "pvp_losses")
    else:
        db.log_pvp_attack(att_id, def_id, 0, "fail")
        db.increment_pvp_field(att_id, "pvp_losses")
        db.increment_pvp_field(def_id, "pvp_wins")

    atk_elo = int(at.get("elo_pvp", 1000))
    def_elo = int(de.get("elo_pvp", 1000))

    def expected(a, b):
        return 1 / (1 + 10 ** ((b - a) / 400))

    E = expected(atk_elo, def_elo)

    if win:
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
            side = "attacker" if ev["actor"] == "attacker" else "defender"
            best[side]["damage"] = max(best[side]["damage"], ev["damage"])

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
def send_result_card(bot, sess, s):
    at = db.get_user(sess.attacker_id)
    de = db.get_user(sess.defender_id)
    an = get_display_name(at)
    dn = get_display_name(de)

    out = []
    if sess.winner == "attacker":
        out.append("🏆 *VICTORY!*")
        out.append(f"You defeated *{dn}*")
        out.append(f"🎁 XP Stolen: +{s['xp_stolen']}")
    else:
        out.append("💀 *DEFEAT*")
        out.append(f"You were repelled by *{dn}*")
        out.append(f"📉 XP Lost: -{s['xp_stolen']}")

    out.append(f"🏅 ELO Change: {s['elo_change']:+d}")
    out.append("")
    out.append(f"❤️ {an}: {s['attacker_hp']}")
    out.append(f"💀 {dn}: {s['defender_hp']}")
    out.append("")
    out.append("*Highlights:*")

    if s["best_hits"]["attacker"]["damage"]:
        out.append(f"💥 Your best hit: {s['best_hits']['attacker']['damage']}")
    if s["best_hits"]["defender"]["damage"]:
        out.append(f"💢 Enemy best hit: {s['best_hits']['defender']['damage']}")

    bot.send_message(sess._last_msg["chat"], "\n".join(out), parse_mode="Markdown")


# ---------------------------------------------------------------
# MENU BUILDERS
# ---------------------------------------------------------------
def menu_main(user_id):
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
        types.InlineKeyboardButton("📊 Stats", callback_data=f"pvp:menu:stats:{user_id}"),
    )
    return kb


def back_btn(user_id):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))
    return kb


def build_browse(users, page, pages, user_id):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for u in users:
        kb.add(types.InlineKeyboardButton(
            f"Attack {get_display_name(u)}",
            callback_data=f"pvp:rec:{user_id}:{u['user_id']}"
        ))

    nav = []
    if page > 1:
        nav.append(types.InlineKeyboardButton("⏮ Prev", callback_data=f"pvp:menu:browse:{page-1}:{user_id}"))
    if page < pages:
        nav.append(types.InlineKeyboardButton("Next ⏭", callback_data=f"pvp:menu:browse:{page+1}:{user_id}"))
    if nav:
        kb.add(*nav)

    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))
    return kb


# ---------------------------------------------------------------
# HELP MENU
# ---------------------------------------------------------------
def help_menu(user_id):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📘 How PvP Works", callback_data=f"pvp:help:how:{user_id}"))
    kb.add(types.InlineKeyboardButton("📜 PvP Commands", callback_data=f"pvp:help:commands:{user_id}"))
    kb.add(types.InlineKeyboardButton("🎓 PvP Tutorial", callback_data=f"pvp:help:tutorial:{user_id}"))
    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))
    return kb


# ---------------------------------------------------------------
# STATS MENU
# ---------------------------------------------------------------
def stats_menu(user_id):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📈 Your Stats", callback_data=f"pvp:stats:me:{user_id}"))
    kb.add(types.InlineKeyboardButton("🏅 Rank Details", callback_data=f"pvp:stats:rank:{user_id}"))
    kb.add(types.InlineKeyboardButton("📊 Win Rate", callback_data=f"pvp:stats:winrate:{user_id}"))
    kb.add(types.InlineKeyboardButton("🏆 Leaderboards", callback_data=f"pvp:stats:lb:{user_id}"))
    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))
    return kb


# =================================================================
# SETUP – MAIN HANDLERS
# =================================================================
def setup(bot: TeleBot):
    globals()["bot_instance"] = bot

    # ---------------------------------------------------------------
    # /pvp COMMAND
    # ---------------------------------------------------------------
    @bot.message_handler(commands=["pvp"])
    def cmd_pvp(message):
        uid = message.from_user.id
        u = db.get_user(uid)
        rank, _ = ranking_module.elo_to_rank(int(u.get("elo_pvp", 1000)))

        text = (
            "⚔️ *MEGAGROK PvP ARENA*\n\n"
            f"Welcome, {get_display_name(u)}!\n\n"
            f"📈 Rank: *{rank}* — ELO: *{u.get('elo_pvp',1000)}*\n\n"
            "Choose an option:"
        )

        bot.reply_to(
            message,
            text,
            parse_mode="Markdown",
            reply_markup=menu_main(uid),
        )

    # ---------------------------------------------------------------
    # MENU: MAIN / HELP / STATS / BROWSE / RECOMMENDED / REVENGE
    # ---------------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:menu"))
    def cb_menu(call):
        parts = call.data.split(":")
        _, _, menu_type, *rest = parts
        user_id = int(rest[-1])

        if call.from_user.id != user_id:
            return bot.answer_callback_query(call.id, "Not your menu.", show_alert=True)

        # MAIN
        if menu_type == "main":
            u = db.get_user(user_id)
            rank, _ = ranking_module.elo_to_rank(int(u.get("elo_pvp", 1000)))

            text = (
                "⚔️ *MEGAGROK PvP ARENA*\n\n"
                f"Welcome, {get_display_name(u)}!\n\n"
                f"📈 Rank: *{rank}* — ELO: *{u.get('elo_pvp',1000)}*\n\n"
                "Choose an option:"
            )

            return bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown",
                reply_markup=menu_main(user_id),
            )

        # HELP MENU
        if menu_type == "help":
            text = "❓ *PvP Help*\n\nChoose a topic:"
            return bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown",
                reply_markup=help_menu(user_id),
            )

        # STATS MENU
        if menu_type == "stats":
            text = "📊 *PvP Stats & Leaderboards*\n\nChoose a category:"
            return bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown",
                reply_markup=stats_menu(user_id),
            )

        # RECOMMENDED
        if menu_type == "recommended":
            recs = pvp_targets.get_recommended_targets(user_id)
            if not recs:
                return bot.edit_message_text(
                    "🎯 *Recommended*\n\nNo recommended players.",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown",
                    reply_markup=back_btn(user_id),
                )

            lines = ["🎯 *Recommended Targets*\n"]
            kb = types.InlineKeyboardMarkup(row_width=1)

            for r in recs:
                lines.append(f"• {r['display_name']} — L{r['level']} — P{r['power']} — {r['rank']}")
                kb.add(types.InlineKeyboardButton(
                    f"Attack {r['display_name']}",
                    callback_data=f"pvp:rec:{user_id}:{r['user_id']}",
                ))

            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))
            return bot.edit_message_text(
                "\n".join(lines),
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown",
                reply_markup=kb,
            )

        # REVENGE
        if menu_type == "revenge":
            rev = pvp_targets.get_revenge_targets(user_id)
            if not rev:
                return bot.edit_message_text(
                    "🔥 *Revenge*\n\nNo attackers found.",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown",
                    reply_markup=back_btn(user_id),
                )

            lines = ["🔥 *Revenge Targets*\n"]
            kb = types.InlineKeyboardMarkup(row_width=1)

            for r in rev:
                lines.append(f"• {r['display_name']} | {r['time_ago']} | +{r['xp_stolen']} XP")
                kb.add(types.InlineKeyboardButton(
                    f"Revenge {r['display_name']}",
                    callback_data=f"pvp:rev:{user_id}:{r['user_id']}",
                ))

            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"pvp:menu:main:{user_id}"))

            return bot.edit_message_text(
                "\n".join(lines),
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown",
                reply_markup=kb,
            )

        # SHIELDED
        if menu_type == "shielded":
            now = int(time.time())
            allu = db.get_all_users()
            shielded = [u for u in allu if int(u.get("pvp_shield_until", 0)) > now]

            if not shielded:
                return bot.edit_message_text(
                    "🛡 *Shielded Players*\n\nNone are shielded.",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown",
                    reply_markup=back_btn(user_id),
                )

            lines = ["🛡 *Shielded Players*\n"]
            for u in shielded:
                rem = int(u["pvp_shield_until"]) - now
                lines.append(f"• {get_display_name(u)} — {rem//3600}h {(rem%3600)//60}m")

            return bot.edit_message_text(
                "\n".join(lines),
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown",
                reply_markup=back_btn(user_id),
            )

        # BROWSE
        if menu_type == "browse":
            page = int(rest[0])
            allu = db.get_all_users()
            allu.sort(key=lambda x: get_display_name(x).lower())
            total = len(allu)
            pages = max(1, (total + BROWSE_PAGE_SIZE - 1) // BROWSE_PAGE_SIZE)
            page = max(1, min(page, pages))

            start = (page - 1) * BROWSE_PAGE_SIZE
            page_users = allu[start:start + BROWSE_PAGE_SIZE]

            lines = [f"📜 *Browse Players* {page}/{pages}\n"]
            for u in page_users:
                pw = pvp_targets.calculate_power({
                    "hp": u.get("hp", 100),
                    "attack": u.get("attack", 10),
                    "defense": u.get("defense", 5),
                })
                lines.append(f"• {get_display_name(u)} — L{u.get('level',1)} — P{pw}")

            return bot.edit_message_text(
                "\n".join(lines),
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown",
                reply_markup=build_browse(page_users, page, pages, user_id),
            )

        return bot.answer_callback_query(call.id)

    # ---------------------------------------------------------------
    # HELP SUBMENU HANDLER
    # ---------------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:help"))
    def cb_help(call):
        parts = call.data.split(":")
        _, _, topic, user_id = parts
        user_id = int(user_id)

        # HOW PvP Works
        if topic == "how":
            txt = (
                "📘 *How PvP Works*\n\n"
                "• You initiate a raid via /pvp.\n"
                "• You fight using the action buttons.\n"
                "• Win to steal XP and ELO.\n"
                "• The loser receives a shield.\n"
            )
            return bot.edit_message_text(
                txt, call.message.chat.id, call.message.message_id,
                parse_mode="Markdown", reply_markup=help_menu(user_id)
            )

        # COMMANDS
        if topic == "commands":
            txt = (
                "📜 *PvP Commands*\n\n"
                "• /pvp — open PvP panel\n"
                "• /pvp\\_stat — your stats\n"
                "• /pvp\\_ranking — your rank\n"
                "• /pvp\\_top — global ELO top\n"
            )
            return bot.edit_message_text(
                txt, call.message.chat.id, call.message.message_id,
                parse_mode="Markdown", reply_markup=help_menu(user_id)
            )

        # TUTORIAL LAUNCH
        if topic == "tutorial":
            from bot.handlers import pvp_tutorial
            pvp_tutorial.show_tutorial_for_user(bot, call.message.chat.id, 0)
            return bot.answer_callback_query(call.id)

        return bot.answer_callback_query(call.id)

    # ---------------------------------------------------------------
    # STATS SUBMENU HANDLER
    # ---------------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:stats"))
    def cb_stats(call):
        parts = call.data.split(":")
        _, _, sub, user_id = parts
        user_id = int(user_id)

        u = db.get_user(user_id)
        stats = db.get_pvp_stats(user_id)

        # ME
        if sub == "me":
            rank, _ = ranking_module.elo_to_rank(int(u.get("elo_pvp", 1000)))
            txt = (
                f"📈 *Your PvP Stats — {get_display_name(u)}*\n\n"
                f"🏅 Rank: {rank}\n"
                f"🎯 ELO: {u.get('elo_pvp',1000)}\n"
                f"🏆 Wins: {stats['wins']} | 📉 Losses: {stats['losses']}\n"
                f"⚔️ Raids Started: {stats['started']}\n"
                f"🛡 Successful Defenses: {stats['successful_def']}\n"
            )
            return bot.edit_message_text(
                txt, call.message.chat.id, call.message.message_id,
                parse_mode="Markdown", reply_markup=stats_menu(user_id)
            )

        # RANK
        if sub == "rank":
            rank, info = ranking_module.elo_to_rank(int(u.get("elo_pvp", 1000)))
            txt = (
                f"🏅 *Rank Details*\n\n"
                f"Rank: {rank}\n"
                f"ELO: {u.get('elo_pvp',1000)}\n"
                f"{info}"
            )
            return bot.edit_message_text(
                txt, call.message.chat.id, call.message.message_id,
                parse_mode="Markdown", reply_markup=stats_menu(user_id)
            )

        # WINRATE
        if sub == "winrate":
            w = stats["wins"]
            l = stats["losses"]
            total = w + l
            rate = (w / total * 100) if total > 0 else 0
            txt = (
                f"📊 *Win Rate*\n\n"
                f"Total Fights: {total}\n"
                f"Wins: {w}\nLosses: {l}\n\n"
                f"🏆 Win Rate: {rate:.1f}%"
            )
            return bot.edit_message_text(
                txt, call.message.chat.id, call.message.message_id,
                parse_mode="Markdown", reply_markup=stats_menu(user_id)
            )

        # LEADERBOARD LINK
        if sub == "lb":
            from bot.handlers import pvp_leaderboard            
            # Reuse existing leaderboard generator
            text = pvp_leaderboard.build_leaderboard_text(limit=10)
            # Send as NEW message (do NOT edit menu)
            bot.send_message(
                call.message.chat.id,
                text,
                parse_mode="Markdown"
               
            )

        return bot.answer_callback_query(call.id)

    # ---------------------------------------------------------------
    # START DUEL
    # ---------------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:rec") or c.data.startswith("pvp:rev"))
    def cb_start(call):
        parts = call.data.split(":")
        typ = parts[1]
        attacker_id = int(parts[2])
        defender_id = int(parts[3])

        if call.from_user.id != attacker_id:
            return bot.answer_callback_query(call.id, "Not your action.", show_alert=True)
        if db.is_pvp_shielded(defender_id):
            return bot.answer_callback_query(call.id, "Target is shielded.", show_alert=True)

        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except:
            pass

        a = db.get_user(attacker_id)
        d = db.get_user(defender_id)
        a_stats = pvp_stats.build_pvp_stats(a)
        d_stats = pvp_stats.build_pvp_stats(d)

        is_rev = (typ == "rev")
        sess = fight_session.manager.create_pvp_session(
            attacker_id, defender_id, a_stats, d_stats, revenge_fury=is_rev
        )

        if is_rev:
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

        return bot.answer_callback_query(call.id)

    # ---------------------------------------------------------------
    # ACTION HANDLER
    # ---------------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:act"))
    def cb_action(call):
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
                from bot.handlers.pvp import finalize_pvp as ext
                summ = ext(sess.attacker_id, sess.defender_id, sess)
            except:
                summ = finalize_pvp_local(sess.attacker_id, sess.defender_id, sess)

            send_result_card(bot, sess, summ)

            try:
                bot.delete_message(chat_id, msg_id)
            except:
                pass

            fight_session.manager.end_session_by_sid(sess.session_id)
            return bot.answer_callback_query(call.id)

        # NORMAL TURN
        sess.resolve_attacker_action(action)
        fight_session.manager.save_session(sess)

        # END
        if sess.ended:
            try:
                from bot.handlers.pvp import finalize_pvp as ext
                summ = ext(sess.attacker_id, sess.defender_id, sess)
            except:
                summ = finalize_pvp_local(sess.attacker_id, sess.defender_id, sess)

            send_result_card(bot, sess, summ)

            try:
                bot.delete_message(chat_id, msg_id)
            except:
                pass

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

# END OF FILE
