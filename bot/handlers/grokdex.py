# bot/handlers/grokdex.py
# Final fixed version — ALWAYS one message, no duplicate frames

import os
import urllib.parse
from telebot import types
from telebot import TeleBot

from bot.mobs import MOBS, TIERS
from bot.grokdex import get_grokdex_list, search_mob

TITLE = "📘 *MEGAGROK DEX — Choose a Creature Tier*"
MOB_IMAGE_FOLDER = "assets/mobs"

CB_PREFIX_TIER = "grokdex:tier:"
CB_PREFIX_MOB = "grokdex:mob:"
CB_PREFIX_BACK = "grokdex:back:"


# ---------------------------------------------------------
# DYNAMIC KEYBOARD GENERATOR
# ---------------------------------------------------------

def build_dynamic_keyboard(buttons, max_cols=3):
    kb = types.InlineKeyboardMarkup()
    for i in range(0, len(buttons), max_cols):
        kb.add(*buttons[i:i + max_cols])
    return kb


# ---------------------------------------------------------
# Tier list keyboard
# ---------------------------------------------------------

def _kb_tier_selection():
    btns = [
        types.InlineKeyboardButton(
            f"Tier {tier}",
            callback_data=f"{CB_PREFIX_TIER}{tier}"
        )
        for tier in sorted(TIERS.keys())
    ]
    return build_dynamic_keyboard(btns, max_cols=3)


# ---------------------------------------------------------
# Mob list keyboard
# ---------------------------------------------------------

def _kb_mobs_for_tier(tier):
    try:
        tier = int(tier)
    except:
        return types.InlineKeyboardMarkup()

    dex = get_grokdex_list()
    mobs = dex.get(tier, [])

    btns = []
    for mob in mobs:
        mob_key = None
        for k, v in MOBS.items():
            if v["name"].lower() == mob["name"].lower():
                mob_key = k
                break

        if not mob_key:
            continue

        safe_key = urllib.parse.quote_plus(mob_key)
        btns.append(
            types.InlineKeyboardButton(
                mob["name"],
                callback_data=f"{CB_PREFIX_MOB}{safe_key}"
            )
        )

    kb = build_dynamic_keyboard(btns, max_cols=3)
    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"{CB_PREFIX_BACK}main"))
    return kb


def _kb_back_from_mob(tier):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("⬅ Back to Tier", callback_data=f"{CB_PREFIX_TIER}{tier}"),
        types.InlineKeyboardButton("⬅ GrokDex", callback_data=f"{CB_PREFIX_BACK}main")
    )
    return kb


# ---------------------------------------------------------
# MAIN SETUP
# ---------------------------------------------------------

def setup(bot: TeleBot):

    # ENTRY: always use send_message, never reply_to
    @bot.message_handler(commands=["grokdex"])
    def grokdex_entry(message):
        bot.send_message(
            message.chat.id,
            TITLE,
            parse_mode="Markdown",
            reply_markup=_kb_tier_selection()
        )

    # ---------------------------------------------------------
    # CALLBACK ROUTING
    # ---------------------------------------------------------

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("grokdex:"))
    def grokdex_callback(call: types.CallbackQuery):

        data = call.data
        chat_id = call.message.chat.id
        msg_id = call.message.message_id

        # =====================================================
        # TIER SELECTED
        # =====================================================
        if data.startswith(CB_PREFIX_TIER):
            _, _, tier_str = data.split(":", 2)
            tier = int(tier_str)

            # Delete previous media message if any
            try:
                bot.delete_message(chat_id, msg_id)
            except:
                pass

            mobs = get_grokdex_list().get(tier, [])

            text = f"🟩 *Tier {tier} — {TIERS.get(tier, '?')}*\n\n"
            for mob in mobs:
                text += f"• *{mob['name']}*\n"
            text += "\nSelect a creature:"

            # Send a fresh editable message
            bot.send_message(
                chat_id,
                text,
                parse_mode="Markdown",
                reply_markup=_kb_mobs_for_tier(tier)
            )

            bot.answer_callback_query(call.id)
            return

        # =====================================================
        # MOB SELECTED
        # =====================================================
        if data.startswith(CB_PREFIX_MOB):
            _, _, encoded = data.split(":", 2)
            mob_key = urllib.parse.unquote_plus(encoded)

            mob = MOBS.get(mob_key) or search_mob(mob_key)
            if not mob:
                bot.answer_callback_query(call.id, "Not found.")
                return

            portrait = mob.get("portrait")
            tier = mob.get("tier", "?")

            caption = (
                f"📘 *{mob['name']}* (Tier {tier})\n"
                f"{mob['type']}\n"
                f"Rarity: {mob['rarity']}\n\n"
                "Tap image to view full."
            )

            # Delete previous text message (text → media)
            try:
                bot.delete_message(chat_id, msg_id)
            except:
                pass

            # Send media fresh (much safer than editing)
            try:
                with open(portrait, "rb") as f:
                    bot.send_photo(
                        chat_id,
                        f,
                        caption=caption,
                        parse_mode="Markdown",
                        reply_markup=_kb_back_from_mob(tier)
                    )
                bot.answer_callback_query(call.id)
                return
            except:
                pass

            # Final fallback
            bot.send_message(
                chat_id,
                caption,
                parse_mode="Markdown",
                reply_markup=_kb_back_from_mob(tier)
            )
            bot.answer_callback_query(call.id)
            return

        # =====================================================
        # BACK BUTTONS
        # =====================================================
        if data.startswith(CB_PREFIX_BACK):
            _, _, what = data.split(":", 2)

            # BACK TO MAIN
            if what == "main":
                try:
                    bot.delete_message(chat_id, msg_id)
                except:
                    pass

                bot.send_message(
                    chat_id,
                    TITLE,
                    parse_mode="Markdown",
                    reply_markup=_kb_tier_selection()
                )
                bot.answer_callback_query(call.id)
                return

            bot.answer_callback_query(call.id)
            return
