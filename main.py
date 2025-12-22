# main.py — Full production Telegram bot for Render Background Worker
# Includes:
# - graceful shutdown
# - heartbeat
# - webhook cleanup
# - 409 duplicate poller protection
# - legacy commands loader
# - modular handlers loader
# - safe fallback loaders
# - stable polling loop for worker mode
# - automatic cleanup of battle_sessions.json
# - GROKPEDIA 3-hour auto-poster (NEW)

import os
import sys
import time
import threading
import signal
import importlib
import importlib.util
import requests
import json
from pathlib import Path

from telebot import TeleBot, apihelper


# ==============================================
# Load API Token (supports multiple env names)
# ==============================================
TOKEN = (
    os.getenv("Telegram_token") or
    os.getenv("TELEGRAM_TOKEN") or
    os.getenv("BOT_TOKEN") or
    os.getenv("TOKEN")
)

if not TOKEN:
    raise RuntimeError("Missing environment variable: Telegram_token / BOT_TOKEN / TELEGRAM_TOKEN")

print(f"BOOT: PID={os.getpid()} TOKEN_PREFIX={TOKEN[:8]}…")

bot = TeleBot(TOKEN)


# ==============================================
# Heartbeat (helps Render logs)
# ==============================================
def heartbeat():
    while True:
        print(f"💓 HEARTBEAT PID={os.getpid()} TIME={time.time()}")
        time.sleep(60)

threading.Thread(target=heartbeat, daemon=True).start()


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


# ======================================================
# Automatic Cleanup of Corrupted Battle Sessions
# ======================================================
SESS_FILE = os.path.join(ROOT_DIR, "data", "battle_sessions.json")

def cleanup_battle_sessions():
    try:
        sess_path = Path(SESS_FILE)
        if not sess_path.exists():
            print("[INIT] No battle_sessions.json found — OK.")
            return

        with open(sess_path, "r") as f:
            data = json.load(f)

        cleaned = {}
        removed = 0

        for uid, sess in data.items():
            if not isinstance(sess, dict):
                removed += 1
                continue

            # Required keys for a valid session
            if (
                "player" not in sess or
                "mob" not in sess or
                "player_hp" not in sess or
                "mob_hp" not in sess
            ):
                removed += 1
                continue

            cleaned[uid] = sess

        with open(sess_path, "w") as f:
            json.dump(cleaned, f, indent=2)

        print(f"[INIT] battle_sessions.json cleaned → {len(cleaned)} kept, {removed} removed.")

    except Exception as e:
        print(f"[INIT] Error cleaning battle_sessions.json: {e}")

cleanup_battle_sessions()


# ==============================================
# Webhook cleanup
# ==============================================
def safe_delete_webhook():
    try:
        r = requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook", timeout=10)
        print("deleteWebhook ->", r.status_code, r.text)
    except Exception as e:
        print("⚠ Could not delete webhook:", e)

safe_delete_webhook()


# ==============================================
# Graceful Shutdown
# ==============================================
_shutdown = False

def shutdown_handler(signum, frame):
    global _shutdown
    print(f"🔻 Received shutdown signal ({signum}), stopping bot…")
    _shutdown = True

    try:
        bot.stop_polling()
        print("stop_polling() called")
    except Exception as e:
        print("⚠ stop_polling error:", e)

    safe_delete_webhook()
    print("Shutdown complete.")
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


# ==============================================
# Load Legacy Commands
# ==============================================
def load_legacy_commands():
    loaded = False

    try:
        import bot.commands as legacy
        if hasattr(legacy, "register_handlers"):
            legacy.register_handlers(bot)
            loaded = True
            print("✔ Loaded bot/commands.py")
        else:
            print("⚠ bot/commands.py exists but has no register_handlers(bot)")
    except Exception as e:
        print("⚠ Import bot.commands failed:", e)

    if not loaded:
        legacy_path = os.path.join(ROOT_DIR, "bot", "commands.py")
        if os.path.exists(legacy_path):
            try:
                spec = importlib.util.spec_from_file_location("legacy_commands", legacy_path)
                legacy = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(legacy)

                if hasattr(legacy, "register_handlers"):
                    legacy.register_handlers(bot)
                    print("✔ Loaded legacy commands via file load")
                else:
                    print("⚠ No register_handlers(bot) in commands.py")
            except Exception as e:
                print("❌ Failed executing commands.py:", e)
        else:
            print("⚠ No commands.py found")

load_legacy_commands()


# ==============================================
# Load Modular Handlers
# ==============================================
def load_modular_handlers():
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
                print(f"✔ Loaded handler: {module_name}")
            else:
                print(f"⚠ No setup(bot) in {module_name}")
        except Exception as e:
            print(f"⚠ Import failed for {module_name}: {e}")
            print("Trying file-based load…")

            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

                if hasattr(mod, "setup"):
                    mod.setup(bot)
                    print(f"✔ Loaded handler file: {file_path}")
                else:
                    print(f"⚠ No setup(bot) in handler file {filename}")
            except Exception as e2:
                print(f"❌ Failed loading handler: {file_path}: {e2}")

load_modular_handlers()


# ==============================================
# ⏰ GROKPEDIA: Start 3-hour Auto-Poster (NEW)
# ==============================================
try:
    from services import scheduler
    scheduler.start_grokpedia_autopost(bot)
    print("✔ Grokpedia scheduler initialized.")
except Exception as e:
    print("⚠ Failed to start Grokpedia scheduler:", e)


# ==============================================
# Polling Loop with Duplicate Poller Protection
# ==============================================
def run_polling():
    backoff = 2
    max_backoff = 60

    while not _shutdown:
        try:
            print("▶ Starting polling…")
            bot.polling(none_stop=True, timeout=20)
            print("⏹ Polling stopped cleanly.")
            break
        except apihelper.ApiTelegramException as ate:
            err = str(ate)
            print("🔥 TELEGRAM API ERROR:", err)

            if "409" in err or "Conflict: terminated by other getUpdates request" in err:
                print("❌ DUPLICATE POLLER DETECTED (409)")
                safe_delete_webhook()
                sys.exit(1)

            print(f"⚠ API error → retrying in {backoff}s")
        except Exception as e:
            print("⚠ Polling exception:", repr(e))
            print(f"Retrying in {backoff}s")

        time.sleep(backoff)
        backoff = min(max_backoff, backoff * 2)


if __name__ == "__main__":
    run_polling()
