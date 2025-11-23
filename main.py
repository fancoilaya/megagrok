# bot/main.py — Corrected for TeleBot + modular command loading

import os
import importlib
from telebot import TeleBot

# ============================
# Load Bot Token
# ============================
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("Missing API_KEY environment variable")

bot = TeleBot(API_KEY)

print("🔧 Loading MegaGrok command modules…")


# ============================
# Load legacy /bot/commands.py
# ============================
try:
    import bot.commands as legacy_commands

    if hasattr(legacy_commands, "register_handlers"):
        legacy_commands.register_handlers(bot)
        print("✔ Loaded legacy /bot/commands.py")
    else:
        print("⚠ /bot/commands.py found but no register_handlers(bot) function")

except Exception as e:
    print(f"❌ Unable to load /bot/commands.py: {e}")


# ============================
# Dynamic loader for modular /bot/commands/*.py
# ============================
def load_command_modules(bot):
    # path to folder /bot/commands/
    commands_dir = os.path.join(os.path.dirname(__file__), "commands")

    if not os.path.isdir(commands_dir):
        print("⚠ No commands/ directory found. Skipping modular loading.")
        return

    for filename in os.listdir(commands_dir):

        # load only .py modules (skip __init__.py)
        if not filename.endswith(".py") or filename.startswith("_"):
            continue

        # skip legacy commands.py if someone ever placed one in the folder
        if filename == "commands.py":
            continue

        module_name = f"bot.commands.{filename[:-3]}"

        try:
            module = importlib.import_module(module_name)

            if hasattr(module, "setup"):
                module.setup(bot)
                print(f"✔ Loaded module: {module_name}")
            else:
                print(f"⚠ Skipped {module_name} (no setup(bot) function)")

        except Exception as e:
            print(f"❌ Error loading {module_name}: {e}")


# Load modular commands (such as growmygrok.py)
load_command_modules(bot)

print("🚀 MegaGrok Bot is running via polling…")


# ============================
# Start Bot Polling
# ============================
bot.polling(none_stop=True)
