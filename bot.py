# bot.py (root launcher)
import os
from telebot import TeleBot
from bot.commands import register_handlers

# Load API key
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise Exception("Missing API_KEY environment variable")

# Create bot instance
bot = TeleBot(API_KEY, parse_mode="Markdown")

# Register all command handlers
register_handlers(bot)

# Start bot
if __name__ == "__main__":
    print("✨ MegaGrok Bot is running...")
    bot.polling(none_stop=True, interval=0, timeout=60)
