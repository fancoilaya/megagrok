import os
import time
import json
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

from bot.images import generate_profile_image, generate_leaderboard_image
from bot.mobs import get_random_mob   # <-- Unified mob database function
from bot.utils import safe_send_gif
import bot.evolutions as evolutions


# --------------------------
# HELP TEXT
# --------------------------
HELP_TEXT = (
    "🐸 **MegaGrok Bot Commands**\n\n"
    "/start – Begin your journey.\n"
    "/help – Show this help menu.\n"
    "/growmygrok – Gain XP and grow your Grok.\n"
    "/hop – Perform your daily hop ritual.\n"
    "/fight – Fight a random mob for XP.\n"
    "/profile – Show your Grok profile card.\n"
    "/leaderboard – View the Top 10 Grok tamers.\n"
    "/grokdex – View all known creatures.\n"
    "/mob <name> – Inspect a specific creature.\n\n"
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


# ---------------------------------------
# REGISTER HANDLERS
# ---------------------------------------
def register_handlers(bot: TeleBot):

    # ---------------- START ----------------
    @bot.message_handler(commands=['start'])
    def start(message):
        bot.reply_to(message, start_text, parse_mode="Markdown")

    # ---------------- HELP ----------------
    @bot.message_handler(commands=['help'])
    def help_cmd(message):
        bot.reply_to(message, HELP_TEXT, parse_mode="Markdown")

    # ---------------- HOP ----------------
    @bot.message_handler(commands=['hop'])
    def hop(message):

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

    # ---------------- FIGHT ----------------
    @bot.message_handler(commands=['fight'])
    def fight(message):
        user_id = message.from_user.id
        q = get_quests(user_id)

        if q.get("fight", 0) == 1:
            bot.reply_to(message, "⚔️ You already fought today.")
            return

        # Unified mob database now requires: get_random_mob()
        mob = get_random_mob()

        bot.reply_to(
            message,
            f"⚔️ **{mob['name']} Encounter!**\n\n{mob.get('intro','')}",
            parse_mode="Markdown"
        )

        # Show portrait if available
        portrait = mob.get("portrait")
        try:
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

        tier_mult = evolutions.get_xp_multiplier_for_level(level)
        user_mult = float(user.get("evolution_multiplier", 1.0))
        evo_mult = tier_mult * user_mult

        effective_xp = int(round(base_xp * evo_mult))

        # XP update
        xp_total = user["xp_total"] + effective_xp
        cur = user["xp_current"] + effective_xp
        xp_to_next = user["xp_to_next_level"]
        level = user["level"]
        curve = user["level_curve_factor"]

        leveled_up = False
        while cur >= xp_to_next:
            cur -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * curve)
            leveled_up = True

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

        pct = cur / xp_to_next
        fill = int(20 * pct)
        bar = "▓" * fill + "░" * (20 - fill)
        pct_int = int(pct * 100)

        msg = (
            f"⚔️ **Battle Outcome: {'VICTORY' if win else 'DEFEAT'}!**\n"
            f"Enemy: *{mob['name']}*\n\n"
            f"📈 **Base XP:** +{base_xp}\n"
            f"🔮 **Evo Boost:** ×{evo_mult:.2f}\n"
            f"⚡ **Effective XP:** +{effective_xp}\n\n"
            f"🧬 **Level:** {level}\n"
            f"🔸 **XP:** {cur} / {xp_to_next}\n"
            f"🟩 **Progress:** `{bar}` {pct_int}%\n"
        )

        if leveled_up:
            msg += "\n🎉 **LEVEL UP!** Your MegaGrok grows stronger!"

        bot.send_message(message.chat.id, msg, parse_mode="Markdown")

    # ---------------- PROFILE ----------------
    @bot.message_handler(commands=['profile'])
    def profile(message):

        user_id = message.from_user.id
        user = get_user(user_id)

        user_payload = {
            "user_id": user_id,
            "username": message.from_user.username or f"User{user_id}",
            "form": user.get("form"),
            "level": user.get("level"),
            "wins": user.get("wins"),
            "fights": user.get("mobs_defeated"),
            "rituals": user.get("rituals"),
            "xp_total": user.get("xp_total")
        }

        try:
            png_path = generate_profile_image(user_payload)
            jpeg_path = f"/tmp/profile_{user_id}_{int(time.time())}.jpg"

            img = Image.open(png_path).convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 249, 230))
            bg_paste = img.split()[3]
            bg.paste(img, mask=bg_paste)
            bg.save(jpeg_path, quality=95)

            with open(jpeg_path, "rb") as f:
                bot.send_photo(message.chat.id, f)

            try:
                os.remove(jpeg_path)
            except:
                pass

        except Exception as e:
            bot.reply_to(message, f"Error generating profile: {e}")

    # ---------------- LEADERBOARD ----------------
    @bot.message_handler(commands=['leaderboard'])
    def leaderboard(message):
        try:
            path = generate_leaderboard_image()
            if path and os.path.exists(path):
                with open(path, "rb") as f:
                    bot.send_photo(message.chat.id, f)
            else:
                bot.reply_to(message, "Leaderboard not available.")
        except Exception as e:
            bot.reply_to(message, f"Error generating leaderboard: {e}")
