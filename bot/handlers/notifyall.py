import os
from telebot import TeleBot, types
from services.permissions import is_megacrew, is_admin
from services.audit_log import log_admin_action

_CHANNEL_RAW = os.getenv("GROKPEDIA_CHANNEL_ID")

GROKPEDIA_CHANNEL_ID = None
if _CHANNEL_RAW:
    try:
        GROKPEDIA_CHANNEL_ID = int(_CHANNEL_RAW)
    except ValueError:
        GROKPEDIA_CHANNEL_ID = None


# Per-user drafts
DRAFTS = {}


def setup(bot: TeleBot):

    @bot.message_handler(commands=["notifyall"])
    def preview(message):
        uid = message.from_user.id

        if not (is_admin(uid) or is_megacrew(uid)):
            bot.reply_to(message, "⛔ MegaCrew access required.")
            return

        if GROKPEDIA_CHANNEL_ID is None:
            bot.reply_to(
                message,
                "❌ GROKPEDIA_CHANNEL_ID is not configured."
            )
            return

        text = message.text.replace("/notifyall", "").strip()
        if not text:
            bot.reply_to(message, "Usage:\n/notifyall Your message")
            return

        payload = f"📣 **MegaGrok Announcement**\n\n{text}"
        DRAFTS[uid] = payload

        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("🧪 Test in Admin Chat", callback_data="announce_test"),
            types.InlineKeyboardButton("✅ Publish to Channel", callback_data="announce_publish"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="announce_cancel"),
        )

        bot.send_message(
            message.chat.id,
            f"🧪 **Preview**\n\n{payload}\n\n"
            "_Test Mode is button-only. There is NO test command._",
            reply_markup=kb,
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("announce_"))
    def announce_action(call):
        uid = call.from_user.id

        if not (is_admin(uid) or is_megacrew(uid)):
            bot.answer_callback_query(call.id, "Access denied.")
            return

        payload = DRAFTS.get(uid)
        if not payload:
            bot.answer_callback_query(call.id, "No draft found.")
            return

        if call.data == "announce_cancel":
            DRAFTS.pop(uid, None)
            bot.edit_message_text(
                "❌ Announcement cancelled.",
                call.message.chat.id,
                call.message.message_id
            )
            return

        if call.data == "announce_test":
            bot.send_message(
                call.message.chat.id,
                "🧪 **TEST POST (ADMIN ONLY)**\n\n"
                "(This message is NOT visible to the public channel)\n\n"
                + payload,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id, "Test message sent.")
            return

        if call.data == "announce_publish":
            bot.send_message(
                GROKPEDIA_CHANNEL_ID,
                payload,
                parse_mode="Markdown"
            )

            log_admin_action(
                uid,
                "publish_announcement",
                {"text": payload}
            )

            bot.edit_message_text(
                "✅ Announcement published to MegaGrok channel.",
                call.message.chat.id,
                call.message.message_id
            )

            DRAFTS.pop(uid, None)

        bot.answer_callback_query(call.id)
