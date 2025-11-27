# bot/handlers/grokdex.py
# Interactive GrokDex UI (single-message window)
# Tier → Mob List → Poster → Back (all inside same message)

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


# ================
# KEYBOARD BUILDERS
# ================

def _kb_tier_selection():
    kb = types.InlineKeyboardMarkup(row_width=2)
    for tier in sorted(TIERS.keys()):
        kb.add(types.InlineKeyboardButton(f"Tier {tier}", callback_data=f"{CB_PREFIX_TIER}{tier}"))
    return kb


def _kb_mobs_for_tier(tier):
    kb = types.InlineKeyboardMarkup(row_width=1)

    try:
        tier = int(tier)
    except:
        return kb

    dex = get_grokdex_list()
    mobs = dex.get(tier, [])

    for mob in mobs:
        mob_key = None
        for k, v in MOBS.items():
            if v.get("name", "").lower() == mob.get("name", "").lower():
                mob_key = k
                break
        if not mob_key:
            continue

        safe_key = urllib.parse.quote_plus(mob_key)
        kb.add(types.InlineKeyboardButton(mob["name"], callback_data=f"{CB_PREFIX_MOB}{safe_key}"))

    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"{CB_PREFIX_BACK}main"))
    return kb


def _kb_back_from_mob(tier):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("⬅ Back to Tier", callback_data=f"{CB_PREFIX_TIER}{tier}"),
        types.InlineKeyboardButton("⬅ GrokDex", callback_data=f"{CB_PREFIX_BACK}main")
    )
    return kb


# =================
# MAIN SETUP
# =================
def setup(bot: TeleBot):

    # /grokdex entry point
    @bot.message_handler(commands=["grokdex"])
    def grokdex_entry(message):
        bot.reply_to(
            message,
            TITLE,
            parse_mode="Markdown",
            reply_markup=_kb_tier_selection()
        )

    # Callback handler
    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("grokdex:"))
    def grokdex_callback(call: types.CallbackQuery):
        data = call.data

        # ============
        # SELECT TIER
        # ============
        if data.startswith(CB_PREFIX_TIER):
            try:
                _, _, tier_str = data.split(":", 2)
                tier = int(tier_str)
            except:
                bot.answer_callback_query(call.id, "Invalid tier.")
                return

            dex = get_grokdex_list()
            mobs = dex.get(tier, [])

            text = f"🟩 *Tier {tier} — {TIERS.get(tier, '?')}*\n\n"
            for mob in mobs:
                text += f"• *{mob.get('name', '?')}*\n"
            text += "\nSelect a creature:"

            # Replace message with tier list
            try:
                call.message.edit_text(
                    text,
                    parse_mode="Markdown",
                    reply_markup=_kb_mobs_for_tier(tier)
                )
            except:
                bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=_kb_mobs_for_tier(tier))

            bot.answer_callback_query(call.id)
            return

        # ============
        # SELECT MOB
        # ============
        if data.startswith(CB_PREFIX_MOB):
            try:
                _, _, encoded = data.split(":", 2)
                mob_key = urllib.parse.unquote_plus(encoded)
            except:
                bot.answer_callback_query(call.id, "Invalid mob.")
                return

            mob = MOBS.get(mob_key) or search_mob(mob_key)
            if not mob:
                bot.answer_callback_query(call.id, "Creature not found.")
                return

            portrait = mob.get("portrait") or os.path.join(MOB_IMAGE_FOLDER, f"{mob_key}.png")

            caption = (
                f"📘 *{mob.get('name','?')}* (Tier {mob.get('tier','?')})\n"
                f"{mob.get('type','')}\n"
                f"Rarity: {mob.get('rarity','?')}\n\n"
                "Tap image to view full."
            )

            # Try to replace the current message with the poster
            try:
                from telebot.types import InputMediaPhoto
                with open(portrait, "rb") as f:
                    media = InputMediaPhoto(f, caption=caption, parse_mode="Markdown")

                    # Replace message media
                    bot.edit_message_media(
                        media=media,
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id
                    )

                # Replace caption + keyboard
                bot.edit_message_caption(
                    caption=caption,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="Markdown",
                    reply_markup=_kb_back_from_mob(mob.get("tier", 1))
                )

                bot.answer_callback_query(call.id)
                return

            except Exception as e:
                # Fallback: send it as a new message
                try:
                    with open(portrait, "rb") as f:
                        bot.send_photo(
                            call.message.chat.id,
                            f,
                            caption=caption,
                            parse_mode="Markdown",
                            reply_markup=_kb_back_from_mob(mob.get("tier", 1))
                        )
                    bot.answer_callback_query(call.id)
                    return
                except:
                    pass

            # Final fallback: text
            bot.send_message(
                call.message.chat.id,
                caption,
                parse_mode="Markdown",
                reply_markup=_kb_back_from_mob(mob.get("tier", 1))
            )
            bot.answer_callback_query(call.id)
            return

        # ============
        # BACK BUTTONS
        # ============
        if data.startswith(CB_PREFIX_BACK):
            try:
                _, _, what = data.split(":", 2)
            except:
                what = "main"

            if what == "main":
                try:
                    call.message.edit_text(
                        TITLE,
                        parse_mode="Markdown",
                        reply_markup=_kb_tier_selection()
                    )
                except:
                    bot.send_message(call.message.chat.id, TITLE, parse_mode="Markdown", reply_markup=_kb_tier_selection())

                bot.answer_callback_query(call.id)
                return

            bot.answer_callback_query(call.id, "Unknown back action.")
            return
