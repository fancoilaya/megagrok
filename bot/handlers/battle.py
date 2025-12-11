# bot/handlers/battle.py — FINAL VERSION v9
# Complete battle handler with:
# - session_id-based isolation
# - evolution-enhanced player stats
# - real mob names & metadata
# - 12-hour cooldown on /battle
# - single final result message
# - XP + level progression
# - kill milestone flair
# - only last 2 recent actions shown during battle
# - safe and minimal DB writes

import time
import random
from telebot import TeleBot, types
from typing import Optional

from services.fight_session_battle import (
    manager as battle_manager,
    BattleSession,
    build_player_stats_from_user,
    build_mob_stats_from_mob,
    ACTION_ATTACK,
    ACTION_BLOCK,
    ACTION_DODGE,
    ACTION_CHARGE,
    ACTION_AUTO,
    ACTION_SURRENDER,
)

import bot.db as db
import bot.mobs as mobs

# ============================================================
# Helpers
# ============================================================

def _cbdata(action: str, sid: str) -> str:
    return f"battle:act:{action}:{sid}"

def _hp_bar(cur: int, maxhp: int, width: int = 22) -> str:
    ratio = cur / maxhp if maxhp else 0
    full = int(ratio * width)
    return "▓" * full + "░" * (width - full)

def _safe_edit(bot: TeleBot, chat_id: int, msg_id: Optional[int], text: str, kb: Optional[types.InlineKeyboardMarkup]):
    """Safe wrapper around edit_message_text with fallback to send_message."""
    try:
        if msg_id:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        if "message is not modified" in str(e).lower():
            return
        try:
            bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass

def _progress_line(user: dict) -> str:
    """Level + XP progress bar (matches /growmygrok style)."""
    level = user.get("level", 1)
    xp_current = user.get("xp_current", 0)
    xp_to = user.get("xp_to_next_level", 100)
    pct = int(xp_current * 100 / xp_to) if xp_to else 0

    bar_width = 22
    full = int((pct / 100.0) * bar_width)
    bar = "▓" * full + "░" * (bar_width - full)

    return (
        f"🧬 Level {level} — {bar} {pct}% ({xp_current}/{xp_to})\n"
        f"➡ XP needed to next level: {max(0, xp_to - xp_current)}"
    )

def _kill_milestone_flair(kills: int) -> Optional[str]:
    """Fun flair for kill milestones."""
    if kills and kills % 100 == 0:
        return f"🏆 {kills} kills milestone!"
    if kills and kills % 50 == 0:
        return f"🎖 {kills} kills milestone!"
    if kills and kills % 25 == 0:
        return f"✨ {kills} kills milestone!"
    if kills and kills % 10 == 0:
        return f"🔥 {kills} kills milestone!"
    return None

# ============================================================
# SETUP
# ============================================================

