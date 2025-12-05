# bot/commands.py
# Defensive commands loader for MegaGrok — avoids import-time crashes.
# Exports register_handlers(bot) expected by main.py.

import os
import time
import random
import traceback
from telebot import TeleBot

# Admin ID (Telegram numeric ID)
try:
    ADMIN_ID = int(os.getenv("MEGAGROK_ADMIN_ID", "7574908943"))
except:
    ADMIN_ID = 7574908943

HELP_TEXT = (
    "🐸 **MegaGrok Commands**\n\n"
    "/start - Begin your journey\n"
    "/help - Show help\n"
    "/growmygrok - Gain XP and grow your Grok\n"
    "/hop - Daily ritual\n"
    "/fight - Quick fight (1/day)\n"
    "/battle - Advanced interactive battle\n"
    "/profile - Show your Grok profile card\n"
    "/leaderboard - Show leaderboard poster\n"
    "/wipe <username> - (admin) delete a player\n"
)

def _safe_reply(bot, chat_id, text):
    try:
        bot.send_message(chat_id, text, parse_mode="Markdown")
    except:
        bot.send_message(chat_id, text)

# --------------------------------------------------------------------
# REGISTER HANDLERS
# --------------------------------------------------------------------
def register_handlers(bot: TeleBot):

    # Lazy DB imports
    try:
        from bot.db import (
            get_user,
            update_user_xp,
            get_quests,
            record_quest,
            increment_win,
            increment_ritual,
            get_top_users,
            cursor,
            conn,
        )
    except Exception as e:
        # Fail-safe fallbacks
        def _missing(*args, **kwargs):
            raise RuntimeError(f"DB error: {e}")
        get_user = update_user_xp = get_quests = record_quest = increment_win = increment_ritual = get_top_users = _missing
        cursor = conn = None

    # Import mobs
    try:
        from bot.mobs import MOBS
    except:
        MOBS = {}

    # ------------------------------------------------------------
    @bot.message_handler(commands=["start"])
    def _start(message):
        text = (
            "🐸🌌 *THE COSMIC AMPHIBIAN HAS AWAKENED* 🌌🐸\n\n"
            "Welcome to the MegaGrok Metaverse.\n"
            "Use /help to explore your journey."
        )
        _safe_reply(bot, message.chat.id, text)

    # ------------------------------------------------------------
    @bot.message_handler(commands=["help"])
    def _help(message):
        _safe_reply(bot, message.chat.id, HELP_TEXT)

    # ------------------------------------------------------------
    @bot.message_handler(commands=["hop"])
    def _hop(message):
        try:
            user_id = message.from_user.id
            q = get_quests(user_id)

            if q.get("hop", 0) == 1:
                bot.reply_to(message, "🐸 You already performed today’s ritual!")
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
                "level": level,
            })

            record_quest(user_id, "hop")
            increment_ritual(user_id)

            text = f"✨ Hop Ritual complete! +{xp_gain} XP"
            if leveled:
                text += "\n🎉 LEVEL UP!"
            bot.reply_to(message, text)

        except Exception as e:
            bot.reply_to(message, f"Hop failed:\n{traceback.format_exc()}")

    # ------------------------------------------------------------
    @bot.message_handler(commands=["fight"])
    def _fight(message):
        try:
            user_id = message.from_user.id
            q = get_quests(user_id)

            if q.get("fight", 0) == 1:
                bot.reply_to(message, "⚔️ You already fought today.")
                return

            # Choose random mob
            mob = random.choice(list(MOBS.values())) if MOBS else None

            mob_name = mob.get("name", "Creature") if mob else "Creature"
            intro = mob.get("intro", "") if mob else ""

            bot.reply_to(message, f"⚔️ **{mob_name} appears!**\n{intro}", parse_mode="Markdown")

            # Portrait
            try:
                portrait = mob.get("portrait")
                if portrait and os.path.exists(portrait):
                    with open(portrait, "rb") as f:
                        bot.send_photo(message.chat.id, f)
            except:
                pass

            # Fight result
            win = random.choice([True, False])
            base_xp = random.randint(mob.get("min_xp", 10), mob.get("max_xp", 25)) if mob else 20

            if win:
                increment_win(user_id)

            # XP gain
            user = get_user(user_id)
            level = user["level"]

            # Evolution multiplier
            try:
                import bot.evolutions as evolutions
                evo_mult = evolutions.get_xp_multiplier_for_level(level) * float(user.get("evolution_multiplier", 1.0))
            except:
                evo_mult = float(user.get("evolution_multiplier", 1.0))

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

            update_user_xp(user_id, {
                "xp_total": xp_total,
                "xp_current": cur,
                "xp_to_next_level": xp_to_next,
                "level": level,
            })

            record_quest(user_id, "fight")

            pct = cur / xp_to_next
            bar = "▓" * int(pct * 20) + "░" * (20 - int(pct * 20))

            text = (
                f"⚔️ **{'VICTORY' if win else 'DEFEAT'}** vs *{mob_name}*\n\n"
                f"📈 Base XP: +{base_xp}\n"
                f"🔮 Multiplier: ×{evo_mult:.2f}\n"
                f"⚡ Effective XP: +{effective_xp}\n\n"
                f"🧬 Level {level}\n"
                f"XP: {cur}/{xp_to_next}\n"
                f"`{bar}` {int(pct*100)}%\n"
            )

            if leveled:
                text += "\n🎉 **LEVEL UP!**"

            bot.send_message(message.chat.id, text, parse_mode="Markdown")

        except Exception as e:
            bot.reply_to(message, f"Fight failed:\n{traceback.format_exc()}")

    # ------------------------------------------------------------
    @bot.message_handler(commands=["profile"])
    def _profile(message):
        try:
            from bot.profile_image import generate_profile_image
        except:
            from bot.images import generate_profile_image

        user_id = message.from_user.id
        user = get_user(user_id)

        payload = {
            "user_id": user_id,
            "username": message.from_user.username or f"User{user_id}",
            "level": user.get("level"),
            "wins": user.get("wins"),
            "fights": user.get("mobs_defeated", 0),
            "rituals": user.get("rituals"),
            "xp_total": user.get("xp_total"),
        }

        out = generate_profile_image(payload)
        with open(out, "rb") as f:
            bot.send_photo(message.chat.id, f)

    # ------------------------------------------------------------
    @bot.message_handler(commands=["leaderboard"])
    def _leaderboard(message):
        try:
            users = get_top_users(12)

            from bot.images import generate_leaderboard_premium
            out = generate_leaderboard_premium(users)

            with open(out, "rb") as f:
                bot.send_photo(message.chat.id, f)

        except Exception as e:
            bot.reply_to(message, f"Leaderboard failed:\n{traceback.format_exc()}")

    # ------------------------------------------------------------
    @bot.message_handler(commands=["wipe"])
    def _wipe(message):
        if message.from_user.id != ADMIN_ID:
            bot.reply_to(message, "❌ You are not allowed to use this command.")
            return

        parts = message.text.split(" ", 1)
        if len(parts) < 2:
            bot.reply_to(message, "Usage: /wipe <username>")
            return

        target = parts[1].strip().lstrip("@").lower()

        try:
            from bot.db import cursor as cur, conn as conn_obj
        except:
            bot.reply_to(message, "DB unavailable.")
            return

        cur.execute("SELECT user_id, username FROM users")
        found = None
        for uid, uname in cur.fetchall():
            if uname and uname.lower().lstrip("@") == target:
                found = uid
                break

        if not found:
            bot.reply_to(message, "❌ No such user found.")
            return

        cur.execute("DELETE FROM users WHERE user_id=?", (found,))
        conn_obj.commit()

        bot.reply_to(message, "User is wiped from the Metaverse ✨")

