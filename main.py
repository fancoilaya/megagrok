# bot/main.py — Updated for modular command loading (Telegram / TeleBot)
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
# Load legacy commands.py (if exists)
# ============================
try:
    from bot import commands as legacy_commands

    if hasattr(legacy_commands, "register_handlers"):
        legacy_commands.register_handlers(bot)
        print("✔ Loaded legacy commands.py")
    else:
        print("⚠ commands.py found but no register_handlers(bot) function")
except Exception as e:
    print(f"⚠ Unable to load legacy commands.py: {e}")


# ============================
# Dynamic loader for modular commands/
# ============================
def load_command_modules(bot):
    commands_dir = os.path.join(os.path.dirname(__file__), "commands")

    if not os.path.isdir(commands_dir):
        print("⚠ No commands/ directory found. Skipping modular loading.")
        return

    for filename in os.listdir(commands_dir):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue

        module_name = f"bot.commands.{filename[:-3]}"

        try:
            module = importlib.import_module(module_name)

            if hasattr(module, "setup"):
                module.setup(bot)
                print(f"✔ Loaded module: {module_name}")
            else:
                print(f"⚠ Skipped module (no setup(bot)): {module_name}")

        except Exception as e:
            print(f"❌ Error loading {module_name}: {e}")


# Load modular commands
load_command_modules(bot)

print("🚀 MegaGrok Bot is running via polling…")


# ============================
# Start Bot Polling
# ============================
bot.polling(none_stop=True)
