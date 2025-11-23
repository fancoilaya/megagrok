# main.py — launcher for TeleBot when main.py is in the project root.
# Loads legacy commands from bot/commands.py and modular handler files from bot/handlers/

import os
import sys
import importlib
import importlib.util
from telebot import TeleBot

# ============================
# Load Bot Token
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
    print("deleteWebhook call failed:", e)

bot = TeleBot(API_KEY)

print("🔧 Loading MegaGrok bot modules…")


# ============================
# Load legacy /bot/commands.py
# ============================
legacy_loaded = False
try:
    import bot.commands as legacy_commands
    if hasattr(legacy_commands, "register_handlers"):
        legacy_commands.register_handlers(bot)
        legacy_loaded = True
        print("✔ Loaded legacy bot/commands.py via import")
    else:
        print("⚠ bot/commands.py has no register_handlers(bot) function")
except Exception as e:
    print(f"⚠ Failed importing bot.commands: {e}. Attempting direct file load.")

# Fallback loading legacy commands by file path
if not legacy_loaded:
    legacy_path = os.path.join(ROOT_DIR, "bot", "commands.py")
    if os.path.exists(legacy_path):
        try:
            spec = importlib.util.spec_from_file_location("legacy_commands", legacy_path)
            legacy_commands = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(legacy_commands)
            if hasattr(legacy_commands, "register_handlers"):
                legacy_commands.register_handlers(bot)
                print(f"✔ Loaded legacy commands from file: {legacy_path}")
            else:
                print(f"⚠ Legacy commands file exists but no register_handlers(bot)")
        except Exception as e:
            print(f"❌ Failed executing legacy commands.py: {e}")
    else:
        print(f"⚠ No legacy commands.py found at {legacy_path}")


# ============================
# Load modular handlers in /bot/handlers/
# ============================
def load_handler_modules(bot):
    handlers_dir = os.path.join(ROOT_DIR, "bot", "handlers")

    if not os.path.isdir(handlers_dir):
        print(f"⚠ No handlers directory found at {handlers_dir}")
        return

    for filename in os.listdir(handlers_dir):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue

        module_name = f"bot.handlers.{filename[:-3]}"
        file_path = os.path.join(handlers_dir, filename)

        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "setup"):
                module.setup(bot)
                print(f"✔ Loaded handler module: {module_name}")
            else:
                print(f"⚠ {module_name} has no setup(bot) function")
        except Exception as e:
            print(f"⚠ Import failed for {module_name}: {e}. Trying file load…")

            # fallback: direct file execution
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "setup"):
                    mod.setup(bot)
                    print(f"✔ Loaded handler via file: {file_path}")
                else:
                    print(f"⚠ Loaded {file_path} but missing setup(bot)")
            except Exception as e2:
                print(f"❌ Failed loading handler {file_path}: {e2}")


# Load modular handlers (growmygrok, etc)
load_handler_modules(bot)

print("🚀 MegaGrok Bot ready — starting polling…")

# ============================
# Start Polling
# ============================
bot.polling(none_stop=True)
