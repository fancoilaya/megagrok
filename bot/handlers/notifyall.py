from telebot import TeleBot, types
from services.permissions import is_megacrew
from services.audit_log import log_admin_action
from config import GROKPEDIA_CHANNEL_ID

LAST_ANNOUNCEMENT = {}

def setup(bot: TeleBot):

    @bot.message_handler(commands=["notifyall"])
    def preview(message):
        if not is_megacrew(message.from_user.id):
            return

        text = message.text.replace("/notifyall", "").strip()
        if not text:
            bot.reply_to(message, "Usage: /notifyall message")
            return

        payload = f"📣 **MegaGrok Announcement**\n\n{text}"
        LAST_ANNOUNCEMENT[message.from_user.id] = payload

        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("✅ Publish", callback_data="announce_publish"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="announce_cancel")
        )

        bot.send_message(
            message.chat.id,
            f"🧪 **Preview**\n\n{payload}",
            reply_markup=kb,
            parse_mode="Markdown"
        )
