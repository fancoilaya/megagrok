# bot/handlers/activity_tracker.py
# FINAL SAFE VERSION — does not block commands or UI callbacks

from telebot import TeleBot
import bot.db as db

# IMPORTANT:
# - DO NOT intercept commands
# - DO NOT intercept navigation callbacks
# - ONLY track safe activity signals

NAV_PREFIX = "__nav__:"


def setup(bot: TeleBot):

    # -------------------------------------------------
    # Track NON-COMMAND text messages only
    # -------------------------------------------------
    @bot.message_handler(
        func=lambda m: bool(m.text) and not m.text.startswith("/")
    )
    def track_message_activity(message):
        try:
            if message.from_user:
                db.touch_last_active(message.from_user.id)
        except Exception as e:
            print("[ACTIVITY ERROR message]", e)

    # -------------------------------------------------
    # Track ONLY NON-NAV callbacks (safe signals)
    # -------------------------------------------------
    @bot.callback_query_handler(
        func=lambda c: not c.data.startswith(NAV_PREFIX)
    )
    def track_callback_activity(call):
        try:
            if call.from_user:
                db.touch_last_active(call.from_user.id)
        except Exception as e:
            print("[ACTIVITY ERROR callback]", e)
