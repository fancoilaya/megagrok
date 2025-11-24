# bot/commands.py — corrected imports & stable legacy commands

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
from bot.mobs import MOBS
from bot.utils import safe_send_gif
from bot.grokdex import GROKDEX
import bot.evolutions as evolutions  # included for future use / compatibility

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
# GROW COOLDOWN STORAGE (kept for compatibility if needed)
# ---------------------------------------
COOLDOWN_FILE = "/tmp/grow_cooldowns.json"
GROW_COOLDOWN_SECONDS = 30 * 60  # 30 minutes


def _load_cooldowns():
    try:
        if os.path.exists(COOLDOWN_FILE):
            return json.load(open(COOLDOWN_FILE, "r"))
    except Exception:
        pass
    return {}


def _save_cooldowns(data):
    try:
        json.dump(data, open(COOLDOWN_FILE, "w"))
    except Exception:
        pass


def _format_seconds_left(secs):
    secs = max(int(secs), 0)
    m = secs // 60
    s = secs % 60
    return f"{m}m {s}s" if m else f"{s}s"


def _render_progress_bar(pct, length=20):
    pct = max(0, min(1, pct))
    fill = int(pct * length)
    bar = "█" * fill + "░" * (length - fill)
    return f"`{bar}` {int(pct*100)}%"


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

    # ======================================================
    #   GROW COMMAND *REMOVED* — MOVED TO bot/handlers/growmygrok.py
    # ======================================================

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
            bot.reply_to(message, "⚔️ You already fought today!")
            return

        mob = random.choice(MOBS)

        bot.reply_to(
            message,
            f"⚔️ **{mob['name']} Encounter!**\n\n{mob.get('intro','')}",
            parse_mode="Markdown"
        )

        try:
            portrait = mob.get("portrait")
            if portrait and os.path.exists(portrait):
                with open(portrait, "rb") as f:
                    bot.send_photo(message.chat.id, f)
        except Exception:
            pass

        win = random.choice([True, False])
        if win:
            base_xp = random.randint(mob.get("min_xp", 10), mob.get("max_xp", 25))
            outcome = mob.get("win_text", "You won!")
            increment_win(user_id)
        else:
            base_xp = random.randint(10, 25)
            outcome = mob.get("lose_text", "You lost!")

        # Evolution multiplier: tier multiplier * optional user multiplier
        user = get_user(user_id)
        level = int(user.get("level", 1))
        tier_mult = float(evolutions.get_xp_multiplier_for_level(level))
        user_mult = float(user.get("evolution_multiplier", 1.0))
        evo_mult = tier_mult * user_mult

        effective_xp = int(round(base_xp * evo_mult))

        try:
            gif_path = mob.get("gif")
            if gif_path:
                safe_send_gif(bot, message.chat.id, gif_path)
        except Exception:
            pass

        xp_total = user["xp_total"] + effective_xp
        cur = user["xp_current"] + effective_xp
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

        record_quest(user_id, "fight")

        # Report base vs effective XP in message so players see multiplier
        try:
            bot.send_message(
                message.chat.id,
                f"{outcome}\n\n"
                f"Base XP: {base_xp}  →  Effective XP: {effective_xp} (×{evo_mult:.2f})\n\n"
                f"✨ **XP Gained:** {effective_xp}",
                parse_mode="Markdown"
            )
        except Exception:
            bot.send_message(message.chat.id, f"{outcome}\n\nXP Gained: {effective_xp}")

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
            bg.paste(img, mask=img.split()[3])
            bg.save(jpeg_path, quality=95)

            with open(jpeg_path, "rb") as f:
                bot.send_photo(message.chat.id, f)

            try:
                os.remove(jpeg_path)
            except Exception:
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

    # ---------------- GROKDEX ----------------
    @bot.message_handler(commands=['grokdex'])
    def grokdex_cmd(message):
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
        except Exception:
            bot.reply_to(message, "Usage: `/mob FUDling`", parse_mode="Markdown")
            return

        if name not in GROKDEX:
            bot.reply_to(message, "❌ Creature not found.")
            return

        mob = GROKDEX[name]

        txt = (
            f"📘 *{mob['name']}*\n"
            f"⭐ Rarity: *{mob['rarity']}*\n"
            f"🎭 Type: {mob.get('type','?')}\n"
            f"💥 Power: {mob.get('combat_power','?')}\n\n"
            f"📜 {mob.get('description','No description.')}\n\n"
            f"⚔️ Strength: {mob.get('strength','?')}\n"
            f"🛡 Weakness: {mob.get('weakness','?')}\n"
            f"🎁 Drops: {', '.join(mob.get('drops',[]))}"
        )

        try:
            portrait = mob.get("portrait")
            if portrait and os.path.exists(portrait):
                with open(portrait, "rb") as f:
                    bot.send_photo(message.chat.id, f, caption=txt, parse_mode="Markdown")
            else:
                bot.reply_to(message, txt, parse_mode="Markdown")
        except Exception:
            bot.reply_to(message, txt, parse_mode="Markdown")
