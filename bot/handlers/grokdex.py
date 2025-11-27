# bot/handlers/grokdex.py
# Handler: interactive GrokDex UI (tier -> list -> poster)
# Drop this file into /bot/handlers and it will be auto-loaded by main.py

import os
import urllib.parse
from telebot import types
from telebot import TeleBot

from bot.mobs import MOBS, TIERS
from bot.grokdex import get_grokdex_list, search_mob

# Constants
TITLE = "📘 *MEGAGROK DEX — Choose a Creature Tier*"
MOB_IMAGE_FOLDER = "assets/mobs"  # adjust if you store posters elsewhere
# Callback prefixes
CB_PREFIX_TIER = "grokdex:tier:"
CB_PREFIX_MOB = "grokdex:mob:"
CB_PREFIX_BACK = "grokdex:back:"

# helper: build tier keyboard
def _kb_tier_selection():
    kb = types.InlineKeyboardMarkup(row_width=2)
    # show tiers as buttons (1..5)
    rows = []
    for tier in sorted(TIERS.keys()):
        label = f"Tier {tier}"
        cb = f"{CB_PREFIX_TIER}{tier}"
        kb.add(types.InlineKeyboardButton(label, callback_data=cb))
    return kb

# helper: build keyboard listing mobs in a tier (and add Back)
def _kb_mobs_for_tier(tier):
    kb = types.InlineKeyboardMarkup(row_width=1)
    # ensure tier is int
    try:
        tier = int(tier)
    except Exception:
        return kb

    # gather mobs
    dex = get_grokdex_list()
    mobs = dex.get(tier, [])
    for mob in mobs:
        # use canonical key from MOBS by searching name -> key
        # find the key whose mob['name'] matches (case-insensitive)
        mob_key = None
        for k, v in MOBS.items():
            if v.get("name", "").lower() == mob.get("name", "").lower() or k.lower() == mob.get("name", "").lower():
                mob_key = k
                break
        if not mob_key:
            continue
        safe_key = urllib.parse.quote_plus(mob_key)
        kb.add(types.InlineKeyboardButton(mob['name'], callback_data=f"{CB_PREFIX_MOB}{safe_key}"))

    # Back button to main tiers
    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data=f"{CB_PREFIX_BACK}main"))
    return kb

# helper: keyboard under a mob poster (Back to tier / Back to GrokDex)
def _kb_back_from_mob(tier):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("⬅ Back to Tier", callback_data=f"{CB_PREFIX_TIER}{tier}"),
        types.InlineKeyboardButton("⬅ GrokDex", callback_data=f"{CB_PREFIX_BACK}main")
    )
    return kb

def setup(bot: TeleBot):

    # /grokdex entrypoint
    @bot.message_handler(commands=["grokdex"])
    def grokdex_entry(message):
        try:
            bot.reply_to(message, TITLE, parse_mode="Markdown", reply_markup=_kb_tier_selection())
        except Exception as e:
            bot.reply_to(message, f"Error opening GrokDex: {e}")

    # callback for tier buttons and back
    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("grokdex:"))
    def grokdex_callback(call: types.CallbackQuery):
        data = call.data

        # Tier selected
        if data.startswith(CB_PREFIX_TIER):
            # data looks like grokdex:tier:1
            try:
                _, _, tier_str = data.split(":", 2)
                tier = int(tier_str)
            except Exception:
                bot.answer_callback_query(call.id, "Invalid tier.")
                return

            # Build text listing mobs in the tier
            dex = get_grokdex_list()
            mobs = dex.get(tier, [])
            if not mobs:
                text = f"Tier {tier} — {TIERS.get(tier,'?')}\n\nNo creatures found."
            else:
                text = f"🟩 *Tier {tier} — {TIERS.get(tier,'?')}*\n\n"
                for mob in mobs:
                    text += f"• *{mob.get('name','?')}*\n"
                text += "\nSelect a creature below."

            # Edit the original message (safer UX)
            try:
                call.message.edit_text(text, parse_mode="Markdown", reply_markup=_kb_mobs_for_tier(tier))
                bot.answer_callback_query(call.id)
            except Exception:
                # If edit fails (e.g., message was a photo), send a new message instead
                bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=_kb_mobs_for_tier(tier))
                bot.answer_callback_query(call.id)

            return

        # Mob selected
        if data.startswith(CB_PREFIX_MOB):
            # data looks like grokdex:mob:<encoded_key>
            try:
                _, _, encoded = data.split(":", 2)
                mob_key = urllib.parse.unquote_plus(encoded)
            except Exception:
                bot.answer_callback_query(call.id, "Invalid mob.")
                return

            mob = MOBS.get(mob_key)
            if not mob:
                # try a case-insensitive search fallback
                from bot.grokdex import search_mob as _search
                mob = _search(mob_key)
                if mob:
                    # find canonical key
                    for k, v in MOBS.items():
                        if v is mob:
                            mob_key = k
                            break

            if not mob:
                bot.answer_callback_query(call.id, "Creature not found.")
                return

            # send the poster image if exists, otherwise send text
            caption = f"📘 *{mob.get('name','?')}* (Tier {mob.get('tier','?')})\n{mob.get('type','')}\nRarity: {mob.get('rarity','?')}\n\nTap image to view in full."
            portrait = mob.get("portrait") or os.path.join(MOB_IMAGE_FOLDER, f"{mob_key}.png")

            try:
                if portrait and os.path.exists(portrait):
                    with open(portrait, "rb") as f:
                        # send poster as a new message with back buttons
                        sent = bot.send_photo(call.message.chat.id, f, caption=caption, parse_mode="Markdown", reply_markup=_kb_back_from_mob(mob.get("tier", 1)))
                        bot.answer_callback_query(call.id)
                        return
            except Exception:
                # fall through to send text
                pass

            # fallback: send text info and back buttons
            try:
                bot.send_message(call.message.chat.id, caption, parse_mode="Markdown", reply_markup=_kb_back_from_mob(mob.get("tier", 1)))
                bot.answer_callback_query(call.id)
            except Exception as e:
                bot.answer_callback_query(call.id, f"Error showing creature: {e}", show_alert=True)

            return

        # Back actions (main)
        if data.startswith(CB_PREFIX_BACK):
            try:
                _, _, what = data.split(":", 2)
            except Exception:
                what = "main"

            if what == "main":
                # edit original or reply with main menu
                try:
                    call.message.edit_text(TITLE, parse_mode="Markdown", reply_markup=_kb_tier_selection())
                    bot.answer_callback_query(call.id)
                except Exception:
                    bot.send_message(call.message.chat.id, TITLE, parse_mode="Markdown", reply_markup=_kb_tier_selection())
                    bot.answer_callback_query(call.id)
                return

            # Unknown back action
            bot.answer_callback_query(call.id, "Back action unknown.")
            return
