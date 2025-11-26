import os
import sys
import time
import json
import importlib
from pathlib import Path

from telebot import TeleBot
from telebot.types import Update

# ----------------------------------------
# Load environment settings
# ----------------------------------------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("[ERROR] BOT_TOKEN not set in environment variables.")
    sys.exit(1)

bot = TeleBot(TOKEN, parse_mode="HTML")

# ======================================================
# AUTO CLEANUP FOR CORRUPTED BATTLE SESSIONS
# ======================================================

SESS_FILE = "data/battle_sessions.json"

def cleanup_battle_sessions():
    """
    Removes corrupted or incomplete battle sessions leftover
    from previous crashes or restarts.
    This guarantees clean battle behavior every startup.
    """
    try:
        if not os.path.exists(SESS_FILE):
            print("[INIT] No old battle sessions found.")
            return

        with open(SESS_FILE, "r") as f:
            data = json.load(f)

        cleaned = {}
        removed = 0

        for uid, sess in data.items():
            # Must be a dict
            if not isinstance(sess, dict):
                removed += 1
                continue

            # Must have basic session properties
            if "player" not in sess or "mob" not in sess:
                removed += 1
                continue

            if "player_hp" not in sess or "mob_hp" not in sess:
                removed += 1
                continue

            # If it contains last message pointer, keep
            cleaned[uid] = sess

        # Rewrite file with cleaned data
        with open(SESS_FILE, "w") as f:
            json.dump(cleaned, f, indent=2)

        print(f"[INIT] Battle sessions cleaned. {len(cleaned)} valid sessions kept, {removed} removed.")

    except Exception as e:
        print(f"[INIT] Error during session cleanup: {e}")


# Run cleanup before loading bot handlers
cleanup_battle_sessions()


# ======================================================
# LEGACY COMMAND LOADER (commands.py)
# ======================================================

try:
    import bot.commands as legacy
    if hasattr(legacy, "register_handlers"):
        legacy.register_handlers(bot)
        print("[INIT] Loaded legacy commands handler.")
    else:
        print("[INIT] No register_handlers() found in bot.commands")
except Exception as e:
    print(f"[INIT] Failed loading bot.commands: {e}")


# ======================================================
# DYNAMIC HANDLER LOADER (bot/handlers/*.py)
# ======================================================

HANDLERS_PATH = Path("bot/handlers")

if HANDLERS_PATH.exists():
    for file in HANDLERS_PATH.iterdir():
        if file.suffix == ".py" and file.stem not in ["__init__", "commands"]:
            module_name = f"bot.handlers.{file.stem}"
            try:
                module = importlib.import_module(module_name)
                if hasattr(module, "setup"):
                    module.setup(bot)
                    print(f"[INIT] Loaded handler: {module_name}")
                else:
                    print(f"[INIT] Handler {module_name} has no setup() function.")
            except Exception as e:
                print(f"[INIT] Error loading handler {module_name}: {e}")
else:
    print("[INIT] WARNING: bot/handlers directory not found.")


# ======================================================
# WEBHOOK / POLLING (Use one method only)
# ======================================================

USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"

if USE_WEBHOOK:
    print("[INIT] Starting bot with webhook mode.")

    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not WEBHOOK_URL:
        print("[ERROR] USE_WEBHOOK=true but WEBHOOK_URL is missing.")
        sys.exit(1)

    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)

    from flask import Flask, request
    app = Flask(__name__)

    @app.route("/webhook", methods=["POST"])
    def webhook():
        json_str = request.data.decode("UTF-8")
        update = Update.de_json(json.loads(json_str))
        bot.process_new_updates([update])
        return "OK", 200

    if __name__ == "__main__":
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

else:
    print("[INIT] Starting bot with polling mode.")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
