import os
import time
import json
import random
from telebot import TeleBot
from PIL import Image

# DB + utilities
from bot.db import (
    get_user,
    update_user_xp,
    get_quests,
    record_quest,
    increment_win,
    increment_ritual,
    get_top_users,
    cursor,
    conn
)
from bot.images import generate_profile_image, generate_leaderboard_premium
from bot.mobs import MOBS
from bot.utils import safe_send_gif
import bot.evolutions as evolutions

# ========================================
# ADMIN SETTINGS
# ========================================
ADMIN_ID = 7574908943  # <-- replace with YOUR Telegram ID


# ========================================
# STATIC TEXTS
# ========================================
HELP_TEXT = (
    "🐸 **MegaGrok Bot Commands**\n\n"
    "/start – Begin your journey\n"
    "/help – Show this help menu\n"
    "/growmygrok – Gain XP and grow your Grok\n"
    "/hop – Perform your daily ritual\n"
    "/fight – Battle for XP\n"
    "/battle – Advanced interactive fight system\n"
    "/profile – Show your Grok profile card\n"
    "/leaderboard – View the top players\n"
    "/grokdex – View all creatures\n"
    "/mob <name> – Inspect a creature\n"
)

START_TEXT = (
    "🐸🌌 *THE COSMIC AMPHIBIAN AWAKENS!* 🌌🐸\n\n"
    "✨ Your MegaGrok emerges from the liquidity void…\n"
    "✨ Your evolution begins *now*.\n\n"
    "⚡ *Core Commands*\n"
    "🐸 /growmygrok — Feed cosmic hop-energy\n"
    "🔮 /hop — Daily ritual boost\n"
    "⚔️ /fight — Battle Hop-Verse creatures\n"
    "🧬 /profile — View your Grok\n"
    "🏆 /leaderboard — Rank among players\n"
)


