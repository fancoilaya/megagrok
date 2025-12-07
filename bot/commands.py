# bot/commands.py
# MegaGrok Commands Module — Updated /help and /help_admin

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

# NORMAL USER HELP (NO ADMIN COMMANDS)
HELP_TEXT = (
    "🐸 *MegaGrok Commands*\n\n"
    "/start - Begin your journey\n"
    "/help - Show this help menu\n"
    "/growmygrok - Train and evolve your Grok\n"
    "/hop - Daily ritual reward\n"
    "/fight - Quick daily fight\n"
    "/battle - Advanced interactive battle\n"
    "/profile - Show your Grok profile card\n"
    "/leaderboard - Show global rankings\n"
    "/grokdex - Explore all Hop-Verse creatures\n"
)

# ADMIN HELP TEXT (Telegram-safe Markdown)
ADMIN_HELP_TEXT = (
    "🛡️ *MegaGrok Admin Commands*\n\n"
    "/wipe `user` - Reset a user's progress (keeps account)\n"
    "/announce `text` - Post a Markdown announcement to the channel\n"
    "/announce_html `html` - Post an HTML announcement to the channel\n"
    "/help_admin - Show this admin command list\n"
)


def register_handlers(bot: TeleBot):

    # ---------------- IMPORTS ----------------
    from bot.db import (
        get_user,
        update_user_xp,
        get_quests,
        record_quest,
        increment_win,
        increment_ritual,
        get_top_users,
        update_username,
        update_display_name,
    )

    try:
        from bot.mobs import MOBS
    except Exception:
        MOBS = []

    # ---------------- REGISTER SUB-HANDLERS ----------------
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

    try:
        from bot.handlers.announce import setup as announce_setup
        announce_setup(bot)
    except Exception as e:
        print("Failed loading announce handler:", e)

    # ---------------- START ----------------
    @bot.message_handler(commands=["start"])
    def _start(message):
        bot.reply_to(message,
            "🐸🌌 *THE COSMIC AMPHIBIAN HAS AWAKENED*\n\n"
            "Welcome to the MegaGrok Metaverse!\n"
            "Use /help to begin your journey.",
            parse_mode="Markdown"
        )

    # ---------------- USER HELP ----------------
    @bot.message_handler(commands=["help"])
    def _help(message):
        bot.reply_to(message, HELP_TEXT, parse_mode="Markdown")

    # ---------------- ADMIN HELP ----------------
    @bot.message_handler(commands=["help_admin"])
    def _help_admin(message):
        if message.from_user.id != ADMIN_ID:
            return bot.reply_to(message, "❌ Not authorized.")
        bot.reply_to(message, ADMIN_HELP_TEXT, parse_mode="Markdown")

    # ---------------- AUTO SYNC USERNAME / DISPLAY NAME ----------------
    @bot.message_handler(func=lambda m: m.text and not m.text.startswith("/"))
    def _auto_username(msg):
        try:
            if msg.from_user.username:
                update_username(msg.from_user.id, msg.from_user.username)

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

            bot.reply_to(message, f"⚔️ *{mob_name} Encounter!*\n\n{intro}", parse_mode="Markdown")

            try:
                portrait = mob.get("portrait")
                if portrait and os.path.exists(portrait):
                    with open(portrait, "rb") as f:
                        bot.send_photo(message.chat.id, f)
            except:
                pass

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
                f"⚔️ *{'VICTORY' if win else 'DEFEAT'}!*\n"
                f"Enemy: *{mob_name}*\n\n"
                f"📈 Base XP: +{base_xp}\n"
                f"🔮 Evo Multiplier: ×{evo_mult:.2f}\n"
                f"⚡ Total XP: +{effective_xp}\n\n"
                f"🧬 Level: {level}\n"
                f"🔸 Progress: `{bar_txt}`"
            )

            bot.send_message(message.chat.id, msg, parse_mode="Markdown")

        except Exception:
            bot.reply_to(message,
                f"Fight failed:\n```\n{traceback.format_exc()}\n```",
                parse_mode="Markdown"
            )

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
            bot.reply_to(message,
                f"Leaderboard failed:\n```\n{traceback.format_exc()}\n```",
                parse_mode="Markdown"
            )

    # ---------------- WIPE (admin) ----------------
    @bot.message_handler(commands=["wipe"])
    def _wipe(message):
        if message.from_user.id != ADMIN_ID:
            return bot.reply_to(message, "❌ Not authorized.")

        parts = message.text.split(" ", 1)
        if len(parts) < 2:
            return bot.reply_to(message, "Usage: /wipe `user`", parse_mode="Markdown")

        query = parts[1].strip()

        try:
            from bot import db

            rows = db.cursor.execute(
                "SELECT user_id, username, display_name FROM users"
            ).fetchall()

            target_id = None

            # By ID
            if query.isdigit():
                qid = int(query)
                for uid, username, dn in rows:
                    if uid == qid:
                        target_id = uid
                        break

            # By username
            if target_id is None:
                norm = query.lstrip("@").lower()
                for uid, username, dn in rows:
                    if username and username.lower().lstrip("@") == norm:
                        target_id = uid
                        break

            # By display name
            if target_id is None:
                qdn = query.lower()
                for uid, username, dn in rows:
                    if dn and dn.lower() == qdn:
                        target_id = uid
                        break

            if target_id is None:
                return bot.reply_to(message, f"No user found matching: {query}")

            # Reset user
            db.cursor.execute("""
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
            """, (json.dumps({}), json.dumps({}), target_id))
            db.conn.commit()

            bot.reply_to(message,
                f"🧹 User *{query}* (ID {target_id}) has been reset.",
                parse_mode="Markdown"
            )

        except Exception:
            bot.reply_to(message,
                f"Wipe error:\n```\n{traceback.format_exc()}\n```",
                parse_mode="Markdown"
            )
