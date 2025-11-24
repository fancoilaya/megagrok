# main.py — Production polling bot for Render Web Service
# Clean, stable, with graceful shutdown and duplicate-polling protection

import os
import signal
import sys
import time
import threading
import requests
from telebot import TeleBot, apihelper

# ==========================================
# Load Bot Token
# ==========================================
TOKEN = os.getenv("Telegram_token")
if not TOKEN:
    raise RuntimeError("❌ Missing environment variable: Telegram_token")

print(f"BOOT: PID={os.getpid()} TOKEN_PREFIX={TOKEN[:8]}...")

bot = TeleBot(TOKEN)

# ==========================================
# Heartbeat (helps debug duplicate processes)
# ==========================================
def heartbeat():
    while True:
        print(f"💓 HEARTBEAT PID={os.getpid()} TIME={time.time()}")
        time.sleep(60)

threading.Thread(target=heartbeat, daemon=True).start()

# ==========================================
# Delete webhook at startup (idempotent)
# ==========================================
def safe_delete_webhook():
    try:
        r = requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook", timeout=10)
        print("deleteWebhook ->", r.status_code, r.text)
    except Exception as e:
        print("⚠ Could not delete webhook:", e)

safe_delete_webhook()

# ==========================================
# Graceful shutdown on SIGTERM/SIGINT
# ==========================================
_shutdown = False

def shutdown_handler(signum, frame):
    global _shutdown
    print(f"🔻 Received shutdown signal ({signum}), stopping bot...")
    _shutdown = True
    try:
        bot.stop_polling()
    except Exception as e:
        print("⚠ stop_polling error:", e)
    safe_delete_webhook()
    print("Shutdown complete.")
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

# ==========================================
# Basic test command
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Bot is alive and kicking! ⚡️")

# TODO: Re-enable your full command loading later:
# - bot/commands.py (legacy)
# - bot/handlers/ (modular)

# ==========================================
# Polling Loop (with 409 protection)
# ==========================================
def run_polling():
    backoff = 2  # retry delay on non-fatal errors

    while not _shutdown:
        try:
            print("▶ Starting polling…")
            bot.polling(none_stop=True, timeout=20)
            print("⏹ Polling stopped cleanly.")
            break  # Stop loop if stop_polling() triggered
        except apihelper.ApiTelegramException as ate:
            err = str(ate)
            print("🔥 TELEGRAM API ERROR:", err)

            # 409 means another poller exists — DO NOT try to continue
            if "409" in err or "Conflict: terminated by other getUpdates request" in err:
                print("❌ FATAL: Duplicate polling detected (409). Exiting.")
                safe_delete_webhook()
                sys.exit(1)

            print(f"⚠ Non-fatal API error, retrying in {backoff}s…")
        except Exception as e:
            print("⚠ Polling error:", repr(e))
            print(f"Retrying in {backoff}s…")

        time.sleep(backoff)
        backoff = min(60, backoff * 2)

if __name__ == "__main__":
    run_polling()
