# bot/main.py
import os
from telebot import TeleBot

# Import your command registration (this sets up ALL commands, images, xp logic, evolution, etc.)
from bot.commands import register_handlers

# ============================
# Load Bot Token
# ============================
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("Missing API_KEY environment variable")

bot = TeleBot(API_KEY)

# Register all handlers
register_handlers(bot)

print("🚀 MegaGrok Bot is running using polling…")

# Start bot
bot.polling(none_stop=True)
