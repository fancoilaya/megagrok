# bot/handlers/activity_tracker.py
# Global activity tracker — SAFE FOR COMMANDS

from telebot import TeleBot
import bot.db as db


def setup(bot: TeleBot):

    # -------------------------------------------------
    # Track ONLY NON-COMMAND messages
    # -------------------------------------------------
    @bot.message_handler(
        func=lambda m: bool(m.text) and not m.text.startswith("/")
    )
    def track_message_activity(message):
        try:
            if message.from_user:
                db.touch_last_active(message.from_user.id)
        except Exception as e:
            print("[ACTIVITY ERROR]", e)

    # -------------------------------------------------
    # Track ALL callback queries (buttons are safe)
    # -------------------------------------------------
    @bot.callback_query_handler(func=lambda c: True)
    def track_callback_activity(call):
        try:
            if call.from_user:
                db.touch_last_active(call.from_user.id)
        except Exception as e:
            print("[ACTIVITY ERROR]", e)
