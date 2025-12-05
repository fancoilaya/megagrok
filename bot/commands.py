# bot/commands.py
# Defensive commands loader for MegaGrok — avoids import-time crashes.
# Exports register_handlers(bot) expected by main.py.

import os
import time
import random
import traceback
from telebot import TeleBot

# Admin ID can be set via env var MEGAGROK_ADMIN_ID or fallback here
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
    "/battle - Advanced interactive battle (handlers/battle.py)\n"
    "/profile - Show your Grok profile card\n"
    "/leaderboard - Show leaderboard poster\n"
    "/wipe <username> - (admin) delete a player from DB\n"
)


def _safe_reply(bot, chat_id, text):
    try:
        bot.send_message(chat_id, text, parse_mode="Markdown")
    except Exception:
        try:
            bot.send_message(chat_id, text)
        except Exception:
            pass


def register_handlers(bot: TeleBot):
    """
    Register command handlers. Imports that may fail are done inside this function
    so import-time errors don't prevent main.py from loading the module.
    """
    # Lazy imports and fallbacks
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
        # create minimal fallbacks that raise inside handlers with a clear message
        def _missing(*args, **kwargs):
            raise RuntimeError(f"Required DB function missing: {e}")

        get_user = update_user_xp = get_quests = record_quest = increment_win = increment_ritual = get_top_users = None
        cursor = conn = None

    try:
        # images/profile functions may be named differently; import inside handlers where used
        from bot.mobs import MOBS
    except Exception:
        MOBS = []

    # ---------------- START ----------------
    @bot.message_handler(commands=["start"])
    def _start(message):
        try:
            start_text = (
                "🐸🌌 *THE COSMIC AMPHIBIAN HAS AWAKENED* 🌌🐸\n\n"
                "Welcome to the MegaGrok Metaverse.\nUse /help to see available commands."
            )
            bot.reply_to(message, start_text, parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"Error in /start: {e}")

    # ---------------- HELP ----------------
    @bot.message_handler(commands=["help"])
    def _help(message):
        try:
            bot.reply_to(message, HELP_TEXT, parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"Error in /help: {e}")

    # ---------------- HOP ----------------
    @bot.message_handler(commands=["hop"])
    def _hop(message):
        try:
            if get_quests is None or get_user is None or update_user_xp is None or record_quest is None or increment_ritual is None:
                bot.reply_to(message, "Hop unavailable: DB functions missing.")
                return

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

            text = f"🐸✨ Hop Ritual complete! +{xp_gain} XP"
            if leveled:
                text += "\n🎉 LEVEL UP!"
            bot.reply_to(message, text)
        except Exception as e:
            tb = traceback.format_exc()
            bot.reply_to(message, f"Hop failed: {e}\n{tb}")

    # ---------------- FIGHT ----------------
    @bot.message_handler(commands=["fight"])
    def _fight(message):
        try:
            if get_quests is None or get_user is None or update_user_xp is None or record_quest is None:
                bot.reply_to(message, "Fight unavailable: DB functions missing.")
                return

            user_id = message.from_user.id
            q = get_quests(user_id)
            # Assuming there's a 'fight' daily flag elsewhere; fallback to None
            if q.get("fight", 0) == 1:
                bot.reply_to(message, "⚔️ You already fought today.")
                return

            mob = None
            try:
                # choose random mob if available
                import random as _rnd
                if isinstance(MOBS, (list, tuple)) and MOBS:
                    mob = _rnd.choice(MOBS)
                elif isinstance(MOBS, dict) and MOBS:
                    mob = _rnd.choice(list(MOBS.values()))
            except Exception:
                mob = None

            mob_name = mob.get("name") if mob else "Hop-verse Creature"
            intro = mob.get("intro", "") if mob else ""

            bot.reply_to(message, f"⚔️ **{mob_name} Encounter!**\n\n{intro}", parse_mode="Markdown")

            # try sending portrait if path present
            try:
                portrait = mob.get("portrait") if mob else None
                if portrait and os.path.exists(portrait):
                    with open(portrait, "rb") as f:
                        bot.send_photo(message.chat.id, f)
            except Exception:
                pass

            win = random.choice([True, False])
            base_xp = random.randint(mob.get("min_xp", 10), mob.get("max_xp", 25)) if mob else random.randint(10, 25)
            if win and increment_win:
                try:
                    increment_win(user_id)
                except Exception:
                    pass

            user = get_user(user_id)
            level = user.get("level", 1)
            # evolutions may be missing; guard
            evo_mult = 1.0
            try:
                import bot.evolutions as evolutions
                evo_mult = evolutions.get_xp_multiplier_for_level(level) * float(user.get("evolution_multiplier", 1.0))
            except Exception:
                try:
                    evo_mult = float(user.get("evolution_multiplier", 1.0))
                except:
                    evo_mult = 1.0

            effective_xp = int(round(base_xp * evo_mult))

            # XP update
            xp_total = user["xp_total"] + effective_xp
            cur = user["xp_current"] + effective_xp
            xp_to_next = user["xp_to_next_level"]
            curve = user["level_curve_factor"]

            leveled_up = False
            while cur >= xp_to_next:
                cur -= xp_to_next
                level += 1
                xp_to_next = int(xp_to_next * curve)
                leveled_up = True

            update_user_xp(user_id, {
                "xp_total": xp_total,
                "xp_current": cur,
                "xp_to_next_level": xp_to_next,
                "level": level
            })

            record_quest(user_id, "fight")

            pct = cur / xp_to_next if xp_to_next else 0
            fill = int(20 * pct)
            bar = "▓" * fill + "░" * (20 - fill)

            msg = (
                f"⚔️ **Battle Outcome: {'VICTORY' if win else 'DEFEAT'}!**\n"
                f"Enemy: *{mob_name}*\n\n"
                f"📈 **Base XP:** +{base_xp}\n"
                f"🔮 **Evo Boost:** ×{evo_mult:.2f}\n"
                f"⚡ **Effective XP:** +{effective_xp}\n\n"
                f"🧬 **Level:** {level}\n"
                f"🔸 **XP:** {cur} / {xp_to_next}\n"
                f"🟩 **Progress:** `{bar}` {int(pct*100)}%\n"
            )
            if leveled_up:
                msg += "\n🎉 **LEVEL UP!** Your MegaGrok grows stronger!"

            bot.send_message(message.chat.id, msg, parse_mode="Markdown")
        except Exception as e:
            tb = traceback.format_exc()
            bot.reply_to(message, f"Fight failed: {e}\n{tb}")

    # ---------------- PROFILE ----------------
    @bot.message_handler(commands=["profile"])
    def _profile(message):
        try:
            if get_user is None:
                bot.reply_to(message, "Profile unavailable: DB missing.")
                return

            user_id = message.from_user.id
            user = get_user(user_id)

            # lazy import profile generator
            try:
                from bot.profile_image import generate_profile_image
            except Exception:
                try:
                    from bot.images import generate_profile_image
                except Exception:
                    generate_profile_image = None

            if generate_profile_image is None:
                bot.reply_to(message, "Profile generator not available.")
                return

            payload = {
                "user_id": user_id,
                "username": message.from_user.username or f"User{user_id}",
                "level": user.get("level"),
                "wins": user.get("wins"),
                "rituals": user.get("rituals"),
                "xp_total": user.get("xp_total")
            }

            img_path = generate_profile_image(payload)
            if img_path and os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    bot.send_photo(message.chat.id, f)
            else:
                bot.reply_to(message, "Failed to generate profile image.")
        except Exception as e:
            tb = traceback.format_exc()
            bot.reply_to(message, f"Profile failed: {e}\n{tb}")

    # ---------------- LEADERBOARD ----------------
    @bot.message_handler(commands=["leaderboard"])
    def _leaderboard(message):
        try:
            if get_top_users is None:
                bot.reply_to(message, "Leaderboard unavailable: DB missing.")
                return

            users = []
            try:
                # support different signatures: get_top_users(limit=..) or get_top_users(n)
                try:
                    users = get_top_users(limit=12)
                except TypeError:
                    users = get_top_users(12)
            except Exception:
                # fallback query that returns empty
                users = []

            # lazy import image generator
            try:
                from bot.images import generate_leaderboard_premium
            except Exception:
                generate_leaderboard_premium = None

            if not generate_leaderboard_premium:
                bot.reply_to(message, "Leaderboard image generator not available.")
                return

            out = generate_leaderboard_premium(users)
            if out and os.path.exists(out):
                with open(out, "rb") as f:
                    bot.send_photo(message.chat.id, f)
            else:
                bot.reply_to(message, "Failed to render leaderboard image.")
        except Exception as e:
            tb = traceback.format_exc()
            bot.reply_to(message, f"Leaderboard failed: {e}\n{tb}")

    # ---------------- WIPE (admin-only) ----------------
    @bot.message_handler(commands=["wipe"])
    def _wipe(message):
        try:
            # only admin allowed
            if message.from_user.id != ADMIN_ID:
                bot.reply_to(message, "❌ You are not allowed to use this command.")
                return

            parts = message.text.strip().split(" ", 1)
            if len(parts) < 2:
                bot.reply_to(message, "Usage: /wipe <username>\nExample: /wipe @SegmentSol")
                return

            username = parts[1].lstrip("@").strip().lower()
            # use DB cursor/conn if available
            try:
                from bot import db as _dbmod
                cur = getattr(_dbmod, "cursor", None)
                conn_obj = getattr(_dbmod, "conn", None)
            except Exception:
                cur = None
                conn_obj = None

            if cur is None or conn_obj is None:
                # fallback: try to import cursor/conn from bot.db directly
                try:
                    from bot.db import cursor as cur, conn as conn_obj
                except Exception:
                    cur = None
                    conn_obj = None

            if cur is None or conn_obj is None:
                bot.reply_to(message, "Wipe failed: database cursor not available.")
                return

            # find user by username field in users table
            cur.execute("SELECT user_id, username FROM users")
            rows = cur.fetchall()
            target_id = None
            target_username = None
            for uid, uname in rows:
                if uname and uname.lower().lstrip("@") == username:
                    target_id = uid
                    target_username = uname
                    break

            if not target_id:
                bot.reply_to(message, f"❌ No user found with username @{username}")
                return

            # delete user row
            cur.execute("DELETE FROM users WHERE user_id=?", (target_id,))
            conn_obj.commit()

            # remove any cooldowns column if stored elsewhere (attempt best-effort)
            try:
                # if battle_sessions stored in file, remove possible session
                sess_path = "/tmp/battle_sessions.json"
                if os.path.exists(sess_path):
                    import json as _json
                    with open(sess_path, "r") as fh:
                        sess = _json.load(fh)
                    if str(target_id) in sess:
                        del sess[str(target_id)]
                        with open(sess_path, "w") as fh:
                            _json.dump(sess, fh)
            except Exception:
                pass

            bot.reply_to(message, "User is wiped from the Metaverse", parse_mode="Markdown")
        except Exception as e:
            tb = traceback.format_exc()
            bot.reply_to(message, f"Wipe failed: {e}\n{tb}")

    # end register_handlers
