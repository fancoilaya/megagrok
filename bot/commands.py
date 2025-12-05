# bot/commands.py
# Core command handlers for MegaGrok bot
# All modular commands (/battle, /growmygrok, /grokdex, etc.) are in /bot/handlers

import os
import time
import random
from telebot import TeleBot
from PIL import Image

from bot.db import (
    get_user,
    update_user_xp,
    get_quests,
    record_quest,
    increment_win,
    increment_ritual,
    get_top_users
)

from bot.images import generate_leaderboard_poster_v2
from bot.profile_image import generate_profile_image
from bot.mobs import MOBS
import bot.evolutions as evolutions


# ======================================================
# • HELP TEXT
# ======================================================

HELP_TEXT = (
    "🐸 **MEGAGROK COMMANDS**\n\n"
    "/start – Begin your journey\n"
    "/help – Show this help menu\n"
    "/profile – View your Grok profile card\n"
    "/leaderboard – Global ranking poster\n"
    "/growmygrok – Gain XP and evolve your Grok\n"
    "/hop – Daily ritual for bonus XP\n"
    "/fight – Classic fight (1/day)\n"
    "/battle – Advanced RPG battle engine\n"
    "/grokdex – Browse all mobs\n"
    "/mob <name> – Inspect a creature\n\n"
    "🚀 Train. Evolve. Dominate the Hop-Verse."
)

START_TEXT = (
    "🐸🌌 *THE COSMIC AMPHIBIAN HAS AWAKENED*\n\n"
    "A portal cracks open… your MegaGrok emerges…\n"
    "Your evolution begins *now*.\n\n"
    "🔥 Core Commands:\n"
    "• /growmygrok – Feed cosmic hop-energy\n"
    "• /hop – Daily ritual boost\n"
    "• /fight – Quick XP fight\n"
    "• /battle – Full RPG combat\n"
    "• /profile – Your Grok card\n"
    "• /leaderboard – Global ranking\n\n"
    "Welcome to the MegaGrok Metaverse!"
)


# ======================================================
# • REGISTER HANDLERS
# ======================================================

def register_handlers(bot: TeleBot):

    # ---------------- START ----------------
    @bot.message_handler(commands=["start"])
    def start_cmd(message):
        bot.reply_to(message, START_TEXT, parse_mode="Markdown")

    # ---------------- HELP -----------------
    @bot.message_handler(commands=["help"])
    def help_cmd(message):
        bot.reply_to(message, HELP_TEXT, parse_mode="Markdown")

    # ======================================================
    #   /hop COMMAND
    # ======================================================
    @bot.message_handler(commands=["hop"])
    def hop_cmd(message):
        user_id = message.from_user.id
        q = get_quests(user_id)

        if q.get("hop", 0) == 1:
            bot.reply_to(message, "🐸 You already performed today’s Hop Ritual!")
            return

        xp_gain = random.randint(20, 50)
        user = get_user(user_id)

        xp_total = user["xp_total"] + xp_gain
        cur = user["xp_current"] + xp_gain
        xp_to_next = user["xp_to_next_level"]
        lvl = user["level"]
        curve = user["level_curve_factor"]

        if cur >= xp_to_next:
            cur -= xp_to_next
            lvl += 1
            xp_to_next = int(xp_to_next * curve)

        update_user_xp(
            user_id,
            {
                "xp_total": xp_total,
                "xp_current": cur,
                "xp_to_next_level": xp_to_next,
                "level": lvl
            }
        )

        increment_ritual(user_id)
        record_quest(user_id, "hop")
        bot.reply_to(message, f"🐸✨ Hop Ritual complete! +{xp_gain} XP")

    # ======================================================
    #   /fight COMMAND (classic version)
    # ======================================================
    @bot.message_handler(commands=["fight"])
    def fight_cmd(message):
        user_id = message.from_user.id
        q = get_quests(user_id)

        if q.get("fight", 0) == 1:
            bot.reply_to(message, "⚔️ You already fought today.")
            return

        mob = random.choice(list(MOBS.values()))
        bot.reply_to(
            message,
            f"⚔️ **{mob['name']} Encounter!**\n\n{mob.get('intro', '')}",
            parse_mode="Markdown"
        )

        # Try send portrait
        portrait = mob.get("portrait")
        if portrait and os.path.exists(portrait):
            with open(portrait, "rb") as f:
                bot.send_photo(message.chat.id, f)

        win = random.choice([True, False])
        base_xp = random.randint(mob.get("min_xp", 10), mob.get("max_xp", 25))

        user = get_user(user_id)
        lvl = user["level"]

        evo_mult = evolutions.get_xp_multiplier_for_level(lvl) * float(user.get("evolution_multiplier", 1.0))
        effective_xp = int(base_xp * evo_mult)

        # XP UPDATE
        xp_total = user["xp_total"] + effective_xp
        cur = user["xp_current"] + effective_xp
        xp_to_next = user["xp_to_next_level"]
        curve = user["level_curve_factor"]
        leveled = False

        while cur >= xp_to_next:
            cur -= xp_to_next
            lvl += 1
            xp_to_next = int(xp_to_next * curve)
            leveled = True

        update_user_xp(
            user_id,
            {
                "xp_total": xp_total,
                "xp_current": cur,
                "xp_to_next_level": xp_to_next,
                "level": lvl
            }
        )

        # RECORD QUEST
        record_quest(user_id, "fight")
        if win:
            increment_win(user_id)

        pct = cur / xp_to_next
        bar = "▓" * int(20 * pct) + "░" * (20 - int(20 * pct))

        msg = (
            f"⚔️ **{'VICTORY' if win else 'DEFEAT'}**\n"
            f"Enemy: *{mob['name']}*\n\n"
            f"📈 Base XP: +{base_xp}\n"
            f"🔮 Evo Boost: ×{evo_mult:.2f}\n"
            f"⚡ Effective XP: +{effective_xp}\n\n"
            f"🧬 Level: {lvl}\n"
            f"🔸 XP: {cur} / {xp_to_next}\n"
            f"`{bar}` {int(pct * 100)}%\n"
        )

        if leveled:
            msg += "\n🎉 **LEVEL UP!** Your MegaGrok grows stronger!"

        bot.send_message(message.chat.id, msg, parse_mode="Markdown")

    # ======================================================
    #   /profile COMMAND
    # ======================================================
    @bot.message_handler(commands=["profile"])
    def profile_cmd(message):
        try:
            user_id = message.from_user.id
            user = get_user(user_id)

            payload = {
                "user_id": user_id,
                "username": message.from_user.username or f"User{user_id}",
                "level": user["level"],
                "xp_total": user["xp_total"],
            }

            path = generate_profile_image(payload)

            with open(path, "rb") as f:
                bot.send_photo(message.chat.id, f)

        except Exception as e:
            bot.reply_to(message, f"Error generating profile: {e}")

    # ======================================================
    #   /leaderboard COMMAND
    # ======================================================
    @bot.message_handler(commands=["leaderboard"])
    def leaderboard_cmd(message):
        try:
            users = get_top_users(10)  # returns list of dicts
            path = generate_leaderboard_poster_v2(users)

            with open(path, "rb") as f:
                bot.send_photo(message.chat.id, f)

        except Exception as e:
            bot.reply_to(message, f"Error generating leaderboard: {e}")