def setup(bot: TeleBot):

    # ========================================================
    # /battle command — with 12h cooldown
    # ========================================================
    @bot.message_handler(commands=["battle"])
    def cmd_battle(message):
        uid = message.from_user.id

        # 12 hours = 43200 seconds
        COOLDOWN_SECONDS = 12 * 3600  
        cds = db.get_cooldowns(uid) or {}
        last_ts = int(cds.get("battle", 0) or 0)
        now_ts = int(time.time())

        def fmt(sec: int) -> str:
            if sec <= 0:
                return "0s"
            h = sec // 3600
            m = (sec % 3600) // 60
            s = sec % 60
            if h > 0:
                return f"{h}h {m}m"
            if m > 0:
                return f"{m}m {s}s"
            return f"{s}s"

        if last_ts and (last_ts + COOLDOWN_SECONDS) > now_ts:
            remaining = (last_ts + COOLDOWN_SECONDS) - now_ts
            pretty = fmt(remaining)
            bot.reply_to(
                message,
                f"⏳ You can start your next battle in {pretty}. (12-hour cooldown)"
            )
            return

        # Not on cooldown → set now
        cds["battle"] = now_ts
        db.set_cooldowns(uid, cds)

        # Show Tier Menu
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("🐀 Tier 1 — Common", callback_data="battle:choose_tier:1"),
            types.InlineKeyboardButton("⚔️ Tier 2 — Uncommon", callback_data="battle:choose_tier:2"),
        )
        kb.add(
            types.InlineKeyboardButton("🔥 Tier 3 — Rare", callback_data="battle:choose_tier:3"),
            types.InlineKeyboardButton("👑 Tier 4 — Epic", callback_data="battle:choose_tier:4"),
        )
        kb.add(
            types.InlineKeyboardButton("🐉 Tier 5 — Legendary", callback_data="battle:choose_tier:5")
        )

        bot.reply_to(
            message,
            "⚔️ *Choose your opponent tier:*",
            reply_markup=kb,
            parse_mode="Markdown",
        )

    # ========================================================
    # TIER SELECTION
    # ========================================================
    @bot.callback_query_handler(func=lambda c: c.data.startswith("battle:choose_tier"))
    def cb_choose_tier(call):
        try:
            _, _, tier_str = call.data.split(":")
            tier = int(tier_str)
        except:
            return bot.answer_callback_query(call.id, "Invalid tier.")

        uid = call.from_user.id
        user = db.get_user(uid)

        mob_full = mobs.get_random_mob(tier)
        if not mob_full:
            return bot.answer_callback_query(call.id, "No mobs found for this tier.")

        mob_stats = build_mob_stats_from_mob(mob_full)
        player_stats = build_player_stats_from_user(user)

        # Create session
        sess = battle_manager.create_session(uid, player_stats, mob_stats, mob_full)

        # Track the message for editing
        sess._last_msg = {"chat": call.message.chat.id, "msg": call.message.message_id}
        battle_manager.save_session(sess)

        caption = _build_caption(sess)
        kb = _build_keyboard(sess)

        try:
            bot.edit_message_text(
                caption,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb,
                parse_mode="Markdown"
            )
        except:
            bot.send_message(call.message.chat.id, caption, reply_markup=kb, parse_mode="Markdown")

        bot.answer_callback_query(call.id)

    # ========================================================
    # ACTION HANDLER — attack/block/etc
    # ========================================================
    @bot.callback_query_handler(func=lambda c: c.data.startswith("battle:act"))
    def cb_action(call):
        _, _, action, sid = call.data.split(":")

        # Load session
        sess = battle_manager.load_session_by_sid(sid)
        if not sess:
            # legacy fallback
            try:
                uid = int(sid)
                sess = battle_manager.load_session(uid)
            except:
                sess = None

        if not sess:
            return bot.answer_callback_query(call.id, "Session expired.", show_alert=True)

        # owner-only enforcement
        if call.from_user.id != sess.user_id:
            return bot.answer_callback_query(call.id, "❌ This is not your battle.", show_alert=True)

        chat_id = sess._last_msg["chat"] if sess._last_msg else call.message.chat.id
        msg_id = sess._last_msg["msg"] if sess._last_msg else None

        # surrender
        if action == ACTION_SURRENDER:
            sess.ended = True
            sess.winner = "mob"
            battle_manager.save_session(sess)
            _finalize_single_message(bot, sess, chat_id)
            return bot.answer_callback_query(call.id, "You surrendered.")

        # auto mode toggle
        if action == ACTION_AUTO:
            sess.auto_mode = not sess.auto_mode
            battle_manager.save_session(sess)

            if sess.auto_mode:
                for _ in range(4):
                    if sess.ended:
                        break
                    sess.resolve_auto_turn()
                    battle_manager.save_session(sess)

            if sess.ended:
                _finalize_single_message(bot, sess, chat_id)
            else:
                _safe_edit(bot, chat_id, msg_id, _build_caption(sess), _build_keyboard(sess))
            return bot.answer_callback_query(call.id)

        if action not in {ACTION_ATTACK, ACTION_BLOCK, ACTION_DODGE, ACTION_CHARGE}:
            return bot.answer_callback_query(call.id, "Unknown action.", show_alert=True)

        # normal action
        sess.resolve_player_action(action)
        battle_manager.save_session(sess)

        if sess.ended:
            _finalize_single_message(bot, sess, chat_id)
        else:
            _safe_edit(bot, chat_id, msg_id, _build_caption(sess), _build_keyboard(sess))

        return bot.answer_callback_query(call.id)


# ============================================================
# BATTLE CAPTION (live)
# ============================================================
def _build_caption(sess: BattleSession) -> str:
    hp_p = max(0, sess.player_hp)
    hp_m = max(0, sess.mob_hp)
    max_p = sess.player.get("hp", 100)
    max_m = sess.mob.get("hp", 100)

    bar_p = _hp_bar(hp_p, max_p)
    bar_m = _hp_bar(hp_m, max_m)

    mob_name = sess.mob_full.get("name") if sess.mob_full else sess.mob.get("name", "Mob")

    lines = [
        f"⚔️ *Battle vs {mob_name}*",
        "",
        f"🧍 You:   {bar_p} {hp_p}/{max_p}",
        f"👹 Enemy: {bar_m} {hp_m}/{max_m}",
        "",
        f"Turn: {sess.turn}",
        "",
    ]

    # Only last 2 events for clean UX
    if sess.events:
        lines.append("*Recent actions:*")
        for ev in sess.events[:2]:
            actor = "You" if ev["actor"] == "player" else mob_name
            if ev["action"] == "attack":
                lines.append(f"• {actor} dealt {ev['damage']} dmg {ev.get('note','')}")
            else:
                lines.append(f"• {actor}: {ev['action']} {ev.get('note','')}")

    return "\n".join(lines)


