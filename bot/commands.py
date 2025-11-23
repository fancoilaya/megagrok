# bot/commands.py
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
# GROW COOLDOWN STORAGE
# ---------------------------------------
COOLDOWN_FILE = "/tmp/grow_cooldowns.json"
GROW_COOLDOWN_SECONDS = 30 * 60  # 30 minutes


def _load_cooldowns():
    try:
        if os.path.exists(COOLDOWN_FILE):
            return json.load(open(COOLDOWN_FILE, "r"))
    except:
        pass
    return {}


def _save_cooldowns(data):
    try:
        json.dump(data, open(COOLDOWN_FILE, "w"))
    except:
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
        bot.reply_to(message, HELP_TEXT)

    # ---------------- GROW ----------------
    @bot.message_handler(commands=['growmygrok'])
    def grow(message):

        user_id = str(message.from_user.id)

        cooldowns = _load_cooldowns()
        now = time.time()
        last = cooldowns.get(user_id, 0)
        if last and now - last < GROW_COOLDOWN_SECONDS:
            left = GROW_COOLDOWN_SECONDS - (now - last)
            bot.reply_to(message, f"⏳ Wait {_format_seconds_left(left)} before using /growmygrok again.")
            return

        xp_change = random.randint(-10, 25)
        user = get_user(int(user_id))

        xp_total = user["xp_total"]
        xp_current = user["xp_current"]
        xp_to_next = user["xp_to_next_level"]
        level = user["level"]
        curve = user["level_curve_factor"]

        new_total = max(0, xp_total + xp_change)
        cur = xp_current + xp_change

        leveled_up = False
        leveled_down = False

        # level-up loop
        while cur >= xp_to_next:
            cur -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * curve)
            leveled_up = True

        # level-down
        while cur < 0 and level > 1:
            level -= 1
            xp_to_next = int(xp_to_next / curve)
            cur += xp_to_next
            leveled_down = True

        cur = max(0, cur)
        new_total = max(0, new_total)

        update_user_xp(
            int(user_id),
            {
                "xp_total": new_total,
                "xp_current": cur,
                "xp_to_next_level": xp_to_next,
                "level": level
            }
        )

        cooldowns[user_id] = now
        _save_cooldowns(cooldowns)

        bar = _render_progress_bar(cur / xp_to_next)

        msg = [
            f"✨ MegaGrok {'grew' if xp_change>=0 else 'changed'} {xp_change:+d} XP",
            f"**Level {level}**",
            f"XP: {cur}/{xp_to_next}",
            bar
        ]
        if leveled_up:
            msg.append("🎉 **Level up!**")
        if leveled_down:
            msg.append("💀 **Lost a level!**")

        bot.reply_to(message, "\n".join(msg), parse_mode="Markdown")

    # ---------------- HOP ----------------
    @bot.message_handler(commands=['hop'])
    def hop(message):

        user_id = message.from_user.id
        q = get_quests(user_id)

        if q["hop"] == 1:
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

        if q["fight"] == 1:
            bot.reply_to(message, "⚔️ You already fought today!")
            return

        mob = random.choice(MOBS)

        bot.reply_to(
            message,
            f"⚔️ **{mob['name']} Encounter!**\n\n{mob['intro']}",
            parse_mode="Markdown"
        )

        try:
            with open(mob["portrait"], "rb") as f:
                bot.send_photo(message.chat.id, f)
        except:
            pass

        win = random.choice([True, False])
        if win:
            xp = random.randint(mob["min_xp"], mob["max_xp"])
            outcome = mob["win_text"]
            increment_win(user_id)
        else:
            xp = random.randint(10, 25)
            outcome = mob["lose_text"]

        safe_send_gif(bot, message.chat.id, mob.get("gif"))

        user = get_user(user_id)
        xp_total = user["xp_total"] + xp
        cur = user["xp_current"] + xp
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

        bot.send_message(message.chat.id, f"{outcome}\n\n✨ **XP Gained:** {xp}")

    # ---------------- PROFILE ----------------
    @bot.message_handler(commands=['profile'])
    def profile(message):

        user_id = message.from_user.id
        user = get_user(user_id)

        # Guarantee required keys
        user_payload = {
            "user_id": user_id,
            "username": message.from_user.username or f"User{user_id}",
            "form": user["form"],
            "level": user["level"],
            "wins": user["wins"],
            "fights": user["mobs_defeated"],
            "rituals": user["rituals"],
            "xp_total": user["xp_total"]
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

            os.remove(jpeg_path)

        except Exception as e:
            bot.reply_to(message, f"Error generating profile: {e}")
            print("PROFILE ERROR:", e)

    # ---------------- LEADERBOARD ----------------
    @bot.message_handler(commands=['leaderboard'])
    def leaderboard(message):
        try:
            rows = get_top_users(5)
            path = generate_leaderboard_image()
            with open(path, "rb") as f:
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
            bot.reply_to(message, "❌ Creature not found.")
            return

        mob = GROKDEX[name]

        txt = (
            f"📘 *{mob['name']}*\n"
            f"⭐ Rarity: *{mob['rarity']}*\n"
            f"🎭 Type: {mob['type']}\n"
            f"💥 Power: {mob['combat_power']}\n\n"
            f"📜 {mob['description']}\n\n"
            f"⚔️ Strength: {mob['strength']}\n"
            f"🛡 Weakness: {mob['weakness']}\n"
            f"🎁 Drops: {', '.join(mob['drops'])}"
        )

        try:
            with open(mob["portrait"], "rb") as f:
                bot.send_photo(message.chat.id, f, caption=txt, parse_mode="Markdown")
        except:
            bot.reply_to(message, txt, parse_mode="Markdown")
