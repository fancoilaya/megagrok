# bot/handlers/pvp.py
# MegaGrok Async PvP System (Attacker vs AI defender)
# Requires: bot/db.py, services/fight_session.py

import os
import time
import random
from telebot import TeleBot, types

# CORRECT imports for your structure:
import bot.db as db
from services import fight_session

# safe GIF loader (fallback if missing)
try:
    from bot.utils import safe_send_gif
except:
    def safe_send_gif(bot, chat_id, path):
        pass


# ==========================================
# CONFIG
# ==========================================

PVP_FREE_MODE = os.getenv("PVP_FREE_MODE", "true").lower() == "true"
PVP_SHIELD_SECONDS = int(os.getenv("PVP_SHIELD_SECONDS", str(3 * 3600)))
PVP_MIN_STEAL_PERCENT = 0.07     # 7%
PVP_MIN_STEAL_ABS = 20           # min XP
PVP_ELO_K = 32


# ==========================================
# VIP ACCESS CHECK — placeholder
# ==========================================
def has_pvp_access(user_id: int) -> bool:
    if PVP_FREE_MODE:
        return True
    return True  # Will use Redis later


# ==========================================
# UTILITY — HP BAR
# ==========================================
def hp_bar(cur, maxhp, width=16):
    ratio = max(0, min(1, cur / maxhp))
    f = int(width * ratio)
    return "▓" * f + "░" * (width - f)


# ==========================================
# CAPTION BUILDER
# ==========================================
def build_caption(sess: fight_session.FightSession):
    a = sess.pvp_attacker
    d = sess.pvp_defender
    a_name = a.get("username", f"Player{sess.attacker_id}")
    d_name = d.get("username", f"Player{sess.defender_id}")

    a_max = a.get("current_hp", a.get("hp"))
    d_max = d.get("current_hp", d.get("hp"))

    lines = [
        f"⚔️ *PvP Raid:* {a_name} vs {d_name}",
        "",
        f"{a_name}: {hp_bar(sess.attacker_hp, a_max)}  {sess.attacker_hp}/{a_max}",
        f"{d_name}: {hp_bar(sess.defender_hp, d_max)}  {sess.defender_hp}/{d_max}",
        "",
        f"Turn: {sess.turn}",
        "",
    ]

    if sess.events:
        lines.append("*Recent actions:*")
        for ev in sess.events[:4]:
            if ev["action"] == "attack":
                lines.append(f"⚔️ {ev['actor']} dealt {ev['damage']} dmg {ev.get('note', '')}")
            else:
                lines.append(f"{ev['actor']} — {ev['action']} {ev.get('note','')}")
    return "\n".join(lines)


# ==========================================
# INLINE KEYBOARD
# ==========================================
def action_keyboard(attacker_id: int, auto_mode: bool):
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=f"pvp:act:attack:{attacker_id}"),
        types.InlineKeyboardButton("🛡 Block", callback_data=f"pvp:act:block:{attacker_id}"),
        types.InlineKeyboardButton("💨 Dodge", callback_data=f"pvp:act:dodge:{attacker_id}")
    )
    kb.add(types.InlineKeyboardButton("⚡ Charge", callback_data=f"pvp:act:charge:{attacker_id}"))
    kb.add(
        types.InlineKeyboardButton("▶ Auto" if not auto_mode else "⏸ Auto",
                                   callback_data=f"pvp:act:auto:{attacker_id}"),
        types.InlineKeyboardButton("✖ Forfeit", callback_data=f"pvp:act:forfeit:{attacker_id}")
    )
    return kb


# ==========================================
# XP STEAL
# ==========================================
def calc_xp_steal(def_total_xp: int) -> int:
    return max(int(def_total_xp * PVP_MIN_STEAL_PERCENT), PVP_MIN_STEAL_ABS)


# ==========================================
# DEFENDER NOTIFIER
# ==========================================
def notify(bot: TeleBot, uid: int, text: str):
    try:
        bot.send_message(uid, text, parse_mode="Markdown")
    except:
        pass