# ============================================================
# BUTTONS
# ============================================================
def _build_keyboard(sess: BattleSession) -> types.InlineKeyboardMarkup:
    sid = getattr(sess, "session_id", None) or ""
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🗡 Attack", callback_data=_cbdata(ACTION_ATTACK, sid)),
        types.InlineKeyboardButton("🛡 Block", callback_data=_cbdata(ACTION_BLOCK, sid)),
    )
    kb.add(
        types.InlineKeyboardButton("💨 Dodge", callback_data=_cbdata(ACTION_DODGE, sid)),
        types.InlineKeyboardButton("⚡ Charge", callback_data=_cbdata(ACTION_CHARGE, sid)),
    )
    kb.add(
        types.InlineKeyboardButton("▶ Auto" if not sess.auto_mode else "⏸ Auto", callback_data=_cbdata(ACTION_AUTO, sid)),
        types.InlineKeyboardButton("❌ Surrender", callback_data=_cbdata(ACTION_SURRENDER, sid)),
    )
    return kb


# ============================================================
# FINAL RESULT MESSAGE (single message)
# ============================================================
def _finalize_single_message(bot: TeleBot, sess: BattleSession, chat_id: int):
    mob = sess.mob_full or {}
    mob_name = mob.get("name", sess.mob.get("name", "Mob"))
    min_xp = int(mob.get("min_xp", 10))
    max_xp = int(mob.get("max_xp", min_xp + 10))
    drops = mob.get("drops", [])

    xp_gain = random.randint(min_xp, max_xp)

    uid = sess.user_id
    user = db.get_user(uid)

    # XP/level logic
    xp_current = int(user.get("xp_current", 0)) + xp_gain
    xp_total = int(user.get("xp_total", 0)) + xp_gain
    xp_to_next = int(user.get("xp_to_next_level", 100))
    level = int(user.get("level", 1))
    curve = float(user.get("level_curve_factor", 1.35) or 1.35)

    leveled = 0
    while xp_current >= xp_to_next:
        xp_current -= xp_to_next
        level += 1
        leveled += 1
        xp_to_next = int(xp_to_next * curve)

    mobs_defeated = int(user.get("mobs_defeated", 0))
    if sess.winner == "player":
        mobs_defeated += 1

    db.update_user_xp(uid, {
        "xp_total": xp_total,
        "xp_current": xp_current,
        "xp_to_next_level": xp_to_next,
        "level": level,
        "mobs_defeated": mobs_defeated
    })

    # Build final message
    display_name = user.get("display_name") or user.get("username") or f"User{uid}"
    header = f"*{display_name}*\n/battle\n"
    result_line = "🏆 VICTORY!" if sess.winner == "player" else "💀 DEFEAT…"
    title = f"{result_line} vs {mob_name}\n\n"

    xp_line = f"📈 XP Gained: +{xp_gain}\n"
    if leveled:
        xp_line += f"🎉 Level up! +{leveled}\n"

    progress = _progress_line(db.get_user(uid))

    # highlights
    best_player_hit = 0
    best_mob_hit = 0
    for ev in sess.events:
        if ev.get("action") == "attack":
            if ev.get("actor") == "player":
                best_player_hit = max(best_player_hit, int(ev.get("damage") or 0))
            else:
                best_mob_hit = max(best_mob_hit, int(ev.get("damage") or 0))

    highlights = [
        "*Highlights:*",
        f"• Your best hit: {best_player_hit} dmg",
        f"• Enemy best hit: {best_mob_hit} dmg",
        f"• Turns: {sess.turn}",
    ]

    drops_text = ""
    if drops:
        drops_text = "🎁 Drops: " + ", ".join(drops)

    milestone = _kill_milestone_flair(mobs_defeated)
    milestone_text = f"\n\n{milestone}" if milestone else ""

    final_text = "\n".join([
        header,
        title,
        xp_line,
        progress,
        "",
        "\n".join(highlights),
        "",
        drops_text,
        milestone_text
    ])

    # send or edit final message
    try:
        msg_id = sess._last_msg["msg"] if sess._last_msg else None
        chat = sess._last_msg["chat"] if sess._last_msg else chat_id
        if msg_id:
            bot.edit_message_text(final_text, chat, msg_id, parse_mode="Markdown")
        else:
            bot.send_message(chat, final_text, parse_mode="Markdown")
    except Exception:
        bot.send_message(chat_id, final_text, parse_mode="Markdown")

    # cleanup
    sid = getattr(sess, "session_id", None)
    if sid:
        battle_manager.end_session_by_sid(sid)
    else:
        battle_manager.end_session(sess.user_id)
