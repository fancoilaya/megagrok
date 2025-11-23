# main.py — launcher for TeleBot when main.py is in the project root.
# Works with commands in bot/ (legacy file at bot/commands.py and modular files in bot/commands/*.py)

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
    raise ValueError("Missing Telegram_token environment variable")

# Ensure repo root is on sys.path (should be, but be explicit)
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Safe delete webhook (idempotent)
try:
    import requests
    r = requests.get(f"https://api.telegram.org/bot{API_KEY}/deleteWebhook")
    print("deleteWebhook ->", r.status_code, r.text)
except Exception as e:
    print("deleteWebhook call failed:", e)

bot = TeleBot(API_KEY)

print("🔧 Loading MegaGrok command modules… (main at repo root)")

# ============================
# Load legacy /bot/commands.py
# ============================
legacy_module_loaded = False
try:
    # first try normal import (if 'bot' is a package)
    import bot.commands as legacy_commands
    if hasattr(legacy_commands, "register_handlers"):
        legacy_commands.register_handlers(bot)
        legacy_module_loaded = True
        print("✔ Loaded legacy module via import: bot.commands")
    else:
        print("⚠ bot.commands imported but no register_handlers(bot) found")
except Exception as e:
    print(f"⚠ import bot.commands failed: {e} — falling back to file-load")

if not legacy_module_loaded:
    # fallback: load the file bot/commands.py by path (safe when there's no package)
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
                print(f"⚠ Loaded legacy file but no register_handlers(bot) found: {legacy_path}")
        except Exception as e:
            print(f"❌ Failed to exec legacy commands file {legacy_path}: {e}")
    else:
        print(f"⚠ Legacy commands file not found at {legacy_path}")

# ============================
# Dynamic loader for modular /bot/commands/*.py
# ============================
def load_command_modules(bot):
    commands_dir = os.path.join(ROOT_DIR, "bot", "commands")

    if not os.path.isdir(commands_dir):
        print(f"⚠ No commands/ directory found at {commands_dir}. Skipping modular loading.")
        return

    for filename in os.listdir(commands_dir):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue

        # skip legacy commands.py so we don't attempt a duplicate
        if filename == "commands.py":
            continue

        module_name = f"bot.commands.{filename[:-3]}"
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "setup"):
                module.setup(bot)
                print(f"✔ Loaded module by import: {module_name}")
            else:
                print(f"⚠ Skipped {module_name} (no setup(bot) function)")
        except Exception as e:
            # fallback: try loading by file path
            filepath = os.path.join(commands_dir, filename)
            try:
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "setup"):
                    mod.setup(bot)
                    print(f"✔ Loaded module by file: {filepath}")
                else:
                    print(f"⚠ Loaded file {filepath} but no setup(bot) found")
            except Exception as e2:
                print(f"❌ Error loading {module_name} from {filepath}: {e2}")

# Load modular commands (such as growmygrok.py)
load_command_modules(bot)

print("🚀 MegaGrok Bot prepared — starting polling now...")

# ============================
# Start Bot Polling
# ============================
bot.polling(none_stop=True)
