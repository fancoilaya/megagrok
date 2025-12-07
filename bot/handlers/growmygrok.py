# bot/handlers/growmygrok.py
# GrowMyGrok 2.0 — Train / Forage / Gamble, with streaks, micro-events, and fair losses.

import os
import time
import random
import json
from telebot import TeleBot

from bot.db import (
    get_user,
    update_user_xp,
    get_quests,
    record_quest,
    get_cooldowns,
    set_cooldowns
)
from bot.utils import safe_send_gif
import bot.evolutions as evolutions
from bot.leaderboard_tracker import announce_leaderboard_if_changed

# Cooldowns (seconds)
COOLDOWNS = {
    "train": 20 * 60,    # 20 minutes
    "forage": 30 * 60,   # 30 minutes
    "gamble": 45 * 60    # 45 minutes
}

# XP ranges per action (base before evo multiplier & streaks & modifiers)
XP_RANGES = {
    "train": (-2, 10),
    "forage": (-8, 20),
    "gamble": (-25, 40)
}

# Streak config
STREAK_KEY = "grow_streak"      # stored inside cooldowns JSON for user
STREAK_BONUS_PER = 0.03        # +3% per successive success
STREAK_CAP = 10                # cap streak bonus at +30%

# Micro-event chances
MICRO_EVENT_CHANCE = 1 / 20.0  # 5% chance
MICRO_EVENTS = [
    ("lucky_find", "🌟 Your Grok found a glowing mushroom!", 50),
    ("bad_weather", "🌧️ Bad weather! Your Grok got damp and lost energy.", -10),
    ("mini_fight", "⚔️ Your Grok fought a tiny critter and trained through the scuffle.", 12),
    ("mystic_whisper", "🔮 A whisper passes — you feel closer to evolution (cosmetic).", 0),
]

# Loss cap: max percent of xp_to_next that can be lost on a negative result
MAX_LOSS_PCT = 0.05  # 5% of xp_to_next_level

COOLDOWN_STORE_DIR = "/tmp/megagrok_grow_cooldowns"
os.makedirs(COOLDOWN_STORE_DIR, exist_ok=True)


def _user_cooldowns(uid: int) -> dict:
    """
    Load cooldowns from DB (JSON stored in users.cooldowns column).
    Falls back to empty dict.
    """
    try:
        cd = get_cooldowns(uid)
        if isinstance(cd, dict):
            return cd
    except Exception:
        pass
    return {}


def _save_user_cooldowns(uid: int, cd: dict):
    try:
        set_cooldowns(uid, cd)
    except Exception:
        pass


def _now_ts():
    return int(time.time())


def _time_of_day_modifier():
    """
    Small time-of-day flavor modifiers:
      - Morning (06-11): +5 flat XP
      - Evening (18-21): +10% multiplier
      - LateNight (00-03): -10% chance of loss increased (we'll adapt by returning a multiplier)
    Returns a tuple (flat_add, pct_mult, loss_risk_mult) where pct_mult multiplies XP gains,
    loss_risk_mult can be used to slightly increase chance of negative outcome if desired.
    """
    t = time.localtime()
    hr = t.tm_hour
    if 6 <= hr < 12:
        return (5, 1.0, 1.0)
    if 18 <= hr < 22:
        return (0, 1.10, 1.0)  # +10% XP
    if 0 <= hr < 4:
        return (0, 0.95, 1.2)  # slightly worse
    return (0, 1.0, 1.0)


def _cap_negative_loss(neg_value: int, xp_to_next: int) -> int:
    """
    Ensure negative XP losses are bounded to MAX_LOSS_PCT of xp_to_next (at least -1).
    neg_value is negative (e.g. -12). Returns a negative int.
    """
    if neg_value >= 0:
        return neg_value
    cap = max(1, int(xp_to_next * MAX_LOSS_PCT))
    return -min(cap, abs(neg_value))