# ==========================================
# FINALIZE PVP RESULT
# ==========================================
def finalize_pvp(bot: TeleBot, sess: fight_session.FightSession):

    attacker_id = sess.attacker_id
    defender_id = sess.defender_id

    attacker = db.get_user(attacker_id)
    defender = db.get_user(defender_id)

    atk_xp = attacker.get("xp_total", 0)
    def_xp = defender.get("xp_total", 0)

    attacker_won = sess.winner == "attacker"

    xp_stolen = 0

    if attacker_won:
        xp_stolen = calc_xp_steal(def_xp)

        db.cursor.execute("UPDATE users SET xp_total = xp_total - ?, xp_current = xp_current - ? WHERE user_id=?",
                          (xp_stolen, xp_stolen, defender_id))
        db.cursor.execute("UPDATE users SET xp_total = xp_total + ?, xp_current = xp_current + ? WHERE user_id=?",
                          (xp_stolen, xp_stolen, attacker_id))

        db.increment_pvp_field(attacker_id, "pvp_wins")
        db.increment_pvp_field(defender_id, "pvp_losses")
        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_fights_defended")

        # defender gets shield
        db.set_pvp_shield(defender_id, int(time.time()) + PVP_SHIELD_SECONDS)

    else:
        # attacker loses XP
        penalty = max(1, int(atk_xp * 0.05))
        db.cursor.execute("UPDATE users SET xp_total = xp_total - ?, xp_current = xp_current - ? WHERE user_id=?",
                          (penalty, penalty, attacker_id))
        db.cursor.execute("UPDATE users SET xp_total = xp_total + ?, xp_current = xp_current + ? WHERE user_id=?",
                          (penalty, penalty, defender_id))

        db.increment_pvp_field(attacker_id, "pvp_losses")
        db.increment_pvp_field(defender_id, "pvp_wins")

    db.conn.commit()

    # --------------------
    # ELO CALCULATION
    # --------------------
    atk_elo = attacker.get("elo_pvp", 1000)
    def_elo = defender.get("elo_pvp", 1000)

    def expected(a, b):
        return 1 / (1 + 10 ** ((b - a) / 400))

    E = expected(atk_elo, def_elo)

    if attacker_won:
        new_atk = atk_elo + int(PVP_ELO_K * (1 - E))
        new_def = def_elo - int(PVP_ELO_K * (1 - E))
    else:
        new_atk = atk_elo + int(PVP_ELO_K * (0 - E))
        new_def = def_elo - int(PVP_ELO_K * (0 - E))

    db.update_elo(attacker_id, new_atk)
    db.update_elo(defender_id, new_def)

    # Defender notification
    if attacker_won:
        notify(bot, defender_id,
               f"⚠️ You were raided by {attacker.get('username') or attacker_id}!\n"
               f"XP lost: {xp_stolen}\n"
               f"ELO: {new_def - def_elo}\n"
               f"Shield active for {PVP_SHIELD_SECONDS//3600}h.")
    else:
        notify(bot, defender_id,
               f"🛡 Your AI defender repelled {attacker.get('username') or attacker_id}!\n"
               f"ELO: {new_def - def_elo}")

    return {
        "winner": sess.winner,
        "xp_stolen": xp_stolen,
        "elo_attacker": new_atk - atk_elo,
        "elo_defender": new_def - def_elo
    }


