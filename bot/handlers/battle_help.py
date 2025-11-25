# bot/handlers/battle_help.py
from telebot import TeleBot

def setup(bot: TeleBot):

    @bot.message_handler(commands=['battle_help'])
    def battle_help(message):
        help_text = (
            "⚔️ *MEGAGROK BATTLE HELP*\n\n"
            "🗡 *Attack*\n"
            "‣ Deal damage based on your Attack.\n"
            "‣ Randomized ±30%.\n"
            "‣ Can critically hit.\n"
            "‣ Enemy may dodge.\n\n"

            "🛡 *Block*\n"
            "‣ Reduce incoming damage to 40%.\n"
            "‣ No damage dealt.\n\n"

            "💨 *Dodge*\n"
            "‣ 25% chance to avoid all damage.\n"
            "‣ If failed, you take full damage.\n\n"

            "⚡ *Charge*\n"
            "‣ Store +50% Attack as bonus.\n"
            "‣ Applies to next Attack.\n"
            "‣ Stacks.\n\n"

            "▶️ *Auto Mode*\n"
            "‣ Smart AI chooses your moves.\n"
            "‣ Finishes enemies efficiently.\n"
            "‣ Blocks/dodges tactically.\n\n"

            "✖ *Surrender*\n"
            "‣ End the battle immediately.\n\n"

            "Use `/battle` to start a cinematic fight."
        )
        bot.reply_to(message, help_text, parse_mode="Markdown")
