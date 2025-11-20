import os
import random
import datetime
from telebot import TeleBot
from PIL import Image, ImageDraw, ImageFont

from bot.db import get_user, add_xp, get_quests, record_quest
from bot.images import generate_profile_image, generate_leaderboard_image
from bot.mobs import MOBS
from bot.utils import safe_send_gif


# ------------------------
# HELP TEXT
# ------------------------
HELP_TEXT = (
    "🐸 **MegaGrok Bot Commands**\n\n"
    "/start – Begin your journey.\n"
    "/help – Show this help menu.\n"
    "/growmygrok – Gain XP and grow your Grok.\n"
    "/hop – Perform your daily hop ritual.\n"
    "/fight – Fight a random mob for XP.\n"
    "/profile – Show your Grok profile card.\n"
    "/leaderboard – View the Top 10 Grok tamers.\n\n"
    "Evolve your Grok, level up, complete quests and climb the ranks!"
)

start_text = (
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

# ------------------------
# REGISTER COMMANDS
# ------------------------
def register_handlers(bot: TeleBot):

    # ---------------- START ----------------
    
    @bot.message_handler(commands=['start'])
    def start(message):
        bot.reply_to(message, start_text, parse_mode="Markdown")

    # ---------------- HELP ----------------
    @bot.message_handler(commands=['help'])
    def help_cmd(message):
        bot.reply_to(message, HELP_TEXT)

    # ---------------- GROW ----------------
    @bot.message_handler(commands=['growmygrok'])
    def grow(message):
        user_id = message.from_user.id
        xp_gain = random.randint(5, 25)

        add_xp(user_id, xp_gain)
        user = get_user(user_id)
        current_xp = user["xp"]
        level = user["level"]
        next_xp = level * 200

        progress = int((current_xp / next_xp) * 10)
        progress_bar = "█" * progress + "░" * (10 - progress)

        bot.reply_to(
            message,
            f"✨ Your MegaGrok grew! +{xp_gain} XP\n"
            f"**Level {level}**\n"
            f"XP: {current_xp}/{next_xp}\n"
            f"`{progress_bar}`"
        )

    # ---------------- HOP ----------------
    @bot.message_handler(commands=['hop'])
    def hop(message):
        user_id = message.from_user.id
        quests = get_quests(user_id)

        if quests["hop"] == 1:
            bot.reply_to(message, "🐸 You've already performed your Hop Ritual today!")
            return

        xp_gain = random.randint(20, 50)
        add_xp(user_id, xp_gain)
        record_quest(user_id, "hop")

        bot.reply_to(
            message,
            f"🐸✨ Hop Ritual complete! +{xp_gain} XP\n"
            f"The cosmic hop-energy flows through your MegaGrok!"
        )

    # ---------------- FIGHT ----------------
    @bot.message_handler(commands=['fight'])
    def fight(message):
        user_id = message.from_user.id
        quests = get_quests(user_id)

        if quests["fight"] == 1:
            bot.reply_to(message, "⚔️ You've already fought today!")
            return

        # Select mob
        mob = random.choice(MOBS)

        bot.reply_to(
            message,
            f"⚔️ **A wild {mob['name']} appears!**\n"
            f"{mob['intro']}"
        )

        # Send GIF
        if mob.get("gif"):
            safe_send_gif(bot, message.chat.id, mob["gif"])

        # Determine win
        win = random.choice([True, False, False])  # harder mobs = 33% win

        if win:
            xp = random.randint(80, 150)
            bot.send_message(
                message.chat.id,
                f"🔥 **Victory!**\nYour MegaGrok destroyed the {mob['name']}! +{xp} XP"
            )
        else:
            xp = random.randint(10, 40)
            bot.send_message(
                message.chat.id,
                f"💀 Defeat.\nThe {mob['name']} overpowered you, but you learned. +{xp} XP"
            )

        add_xp(user_id, xp)
        record_quest(user_id, "fight")

    # ---------------- PROFILE ----------------
    @bot.message_handler(commands=['profile'])
    def profile(message):
        user_id = message.from_user.id
        user = get_user(user_id)

        try:
            img_path = generate_profile_image(
                user_id=user_id,
                level=user["level"],
                xp=user["xp"],
                form=user["form"]
            )
            with open(img_path, "rb") as f:
                bot.send_photo(message.chat.id, f)
        except Exception as e:
            bot.reply_to(message, f"Error generating profile: {e}")

    # ---------------- LEADERBOARD ----------------
    @bot.message_handler(commands=['leaderboard'])
    def leaderboard(message):
        try:
            img_path = generate_leaderboard_image()
            with open(img_path, "rb") as f:
                bot.send_photo(message.chat.id, f)
        except Exception as e:
            bot.reply_to(message, f"Error generating leaderboard: {e}")
