# bot/handlers/activity_tracker.py
# Global activity tracker (middleware-based, non-blocking)
# DIAGNOSTIC VERSION — prints when middleware fires

from telebot import TeleBot
import time
import bot.db as db


def setup(bot: TeleBot):

    # -------------------------------------------------
    # Track ALL incoming messages (non-blocking)
    # -------------------------------------------------
    @bot.middleware_handler(update_types=["message"])
    def track_message_activity(bot_instance, message):
        try:
            if message and message.from_user:
                uid = message.from_user.id
                print("[ACTIVITY] message from", uid)
                db.touch_last_active(uid)
        except Exception as e:
            print("[ACTIVITY ERROR] message:", e)

    # -------------------------------------------------
    # Track ALL callback queries (non-blocking)
    # -------------------------------------------------
    @bot.middleware_handler(update_types=["callback_query"])
    def track_callback_activity(bot_instance, call):
        try:
            if call and call.from_user:
                uid = call.from_user.id
                print("[ACTIVITY] callback from", uid)
                db.touch_last_active(uid)
        except Exception as e:
            print("[ACTIVITY ERROR] callback:", e)