# ========================================
# REGISTER TELEGRAM HANDLERS
# ========================================
def register_handlers(bot: TeleBot):

    # --------------------------------------
    # START
    # --------------------------------------
    @bot.message_handler(commands=["start"])
    def start_cmd(message):
        bot.reply_to(message, START_TEXT, parse_mode="Markdown")

    # --------------------------------------
    # HELP
    # --------------------------------------
    @bot.message_handler(commands=["help"])
    def help_cmd(message):
        bot.reply_to(message, HELP_TEXT, parse_mode="Markdown")

    # --------------------------------------
    # GROW
    # (Handled in separate handler file)
    # --------------------------------------

    # --------------------------------------
    # HOP
    # --------------------------------------
    @bot.message_handler(commands=["hop"])
    def hop(message):

        user_id = message.from_user.id
        q = get_quests(user_id)

        # one per day
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

        leveled = False
        if cur >= xp_to_next:
            cur -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * curve)
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

        record_quest(user_id, "hop")
        increment_ritual(user_id)

        text = f"🐸✨ Hop Ritual complete! +{xp_gain} XP"
        if leveled:
            text += "\n🎉 LEVEL UP!"
        bot.reply_to(message, text)

    # --------------------------------------
    # FIGHT (simple fight system)
    # --------------------------------------
    @bot.message_handler(commands=["fight"])
    def fight(message):
        user_id = message.from_user.id
        q = get_quests(user_id)

        if q.get("fight", 0) == 1:
            bot.reply_to(message, "⚔️ You already fought today.")
            return

        mob = random.choice(MOBS)

        bot.reply_to(
            message,
            f"⚔️ **{mob['name']} appears!**\n\n{mob.get('intro','')}",
            parse_mode="Markdown"
        )

        try:
            if mob.get("portrait") and os.path.exists(mob["portrait"]):
                with open(mob["portrait"], "rb") as f:
                    bot.send_photo(message.chat.id, f)
        except:
            pass

        win = random.choice([True, False])
        base_xp = random.randint(mob.get("min_xp", 10), mob.get("max_xp", 25))
        if win:
            increment_win(user_id)

        user = get_user(user_id)
        level = user["level"]

        evo_mult = evolutions.get_xp_multiplier_for_level(level) * float(user.get("evolution_multiplier", 1.0))
        effective_xp = int(base_xp * evo_mult)

        # update XP
        xp_total = user["xp_total"] + effective_xp
        cur = user["xp_current"] + effective_xp
        xp_to_next = user["xp_to_next_level"]
        curve = user["level_curve_factor"]

        leveled = False
        while cur >= xp_to_next:
            cur -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * curve)
            leveled = True

        update_user_xp(
            user_id,
            {"xp_total": xp_total, "xp_current": cur, "xp_to_next_level": xp_to_next, "level": level}
        )

        record_quest(user_id, "fight")

        pct = cur / xp_to_next
        bar = "▓" * int(20 * pct) + "░" * (20 - int(20 * pct))

        msg = (
            f"⚔️ **{'VICTORY' if win else 'DEFEAT'}**\n"
            f"Enemy: *{mob['name']}*\n\n"
            f"📈 Base XP: +{base_xp}\n"
            f"🔮 Evo Boost: ×{evo_mult:.2f}\n"
            f"⚡ Effective XP: +{effective_xp}\n\n"
            f"🧬 Level: {level}\n"
            f"🟩 `{bar}` {int(pct * 100)}%"
        )

        if leveled:
            msg += "\n🎉 **LEVEL UP!**"

        bot.send_message(message.chat.id, msg, parse_mode="Markdown")

    # --------------------------------------
    # PROFILE
    # --------------------------------------
    @bot.message_handler(commands=["profile"])
    def profile(message):

        user_id = message.from_user.id
        user = get_user(user_id)

        payload = {
            "user_id": user_id,
            "username": message.from_user.username or f"User{user_id}",
            "form": user.get("form"),
            "level": user.get("level"),
            "wins": user.get("wins"),
            "fights": user.get("mobs_defeated"),
            "rituals": user.get("rituals"),
            "xp_total": user.get("xp_total"),
        }

        try:
            img_path = generate_profile_image(payload)

            with open(img_path, "rb") as f:
                bot.send_photo(message.chat.id, f)

        except Exception as e:
            bot.reply_to(message, f"Error generating profile: {e}")

    # --------------------------------------
    # LEADERBOARD (new premium poster)
    # --------------------------------------
    @bot.message_handler(commands=["leaderboard"])
    def leaderboard(message):
        try:
            users = get_top_users(limit=12)
            out = generate_leaderboard_premium(users)
            with open(out, "rb") as f:
                bot.send_photo(message.chat.id, f)
        except Exception as e:
            bot.reply_to(message, f"Error generating leaderboard: {e}")

    # --------------------------------------
    # ADMIN: WIPE USER
    # --------------------------------------
    @bot.message_handler(commands=["wipe"])
    def wipe_user(message):
        # authentication
        if message.from_user.id != ADMIN_ID:
            bot.reply_to(message, "❌ You are not allowed to use this command.")
            return

        parts = message.text.strip().split(" ", 1)
        if len(parts) < 2:
            bot.reply_to(message, "Usage: /wipe <username>\nExample: /wipe @SegmentSol")
            return

        username = parts[1].replace("@", "").strip().lower()

        # find user by username
        cursor.execute("SELECT user_id, username FROM users")
        rows = cursor.fetchall()

        target_id = None
        for uid, uname in rows:
            if uname and uname.lower() == username:
                target_id = uid
                break

        if not target_id:
            bot.reply_to(message, f"❌ No user found with username @{username}")
            return

        # delete user
        cursor.execute("DELETE FROM users WHERE user_id=?", (target_id,))
        conn.commit()

        bot.reply_to(message, f"🗑 **User @{username} is wiped from the Metaverse.**")