def _apply_leveling_logic_and_persist(uid: int, user_before: dict, delta_xp: int):
    """
    Applies delta_xp to the user and persists using update_user_xp.
    Returns a tuple (new_user_dict, leveled_up_flag, leveled_down_flag)
    """
    level = int(user_before.get("level", 1))
    xp_total = int(user_before.get("xp_total", 0))
    cur = int(user_before.get("xp_current", 0))
    xp_to_next = int(user_before.get("xp_to_next_level", 100))
    curve = float(user_before.get("level_curve_factor", 1.15))

    new_total = max(0, xp_total + delta_xp)
    cur += delta_xp

    leveled_up = False
    leveled_down = False

    # Level up loop
    while cur >= xp_to_next:
        cur -= xp_to_next
        level += 1
        xp_to_next = int(max(1, xp_to_next * curve))
        leveled_up = True

    # Level down loop
    while cur < 0 and level > 1:
        # step down one level
        level -= 1
        xp_to_next = int(max(1, xp_to_next / curve))
        cur += xp_to_next
        leveled_down = True

    cur = max(0, cur)
    new_total = max(0, new_total)

    update_user_xp(uid, {
        "xp_total": new_total,
        "xp_current": cur,
        "xp_to_next_level": xp_to_next,
        "level": level
    })

    # reload user
    new_user = get_user(uid)
    return new_user, leveled_up, leveled_down


def _maybe_micro_event():
    if random.random() < MICRO_EVENT_CHANCE:
        ev = random.choice(MICRO_EVENTS)
        # ev tuple: (key, message, xp_delta)
        return ev
    return None


