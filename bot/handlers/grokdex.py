# bot/handlers/grokdex.py
# GrokDex & Mob Info handlers for MegaGrok Bot

import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.grokdex import get_grokdex_list, search_mob
from bot.mobs import TIERS

# Rarity emojis
RARITY_EMOJI = {
    "Common": "⚪",
    "Uncommon": "🟢",
    "Rare": "🔵",
    "Epic": "🟣",
    "Legendary": "🟡",
}

def setup(bot):

    # -----------------------
    # /grokdex
    # -----------------------
    @bot.message_handler(commands=["grokdex"])
    def grokdex_cmd(message):
        try:
            dex = get_grokdex_list()
            text = "📘 *MEGAGROK DEX — Villains of the Hop-Verse*\n\n"

            for tier in sorted(dex.keys()):
                mobs = dex[tier]
                text += f"*Tier {tier} — {TIERS.get(tier,'?')}*\n"
                for mob in mobs:
                    rarity = mob.get("rarity", "Common")
                    emo = RARITY_EMOJI.get(rarity, "⚪")
                    text += f"{emo} *{mob['name']}* — _{rarity}_\n"
                text += "\n"

            text += "Use `/mob <name>` to inspect any creature."
            bot.reply_to(message, text, parse_mode="Markdown")

        except Exception as e:
            bot.reply_to(message, f"Error loading GrokDex: {e}")

    # -----------------------
    # /mob <name>
    # -----------------------
    @bot.message_handler(commands=["mob"])
    def mob_info(message):
        try:
            parts = message.text.split(" ", 1)
            if len(parts) < 2 or not parts[1].strip():
                bot.reply_to(message, "Usage: `/mob FUDling`", parse_mode="Markdown")
                return

            query = parts[1].strip()
            mob = search_mob(query)

            if not mob:
                bot.reply_to(message, "❌ Creature not found in the GrokDex.", parse_mode="Markdown")
                return

            rarity = mob.get("rarity", "Common")
            tier = mob.get("tier", 1)
            emo = RARITY_EMOJI.get(rarity, "⚪")

            # Build info card
            txt = (
                f"📘 *{mob['name']}*\n"
                f"{emo} *{rarity}* — Tier {tier} ({TIERS.get(tier,'?')})\n"
                f"🎭 *Type:* {mob.get('type','?')}\n\n"

                f"📝 *Description*\n"
                f"{mob.get('description','No description.')}\n\n"

                f"💥 *Combat Stats*\n"
                f"• HP: {mob.get('hp','?')}\n"
                f"• Attack: {mob.get('attack','?')}\n"
                f"• Defense: {mob.get('defense','?')}\n"
                f"• Crit Chance: {int(mob.get('crit_chance',0)*100)}%\n"
                f"• Dodge Chance: {int(mob.get('dodge_chance',0)*100)}%\n\n"

                f"🪙 *XP Reward*\n"
                f"{mob.get('min_xp','?')} – {mob.get('max_xp','?')} XP\n\n"

                f"⚖ *Strength:* {mob.get('strength','?')}\n"
                f"⚠ *Weakness:* {mob.get('weakness','?')}\n\n"

                f"🎁 *Drops:*\n"
                f"{', '.join(mob.get('drops', []))}\n"
            )

            portrait = mob.get("portrait")

            # Try to send portrait
            if portrait and os.path.exists(portrait):
                try:
                    with open(portrait, "rb") as f:
                        bot.send_photo(
                            message.chat.id,
                            f,
                            caption=txt,
                            parse_mode="Markdown"
                        )
                    return
                except:
                    pass  # fallback to text only

            bot.reply_to(message, txt, parse_mode="Markdown")

        except Exception as e:
            bot.reply_to(message, f"Error fetching mob info: {e}")
