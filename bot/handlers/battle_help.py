# bot/handlers/battle_help.py
from telebot import TeleBot

def setup(bot: TeleBot):

    @bot.message_handler(commands=['battle_help'])
    def battle_help(message):
        help_text = (
            "⚔️ *MEGAGROK BATTLE SYSTEM — COMPLETE GUIDE*\n\n"
            "Welcome to the upgraded combat engine! Each action has unique effects, "
            "synergies, and risks. Master them to defeat higher-tier mobs.\n\n"

            "=============================\n"
            "🗡 *ATTACK*\n"
            "=============================\n"
            "‣ Deals damage based on your Attack & enemy Defense.\n"
            "‣ Has a chance to *crit* for double damage.\n"
            "‣ Damage varies ±25%.\n"
            "‣ Enemy may attempt to dodge.\n"
            "‣ If you successfully dodged last turn → *Guaranteed Crit!*\n"
            "‣ Consumes any Charge stacks.\n\n"

            "=============================\n"
            "🛡 *BLOCK*\n"
            "=============================\n"
            "‣ Reduces incoming damage to ~35%.\n"
            "‣ Safe and reliable defense.\n"
            "‣ If you have Charge stacks while blocking → *Perfect Block* next turn.\n"
            "‣ *Perfect Block:* Negates all damage and reflects 15% back to the enemy.\n\n"

            "=============================\n"
            "💨 *DODGE*\n"
            "=============================\n"
            "‣ ~25% chance to avoid all incoming damage.\n"
            "‣ Successful Dodge triggers a *counterattack* (small damage).\n"
            "‣ Successful Dodge also gives a *Guaranteed Crit* on your next Attack.\n"
            "‣ Failed Dodge makes you take *20% extra damage*.\n\n"

            "=============================\n"
            "⚡ *CHARGE*\n"
            "=============================\n"
            "‣ Adds a Charge stack (max 3).\n"
            "‣ Each stack gives +50% of your Attack as bonus on your next Attack.\n"
            "‣ Using Attack consumes all stacks.\n"
            "‣ Using Block after Charging enables *Perfect Block*.\n\n"

            "=============================\n"
            "▶️ *AUTO MODE*\n"
            "=============================\n"
            "‣ Your bot plays automatically using an optimized AI.\n"
            "‣ Chooses smart actions based on HP %, mob HP, and Charge synergy.\n"
            "‣ Plays several turns per second using burst processing.\n"
            "‣ Great for grinding or high-tier mobs.\n\n"

            "=============================\n"
            "👹 *MOB TIERS (1–5)*\n"
            "=============================\n"
            "‣ *Tier 1 – Common:* Weak, predictable.\n"
            "‣ *Tier 2 – Uncommon:* More dodge/block behavior.\n"
            "‣ *Tier 3 – Rare:* Smarter patterns and mixed defense.\n"
            "‣ *Tier 4 – Epic:* Aggressive, higher crits & dodges.\n"
            "‣ *Tier 5 – Legendary:* Boss-level AI with strong reactions.\n\n"
            "Choose tier using `/battle` → select Tier.\n\n"

            "=============================\n"
            "✖ *SURRENDER*\n"
            "=============================\n"
            "‣ Immediately ends the battle.\n\n"

            "Use `/battle` to begin your fight!\n"
            "Master these mechanics to conquer Legendary Tier 5 mobs! ⚔️🔥"
        )
        bot.reply_to(message, help_text, parse_mode="Markdown")
