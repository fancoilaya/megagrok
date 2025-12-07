# bot/commands.py
# MegaGrok Commands Module — Stable & Safe Edition (FULLY UPDATED)

import os
import time
import random
import traceback
import json
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
    "/wipe <user> - (admin) Reset a user's progress\n"
)


def register_handlers(bot: TeleBot):
    """
    Registers all handlers SAFELY.
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
            update_display_name,   # ⭐ required for display name sync
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

            # Sync display name
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

            # Decide win
            win = random.choice([True, False])
            base_xp = random.randint(mob.get("min_xp", 10), mob.get("max_xp", 50))

            if win:
                increment_win(uid)

            user = get_user(uid)
            level = user["level"]

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
                xp_to_next = int(xp_to_next * curve)
                leveled = True

            update_user_xp(uid, {
                "xp_total": xp_total,
                "xp_current": cur,
                "xp_to_next_level": xp_to_next,
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
            bot.reply_to(
                message,
                f"Fight failed:\n```\n{traceback.format_exc()}\n```",
                parse_mode="Markdown"
            )


    # ---------------- PROFILE ----------------
    @bot.message_handler(commands=["profile"])
    def _profile(message):
        try:
            from bot.profile_image import generate_profile_image
        except Exception:
            return bot.reply_to(message, "Profile generator missing.")

        user_id = message.from_user.id
        user = get_user(user_id)

        # Use display name > username > fallback  
        display_name = (
            user.get("display_name")
            or message.from_user.first_name
            or user.get("username")
            or f"User{user_id}"
        )

        data = {
            "user_id": user_id,
            "display_name": display_name,
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
            bot.reply_to(
                message,
                f"Leaderboard failed:\n```\n{traceback.format_exc()}\n```",
                parse_mode="Markdown"
            )


    # ---------------- WIPE USER (admin) — RESET, NOT DELETE ----------------
    @bot.message_handler(commands=["wipe"])
    def _wipe(message):
        if message.from_user.id != ADMIN_ID:
            return bot.reply_to(message, "❌ Not authorized.")

        parts = message.text.split(" ", 1)
        if len(parts) < 2:
            return bot.reply_to(
                message,
                "Usage: /wipe <user_id | @username | display name>"
            )

        query = parts[1].strip()

        try:
            from bot import db

            rows = db.cursor.execute(
                "SELECT user_id, username, display_name FROM users"
            ).fetchall()

            target_id = None

            # 1️⃣ Check numeric ID
            if query.isdigit():
                for uid, u, d in rows:
                    if uid == int(query):
                        target_id = uid
                        break

            # 2️⃣ Username match
            if target_id is None:
                q_u = query.lower().lstrip("@")
                for uid, username, display_name in rows:
                    if username and username.lower().lstrip("@") == q_u:
                        target_id = uid
                        break

            # 3️⃣ Display name match
            if target_id is None:
                q_dn = query.lower()
                for uid, username, display_name in rows:
                    if display_name and display_name.lower() == q_dn:
                        target_id = uid
                        break

            if target_id is None:
                return bot.reply_to(message, f"❌ No user found matching: {query}")

            # ⭐ RESET USER DATA (do not delete row)
            db.cursor.execute(
                """
                UPDATE users SET
                    level = 1,
                    xp_total = 0,
                    xp_current = 0,
                    xp_to_next_level = 100,
                    level_curve_factor = 1.35,
                    wins = 0,
                    mobs_defeated = 0,
                    rituals = 0,
                    quests = ?,
                    cooldowns = ?,
                    evolution_multiplier = 1.0
                WHERE user_id = ?
                """,
                (json.dumps({}), json.dumps({}), target_id)
            )
            db.conn.commit()

            bot.reply_to(
                message,
                f"🧹 User *{query}* (ID {target_id}) has been reset.\n"
                f"They remain registered but are now Level 1.",
                parse_mode="Markdown"
            )

        except Exception:
            bot.reply_to(
                message,
                f"Wipe error:\n```\n{traceback.format_exc()}\n```",
                parse_mode="Markdown"
            )
