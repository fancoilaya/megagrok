# bot/handlers/announce.py
# Admin Announcement Handler (Markdown + HTML Support)
# Posts ONLY to LEADERBOARD_CHANNEL_ID

import os
import traceback
from telebot import TeleBot

def setup(bot: TeleBot):

    ADMIN_ID = int(os.getenv("MEGAGROK_ADMIN_ID", "0"))
    CHANNEL_ID = os.getenv("LEADERBOARD_CHANNEL_ID")

    if not CHANNEL_ID:
        print("WARNING: LEADERBOARD_CHANNEL_ID is missing. Announcements disabled.")
        CHANNEL_ID = None

    # ---------------- MARKDOWN ANNOUNCEMENT ----------------
    @bot.message_handler(commands=["announce"])
    def announce_markdown(message):
        if message.from_user.id != ADMIN_ID:
            return bot.reply_to(message, "❌ Not authorized.")

        if not CHANNEL_ID:
            return bot.reply_to(message, "❌ LEADERBOARD_CHANNEL_ID not set.")

        parts = message.text.split(" ", 1)
        if len(parts) < 2:
            return bot.reply_to(message, "Usage:\n/announce <message>")

        content = parts[1].strip()

        try:
            sent = bot.send_message(
                int(CHANNEL_ID),
                f"📢 *Announcement*\n\n{content}",
                parse_mode="Markdown"
            )

            try:
                bot.pin_chat_message(
                    chat_id=int(CHANNEL_ID),
                    message_id=sent.message_id,
                    disable_notification=True
                )
            except Exception as e:
                bot.reply_to(message, f"⚠️ Unable to pin message:\n{e}")

            bot.reply_to(message, "✅ Announcement posted.")

        except Exception:
            bot.reply_to(
                message,
                f"❌ Failed:\n```\n{traceback.format_exc()}\n```",
                parse_mode="Markdown"
            )

    # ---------------- HTML ANNOUNCEMENT ----------------
    @bot.message_handler(commands=["announce_html"])
    def announce_html(message):
        if message.from_user.id != ADMIN_ID:
            return bot.reply_to(message, "❌ Not authorized.")

        if not CHANNEL_ID:
            return bot.reply_to(message, "❌ LEADERBOARD_CHANNEL_ID not set.")

        parts = message.text.split(" ", 1)
        if len(parts) < 2:
            return bot.reply_to(message, "Usage:\n/announce_html <html message>")

        html_content = parts[1].strip()

        try:
            sent = bot.send_message(
                int(CHANNEL_ID),
                f"<b>📢 Announcement</b><br><br>{html_content}",
                parse_mode="HTML"
            )

            try:
                bot.pin_chat_message(
                    chat_id=int(CHANNEL_ID),
                    message_id=sent.message_id,
                    disable_notification=True
                )
            except Exception as e:
                bot.reply_to(message, f"⚠️ Unable to pin message:\n{e}")

            bot.reply_to(message, "✅ HTML announcement posted.")

        except Exception:
            bot.reply_to(
                message,
                f"❌ HTML Announcement failed:\n```\n{traceback.format_exc()}\n```",
                parse_mode="Markdown"
            )
