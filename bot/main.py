import os
import telebot
from bot.commands import register_handlers

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY environment variable not set")

bot = telebot.TeleBot(API_KEY)

register_handlers(bot)

if __name__ == "__main__":
    print("Starting MegaGrok bot (polling)...")
    bot.polling(none_stop=True)
