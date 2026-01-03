from telebot import TeleBot, types
from services.permissions import is_megacrew
from services.audit_log import log_admin_action
from config import GROKPEDIA_CHANNEL_ID

# In-memory store (per admin)
LAST_ANNOUNCEMENT = {}


def setup(bot: TeleBot):

    @bot.message_handler(commands=["notifyall"])
    def preview(message):
        if not is_megacrew(message.from_user.id):
            bot.reply_to(message, "⛔ MegaCrew access required.")
            return

        text = message.text.replace("/notifyall", "").strip()
        if not text:
            bot.reply_to(message, "Usage:\n/notifyall Your message")
            return

        payload = f"📣 **MegaGrok Announcement**\n\n{text}"
        LAST_ANNOUNCEMENT[message.from_user.id] = payload

        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("✅ Publish", callback_data="announce_publish"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="announce_cancel"),
        )

        bot.send_message(
            message.chat.id,
            f"🧪 **Preview**\n\n{payload}",
            reply_markup=kb,
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("announce_"))
    def announce_action(call):
        if not is_megacrew(call.from_user.id):
            bot.answer_callback_query(call.id, "Access denied.")
            return

        payload = LAST_ANNOUNCEMENT.get(call.from_user.id)
        if not payload:
            bot.answer_callback_query(call.id, "Nothing to publish.")
            return

        if call.data == "announce_cancel":
            LAST_ANNOUNCEMENT.pop(call.from_user.id, None)
            bot.edit_message_text(
                "❌ Announcement cancelled.",
                call.message.chat.id,
                call.message.message_id
            )
            return

        # Publish to channel
        bot.send_message(
            GROKPEDIA_CHANNEL_ID,
            payload,
            parse_mode="Markdown"
        )

        log_admin_action(
            call.from_user.id,
            "publish_announcement",
            {"text": payload}
        )

        bot.edit_message_text(
            "✅ Announcement published to MegaGrok channel.",
            call.message.chat.id,
            call.message.message_id
        )

        bot.answer_callback_query(call.id)
