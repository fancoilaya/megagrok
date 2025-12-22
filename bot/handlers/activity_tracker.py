# bot/handlers/activity_tracker.py
# Global user activity tracker (online detection backbone)

import time
from telebot import TeleBot
import bot.db as db

def setup(bot: TeleBot):

    @bot.message_handler(func=lambda m: True)
    def track_message_activity(message):
        try:
            db.touch_last_active(message.from_user.id)
        except Exception:
            pass

    @bot.callback_query_handler(func=lambda c: True)
    def track_callback_activity(call):
        try:
            db.touch_last_active(call.from_user.id)
        except Exception:
            pass
