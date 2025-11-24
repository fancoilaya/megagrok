# --- MINIMAL main.py FOR DEBUGGING ---
# test comment
import os
from telebot import TeleBot

TOKEN = os.getenv("Telegram_token")
if not TOKEN:
    raise RuntimeError("Telegram_token environment variable is missing!")

print("Bot starting with token:", TOKEN[:10], "...")

bot = TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Bot is alive! ✅")

print("Polling started...")
bot.polling(none_stop=True)
