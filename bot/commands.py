import os
import time
import random
from telebot import TeleBot

from bot.db import (
    get_user,
    update_user_xp,
    get_quests,
    record_quest,
    increment_win,
    increment_ritual
)
from bot.images import generate_profile_image, generate_leaderboard_image
from bot.mobs import MOBS
from bot.utils import safe_send_gif
from bot.grokdex import GROKDEX
from PIL import Image


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


# ---------------------------------------------------------
# MAIN HANDLER REGISTRATION
# ---------------------------------------------------------
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
        user = get_user(user_id)

        xp_gain = random.randint(-10, 25)

        xp_total = max(user["xp_total"] + xp_gain, 0)
        xp_current = max(user["xp_current"] + xp_gain, 0)
        xp_to_next = user["xp_to_next_level"]
        level = user["level"]

        # level adjustments
        if xp_current >= xp_to_next:
            xp_current -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * user["level_curve_factor"])

        elif xp_current < 0 and level > 1:
            level -= 1
            xp_to_next = int(xp_to_next / user["level_curve_factor"])
            xp_current = max(0, xp_current)

        update_user_xp(user_id, {
            "xp_total": xp_total,
            "xp_current": xp_current,
            "xp_to_next_level": xp_to_next,
            "level": level
        })

        sign = "+" if xp_gain >= 0 else ""
        bot.reply_to(
            message,
            f"✨ Your MegaGrok grew! {sign}{xp_gain} XP\n"
            f"Level {level}\n"
            f"XP: {xp_current}/{xp_to_next}"
        )


    # ---------------- HOP (RITUAL) ----------------
    @bot.message_handler(commands=['hop'])
    def hop(message):
        user_id = message.from_user.id
        quests = get_quests(user_id)

        if quests["hop"] == 1:
            bot.reply_to(message, "🐸 You've already performed your Hop Ritual today!")
            return

        xp_gain = random.randint(20, 50)
        user = get_user(user_id)

        xp_total = user["xp_total"] + xp_gain
        xp_current = user["xp_current"] + xp_gain
        xp_to_next = user["xp_to_next_level"]
        level = user["level"]

        if xp_current >= xp_to_next:
            xp_current -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * user["level_curve_factor"])

        update_user_xp(user_id, {
            "xp_total": xp_total,
            "xp_current": xp_current,
            "xp_to_next_level": xp_to_next,
            "level": level
        })

        record_quest(user_id, "hop")
        increment_ritual(user_id, 1)

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

        mob = random.choice(MOBS)

        bot.reply_to(message, f"⚔️ **{mob['name']} Encounter!**\n\n{mob['intro']}", parse_mode="Markdown")

        try:
            with open(mob["portrait"], "rb") as img:
                bot.send_photo(message.chat.id, img)
        except:
            bot.reply_to(message, "⚠️ Failed to load mob portrait.")

        win = random.choice([True, False])

        if win:
            xp = random.randint(mob["min_xp"], mob["max_xp"])
            outcome_text = mob["win_text"]
            increment_win(user_id, 1)
        else:
            xp = random.randint(10, 25)
            outcome_text = mob["lose_text"]

        safe_send_gif(bot, message.chat.id, mob["gif"])

        user = get_user(user_id)
        xp_total = user["xp_total"] + xp
        xp_current = user["xp_current"] + xp
        xp_to_next = user["xp_to_next_level"]
        level = user["level"]

        if xp_current >= xp_to_next:
            xp_current -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * user["level_curve_factor"])

        update_user_xp(user_id, {
            "xp_total": xp_total,
            "xp_current": xp_current,
            "xp_to_next_level": xp_to_next,
            "level": level
        })

        record_quest(user_id, "fight")

        bot.send_message(
            message.chat.id,
            f"{outcome_text}\n\n✨ **XP Gained:** {xp}"
        )


    # ---------------- PROFILE ----------------
    @bot.message_handler(commands=['profile'])
    def profile(message):
        """
        Fog-proof version: converts PNG → flattened JPEG before sending.
        Prevents Telegram client preview tinting.
        """
        user_id = message.from_user.id
        user = get_user(user_id)

        try:
            png_path = generate_profile_image(user)

            # Unique safe jpeg path
            jpeg_path = f"/tmp/profile_{user_id}_{int(time.time())}.jpg"

            img = Image.open(png_path).convert("RGBA")
            paper = (255, 249, 230)
            bg = Image.new("RGB", img.size, paper)

            if img.mode == "RGBA":
                bg.paste(img, mask=img.split()[3])
            else:
                bg.paste(img)

            bg.save(jpeg_path, format="JPEG", quality=95)

            with open(jpeg_path, "rb") as f:
                bot.send_photo(message.chat.id, f)

            # clean temp jpeg
            try:
                os.remove(jpeg_path)
            except:
                pass

        except Exception as e:
            bot.reply_to(message, f"Error generating profile: {e}")
            print("PROFILE ERROR:", e)



    # ---------------- LEADERBOARD ----------------
    @bot.message_handler(commands=['leaderboard'])
    def leaderboard(message):
        try:
            img_path = generate_leaderboard_image()
            with open(img_path, "rb") as f:
                bot.send_photo(message.chat.id, f)
        except Exception as e:
            bot.reply_to(message, f"Error generating leaderboard: {e}")


    # ---------------- GROKDEX ----------------
    @bot.message_handler(commands=['grokdex'])
    def grokdex(message):
        text = "📘 *MEGAGROK DEX — Known Creatures*\n\n"

        for key, mob in GROKDEX.items():
            text += f"• *{mob['name']}* — {mob['rarity']}\n"

        text += "\nUse `/mob <name>` for details."
        bot.reply_to(message, text, parse_mode="Markdown")


    # ---------------- MOB INFO ----------------
    @bot.message_handler(commands=['mob'])
    def mob_info(message):
        try:
            name = message.text.split(" ", 1)[1].strip()
        except:
            bot.reply_to(message, "Usage: `/mob FUDling`", parse_mode="Markdown")
            return

        if name not in GROKDEX:
            bot.reply_to(message, "❌ Creature not found in the GrokDex.")
            return

        mob = GROKDEX[name]

        text = (
            f"📘 *{mob['name']}*\n"
            f"⭐ Rarity: *{mob['rarity']}*\n"
            f"🎭 Type: {mob['type']}\n"
            f"💥 Power: {mob['combat_power']}\n\n"
            f"📜 *Lore*\n{mob['description']}\n\n"
            f"⚔️ Strength: {mob['strength']}\n"
            f"🛡 Weakness: {mob['weakness']}\n"
            f"🎁 Drops: {', '.join(mob['drops'])}\n"
        )

        try:
            with open(mob["portrait"], "rb") as img:
                bot.send_photo(message.chat.id, img, caption=text, parse_mode="Markdown")
        except:
            bot.reply_to(message, text, parse_mode="Markdown")
