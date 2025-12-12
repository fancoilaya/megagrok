# bot/handlers/pvp.py  (patch + new UI)
import time
from telebot import TeleBot, types

import services.fight_session_pvp as fight_session
import services.pvp_targets as pvp_targets
import bot.db as db
import bot.handlers.pvp_ranking as ranking_module  # your ranking helper. :contentReference[oaicite:4]{index=4}

# config
UI_EDIT_THROTTLE_SECONDS = 1.0

def get_display_name(user):
    if not user:
        return "Unknown"
    if user.get("display_name"):
        return user["display_name"]
    if user.get("username"):
        return "@" + user["username"]
    return f"User{user.get('user_id')}"

def hp_bar(cur, maxhp, width=20):
    cur = max(0, int(cur)); maxhp = max(1, int(maxhp))
    filled = int((cur / maxhp) * width)
    return "▓" * filled + "░" * (width - filled)

def has_pvp_access(uid):
    try:
        # free mode
        return True
    except:
        return True

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

# keyboard builder — Heal replaces Auto
def _action_cb(action, token):
    return f"pvp:act:{action}:{token}"

def action_keyboard(sess):
    sid = getattr(sess, "session_id", None) or getattr(sess, "session_id", None)
    token = sid if sid else str(getattr(sess, "attacker_id", ""))
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=_action_cb("attack", token)),
        types.InlineKeyboardButton("🛡 Block", callback_data=_action_cb("block", token)),
    )
    kb.add(
        types.InlineKeyboardButton("💨 Dodge", callback_data=_action_cb("dodge", token)),
        types.InlineKeyboardButton("⚡ Charge", callback_data=_action_cb("charge", token)),
    )
    kb.add(
        types.InlineKeyboardButton("💉 Heal (20%)", callback_data=_action_cb("heal", token)),
        types.InlineKeyboardButton("❌ Forfeit", callback_data=_action_cb("forfeit", token)),
    )
    return kb

def build_caption(sess):
    a = getattr(sess, "attacker", None) or getattr(sess, "pvp_attacker", {}) or {}
    d = getattr(sess, "defender", None) or getattr(sess, "pvp_defender", {}) or {}
    a_name = get_display_name(a)
    d_name = get_display_name(d)
    a_max = int(a.get("max_hp", a.get("hp", 100)))
    d_max = int(d.get("max_hp", d.get("hp", 100)))
    a_hp = int(a.get("hp", getattr(sess, "attacker_hp", a_max)))
    d_hp = int(d.get("hp", getattr(sess, "defender_hp", d_max)))

    lines = [
        f"⚔️ *PvP Raid:* {a_name} vs {d_name}",
        "",
        f"{a_name}: {hp_bar(a_hp, a_max, 20)} {a_hp}/{a_max}",
        f"{d_name}: {hp_bar(d_hp, d_max, 20)} {d_hp}/{d_max}",
        "",
        f"Turn: {getattr(sess, 'turn', 1)}",
        "",
    ]
    evs = getattr(sess, "events", []) or []
    if evs:
        lines.append("*Recent actions:*")
        for ev in evs[:6]:
            actor = a_name if ev["actor"] == "attacker" else d_name
            if ev["action"] == "attack":
                lines.append(f"• {actor} dealt {ev['damage']} dmg {ev.get('note','')}")
            else:
                lines.append(f"• {actor}: {ev['action']} {ev.get('note','')}")
    return "\n".join(lines)

def send_result_card(bot, sess, summary):
    # reuse your existing finalize + result formatting if present
    try:
        from bot.handlers.pvp import finalize_pvp, send_result_card as old_send
        # if you already have old finalizer, call that (keeps XP/ELO logic)
        old_send(bot, sess, summary)
        return
    except Exception:
        # fallback minimal
        attacker = getattr(sess, "attacker", {}) or {}
        defender = getattr(sess, "defender", {}) or {}
        a_name = get_display_name(attacker); d_name = get_display_name(defender)
        a_hp = attacker.get("hp", 0); d_hp = defender.get("hp", 0)
        card = [
            ("🏆 *VICTORY!*" if sess.winner == "attacker" else "💀 *DEFEAT*"),
            "",
            f"❤️ {a_name}: {a_hp}",
            f"💀 {d_name}: {d_hp}"
        ]
        bot.send_message(getattr(sess, "_last_msg", {}).get("chat", sess.attacker_id), "\n".join(card), parse_mode="Markdown")