def setup(bot: TeleBot):

    @bot.message_handler(commands=["growmygrok"])
    def grow(message):
        """
        /growmygrok [train|forage|gamble]
        Default: train
        """
        uid = message.from_user.id
        args = (message.text or "").split()
        action = "train"
        if len(args) >= 2 and args[1].lower() in ("train", "forage", "gamble"):
            action = args[1].lower()

        now = _now_ts()

        # Load user
        user = get_user(uid)
        if not user:
            return bot.reply_to(message, "❌ You do not have a Grok yet.")

        # Cooldown check stored in per-user cooldowns JSON
        cd = _user_cooldowns(uid)
        last_action = cd.get("grow_last_action", {}).get(action, 0)
        cooldown_seconds = COOLDOWNS.get(action, COOLDOWNS["train"])
        if last_action and now - last_action < cooldown_seconds:
            left = cooldown_seconds - (now - last_action)
            mins = left // 60
            secs = left % 60
            return bot.reply_to(message, f"⏳ `{action}` is on cooldown — wait {mins}m {secs}s.", parse_mode="Markdown")

        # Base random XP
        base_lo, base_hi = XP_RANGES.get(action, XP_RANGES["train"])
        base_xp = random.randint(base_lo, base_hi)

        # Time of day modifiers
        flat_td, pct_td, loss_risk_td = _time_of_day_modifier()

        # Evolution multiplier from your system
        try:
            evo_mult = float(evolutions.get_xp_multiplier_for_level(int(user.get("level", 1)))) * float(user.get("evolution_multiplier", 1.0))
        except Exception:
            evo_mult = 1.0

        # Streak handling inside cooldowns JSON
        streak = int(cd.get(STREAK_KEY, 0))
        streak_bonus = 1.0 + min(STREAK_CAP, streak) * STREAK_BONUS_PER

        # Apply multipliers
        effective = base_xp

        # Apply time-of-day percent (only to gains)
        if effective > 0:
            effective = int(round(effective * pct_td))
        # add flat time-of-day
        effective = effective + flat_td

        # Apply evolution multiplier & streak multiplier
        effective = int(round(effective * evo_mult * streak_bonus))

        # Micro-event
        micro = _maybe_micro_event()
        micro_msg = None
        if micro:
            key, mmsg, mdelta = micro
            micro_msg = mmsg
            # apply micro-event xp (this is additive after effective)
            # if mdelta negative, cap it similarly
            if mdelta < 0:
                mdelta = _cap_negative_loss(mdelta, int(user.get("xp_to_next_level", 100)))
            effective += mdelta

        # If negative, cap based on xp_to_next to avoid brutal punishment
        if effective < 0:
            effective = _cap_negative_loss(effective, int(user.get("xp_to_next_level", 100)))

        # Prepare narrative
        action_narratives = {
            "train": "🛠️ Training session",
            "forage": "🍃 Foraging outing",
            "gamble": "🎲 Reckless gamble"
        }
        narrative = action_narratives.get(action, "🛠️ Training")

        # Determine success/failure for streak management:
        # success = final effective XP > 0
        success = effective > 0

        # Persist XP change (and compute level up/down)
        try:
            new_user, leveled_up, leveled_down = _apply_leveling_logic_and_persist(uid, user, effective)
        except Exception as e:
            # don't crash; report error
            bot.reply_to(message, f"Error applying XP: {e}")
            return

        # Announce leaderboard changes (best-effort)
        try:
            announce_leaderboard_if_changed(bot)
        except Exception:
            pass

        # Update cooldowns + streak in DB
        try:
            cd.setdefault("grow_last_action", {})
            cd["grow_last_action"][action] = now
            # update streak: increment on success, reset on failure
            if success:
                cd[STREAK_KEY] = min(STREAK_CAP, streak + 1)
            else:
                cd[STREAK_KEY] = 0
            _save_user_cooldowns(uid, cd)
        except Exception:
            pass

        # record that user used grow today for quest tracking (optionally)
        try:
            record_quest(uid, "grow")
        except Exception:
            pass

        # Build response message
        parts = []
        parts.append(f"{narrative} — *{action.title()}*")
        parts.append(f"📈 Effective XP: `{effective:+d}`")
        if micro_msg:
            parts.append(micro_msg)

        # Streak info
        if success and cd.get(STREAK_KEY, 0) > 1:
            parts.append(f"🔥 Streak: {cd.get(STREAK_KEY)} (bonus +{int((cd.get(STREAK_KEY))*STREAK_BONUS_PER*100)}%)")
        elif not success:
            parts.append("❌ Streak reset.")

        # Level messages
        if leveled_up:
            parts.append("🎉 *LEVEL UP!* Your MegaGrok ascended!")
        if leveled_down:
            parts.append("💀 *LEVEL DOWN!* Your MegaGrok weakened.")

        # Progress bar for display
        try:
            cur = int(new_user.get("xp_current", 0))
            nxt = int(new_user.get("xp_to_next_level", 100))
            pct = int(round((cur / nxt) * 100)) if nxt else 0
            bar_len = 20
            fill = int((pct / 100) * bar_len)
            bar = "▓" * fill + "░" * (bar_len - fill)
            parts.append(f"🧬 Level: {new_user.get('level',1)} — `{bar}` {pct}% ({cur}/{nxt})")
        except Exception:
            pass

        # Attempt evolution event notification (non-blocking)
        try:
            old_stage = int(user.get("evolution_stage", 0))
            new_stage = int(new_user.get("evolution_stage", old_stage))
            if new_stage > old_stage:
                # try to send gif and message
                name_slug = new_user.get("evolution_name", "evolved").lower().replace(" ", "_")
                gif_path = f"assets/evolutions/{name_slug}/levelup.gif"
                fallback = f"assets/evolutions/{name_slug}/idle.gif"
                try:
                    if os.path.exists(gif_path):
                        safe_send_gif(bot, message.chat.id, gif_path)
                    elif os.path.exists(fallback):
                        safe_send_gif(bot, message.chat.id, fallback)
                except Exception:
                    pass
                parts.append(f"🔥 *Evolution!* Your MegaGrok became *{new_user.get('evolution_name','a new form')}*")
        except Exception:
            pass

        # Final send
        try:
            bot.reply_to(message, "\n\n".join(parts), parse_mode="Markdown")
        except Exception:
            # fallback plain text
            bot.reply_to(message, " ".join(parts))

