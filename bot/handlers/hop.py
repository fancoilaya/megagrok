# bot/handlers/hop.py
# Hop 2.1 — Robust Hop handler
# - Uses shared cooldowns dict (merges, does not overwrite)
# - Rarity-based XP (common/rare/epic/legendary)
# - Hop streak (7/14/30 badges supported through cooldowns)
# - Micro-events (10% chance)
# - Evolution-aware multiplier
# - Safe math (no ZeroDivisionError), defensive coding
# - Always replies (falls back to a safe message on error)
# - DEBUG_HOP env toggle for diagnostic prints

import os
import time
import random
from telebot import TeleBot

from bot.db import (
    get_user,
    update_user_xp,
    get_quests,
    record_quest,
    get_cooldowns,
    set_cooldowns,
)

import bot.evolutions as evolutions
from bot.leaderboard_tracker import announce_leaderboard_if_changed

# -------------------------
# Config
# -------------------------
GLOBAL_HOP_KEY = "hop"           # quest key marking hop used today
HOP_STREAK_KEY = "hop_streak"
HOP_LAST_DAY_KEY = "hop_last_day"
DEBUG = os.getenv("DEBUG_HOP", "0") in ("1", "true", "True", "TRUE")
# Rarity chances: legendary 1%, epic 9%, rare 20%, common rest
MICRO_EVENT_CHANCE = 0.10

def _debug(*args, **kwargs):
    if DEBUG:
        print("[HOP DEBUG]", *args, **kwargs)

