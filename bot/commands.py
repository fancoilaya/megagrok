# bot/handlers/commands.py
# ------------------------------------------------------------
# Main command handlers for MegaGrok RPG
# ------------------------------------------------------------

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
    get_top_users,
    update_username   # NEW: keep Telegram username synced
)

# NEW IMPORTS (split image system)
from bot.profile_image import generate_profile_image
from bot.images import generate_leaderboard_poster_v2

from bot.mobs import MOBS
import bot.evolutions as evolutions
from bot.utils import safe_send_gif


# ------------------------------------------------------------
# STATIC TEXTS
# ------------------------------------------------------------

HELP_TEXT = (
    "🐸 **MegaGrok Bot Commands**\n\n"
    "/start – Begin your journey.\n"
    "/help – Show this help menu.\n"
    "/growmygrok – Gain XP and grow your Grok.\n"
    "/hop – Perform your daily hop ritual.\n"
    "/fight – Fight a random mob for XP.\n"
    "/battle – Advanced turn-based combat.\n"
    "/profile – Show your Grok profile card.\n"
    "/leaderboard – View the MegaGrok Leaderboard.\n"
    "/grokdex – Explore the Mob Encyclopedia.\n\n"
    "Evolve your Grok, gain XP, and conquer the Hop-Verse!"
)

START_TEXT = (
    "🐸🌌 *THE COSMIC AMPHIBIAN HAS AWAKENED* 🌌🐸\n\n"
    "✨ A portal cracks open…\n"
    "✨ Your MegaGrok emerges from the liquidity void…\n"
    "✨ Your evolution begins *now*.\n\n"
    "⚡ *Core Commands*\n"
    "🐸 /growmygrok — Feed cosmic hop-energy\n"
    "🔮 /hop — Daily ritual boost\n"
    "⚔️ /fight — Battle Hop-Verse creatures\n"
    "🧬 /profile — View your Grok\n"
    "📜 /help — Full command list\n\n"
    "🚀 Train him. Evolve him. Conquer the Hop-Verse."
)


# ------------------------------------------------------------
# REGISTER COMMAND HANDLERS
# ------------------------------------------------------------

def register_handlers(bot: TeleBot):

    # Utility: Always keep username updated
    def sync_username(message):
        try:
            uid = message.from_user.id
            uname = message.from_user.username or ""
            update_username(uid, uname)
        except:
            pass


    # START COMMAND
    @bot.message_handler(commands=['start'])
    def start(message):
        sync_username(message)
        bot.reply_to(message, START_TEXT, parse_mode="Markdown")


    # HELP COMMAND
    @bot.message_handler(commands=['help'])
    def help_cmd(message):
        sync_username(message)
        bot.reply_to(message, HELP_TEXT, parse_mode="Markdown")


    # ------------------------------------------------------------
    # HOP COMMAND
    # ------------------------------------------------------------
    @bot.message_handler(commands=['hop'])
    def hop(message):
        sync_username(message)

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
        level = user["level"]
        curve = user["level_curve_factor"]

        # Level calculation
        if cur >= xp_to_next:
            cur -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * curve)

        update_user_xp(
            user_id,
            {
                "xp_total": xp_total,
                "xp_current": cur,
                "xp_to_next_level": xp_to_next,
                "level": level
            }
        )

        record_quest(user_id, "hop")
        increment_ritual(user_id)

        bot.reply_to(message, f"🐸✨ Hop Ritual complete! +{xp_gain} XP")


    # ------------------------------------------------------------
    # FIGHT COMMAND (Classic)
    # ------------------------------------------------------------
    @bot.message_handler(commands=['fight'])
    def fight(message):
        sync_username(message)

        user_id = message.from_user.id
        q = get_quests(user_id)

        if q.get("fight", 0) == 1:
            bot.reply_to(message, "⚔️ You already fought today.")
            return

        mob = random.choice(MOBS)

        bot.reply_to(
            message,
            f"⚔️ **{mob['name']} Encounter!**\n\n{mob.get('intro','')}",
            parse_mode="Markdown"
        )

        # Try sending portrait
        try:
            portrait = mob.get("portrait")
            if portrait and os.path.exists(portrait):
                with open(portrait, "rb") as f:
                    bot.send_photo(message.chat.id, f)
        except:
            pass

        win = random.choice([True, False])
        if win:
            base_xp = random.randint(mob.get("min_xp", 10), mob.get("max_xp", 25))
            increment_win(user_id)
        else:
            base_xp = random.randint(10, 25)

        user = get_user(user_id)
        level = user["level"]

        evo_mult = evolutions.get_xp_multiplier_for_level(level) * float(user.get("evolution_multiplier", 1.0))
        effective_xp = int(base_xp * evo_mult)

        xp_total = user["xp_total"] + effective_xp
        cur = user["xp_current"] + effective_xp
        xp_to_next = user["xp_to_next_level"]
        curve = user["level_curve_factor"]

        leveled = False
        while cur >= xp_to_next:
            cur -= xp_to_next
            xp_to_next = int(xp_to_next * curve)
            level += 1
            leveled = True

        update_user_xp(
            user_id,
            {
                "xp_total": xp_total,
                "xp_current": cur,
                "xp_to_next_level": xp_to_next,
                "level": level
            }
        )

        record_quest(user_id, "fight")

        pct = int((cur / xp_to_next) * 100)
        bar = "▓" * (pct // 5) + "░" * (20 - pct // 5)

        msg = (
            f"⚔️ **Battle Outcome: {'VICTORY' if win else 'DEFEAT'}!**\n"
            f"Enemy: *{mob['name']}*\n\n"
            f"📈 Base XP: +{base_xp}\n"
            f"🔮 Evo Boost: ×{evo_mult:.2f}\n"
            f"⚡ Effective XP: +{effective_xp}\n\n"
            f"🧬 Level: {level}\n"
            f"🔸 XP: {cur} / {xp_to_next}\n"
            f"🟩 Progress: `{bar}` {pct}%"
        )

        if leveled:
            msg += "\n🎉 **LEVEL UP!** Your MegaGrok grows stronger!"

        bot.send_message(message.chat.id, msg, parse_mode="Markdown")


    # ------------------------------------------------------------
    # PROFILE (Comic-style poster)
    # ------------------------------------------------------------
    @bot.message_handler(commands=['profile'])
    def profile(message):
        sync_username(message)

        user_id = message.from_user.id
        user = get_user(user_id)

        payload = {
            "user_id": user_id,
            "username": message.from_user.username or f"User{user_id}",
            "form": user.get("form"),
            "level": user.get("level"),
            "wins": user.get("wins"),
            "kills": user.get("mobs_defeated"),
            "rituals": user.get("rituals"),
            "xp_total": user.get("xp_total")
        }

        try:
            path = generate_profile_image(payload)
            with open(path, "rb") as f:
                bot.send_photo(message.chat.id, f)
        except Exception as e:
            bot.reply_to(message, f"Error generating profile: {e}")


    # ------------------------------------------------------------
    # LEADERBOARD (Comic Poster v2)
    # ------------------------------------------------------------
    @bot.message_handler(commands=['leaderboard'])
    def leaderboard(message):
        sync_username(message)

        rows = get_top_users(10)
        if not rows:
            bot.reply_to(message, "No players found.")
            return

        try:
            poster = generate_leaderboard_poster_v2(rows)
            with open(poster, "rb") as f:
                bot.send_photo(
                    message.chat.id,
                    f,
                    caption="🏆 *MegaGrok Leaderboard* 🏆",
                    parse_mode="Markdown"
                )
        except Exception as e:
            bot.reply_to(message, f"Error generating leaderboard: {e}")