# ================================================================
# MAIN SETUP (called automatically by main.py)
# ================================================================
def setup(bot: TeleBot):

    # -----------------------------------------------------------
    # /attack COMMAND
    # -----------------------------------------------------------
    @bot.message_handler(commands=["attack"])
    def cmd_attack(message):

        attacker_id = message.from_user.id

        # VIP gating
        if not has_pvp_access(attacker_id):
            bot.reply_to(message, "🔒 PvP requires VIP access.")
            return

        defender_id = None

        # CASE 1 — reply to message → attack that user
        if message.reply_to_message:
            defender_id = message.reply_to_message.from_user.id

        else:
            # CASE 2 — argument-based
            parts = message.text.split()
            if len(parts) <= 1:
                # Option B: show menu instead of error
                return show_target_menu(bot, message)

            query = parts[1].strip()

            if query.startswith("@"):
                found = db.get_user_by_username(query)
                if not found:
                    bot.reply_to(message, "User not found.")
                    return
                defender_id = found[0]
            else:
                matches = db.search_users_by_name(query)
                if len(matches) == 0:
                    bot.reply_to(message, "No matching users.")
                    return
                elif len(matches) == 1:
                    defender_id = matches[0][0]
                else:
                    # Present selection list
                    kb = types.InlineKeyboardMarkup()
                    for uid, uname, disp in matches:
                        label = disp or uname or f"User{uid}"
                        kb.add(types.InlineKeyboardButton(label,
                                                          callback_data=f"pvp_select:{attacker_id}:{uid}"))
                    bot.reply_to(message, "Multiple matches found:", reply_markup=kb)
                    return

        # VALIDATION
        if defender_id is None:
            bot.reply_to(message, "Cannot determine target.")
            return

        if defender_id == attacker_id:
            bot.reply_to(message, "You cannot attack yourself.")
            return

        if db.is_pvp_shielded(defender_id):
            bot.reply_to(message, "🛡 Target is currently shielded.")
            return

        # BUILD STATS
        attacker = db.get_user(attacker_id)
        defender = db.get_user(defender_id)

        attacker_stats = fight_session.build_player_stats_from_user(attacker)
        defender_stats = fight_session.build_player_stats_from_user(defender)

        sess = fight_session.manager.create_pvp_session(attacker_id, attacker_stats, defender_id, defender_stats)

        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_challenges_received")

        caption = build_caption(sess)
        kb = action_keyboard(attacker_id, sess.auto_mode)

        try:
            safe_send_gif(bot, message.chat.id, "assets/gifs/pvp_intro.gif")
        except:
            pass

        m = bot.send_message(message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)

        # Save pointer
        store = fight_session.manager._sessions.get(str(attacker_id), {})
        store["_last_msg"] = {"chat": message.chat.id, "msg": m.message_id}
        fight_session.manager._sessions[str(attacker_id)] = store
        fight_session.manager.save_session(sess)

    # ============================================================
    # TARGET MENU (Option B)
    # ============================================================
    def show_target_menu(bot, message):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Reply Attack", callback_data="pvp_menu:reply"))
        kb.add(types.InlineKeyboardButton("Search Name", callback_data="pvp_menu:search_name"))
        kb.add(types.InlineKeyboardButton("Search Username", callback_data="pvp_menu:search_username"))
        kb.add(types.InlineKeyboardButton("PvP Leaderboard", callback_data="pvp_menu:top"))
        kb.add(types.InlineKeyboardButton("Cancel", callback_data="pvp_menu:cancel"))

        bot.reply_to(message,
            "⚔️ *PvP Attack Options*\nHow would you like to select a target?",
            parse_mode="Markdown",
            reply_markup=kb
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp_menu"))
    def cb_menu(call):
        action = call.data.split(":")[1]

        if action == "cancel":
            bot.answer_callback_query(call.id, "Cancelled.")
            return

        if action == "reply":
            bot.answer_callback_query(call.id, "Reply to a message and use /attack")
            return

        if action == "search_name":
            bot.answer_callback_query(call.id, "Use: /attack <name>")
            return

        if action == "search_username":
            bot.answer_callback_query(call.id, "Use: /attack @username")
            return

        if action == "top":
            bot.answer_callback_query(call.id, "Use /pvp_top to choose a target.")
            return


    # ============================================================
    # multi-result selection callback
    # ============================================================
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp_select:"))
    def cb_select(call):
        _, attacker_str, defender_str = call.data.split(":")
        attacker_id = int(attacker_str)
        defender_id = int(defender_str)

        attacker = db.get_user(attacker_id)
        defender = db.get_user(defender_id)

        attacker_stats = fight_session.build_player_stats_from_user(attacker)
        defender_stats = fight_session.build_player_stats_from_user(defender)

        sess = fight_session.manager.create_pvp_session(attacker_id, attacker_stats, defender_id, defender_stats)

        db.increment_pvp_field(attacker_id, "pvp_fights_started")
        db.increment_pvp_field(defender_id, "pvp_challenges_received")

        caption = build_caption(sess)
        kb = action_keyboard(attacker_id, sess.auto_mode)

        m = bot.send_message(call.message.chat.id, caption, parse_mode="Markdown", reply_markup=kb)

        store = fight_session.manager._sessions.get(str(attacker_id), {})
        store["_last_msg"] = {"chat": call.message.chat.id, "msg": m.message_id}
        fight_session.manager._sessions[str(attacker_id)] = store
        fight_session.manager.save_session(sess)

        bot.answer_callback_query(call.id, "Raid started!")


    # ============================================================
    # ACTION CALLBACKS
    # ============================================================
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:act"))
    def cb_action(call):

        _, _, action, attacker_str = call.data.split(":")
        attacker_id = int(attacker_str)

        if call.from_user.id != attacker_id:
            bot.answer_callback_query(call.id, "Not your raid.", show_alert=True)
            return

        sess = fight_session.manager.load_session(attacker_id)
        if not sess:
            bot.answer_callback_query(call.id, "Raid not found.", show_alert=True)
            return

        chat_id = call.message.chat.id

        # FORFEIT
        if action == "forfeit":
            sess.ended = True
            sess.winner = "defender"
            fight_session.manager.save_session(sess)
            finalize_pvp(bot, sess)
            fight_session.manager.end_session(attacker_id)

            bot.edit_message_text("❌ You forfeited the raid.", chat_id, call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        # AUTO MODE
        if action == "auto":
            sess.auto_mode = not sess.auto_mode
            fight_session.manager.save_session(sess)

            if sess.auto_mode:
                for _ in range(4):
                    if sess.ended:
                        break
                    sess.resolve_auto_attacker_turn()
                    fight_session.manager.save_session(sess)

            caption = build_caption(sess)
            kb = action_keyboard(attacker_id, sess.auto_mode)
            bot.edit_message_text(caption, chat_id, call.message.message_id,
                                  parse_mode="Markdown", reply_markup=kb)

            if sess.ended:
                finalize_pvp(bot, sess)
                fight_session.manager.end_session(attacker_id)

            bot.answer_callback_query(call.id)
            return

        # NORMAL ACTIONS
        if action not in ("attack", "block", "dodge", "charge"):
            bot.answer_callback_query(call.id, "Invalid action")
            return

        sess.resolve_attacker_action(action)
        fight_session.manager.save_session(sess)

        caption = build_caption(sess)
        kb = action_keyboard(attacker_id, sess.auto_mode)
        bot.edit_message_text(caption, chat_id, call.message.message_id,
                              parse_mode="Markdown", reply_markup=kb)

        bot.answer_callback_query(call.id)

        if sess.ended:
            finalize_pvp(bot, sess)
            fight_session.manager.end_session(attacker_id)



    # ============================================================
    # /pvp_top — leaderboard
    # ============================================================
    @bot.message_handler(commands=["pvp_top"])
    def cmd_pvp_top(message):
        top = db.get_top_pvp(10)
        if not top:
            bot.reply_to(message, "No PvP data yet.")
            return

        lines = ["🏆 *Top PvP Players*"]
        for row in top:
            name = row["name"]
            elo = row["elo"]
            lines.append(f"{row['rank']}. {name} — {elo} ELO ({row['wins']}W/{row['losses']}L)")

        bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")


    # ============================================================
    # /pvp_stats
    # ============================================================
    @bot.message_handler(commands=["pvp_stats"])
    def cmd_pvp_stats(message):
        uid = message.from_user.id
        stats = db.get_pvp_stats(uid)

        msg = (
            f"📊 *Your PvP Stats*\n"
            f"ELO: {stats['elo']}\n"
            f"Wins: {stats['wins']}\n"
            f"Losses: {stats['losses']}\n"
            f"Raids Started: {stats['started']}\n"
            f"Defended: {stats['defended']}\n"
            f"Challenges Received: {stats['challenges']}\n"
            f"Shield until: {time.ctime(stats['shield_until'])}"
        )
        bot.reply_to(message, msg, parse_mode="Markdown")
