# bot/handlers/activity_tracker.py
# Global activity tracker (NON-BLOCKING, compatible with older TeleBot)

from telebot import TeleBot
from telebot.handler_backends import SkipHandler
import bot.db as db


def setup(bot: TeleBot):

    @bot.message_handler(func=lambda m: True)
    def track_message_activity(message):
        try:
            if message.from_user:
                db.touch_last_active(message.from_user.id)
        except Exception as e:
            print("[ACTIVITY ERROR]", e)

        # IMPORTANT: allow other handlers to run
        raise SkipHandler()

    @bot.callback_query_handler(func=lambda c: True)
    def track_callback_activity(call):
        try:
            if call.from_user:
                db.touch_last_active(call.from_user.id)
        except Exception as e:
            print("[ACTIVITY ERROR]", e)

        # IMPORTANT: allow other handlers to run
        raise SkipHandler()
