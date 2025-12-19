# bot/handlers/awaken.py
#
# MegaGrok — Main Entry & Global Navigation
# FINAL VERSION: Arena edits in-place (no chat clutter)

from telebot import TeleBot, types

import bot.db as db
from bot.db import get_user, has_unseen_pvp_attacks

from bot.handlers.xphub import render_hub
from bot.handlers.leaderboard_ui import show_leaderboard_ui
from bot.handlers.pvp import render_pvp_main
from bot.profile_card import generate_profile_card
from bot.evolutions import get_evolution_for_level

from bot.ui.world_status import get_world_status, get_since_you_were_gone

NAV_PREFIX = "__nav__:"


# -------------------------------------------------
# Setup
# -------------------------------------------------
def setup(bot: TeleBot):

    # ----------------------------
    # /awaken entry
    # ----------------------------
    @bot.message_handler(commands=["awaken", "start"])
    def awaken_cmd(message):
        open_game_lobby(bot, message.chat.id, message.from_user.id)

    # ----------------------------
    # Navigation callbacks
    # ----------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith(NAV_PREFIX))
    def nav_cb(call):
        action = call.data.split(":", 1)[1]
        chat_id = call.message.chat.id
        msg_id = call.message.message_id
        uid = call.from_user.id

        # 🧠 Training Grounds (in-place)
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

        # ⚔️ Arena (PvP) — IN-PLACE, CLEAN UX
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

        # 🧾 Profile
        if action == "profile":
            send_profile(bot, chat_id, uid)
            return

        # 🏆 Leaderboards
        if action == "leaderboards":
            show_leaderboard_ui(bot, chat_id, msg_id, uid)
            return

        # ❓ How to Play
        if action == "howtoplay":
            show_how_to_play(bot, chat_id)
            return

        # 🔙 Back to Awaken
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
    get_user(uid)

    db.update_user_xp(uid, {
        "has_awakened": 1,
        "location": "AWAKEN"
    })

    # World + personal status
    world_block = ""
    personal_block = ""

    try:
        world_block = get_world_status()
        personal_block = get_since_you_were_gone(uid)
    except Exception:
        pass  # UI helpers must never break awaken

    text = (
        world_block +
        personal_block +
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
        types.InlineKeyboardButton(
            "🧠 Training Grounds",
            callback_data=f"{NAV_PREFIX}training"
        ),
        types.InlineKeyboardButton(
            "⚔️ Enter Arena",
            callback_data=f"{NAV_PREFIX}arena"
        ),
    )

    # View Revenge shortcut (only if relevant)
    try:
        if has_unseen_pvp_attacks(uid):
            kb.add(
                types.InlineKeyboardButton(
                    "⚔️ View Revenge",
                    callback_data=f"{NAV_PREFIX}arena"
                )
            )
    except Exception:
        pass

    kb.add(
        types.InlineKeyboardButton(
            "🧾 My Profile",
            callback_data=f"{NAV_PREFIX}profile"
        ),
        types.InlineKeyboardButton(
            "🏆 Leaderboards",
            callback_data=f"{NAV_PREFIX}leaderboards"
        ),
    )
    kb.add(
        types.InlineKeyboardButton(
            "❓ How to Play",
            callback_data=f"{NAV_PREFIX}howtoplay"
        ),
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
        "display_name": (
            user.get("display_name")
            or user.get("username")
            or f"User{uid}"
        ),
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
        types.InlineKeyboardButton(
            "🔙 Back to Awaken",
            callback_data=f"{NAV_PREFIX}home"
        )
    )

    bot.send_message(
        chat_id,
        text,
        reply_markup=kb,
        parse_mode="HTML"
    )
