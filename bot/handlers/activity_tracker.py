# bot/handlers/activity_tracker.py
# Global activity tracker using middleware (NON-BLOCKING)

import time
from telebot import TeleBot
import bot.db as db


def setup(bot: TeleBot):

    # Track messages WITHOUT consuming them
    @bot.middleware_handler(update_types=["message"])
    def track_message_activity(bot_instance, message):
        try:
            if message.from_user:
                db.touch_last_active(message.from_user.id)
        except Exception:
            pass

    # Track callbacks WITHOUT consuming them
    @bot.middleware_handler(update_types=["callback_query"])
    def track_callback_activity(bot_instance, call):
        try:
            if call.from_user:
                db.touch_last_active(call.from_user.id)
        except Exception:
            pass
