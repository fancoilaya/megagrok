
# --- PRODUCTION main.py FOR RENDER BACKGROUND WORKER ---
import os
import signal
import sys
import requests
from telebot import TeleBot

# ✅ Load token from environment
TOKEN = os.getenv("Telegram_token")
if not TOKEN:
    raise RuntimeError("Telegram_token environment variable is missing!")

print("Bot starting with token:", TOKEN[:10], "...")

bot = TeleBot(TOKEN)

# ✅ Graceful shutdown handler
def shutdown_handler(signum, frame):
    print("Received shutdown signal. Cleaning up...")
    try:
        # Delete webhook to avoid conflicts
        requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
        print("Webhook deleted successfully.")
    except Exception as e:
        print(f"Error deleting webhook: {e}")
    sys.exit(0)

# Register SIGTERM and SIGINT handlers
signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

# ✅ Webhook cleanup before starting polling
try:
    requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
    print("Webhook cleared before polling.")
except Exception as e:
    print(f"Error clearing webhook: {e}")

# ✅ Bot command handlers
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Bot is alive! ✅")

print("Polling started...")

# ✅ Safe polling loop
while True:
    try:
        bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception as e:
        print(f"Polling error: {e}. Restarting in 5s...")
        import time
        time.sleep(5)
