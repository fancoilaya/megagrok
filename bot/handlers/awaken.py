# bot/handlers/awaken.py
#
# MegaGrok — Unified Entry & Navigation
# SAFE VERSION: additive only, no PvP rewrites

from telebot import TeleBot, types

import bot.db as db
from bot.db import get_user

from bot.handlers.xphub import render_hub
from bot.handlers.pvp import render_pvp_main   # <-- additive helper only
from bot.profile_card import generate_profile_card
from bot.evolutions import get_evolution_for_level


NAV_PREFIX = "__nav__:"


# -------------------------------------------------
# Setup
# -------------------------------------------------
def setup(bot: TeleBot):

    # /awaken (primary entry)
    @bot.message_handler(commands=["awaken", "start"])
    def awaken_cmd(message):
        open_game_lobby(bot, message.chat.id, message.from_user.id)

    # Navigation router
    @bot.callback_query_handler(func=lambda c: c.data.startswith(NAV_PREFIX))
    def nav_cb(call):
        action = call.data.split(":", 1)[1]
        chat_id = call.message.chat.id
        msg_id = call.message.message_id
        uid = call.from_user.id

        # ----------------------------
        # 🧠 Training Grounds (XP Hub)
        # ----------------------------
        if action == "training":
            db.update_user_xp(uid, {"location": "TRAINING"})
            text, kb = render_hub(uid)
            kb.add(
                types.InlineKeyboardButton(
                    "🔙 Back to Awaken",
                    callback_data=f"{NAV_PREFIX}home"
                )
            )
            bot.edit_message_text(
                text,
                chat_id,
                msg_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
            return

        # ----------------------------
        # ⚔️ Arena (PvP) — SAME UX PATTERN
        # ----------------------------
        if action == "arena":
            db.update_user_xp(uid, {"location": "ARENA"})
            text, kb = render_pvp_main(uid)
            kb.add(
                types.InlineKeyboardButton(
                    "🔙 Back to Awaken",
                    callback_data=f"{NAV_PREFIX}home"
                )
            )
            bot.edit_message_text(
                text,
                chat_id,
                msg_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
            return

        # ----------------------------
        # 🧾 Profile
        # ----------------------------
        if action == "profile":
            send_profile(bot, chat_id, uid)
            return

        # ----------------------------
        # 🏆 Leaderboards (chooser)
        # ----------------------------
        if action == "leaderboards":
            show_leaderboard_choice(bot, chat_id)
            return

        if action == "lb_grok":
            bot.send_message(chat_id, "/leaderboard")
            return

        if action == "lb_arena":
            bot.send_message(chat_id, "/pvp")
            return

        # ----------------------------
        # ❓ How to Play
        # ----------------------------
        if action == "howtoplay":
            show_how_to_play(bot, chat_id)
            return

        # ----------------------------
        # 🔙 Back to Awaken
        # ----------------------------
        if action == "home":
            open_game_lobby(
                bot,
                chat_id,
                uid,
                edit=True,
                msg_id=msg_id
            )
            return


# -------------------------------------------------
# Awaken Lobby
# -------------------------------------------------
def open_game_lobby(bot, chat_id, uid, edit=False, msg_id=None):
    user = get_user(uid)

    db.update_user_xp(uid, {
        "has_awakened": 1,
        "location": "AWAKEN"
    })

    text = (
        "⚡ <b>WELCOME BACK, AWAKENED ONE</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🧠 <b>Training Grounds</b>\n"
        "Grow your Grok, fight mobs, earn XP, and evolve.\n\n"
        "⚔️ <b>Arena</b>\n"
        "Challenge other players, risk XP & ELO, and climb the ranks.\n\n"
        "<b>Choose your path:</b>"
        
    )

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🧠 Training Grounds", callback_data=f"{NAV_PREFIX}training"),
        types.InlineKeyboardButton("⚔️ Enter Arena", callback_data=f"{NAV_PREFIX}arena"),
    )
    kb.add(
        types.InlineKeyboardButton("🧾 My Profile", callback_data=f"{NAV_PREFIX}profile"),
        types.InlineKeyboardButton("🏆 Leaderboards", callback_data=f"{NAV_PREFIX}leaderboards"),
    )
    kb.add(
        types.InlineKeyboardButton("❓ How to Play", callback_data=f"{NAV_PREFIX}howtoplay"),
    )

    if edit:
        bot.edit_message_text(
            text,
            chat_id,
            msg_id,
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        bot.send_message(
            chat_id,
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )


# -------------------------------------------------
# Profile
# -------------------------------------------------
def send_profile(bot, chat_id, uid):
    user = get_user(uid)
    if not user:
        return

    evo = get_evolution_for_level(user.get("level", 1))

    data = {
        "user_id": uid,
        "display_name": user.get("display_name") or user.get("username") or f"User{uid}",
        "level": user.get("level", 1),
        "xp_current": user.get("xp_current", 0),
        "xp_to_next_level": user.get("xp_to_next_level", 100),
        "xp_total": user.get("xp_total", 0),
        "wins": user.get("wins", 0),
        "mobs_defeated": user.get("mobs_defeated", 0),
        "evolution": evo.get("name", "Tadpole"),
        "evolution_multiplier": user.get("evolution_multiplier", 1.0),
    }

    try:
        path = generate_profile_card(data)
        with open(path, "rb") as img:
            bot.send_photo(chat_id, img)
    except Exception:
        bot.send_message(chat_id, "❌ Failed to generate profile card.")


# -------------------------------------------------
# Leaderboard chooser
# -------------------------------------------------
def show_leaderboard_choice(bot, chat_id):
    text = (
        "🏆 <b>LEADERBOARDS</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Choose a ranking:"
    )

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🧬 Grok Evolution Leaderboard", callback_data=f"{NAV_PREFIX}lb_grok"),
        types.InlineKeyboardButton("⚔️ Arena Leaderboard", callback_data=f"{NAV_PREFIX}lb_arena"),
        types.InlineKeyboardButton("🔙 Back to Awaken", callback_data=f"{NAV_PREFIX}home"),
    )

    bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")


# -------------------------------------------------
# How to Play
# -------------------------------------------------
def show_how_to_play(bot, chat_id):
    text = (
        "🎮 <b>HOW TO PLAY MEGAGROK</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ Awaken your Grok\n"
        "2️⃣ Train in the Training Grounds\n"
        "3️⃣ Enter the Arena\n"
        "4️⃣ Climb the Leaderboards\n\n"
        "Every action strengthens your Grok."
    )

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🔙 Back to Awaken", callback_data=f"{NAV_PREFIX}home")
    )

    bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