# Setup
def setup(bot: TeleBot):
    globals()["bot_instance_for_pvp"] = bot

    @bot.message_handler(commands=["attack"])
    def cmd_attack(message):
        attacker_id = message.from_user.id
        if not has_pvp_access(attacker_id):
            return bot.reply_to(message, "🔒 PvP requires VIP.")

        parts = message.text.split()
        # if user provided target -> immediate attack
        if len(parts) > 1:
            q = parts[1].strip()
            defender_id = None
            if q.startswith("@"):
                row = db.get_user_by_username(q)
                if not row:
                    return bot.reply_to(message, "User not found.")
                defender_id = row[0] if isinstance(row, (list, tuple)) else row
            else:
                matches = db.search_users_by_name(q)
                if not matches:
                    return bot.reply_to(message, "No matches found.")
                defender_id = matches[0][0]

            if defender_id == attacker_id:
                return bot.reply_to(message, "You cannot attack yourself.")
            if db.is_pvp_shielded(defender_id):
                return bot.reply_to(message, "That user is shielded.")

            attacker = db.get_user(attacker_id) or {}
            defender = db.get_user(defender_id) or {}
            # build balanced pvp stats (should match your pvp.py build_pvp_stats)
            from bot.handlers.pvp import build_pvp_stats as build_pvp_stats_fn  # if exists
            try:
                a_stats = build_pvp_stats_fn(attacker)
                d_stats = build_pvp_stats_fn(defender)
            except Exception:
                # fallback to simple mapping
                a_stats = {"hp": int(attacker.get("hp", 100)), "attack": int(attacker.get("attack", 10)), "defense": int(attacker.get("defense", 5)), "crit_chance": float(attacker.get("crit_chance", 0.04))}
                d_stats = {"hp": int(defender.get("hp", 100)), "attack": int(defender.get("attack", 8)), "defense": int(defender.get("defense", 4)), "crit_chance": float(defender.get("crit_chance", 0.03))}
            # ensure identity
            a_stats["user_id"] = attacker_id; a_stats["username"] = attacker.get("username"); a_stats["display_name"] = attacker.get("display_name")
            d_stats["user_id"] = defender_id; d_stats["username"] = defender.get("username"); d_stats["display_name"] = defender.get("display_name")

            sess = fight_session.manager.create_pvp_session(attacker_id, defender_id, a_stats, d_stats)
            # save last message info so UI edits work
            m = bot.send_message(message.chat.id, "⚔️ Starting duel...", parse_mode="Markdown")
            sess._last_msg = {"chat": m.chat.id, "msg": m.message_id}
            fight_session.manager.save_session(sess)
            kb = action_keyboard(sess)
            safe_edit(bot, sess, m.chat.id, m.message_id, build_caption(sess), kb)
            return

        # ELSE: no args -> show PvP Arena panel (Recommended + Revenge)
        revenge = pvp_targets.get_revenge_targets(attacker_id)
        recs = pvp_targets.get_recommended_targets(attacker_id)
        me = db.get_user(attacker_id) or {}
        elo = int(me.get("elo_pvp", 1000))
        rank_name, _ = ranking_module.elo_to_rank(elo)

        lines = ["⚔️ *MEGAGROK PvP ARENA*", ""]
        if revenge:
            lines.append("🔥 *Revenge Targets:*")
            for r in revenge[:5]:
                name = r.get("display_name") or r.get("username") or f"User{r.get('user_id')}"
                ago = int(r.get("since", 0))
                desc = f"{name} — {ago//3600}h ago — {r.get('xp_stolen',0)} XP"
                lines.append(f"• {desc}")
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
        # add revenge buttons
        for r in (revenge or [])[:5]:
            uid = int(r.get("user_id"))
            label = f"Revenge {r.get('display_name') or r.get('username') or uid}"
            kb.add(types.InlineKeyboardButton(label, callback_data=f"pvp:rev:{attacker_id}:{uid}"))
        # recommended
        for r in (recs or [])[:6]:
            uid = int(r.get("user_id"))
            label = f"Attack {r.get('display_name') or r.get('username') or uid}  (Power {r.get('power')})"
            kb.add(types.InlineKeyboardButton(label, callback_data=f"pvp:rec:{attacker_id}:{uid}"))
        kb.add(types.InlineKeyboardButton("🎲 Random fair match", callback_data=f"pvp:find:{attacker_id}"))
        bot.reply_to(message, text, parse_mode="Markdown", reply_markup=kb)

    # selection callbacks from arena panel
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

        if typ == "rec" or typ == "rev":
            defender_id = int(parts[3])
        elif typ == "find":
            # pick first recommended as random fair
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

        # build balanced pvp stats (reuse your pvp stat builder if present)
        try:
            from bot.handlers.pvp import build_pvp_stats as build_pvp_stats_fn
            a_stats = build_pvp_stats_fn(attacker)
            d_stats = build_pvp_stats_fn(defender)
        except:
            a_stats = {"hp": int(attacker.get("hp", 100)), "attack": int(attacker.get("attack", 10)), "defense": int(attacker.get("defense", 5)), "crit_chance": float(attacker.get("crit_chance", 0.04))}
            d_stats = {"hp": int(defender.get("hp", 100)), "attack": int(defender.get("attack", 8)), "defense": int(defender.get("defense", 4)), "crit_chance": float(defender.get("crit_chance", 0.03))}

        a_stats["user_id"] = attacker_id; a_stats["display_name"] = attacker.get("display_name"); a_stats["username"] = attacker.get("username")
        d_stats["user_id"] = defender_id; d_stats["display_name"] = defender.get("display_name"); d_stats["username"] = defender.get("username")

        sess = fight_session.manager.create_pvp_session(attacker_id, defender_id, a_stats, d_stats)
        m = bot.send_message(call.message.chat.id, "⚔️ Duel starting...", parse_mode="Markdown")
        sess._last_msg = {"chat": m.chat.id, "msg": m.message_id}
        fight_session.manager.save_session(sess)
        kb = action_keyboard(sess)
        safe_edit(bot, sess, m.chat.id, m.message_id, build_caption(sess), kb)
        bot.answer_callback_query(call.id, "Raid started!")

    # action callbacks
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp:act"))
    def cb_pvp_action(call):
        parts = call.data.split(":")
        if len(parts) != 4:
            return bot.answer_callback_query(call.id, "Invalid.")
        _, _, action, token = parts

        # try session_id first
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
            # finalize external logic if present, fallback minimal
            try:
                from bot.handlers.pvp import finalize_pvp
                summary = finalize_pvp(bot, sess)
                send_result_card(bot, sess, summary)
            except:
                send_result_card(bot, sess, {})
            fight_session.manager.end_session_by_sid(getattr(sess, "session_id", ""))
            return bot.answer_callback_query(call.id, "You forfeited.")

        # execute action
        sess.resolve_attacker_action(action)
        fight_session.manager.save_session(sess)

        if sess.ended:
            # run finalize (existing finalize_pvp handles XP/ELO in your codebase)
            try:
                from bot.handlers.pvp import finalize_pvp
                summary = finalize_pvp(bot, sess)
            except:
                summary = {"xp_stolen": 0, "elo_change": 0, "best_hits": {}, "attacker_hp": getattr(sess.attacker, "hp", 0), "defender_hp": getattr(sess.defender, "hp", 0)}
            send_result_card(bot, sess, summary)
            fight_session.manager.end_session_by_sid(getattr(sess, "session_id", ""))
        else:
            safe_edit(bot, sess, chat_id, msg_id, build_caption(sess), action_keyboard(sess))

        bot.answer_callback_query(call.id)