# -------------------------
# Helpers
# -------------------------
def _now_day():
    """Return the UTC day number (integer)."""
    return int(time.time() // 86400)

def _safe_get_cooldowns(uid: int) -> dict:
    try:
        cd = get_cooldowns(uid)
        if isinstance(cd, dict):
            return cd
        # defensive: if stored as JSON string or None, return empty dict
        return {}
    except Exception as e:
        _debug("get_cooldowns failed for", uid, ":", e)
        return {}

def _safe_set_cooldowns(uid: int, cd: dict):
    try:
        set_cooldowns(uid, cd)
    except Exception as e:
        _debug("set_cooldowns failed for", uid, ":", e)

def _rarity_and_base():
    r = random.random()
    if r < 0.01:
        return "legendary", random.randint(150, 250)
    if r < 0.10:
        return "epic", random.randint(70, 120)
    if r < 0.30:
        return "rare", random.randint(35, 65)
    return "common", random.randint(15, 35)

def _micro_event_roll():
    if random.random() < MICRO_EVENT_CHANCE:
        events = [
            ("🍃 Lucky Leaf", random.randint(10, 25)),
            ("🌌 Cosmic Ripple", random.randint(20, 50)),
            ("💦 Hop Slip", random.randint(-15, -5)),
            ("🐸 Spirit Whisper", 0),  # cosmetic
        ]
        return random.choice(events)
    return None

def _streak_bonus_pct(streak: int) -> int:
    """
    Return total bonus percent based on streak.
    Matches design: small scaling with cap.
    """
    if streak <= 1:
        return 0
    # We'll use a stepped system:
    if streak >= 30:
        return 20
    if streak >= 14:
        return 15
    if streak >= 7:
        return 10
    if streak >= 5:
        return 7
    if streak >= 3:
        return 5
    if streak == 2:
        return 3
    return 0

def _safe_progress_bar(cur: int, nxt: int, bar_len: int = 20) -> (str, int):
    """Return (bar_text, pct) safely. Avoid divide by zero."""
    try:
        if nxt <= 0:
            return ("░" * bar_len, 0)
        pct = int((cur / nxt) * 100)
        filled = int((pct / 100.0) * bar_len)
        filled = max(0, min(bar_len, filled))
        bar = "▓" * filled + "░" * (bar_len - filled)
        return bar, pct
    except Exception as e:
        _debug("progress bar calc failed:", e)
        return ("░" * bar_len, 0)

# -------------------------
# Handler
# -------------------------
def setup(bot: TeleBot):

    @bot.message_handler(commands=["hop"])
    def hop_handler(message):
        uid = message.from_user.id
        try:
            user = get_user(uid)
        except Exception as e:
            _debug("get_user failed for", uid, ":", e)
            return bot.reply_to(message, "❌ Error loading your profile. Try again later.")

        if not user:
            return bot.reply_to(message, "❌ You do not have a Grok yet.")

        # QUICK: check quest flag (this is how your system tracked "used today")
        try:
            quests = get_quests(uid)
        except Exception as e:
            _debug("get_quests failed for", uid, ":", e)
            quests = {}

        if quests.get(GLOBAL_HOP_KEY, 0) == 1:
            # user already used hop today
            return bot.reply_to(message, "🕒 You already used /hop today.")

        # load cooldowns (shared object) and safely read streak/day
        cd = _safe_get_cooldowns(uid)
        today = _now_day()

        last_day_raw = cd.get(HOP_LAST_DAY_KEY)
        # normalize last_day to integer if possible
        last_day = None
        if isinstance(last_day_raw, int):
            last_day = last_day_raw
        elif isinstance(last_day_raw, str) and last_day_raw.isdigit():
            try:
                last_day = int(last_day_raw)
            except:
                last_day = None

        # determine streak behavior
        if last_day is None:
            # new or no previous hop info
            prev_streak = int(cd.get(HOP_STREAK_KEY, 0) or 0)
            # If last_day missing but streak exists, we keep streak (safer) and treat as new day
            # but ensure we won't double-apply if a user has quests flagged (handled above)
            can_count = True
        else:
            if last_day == today:
                # shouldn't reach here because quest check above, but safety:
                return bot.reply_to(message, "🕒 You already used /hop today.")
            elif last_day == today - 1:
                prev_streak = int(cd.get(HOP_STREAK_KEY, 0) or 0)
                can_count = True
            else:
                # missed days -> reset streak
                prev_streak = 0
                can_count = True

        # increment streak (start at 1)
        new_streak = prev_streak + 1 if can_count else prev_streak
        bonus_pct = _streak_bonus_pct(new_streak)
        _debug(f"user={uid} prev_streak={prev_streak} new_streak={new_streak} bonus={bonus_pct}%")

        # Rarity & base XP
        rarity, base_xp = _rarity_and_base()
        _debug("rarity/base_xp:", rarity, base_xp)

        # Micro event
        micro = _micro_event_roll()
        micro_label = None
        micro_xp = 0
        if micro:
            micro_label, micro_xp = micro
            _debug("micro event:", micro_label, micro_xp)
            base_xp += micro_xp

        # Evolution multiplier (defensive)
        try:
            evo_mult = float(evolutions.get_xp_multiplier_for_level(int(user.get("level", 1))))
            evo_mult *= float(user.get("evolution_multiplier", 1.0))
        except Exception as e:
            _debug("evolution multiplier failed:", e)
            evo_mult = 1.0

        # final effective XP
        try:
            effective = int(round(base_xp * (1 + (bonus_pct / 100.0)) * evo_mult))
        except Exception as e:
            _debug("final XP calc failed:", e)
            effective = max(0, int(base_xp))

        # Apply XP and leveling (defensive)
        try:
            # persist xp
            level = int(user.get("level", 1))
            xp_total = int(user.get("xp_total", 0)) + effective
            cur = int(user.get("xp_current", 0)) + effective
            nxt = int(user.get("xp_to_next_level", 100))
            curve = float(user.get("level_curve_factor", 1.15))

            leveled = False
            leveled_down = False
            # level up
            while nxt > 0 and cur >= nxt:
                cur -= nxt
                level += 1
                nxt = int(max(1, nxt * curve))
                leveled = True

            # level down (shouldn't usually happen here)
            while cur < 0 and level > 1:
                level -= 1
                nxt = int(max(1, nxt / curve))
                cur += nxt
                leveled_down = True

            # ensure sane
            cur = max(0, cur)
            xp_total = max(0, xp_total)

            update_user_xp(uid, {
                "xp_total": xp_total,
                "xp_current": cur,
                "xp_to_next_level": nxt,
                "level": level
            })
        except Exception as e:
            _debug("XP persist failed for", uid, ":", e)
            return bot.reply_to(message, "⚠️ Error applying hop XP — try again later.")

        # Save hop usage: merge cooldowns safely (DO NOT overwrite other keys)
        try:
            # ensure cd is a dict we modify
            cd = cd if isinstance(cd, dict) else {}
            cd[HOP_STREAK_KEY] = new_streak
            cd[HOP_LAST_DAY_KEY] = today
            # IMPORTANT: don't remove other cooldown keys — just update and write back
            _safe_set_cooldowns(uid, cd)
        except Exception as e:
            _debug("Failed saving hop cooldowns for", uid, ":", e)
            # keep going; do not abort — we want to reply

        # Mark quest used today safely
        try:
            record_quest(uid, GLOBAL_HOP_KEY)
        except Exception as e:
            _debug("record_quest failed for", uid, ":", e)

        # Announce leaderboard update (best-effort)
        try:
            announce_leaderboard_if_changed(bot)
        except Exception as e:
            _debug("announce leaderboard failed:", e)

        # Build response (safe formatting)
        try:
            # load updated user for progress bar
            try:
                updated_user = get_user(uid)
            except Exception:
                updated_user = {
                    "level": level,
                    "xp_current": cur,
                    "xp_to_next_level": nxt
                }

            bar, pct = _safe_progress_bar(int(updated_user.get("xp_current", cur)),
                                          int(updated_user.get("xp_to_next_level", nxt)))

            rarity_emoji = {
                "legendary": "🌈",
                "epic": "💎",
                "rare": "✨",
                "common": "🐸",
            }.get(rarity, "🐸")

            parts = []
            parts.append(f"{rarity_emoji} <b>{rarity.upper()} HOP!</b>")
            parts.append(f"📈 XP gained: <b>{effective}</b>")

            if micro_label:
                sign = "+" if micro_xp > 0 else ""
                parts.append(f"{micro_label} ({sign}{micro_xp} XP)")

            parts.append(f"🔥 Hop streak: <b>{new_streak} days</b> (+{bonus_pct}% bonus)")
            if leveled:
                parts.append("🎉 <b>LEVEL UP!</b>")
            if leveled_down:
                parts.append("💀 <b>LEVEL DOWN!</b>")

            parts.append(f"🧬 Level {level} — <code>{bar}</code> {pct}% ({cur}/{nxt})")
            parts.append("⏳ Next hop available tomorrow")

            # Badge hints (not unlocking logic here, but informative)
            if new_streak >= 30:
                parts.append("🏅 Badge: <b>Hop Ascended (30-day)</b>")
            elif new_streak >= 14:
                parts.append("🏅 Badge: <b>Hop Sage (14-day)</b")
            elif new_streak >= 7:
                parts.append("🏅 Badge: <b>Hop Master (7-day)</b>")

            # final reply
            return bot.reply_to(message, "\n".join(parts), parse_mode="HTML")
        except Exception as e:
            _debug("Failed building/sending reply for", uid, ":", e)
            # fallback minimal reply
            try:
                return bot.reply_to(message, f"✅ Hop complete! XP: {effective}")
            except Exception as e2:
                _debug("Fallback reply failed for", uid, ":", e2)
                # nothing more we can do
                return

    _debug("hop handler registered")
