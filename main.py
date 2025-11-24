# main.py — production-ready polling with graceful shutdown and robust retries

import os
import signal
import sys
import time
import requests
import threading
from telebot import TeleBot, apihelper

# ---------- Configuration ----------
TOKEN = os.getenv("Telegram_token")
if not TOKEN:
    raise RuntimeError("Telegram_token environment variable is missing!")

PRINT_HEARTBEAT = True

# ---------- TeleBot setup ----------
bot = TeleBot(TOKEN)

# simple heartbeat for Render logs (optional)
def heartbeat():
    while True:
        try:
            print(f"HEARTBEAT PID={os.getpid()} TIME={time.time()}")
        except Exception:
            pass
        time.sleep(60)

if PRINT_HEARTBEAT:
    t_hb = threading.Thread(target=heartbeat, daemon=True)
    t_hb.start()

print(f"BOOT PID={os.getpid()} - starting (token prefix: {TOKEN[:8]}...)")

# ---------- Safe webhook cleanup ----------
def safe_delete_webhook():
    try:
        r = requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook", timeout=10)
        print("deleteWebhook ->", r.status_code, r.text)
    except Exception as e:
        print("deleteWebhook failed:", e)

safe_delete_webhook()

# ---------- Graceful shutdown ----------
_shutdown_requested = False

def shutdown_handler(signum, frame):
    global _shutdown_requested
    print(f"Received signal {signum}; requesting shutdown (PID={os.getpid()})")
    _shutdown_requested = True
    try:
        # stop TeleBot polling cleanly
        bot.stop_polling()
        print("Called bot.stop_polling()")
    except Exception as e:
        print("Error calling stop_polling:", e)
    # ensure webhook is deleted to avoid conflicts for next boot
    safe_delete_webhook()
    # allow main thread to exit gracefully
    # do not call sys.exit inside signal handler (let main return)
    
signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

# ---------- Minimal command handlers for testing / extend as needed ----------
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Bot is alive! ✅")

# ---------- Polling loop with backoff and fatal 409 handling ----------
def run_polling():
    backoff = 1.0
    max_backoff = 60.0
    while not _shutdown_requested:
        try:
            print("Polling started (blocking call)...")
            # blocking call - returns when stop_polling() is called or exception occurs
            bot.polling(none_stop=True, timeout=20)
            # If polling returns normally (e.g. stop_polling called), break out
            print("Polling stopped cleanly.")
            break
        except apihelper.ApiTelegramException as ate:
            # TeleBot API exceptions with HTTP info available
            err_text = str(ate)
            print("ApiTelegramException:", err_text)
            # If 409 (duplicate poller) -> this is fatal; do not retry
            if "409" in err_text or "Conflict: terminated by other getUpdates request" in err_text:
                print("ERROR 409 detected (duplicate poller). Exiting to allow manual remediation.")
                # do not retry; exit process so you can rotate token or stop other instance
                # ensure webhook cleared before exit
                safe_delete_webhook()
                sys.exit(1)
            # otherwise, backoff and retry
            print(f"Non-fatal API error; sleeping {backoff}s and retrying...")
        except Exception as e:
            print("Polling error (exception):", repr(e))
            # fallback backoff on generic errors
            print(f"Sleeping {backoff}s before retry...")
        # If we get here, sleep/backoff before retry
        time.sleep(backoff)
        backoff = min(max_backoff, backoff * 2)

    print("Exiting polling loop; shutting down.")

if __name__ == "__main__":
    try:
        run_polling()
    except Exception as e:
        print("Fatal error in run_polling:", repr(e))
    finally:
        print("Final cleanup before exit.")
        safe_delete_webhook()
        # small delay to flush logs
        time.sleep(0.5)
