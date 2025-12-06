# bot/commands.py
# MegaGrok Command Layer — Stable Production Version
# Includes:
# - Auto-save username on every message
# - Help, start, hop, fight, profile, leaderboard, wipe
# - Safe error handling & clean structure

import os
import time
import random
import traceback
from telebot import TeleBot

# ADMIN ID
try:
    ADMIN_ID = int(os.getenv("MEGAGROK_ADMIN_ID", "7574908943"))
except:
    ADMIN_ID = 7574908943


HELP_TEXT = (
    "🐸 **MegaGrok Commands**\n\n"
    "/start - Begin your journey\n"
    "/help - Show help\n"
    "/growmygrok - Gain XP & evolve\n"
    "/hop - Daily ritual\n"
    "/fight - Quick fight (1/day)\n"
    "/battle - Interactive RPG battle\n"
    "/profile - Show your Grok profile card\n"
    "/leaderboard - Show leaderboard poster\n"
    "/wipe <username> - (admin) remove a player\n"
)


def register_handlers(bot: TeleBot):

    # --------------------------------------------------------
    # SAFE DB IMPORTS
    # --------------------------------------------------------
    try:
        from bot.db import (
            get_user,
            update_user_xp,
            get_quests,
            record_quest,
            increment_win,
            increment_ritual,
            get_top_users,
            update_username,
            cursor,
            conn,
        )
    except Exception as e:
        raise RuntimeError(f"DB import failure: {e}")

    # --------------------------------------------------------
    # AUTO-SAVE USERNAME ON EVERY MESSAGE
    # --------------------------------------------------------
    @bot.message_handler(func=lambda m: True, content_types=['text'])
    def _auto_update_username(msg):
        try:
            uid = msg.from_user.id
            uname = msg.from_user.username or ""
            if uname:
                update_username(uid, uname)
        except Exception:
            pass  # silent fail

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------
    @bot.message_handler(commands=["start"])
    def _start(message):
        try:
            text = (
                "🐸🌌 *THE COSMIC AMPHIBIAN AWAKENS* 🌌🐸\n\n"
                "Welcome to the MegaGrok Metaverse!\n"
                "Use /help to begin."
            )
            bot.reply_to(message, text, parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"Start failed: {e}")

    # --------------------------------------------------------
    # HELP
    # --------------------------------------------------------
    @bot.message_handler(commands=["help"])
    def _help(message):
        bot.reply_to(message, HELP_TEXT, parse_mode="Markdown")

    # --------------------------------------------------------
    # HOP
    # --------------------------------------------------------
    @bot.message_handler(commands=["hop"])
    def _hop(message):
        try:
            user_id = message.from_user.id
            quests = get_quests(user_id)

            if quests.get("hop", 0) == 1:
                bot.reply_to(message, "🐸 You already performed today’s ritual.")
                return

            xp_gain = random.randint(20, 50)
            user = get_user(user_id)

            xp_total = user["xp_total"] + xp_gain
            cur = user["xp_current"] + xp_gain
            xp_to_next = user["xp_to_next_level"]
            level = user["level"]
            curve = user["level_curve_factor"]

            leveled = False
            while cur >= xp_to_next:
                cur -= xp_to_next
                level += 1
                xp_to_next = int(xp_to_next * curve)
                leveled = True

            update_user_xp(user_id, {
                "xp_total": xp_total,
                "xp_current": cur,
                "xp_to_next_level": xp_to_next,
                "level": level
            })

            record_quest(user_id, "hop")
            increment_ritual(user_id)

            msg = f"🐸✨ Ritual complete! +{xp_gain} XP"
            if leveled:
                msg += "\n🎉 LEVEL UP!"

            bot.reply_to(message, msg)
        except Exception as e:
            bot.reply_to(message, f"Hop error: {e}")

    # --------------------------------------------------------
    # FIGHT
    # --------------------------------------------------------
    @bot.message_handler(commands=["fight"])
    def _fight(message):
        try:
            from bot.mobs import MOBS
            import bot.evolutions as evolutions
        except:
            bot.reply_to(message, "Fight unavailable — missing modules.")
            return

        user_id = message.from_user.id
        quests = get_quests(user_id)

        if quests.get("fight", 0) == 1:
            bot.reply_to(message, "⚔️ You already fought today.")
            return

        mob = random.choice(list(MOBS.values()))
        bot.reply_to(message,
            f"⚔️ **{mob['name']} Encounter!**\n\n{mob['intro']}",
            parse_mode="Markdown"
        )

        try:
            if os.path.exists(mob["portrait"]):
                with open(mob["portrait"], "rb") as f:
                    bot.send_photo(message.chat.id, f)
        except:
            pass

        win = random.choice([True, False])
        base_xp = random.randint(mob["min_xp"], mob["max_xp"])

        if win:
            increment_win(user_id)

        user = get_user(user_id)
        level = user["level"]

        try:
            evo_mult = evolutions.get_xp_multiplier_for_level(level) * float(user.get("evolution_multiplier", 1.0))
        except:
            evo_mult = 1.0

        earned = int(base_xp * evo_mult)

        # LEVEL SYSTEM
        xp_total = user["xp_total"] + earned
        cur = user["xp_current"] + earned
        xp_to_next = user["xp_to_next_level"]
        curve = user["level_curve_factor"]

        leveled = False
        while cur >= xp_to_next:
            cur -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * curve)
            leveled = True

        update_user_xp(user_id, {
            "xp_total": xp_total,
            "xp_current": cur,
            "xp_to_next_level": xp_to_next,
            "level": level
        })

        record_quest(user_id, "fight")

        pct = int(cur / xp_to_next * 100)
        bar = "▓" * (pct // 5) + "░" * (20 - pct // 5)

        msg = (
            f"⚔️ **{'VICTORY' if win else 'DEFEAT'}**\n"
            f"Enemy: *{mob['name']}*\n\n"
            f"XP: +{earned}\n"
            f"Level: {level}\n"
            f"Progress: `{bar}` {pct}%"
        )
        if leveled:
            msg += "\n🎉 LEVEL UP!"

        bot.send_message(message.chat.id, msg, parse_mode="Markdown")

    # --------------------------------------------------------
    # PROFILE CARD
    # --------------------------------------------------------
    @bot.message_handler(commands=["profile"])
    def _profile(message):
        try:
            from bot.images import generate_profile_image
        except:
            bot.reply_to(message, "Profile image generator missing.")
            return

        user_id = message.from_user.id
        user = get_user(user_id)

        payload = {
            "user_id": user_id,
            "username": message.from_user.username or f"User{user_id}",
            "level": user["level"],
            "wins": user["wins"],
            "rituals": user["rituals"],
            "xp_total": user["xp_total"]
        }

        path = generate_profile_image(payload)
        with open(path, "rb") as f:
            bot.send_photo(message.chat.id, f)

    # --------------------------------------------------------
    # LEADERBOARD
    # --------------------------------------------------------
    @bot.message_handler(commands=["leaderboard"])
    def _leaderboard(message):
        try:
            users = get_top_users(limit=12)

            from bot.images import generate_leaderboard_premium
            path = generate_leaderboard_premium(users)

            with open(path, "rb") as f:
                bot.send_photo(message.chat.id, f)
        except Exception as e:
            tb = traceback.format_exc()
            bot.reply_to(message, f"Leaderboard failed: {e}\n{tb}")

    # --------------------------------------------------------
    # WIPE USER (ADMIN ONLY)
    # --------------------------------------------------------
    @bot.message_handler(commands=["wipe"])
    def _wipe(message):
        try:
            if message.from_user.id != ADMIN_ID:
                bot.reply_to(message, "❌ Not allowed.")
                return

            parts = message.text.split(" ", 1)
            if len(parts) < 2:
                bot.reply_to(message, "Usage: /wipe <username>")
                return

            target = parts[1].lstrip("@").lower()

            cursor.execute("SELECT user_id, username FROM users")
            rows = cursor.fetchall()

            to_delete = None
            for uid, uname in rows:
                if uname and uname.lower() == target:
                    to_delete = uid
                    break

            if not to_delete:
                bot.reply_to(message, f"❌ User @{target} not found.")
                return

            cursor.execute("DELETE FROM users WHERE user_id=?", (to_delete,))
            conn.commit()

            bot.reply_to(message, "🧹 User is wiped from the Metaverse.")
        except Exception as e:
            tb = traceback.format_exc()
            bot.reply_to(message, f"Wipe error: {e}\n{tb}")
