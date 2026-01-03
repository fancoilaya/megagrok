from telebot import TeleBot, types
from services.permissions import is_megacrew
from services.audit_log import log_admin_action
from config import GROKPEDIA_CHANNEL_ID

# Per-user draft store
DRAFTS = {}


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
        DRAFTS[message.from_user.id] = payload

        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("🧪 Test in Admin Chat", callback_data="announce_test"),
            types.InlineKeyboardButton("✅ Publish to Channel", callback_data="announce_publish"),
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
        uid = call.from_user.id
        payload = DRAFTS.get(uid)

        if not payload:
            bot.answer_callback_query(call.id, "No draft found.")
            return

        # ❌ CANCEL
        if call.data == "announce_cancel":
            DRAFTS.pop(uid, None)
            bot.edit_message_text(
                "❌ Announcement cancelled.",
                call.message.chat.id,
                call.message.message_id
            )
            return

        # 🧪 TEST (ADMIN CHAT ONLY)
        if call.data == "announce_test":
            bot.send_message(
                call.message.chat.id,
                "🧪 **TEST POST (ADMIN ONLY)**\n\n" + payload,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id, "Test message sent.")
            return

        # ✅ REAL PUBLISH
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
