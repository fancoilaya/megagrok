# bot/handlers/growmygrok.py
# GrowMyGrok 2.5 — Single-message UX with cooldown refresh (PATCHED)

import os
import time
import random
from telebot import TeleBot, types

from bot.db import (
    get_user,
    update_user_xp,
    get_cooldowns,
    set_cooldowns,
    record_quest,
)
import bot.evolutions as evolutions
from bot.leaderboard_tracker import announce_leaderboard_if_changed


# ----------------------------
# Configuration
# ----------------------------
GLOBAL_GROW_COOLDOWN = 45 * 60

XP_RANGES = {
    "train": (-2, 10),
    "forage": (-8, 20),
    "gamble": (-25, 40),
}

MODE_DESCRIPTIONS = {
    "train": (
        "🛠️ <b>Train</b> — Low Risk\n"
        "• Small, guaranteed XP\n"
        "• Safe progression\n"
        "• No penalties"
    ),
    "forage": (
        "🍃 <b>Forage</b> — Medium Risk\n"
        "• Higher XP potential\n"
        "• Chance of failure"
    ),
    "gamble": (
        "🎲 <b>Gamble</b> — High Risk\n"
        "• Massive XP if successful\n"
        "• Chance to lose XP"
    ),
}

STREAK_KEY = "grow_streak"
STREAK_BONUS_PER = 0.03
STREAK_CAP = 10

MICRO_EVENT_CHANCE = 1 / 20
MICRO_EVENTS = [
    ("lucky_find", "🌟 Your Grok found a glowing mushroom!", 50),
    ("bad_weather", "🌧️ Bad weather drained energy.", -10),
    ("mini_fight", "⚔️ Training fight sharpened instincts.", 12),
]

MAX_LOSS_PCT = 0.05
DEBUG = os.getenv("DEBUG_GROW", "0") in ("1", "true", "True")


# ----------------------------
# Helpers
# ----------------------------
def _now():
    return int(time.time())


def _load_cd(uid):
    try:
        cd = get_cooldowns(uid)
        return cd if isinstance(cd, dict) else {}
    except Exception:
        return {}


def _save_cd(uid, cd):
    try:
        set_cooldowns(uid, cd)
    except Exception:
        pass


def _format_cd(seconds: int) -> str:
    if seconds <= 0:
        return "Ready"
    m, s = divmod(seconds, 60)
    return f"{m}m {s}s"


def _cap_negative(val, xp_next):
    if val >= 0:
        return val
    cap = max(1, int(xp_next * MAX_LOSS_PCT))
    return -min(cap, abs(val))


def _apply_xp(uid, user, delta):
    level = user["level"]
    cur = user["xp_current"]
    nxt = user["xp_to_next_level"]
    curve = user.get("level_curve_factor", 1.15)

    cur += delta
    leveled_up = False

    while cur >= nxt:
        cur -= nxt
        level += 1
        nxt = int(nxt * curve)
        leveled_up = True

    cur = max(0, cur)

    update_user_xp(uid, {
        "level": level,
        "xp_current": cur,
        "xp_to_next_level": nxt,
        "xp_total": user["xp_total"] + delta,
    })

    return get_user(uid), leveled_up


def _cooldown_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔄 Refresh timer", callback_data="grow:refresh"),
        types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="__xphub__:home"),
    )
    return kb


def _button_label(mode: str) -> str:
    first = MODE_DESCRIPTIONS[mode].split("\n")[0]
    return first.replace("<b>", "").replace("</b>", "")


