# main.py — debug version with handler loader disabled
# Loads only legacy bot/commands.py for isolation

import os
import sys
import importlib
import importlib.util
from telebot import TeleBot

# ============================
# Load Token
# ============================
API_KEY = os.getenv("Telegram_token")
if not API_KEY:
    raise ValueError("Missing Telegram_token environment variable!")

# Ensure repo root in sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Safe delete webhook
try:
    import requests
    r = requests.get(f"https://api.telegram.org/bot{API_KEY}/deleteWebhook")
    print("deleteWebhook ->", r.status_code, r.text)
except Exception as e:
    print("deleteWebhook failed:", e)

bot = TeleBot(API_KEY)

print("🔧 Booting MegaGrok (DEBUG MODE — handlers disabled)…")


# ============================
# Load legacy /bot/commands.py
# ============================
legacy_loaded = False
try:
    import bot.commands as legacy_commands
    if hasattr(legacy_commands, "register_handlers"):
        legacy_commands.register_handlers(bot)
        legacy_loaded = True
        print("✔ Loaded bot/commands.py via import")
    else:
        print("⚠ bot/commands.py has no register_handlers(bot)")
except Exception as e:
    print(f"⚠ Failed import bot.commands: {e} — trying direct file load")

if not legacy_loaded:
    legacy_path = os.path.join(ROOT_DIR, "bot", "commands.py")
    if os.path.exists(legacy_path):
        try:
            spec = importlib.util.spec_from_file_location("legacy_commands", legacy_path)
            legacy_commands = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(legacy_commands)
            if hasattr(legacy_commands, "register_handlers"):
                legacy_commands.register_handlers(bot)
                legacy_loaded = True
                print(f"✔ Loaded bot/commands.py via file")
            else:
                print("⚠ legacy commands have no register_handlers(bot)")
        except Exception as e:
            print(f"❌ Failed executing {legacy_path}: {e}")
    else:
        print("⚠ No commands.py found!")


# ============================
# DISABLED: Modular Handler Loader
# ============================
print("⚠ Handler loader DISABLED for debugging. Skipping bot/handlers/...")

# def load_handler_modules(bot):
#     pass
#
# load_handler_modules(bot)


# ============================
# Start Polling
# ============================
print("🚀 MegaGrok (DEBUG) ready — starting polling WITHOUT handlers…")
bot.polling(none_stop=True)
