# bot/commands.py
# MegaGrok Commands Module — Stable & Safe Edition

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
    "/help - Show help menu\n"
    "/growmygrok - Gain XP and grow your Grok\n"
    "/hop - Daily ritual reward\n"
    "/fight - Quick daily fight\n"
    "/battle - Advanced interactive battle\n"
    "/profile - Show your Grok profile card\n"
    "/leaderboard - Show global rankings\n"
    "/grokdex - Explore all Hop-Verse creatures\n"
    "/wipe <username> - (admin) Remove a player\n"
)


def register_handlers(bot: TeleBot):
    """
    Registers all handlers SAFELY.
    This prevents import errors from crashing the whole bot.
    """

    # ---------------- SAFE IMPORTS ----------------
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
            update_display_name,  # ⭐ NEW IMPORT
        )
    except Exception as e:
        raise RuntimeError(f"DB import failure: {e}")

    try:
        from bot.mobs import MOBS
    except Exception:
        MOBS = []

    # ---------------- REGISTER HANDLER MODULES ----------------
    try:
        from bot.handlers.growmygrok import setup as grow_setup
        grow_setup(bot)
    except Exception as e:
        print("Failed loading growmygrok handler:", e)

    try:
        from bot.handlers.battle import setup as battle_setup
        battle_setup(bot)
    except Exception as e:
        print("Failed loading battle handler:", e)

    try:
        from bot.handlers.hop import setup as hop_setup
        hop_setup(bot)
    except Exception as e:
        print("Failed loading hop handler:", e)

    # ---------------- START ----------------
    @bot.message_handler(commands=["start"])
    def _start(message):
        text = (
            "🐸🌌 *THE COSMIC AMPHIBIAN HAS AWAKENED* 🌌🐸\n\n"
            "Welcome to the MegaGrok Metaverse!\n"
            "Use /help to begin your journey."
        )
        bot.reply_to(message, text, parse_mode="Markdown")

    # ---------------- HELP ----------------
    @bot.message_handler(commands=["help"])
    def _help(message):
        bot.reply_to(message, HELP_TEXT, parse_mode="Markdown")

    # ---------------- AUTO USER SYNC (USERNAME + DISPLAY NAME) ----------------
    @bot.message_handler(func=lambda m: m.text and not m.text.startswith("/"))
    def _auto_username(msg):
        try:
            # Sync username (@tag)
            uname = msg.from_user.username
            if uname:
                update_username(msg.from_user.id, uname)

            # ⭐ Sync display name (first + last)
            dname = f"{msg.from_user.first_name or ''} {msg.from_user.last_name or ''}".strip()
            if dname:
                update_display_name(msg.from_user.id, dname)

        except Exception:
            pass

    # ---------------- FIGHT ----------------
    @bot.message_handler(commands=["fight"])
    def _fight(message):
        try:
            uid = message.from_user.id
            q = get_quests(uid)
            if q.get("fight", 0) == 1:
                return bot.reply_to(message, "⚔️ You already fought today.")

            mob = random.choice(list(MOBS.values())) if isinstance(MOBS, dict) else random.choice(MOBS)
            mob_name = mob.get("name", "Mob")
            intro = mob.get("intro", "")

            bot.reply_to(
                message,
                f"⚔️ **{mob_name} Encounter!**\n\n{intro}",
                parse_mode="Markdown"
            )

            # Portrait
            try:
                portrait = mob.get("portrait")
                if portrait and os.path.exists(portrait):
                    with open(portrait, "rb") as f:
                        bot.send_photo(message.chat.id, f)
            except:
                pass

            # Win?
            win = random.choice([True, False])
            base_xp = random.randint(mob.get("min_xp", 10), mob.get("max_xp", 50))

            if win:
                increment_win(uid)

            user = get_user(uid)
            level = user["level"]

            # evo multiplier
            try:
                import bot.evolutions as evolutions
                evo_mult = evolutions.get_xp_multiplier_for_level(level)
            except:
                evo_mult = 1.0

            effective_xp = int(base_xp * evo_mult)

            # XP update
            xp_total = user["xp_total"] + effective_xp
            cur = user["xp_current"] + effective_xp
            xp_to_next = user["xp_to_next_level"]
            curve = user["level_curve_factor"]

            leveled = False
            while cur >= xp_to_next:
                cur -= xp_to_next
                level += 1
                xp_to_next *= curve
                leveled = True

            update_user_xp(uid, {
                "xp_total": xp_total,
                "xp_current": cur,
                "xp_to_next_level": int(xp_to_next),
                "level": level
            })

            record_quest(uid, "fight")

            bar = int((cur / xp_to_next) * 20)
            bar_txt = "▓" * bar + "░" * (20 - bar)

            msg = (
                f"⚔️ **{'VICTORY' if win else 'DEFEAT'}!**\n"
                f"Enemy: *{mob_name}*\n\n"
                f"📈 Base XP: +{base_xp}\n"
                f"🔮 Evo Multiplier: ×{evo_mult:.2f}\n"
                f"⚡ Total XP: +{effective_xp}\n\n"
                f"🧬 Level: {level}\n"
                f"🔸 Progress: `{bar_txt}`"
            )

            bot.send_message(message.chat.id, msg, parse_mode="Markdown")

        except Exception:
            bot.reply_to(message, f"Fight failed:\n```\n{traceback.format_exc()}\n```", parse_mode="Markdown")

    # ---------------- PROFILE ----------------
    @bot.message_handler(commands=["profile"])
    def _profile(message):
        try:
            from bot.images import generate_profile_image
        except Exception:
            return bot.reply_to(message, "Profile generator missing.")

        user_id = message.from_user.id
        user = get_user(user_id)

        # ⭐ Use display name when available
        display_name = user.get("display_name") or message.from_user.first_name
        if not display_name:
            display_name = f"User{user_id}"

        data = {
            "user_id": user_id,
            "display_name": display_name,     # ⭐ NEW FIELD
            "username": user.get("username"),
            "level": user["level"],
            "wins": user["wins"],
            "rituals": user["rituals"],
            "xp_total": user["xp_total"]
        }

        path = generate_profile_image(data)
        if path:
            with open(path, "rb") as f:
                bot.send_photo(message.chat.id, f)
        else:
            bot.reply_to(message, "Failed to generate profile card.")

    # ---------------- LEADERBOARD ----------------
    @bot.message_handler(commands=["leaderboard"])
    def _leaderboard(message):
        try:
            users = get_top_users(50)
            from bot.images import generate_leaderboard_premium
            out = generate_leaderboard_premium(users)

            with open(out, "rb") as f:
                bot.send_photo(message.chat.id, f)

        except Exception:
            bot.reply_to(message, f"Leaderboard failed:\n```\n{traceback.format_exc()}\n```", parse_mode="Markdown")

    # ---------------- WIPE USER (admin) ----------------
    @bot.message_handler(commands=["wipe"])
    def _wipe(message):
        if message.from_user.id != ADMIN_ID:
            return bot.reply_to(message, "❌ Not authorized.")

        parts = message.text.split(" ", 1)
        if len(parts) < 2:
            return bot.reply_to(message, "Usage: /wipe <username>")

        username = parts[1].lstrip("@").lower()

        try:
            from bot import db
            rows = db.cursor.execute("SELECT user_id, username FROM users").fetchall()

            target_id = None
            for uid, uname in rows:
                if uname and uname.lower().lstrip("@") == username:
                    target_id = uid
                    break

            if not target_id:
                return bot.reply_to(message, f"No user @{username} found.")

            db.cursor.execute("DELETE FROM users WHERE user_id=?", (target_id,))
            db.conn.commit()

            bot.reply_to(message, f"User @{username} wiped from the Metaverse.")

        except Exception:
            bot.reply_to(message, f"WIPE error:\n```\n{traceback.format_exc()}\n```", parse_mode="Markdown")
