# bot/commands.py
# MegaGrok Command Router — Fully Corrected Edition

import os
import random
import traceback
from telebot import TeleBot

# ----------------------------------------------------------
# ADMIN ID
# ----------------------------------------------------------
try:
    ADMIN_ID = int(os.getenv("MEGAGROK_ADMIN_ID", "7574908943"))
except:
    ADMIN_ID = 7574908943


# ----------------------------------------------------------
# HELP TEXTS
# ----------------------------------------------------------

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

ADMIN_HELP_TEXT = (
    "🛡️ *MegaGrok Admin Commands*\n\n"
    "/wipe `user` - Reset a user's progress\n"
    "/announce `text` - Markdown announcement to channel\n"
    "/announce_html `html` - HTML announcement to channel\n"
    "/help_admin - Show this admin help\n"
)


# ----------------------------------------------------------
# MAIN HANDLER REGISTRATION
# ----------------------------------------------------------

def register_handlers(bot: TeleBot):

    # ------------------------------------------------------
    # REQUIRED IMPORTS (SAFE)
    # ------------------------------------------------------
    from bot.db import (
        get_user,
        update_user_xp,
        get_quests,
        record_quest,
        increment_win,
        increment_ritual,
        get_top_users,
        update_username,
        update_display_name,    # ⭐ THIS WAS MISSING — CRITICAL FIX
    )

    try:
        from bot.mobs import MOBS
    except Exception:
        MOBS = {}

    # ------------------------------------------------------
    # LOAD SUB-HANDLERS
    # ------------------------------------------------------

    # /growmygrok
    try:
        from bot.handlers.growmygrok import setup as grow_setup
        grow_setup(bot)
    except Exception as e:
        print("Failed loading growmygrok handler:", e)

    # /battle
    try:
        from bot.handlers.battle import setup as battle_setup
        battle_setup(bot)
    except Exception as e:
        print("Failed loading battle handler:", e)

    # /hop
    try:
        from bot.handlers.hop import setup as hop_setup
        hop_setup(bot)
    except Exception as e:
        print("Failed loading hop handler:", e)

    # /announce, /announce_html, /announce_preview
    try:
        from bot.handlers.announce import setup as announce_setup
        announce_setup(bot)
    except Exception as e:
        print("Failed loading announce handler:", e)

    # ------------------------------------------------------
    # /start
    # ------------------------------------------------------
    @bot.message_handler(commands=["start"])
    def _start(message):
        bot.reply_to(
            message,
            "🐸🌌 *THE COSMIC AMPHIBIAN HAS AWAKENED*\n\n"
            "Welcome to the MegaGrok Metaverse!\n"
            "Use /help to begin your journey.",
            parse_mode="Markdown"
        )

    # ------------------------------------------------------
    # USER HELP
    # ------------------------------------------------------
    @bot.message_handler(commands=["help"])
    def _help(message):
        bot.reply_to(message, HELP_TEXT, parse_mode="Markdown")

    # ------------------------------------------------------
    # ADMIN HELP
    # ------------------------------------------------------
    @bot.message_handler(commands=["help_admin"])
    def _help_admin(message):
        if message.from_user.id != ADMIN_ID:
            return bot.reply_to(message, "❌ Not authorized.")
        bot.reply_to(message, ADMIN_HELP_TEXT, parse_mode="Markdown")

    # ------------------------------------------------------
    # AUTO SYNC USERNAME + DISPLAY NAME
    # ------------------------------------------------------
    @bot.message_handler(func=lambda m: m.text and not m.text.startswith("/"))
    def _auto_sync(msg):
        """
        This handler *must not* crash, or it blocks ALL other commands.
        """
        try:
            if msg.from_user.username:
                update_username(msg.from_user.id, msg.from_user.username)

            dname = f"{msg.from_user.first_name or ''} {msg.from_user.last_name or ''}".strip()
            if dname:
                update_display_name(msg.from_user.id, dname)

        except Exception as e:
            # We log the error but DO NOT block other handlers
            print("Auto sync error:", e)

    # ------------------------------------------------------
    # FIGHT (unchanged)
    # ------------------------------------------------------
    @bot.message_handler(commands=["fight"])
    def _fight(message):
        try:
            uid = message.from_user.id
            q = get_quests(uid)

            if q.get("fight", 0) == 1:
                return bot.reply_to(message, "⚔️ You already fought today.")

            # Pick mob
            mob = random.choice(list(MOBS.values())) if isinstance(MOBS, dict) else random.choice(MOBS)
            mob_name = mob.get("name", "Mob")
            intro = mob.get("intro", "")

            bot.reply_to(
                message,
                f"⚔️ *{mob_name} Encounter!* \n\n{intro}",
                parse_mode="Markdown"
            )

            # Appearance
            try:
                portrait = mob.get("portrait")
                if portrait and os.path.exists(portrait):
                    with open(portrait, "rb") as f:
                        bot.send_photo(message.chat.id, f)
            except:
                pass

            # Fight logic
            win = random.choice([True, False])
            base_xp = random.randint(mob.get("min_xp", 10), mob.get("max_xp", 50))

            if win:
                increment_win(uid)

            user = get_user(uid)
            lvl = user["level"]

            try:
                evo_mult = evolutions.get_xp_multiplier_for_level(lvl)
            except:
                evo_mult = 1.0

            effective = int(base_xp * evo_mult)

            # XP update
            total = user["xp_total"] + effective
            cur = user["xp_current"] + effective
            nxt = user["xp_to_next_level"]
            curve = user["level_curve_factor"]

            lvled = False
            while cur >= nxt:
                cur -= nxt
                nxt = int(nxt * curve)
                lvl += 1
                lvled = True

            update_user_xp(uid, {
                "xp_total": total,
                "xp_current": cur,
                "xp_to_next_level": nxt,
                "level": lvl
            })

            record_quest(uid, "fight")

            pct = int((cur / nxt) * 100)
            bar = "▓" * (pct // 5) + "░" * (20 - (pct // 5))

            msg = (
                f"⚔️ *{'VICTORY' if win else 'DEFEAT'}!*\n"
                f"Enemy: *{mob_name}*\n\n"
                f"📈 XP Gain: +{effective}\n"
                f"🧬 Level: {lvl}\n"
                f"🔸 `{bar}` {pct}%"
            )

            bot.send_message(message.chat.id, msg, parse_mode="Markdown")

        except Exception:
            bot.reply_to(
                message,
                f"Fight failed:\n```\n{traceback.format_exc()}\n```",
                parse_mode="Markdown"
            )

    # ------------------------------------------------------
    # PROFILE
    # ------------------------------------------------------
    @bot.message_handler(commands=["profile"])
    def _profile(message):
        try:
            from bot.profile_image import generate_profile_image
        except Exception:
            return bot.reply_to(message, "Profile generator missing.")

        uid = message.from_user.id
        user = get_user(uid)

        display = (
            user.get("display_name")
            or message.from_user.first_name
            or user.get("username")
            or f"User{uid}"
        )

        data = {
            "user_id": uid,
            "display_name": display,
            "username": user.get("username"),
            "level": user["level"],
            "wins": user["wins"],
            "rituals": user["rituals"],
            "xp_total": user["xp_total"],
        }

        path = generate_profile_image(data)
        if path:
            with open(path, "rb") as f:
                bot.send_photo(message.chat.id, f)
        else:
            bot.reply_to(message, "Failed to generate profile card.")

    # ------------------------------------------------------
    # LEADERBOARD
    # ------------------------------------------------------
    @bot.message_handler(commands=["leaderboard"])
    def _leaderboard(message):
        try:
            users = get_top_users(50)
            from bot.images import generate_leaderboard_premium
            img = generate_leaderboard_premium(users)

            with open(img, "rb") as f:
                bot.send_photo(message.chat.id, f)

        except Exception:
            bot.reply_to(
                message,
                f"Leaderboard failed:\n```\n{traceback.format_exc()}\n```",
                parse_mode="Markdown"
            )

    # ------------------------------------------------------
    # WIPE USER (ADMIN)
    # ------------------------------------------------------
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

            target = None
            q = query.lower().lstrip("@")

            # By ID
            if query.isdigit():
                target = int(query)

            # Username match
            if target is None:
                for uid, uname, dn in rows:
                    if uname and uname.lower().lstrip("@") == q:
                        target = uid
                        break

            # Display name match
            if target is None:
                for uid, uname, dn in rows:
                    if dn and dn.lower() == q:
                        target = uid
                        break

            if target is None:
                return bot.reply_to(message, f"❌ No user matching: {query}")

            # Reset user
            db.cursor.execute("""
                UPDATE users SET
                    level=1,
                    xp_total=0,
                    xp_current=0,
                    xp_to_next_level=100,
                    level_curve_factor=1.35,
                    wins=0,
                    mobs_defeated=0,
                    rituals=0,
                    quests='{}',
                    cooldowns='{}',
                    evolution_multiplier=1.0
                WHERE user_id=?
            """, (target,))
            db.conn.commit()

            bot.reply_to(message, f"🧹 User reset: {target}")

        except Exception:
            bot.reply_to(
                message,
                f"Wipe failed:\n```\n{traceback.format_exc()}\n```",
                parse_mode="Markdown"
            )
