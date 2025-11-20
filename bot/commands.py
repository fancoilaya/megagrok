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
        bot.reply_to(message, "⚔️ You've already fought today! Come back tomorrow.")
        return

    # Choose a random mob
    mob = random.choice(MOBS)

    mob_name = mob["name"]
    mob_intro = mob["intro"]
    mob_portrait = mob["portrait"]
    mob_gif = mob["gif"]

    # Send intro text
    bot.reply_to(message, f"⚔️ **{mob_name} Encounter!**\n\n{mob_intro}")

    # Send mob portrait
    try:
        with open(mob_portrait, "rb") as img:
            bot.send_photo(message.chat.id, img)
    except Exception as e:
        bot.reply_to(message, f"⚠️ Error loading mob portrait: {e}")

    # Simulate win/loss
    win = random.choice([True, False])

    if win:
        xp = random.randint(mob["min_xp"], mob["max_xp"])
        outcome_text = mob["win_text"]
    else:
        xp = random.randint(10, 25)
        outcome_text = mob["lose_text"]

    # Send fight GIF
    safe_send_gif(bot, message.chat.id, mob_gif)

    # Apply XP
    add_xp(user_id, xp)
    record_quest(user_id, "fight")  # replace old SQL with the correct helper if using modules

    bot.send_message(
        message.chat.id,
        f"{outcome_text}\n\n"
        f"✨ **XP Gained:** {xp}"
    )

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