# ----------------------------
# PUBLIC UI ENTRY
# ----------------------------
def show_grow_ui(
    bot: TeleBot,
    chat_id: int,
    message_id: int | None = None,
    uid: int | None = None,
):
    # =====================================================
    # NEW: COOLDOWN CHECK ON ENTRY (THIS IS THE FIX)
    # =====================================================
    if uid is not None:
        cd = _load_cd(uid)
        last = cd.get("grow_last_action", 0)
        now = _now()

        if last and now - last < GLOBAL_GROW_COOLDOWN:
            left = GLOBAL_GROW_COOLDOWN - (now - last)

            bot.edit_message_text(
                f"⏳ <b>Grow is on cooldown</b>\n\n"
                f"⏱️ {_format_cd(left)} remaining",
                chat_id,
                message_id,
                reply_markup=_cooldown_keyboard(),
                parse_mode="HTML",
            )
            return
    # =====================================================

    kb = types.InlineKeyboardMarkup(row_width=1)

    for m in XP_RANGES:
        kb.add(
            types.InlineKeyboardButton(
                _button_label(m),
                callback_data=f"grow:{m}"
            )
        )

    kb.add(types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="__xphub__:home"))

    text = (
        "🌱 <b>Choose how to grow your Grok</b>\n\n"
        f"{MODE_DESCRIPTIONS['train']}\n\n"
        f"{MODE_DESCRIPTIONS['forage']}\n\n"
        f"{MODE_DESCRIPTIONS['gamble']}\n\n"
        "👇 Select an option:"
    )

    if message_id:
        bot.edit_message_text(
            text,
            chat_id,
            message_id,
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        bot.send_message(
            chat_id,
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )


# ----------------------------
# Handlers
# ----------------------------
def setup(bot: TeleBot):

    @bot.message_handler(commands=["growmygrok"])
    def grow_cmd(message):
        show_grow_ui(bot, message.chat.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("grow:"))
    def grow_cb(call):
        uid = call.from_user.id
        chat_id = call.message.chat.id
        msg_id = call.message.message_id
        data = call.data
        now = _now()

        user = get_user(uid)
        if not user:
            return

        cd = _load_cd(uid)
        last = cd.get("grow_last_action", 0)

        # ----------------------------
        # REFRESH
        # ----------------------------
        if data == "grow:refresh":
            left = max(0, GLOBAL_GROW_COOLDOWN - (now - last))
            if left <= 0:
                show_grow_ui(bot, chat_id, msg_id, uid)
                return

            bot.edit_message_text(
                f"⏳ <b>Grow is on cooldown</b>\n\n"
                f"⏱️ {_format_cd(left)} remaining",
                chat_id,
                msg_id,
                reply_markup=_cooldown_keyboard(),
                parse_mode="HTML"
            )
            return

        # ----------------------------
        # MODE SELECTED
        # ----------------------------
        mode = data.split(":")[1]

        if last and now - last < GLOBAL_GROW_COOLDOWN:
            left = GLOBAL_GROW_COOLDOWN - (now - last)

            bot.edit_message_text(
                f"⏳ <b>Grow is on cooldown</b>\n\n"
                f"⏱️ {_format_cd(left)} remaining",
                chat_id,
                msg_id,
                reply_markup=_cooldown_keyboard(),
                parse_mode="HTML"
            )
            return

        # ----------------------------
        # EXECUTE GROW
        # ----------------------------
        lo, hi = XP_RANGES[mode]
        base = random.randint(lo, hi)

        evo_mult = evolutions.get_xp_multiplier_for_level(user["level"])
        streak = cd.get(STREAK_KEY, 0)
        streak_mult = 1 + min(streak, STREAK_CAP) * STREAK_BONUS_PER

        xp = int(base * evo_mult * streak_mult)

        micro_msg = None
        if random.random() < MICRO_EVENT_CHANCE:
            _, micro_msg, delta = random.choice(MICRO_EVENTS)
            xp += delta

        xp = _cap_negative(xp, user["xp_to_next_level"])
        success = xp > 0

        new_user, leveled_up = _apply_xp(uid, user, xp)

        cd["grow_last_action"] = now
        cd[STREAK_KEY] = streak + 1 if success else 0
        _save_cd(uid, cd)

        record_quest(uid, "grow")
        announce_leaderboard_if_changed(bot)

        bar_len = 12
        pct = int((new_user["xp_current"] / new_user["xp_to_next_level"]) * 100)
        filled = int((pct / 100) * bar_len)
        bar = "▓" * filled + "░" * (bar_len - filled)

        text = (
            f"{MODE_DESCRIPTIONS[mode].splitlines()[0]}\n"
            f"📈 XP: <b>{xp:+d}</b>\n"
            f"🔥 Streak: {cd[STREAK_KEY]}\n\n"
            f"🧬 Level {new_user['level']} — <code>{bar}</code> {pct}%"
        )

        if micro_msg:
            text += f"\n\n{micro_msg}"
        if leveled_up:
            text += "\n\n🎉 <b>LEVEL UP!</b>"

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="__xphub__:home"))

        bot.edit_message_text(
            text,
            chat_id,
            msg_id,
            reply_markup=kb,
            parse_mode="HTML"
        )
