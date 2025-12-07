import random
import time
from telebot import TeleBot

from bot.db import (
    get_user,
    get_quests,
    update_user_xp,
    record_quest,
    increment_ritual
)

import bot.evolutions as evolutions
from bot.leaderboard_tracker import announce_leaderboard_if_changed


def setup(bot: TeleBot):

    @bot.message_handler(commands=["hop"])
    def hop_cmd(message):

        uid = message.from_user.id

        # --- Daily Hop Restriction ---
        try:
            quests = get_quests(uid)
            if quests.get("hop", 0) == 1:
                return bot.reply_to(
                    message,
                    "🐸 You already performed today’s Hop Ritual!"
                )
        except Exception:
            # Fail-safe: if DB cannot read quests, still attempt ritual
            quests = {}

        try:
            user = get_user(uid)
        except Exception:
            return bot.reply_to(message, "❌ Could not load your profile.")

        # --- XP Reward ---
        base_gain = random.randint(20, 50)

        # Optional: Give evo multiplier bonus (same as battles)
        try:
            evo_mult = evolutions.get_xp_multiplier_for_level(user["level"])
        except Exception:
            evo_mult = 1.0

        effective_xp = int(base_gain * evo_mult)

        xp_total = user["xp_total"] + effective_xp
        cur = user["xp_current"] + effective_xp

        xp_to_next = user["xp_to_next_level"]
        level = user["level"]
        curve = user["level_curve_factor"]

        leveled = False

        # --- Level Up Loop ---
        while cur >= xp_to_next:
            cur -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * curve)
            leveled = True

        # --- Persist XP ---
        update_user_xp(uid, {
            "xp_total": xp_total,
            "xp_current": cur,
            "xp_to_next_level": xp_to_next,
            "level": level
        })

        # --- NEW: Real-time Leaderboard Update ---
        try:
            announce_leaderboard_if_changed(bot)
        except Exception as e:
            print("Leaderboard update failed in hop.py:", e)

        # --- Ritual Count ---
        try:
            record_quest(uid, "hop")
            increment_ritual(uid)
        except Exception:
            pass

        # --- Build Message ---
        msg = (
            f"🐸✨ *Hop Ritual Complete!* +{effective_xp} XP\n"
            f"🔮 (Base {base_gain} × Evo {evo_mult:.2f})"
        )

        if leveled:
            msg += "\n🎉 LEVEL UP! Your MegaGrok grows stronger!"

        bot.reply_to(message, msg, parse_mode="Markdown")
