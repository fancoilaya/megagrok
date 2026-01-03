from telebot import TeleBot
import bot.db as db
from services.permissions import is_admin


def setup(bot: TeleBot):

    @bot.message_handler(commands=["addmegacrew"])
    def add_megacrew(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "⛔ Only the MegaGrok Admin can manage MegaCrew.")
            return

        if not message.reply_to_message:
            bot.reply_to(message, "Reply to a user with /addmegacrew")
            return

        target = message.reply_to_message.from_user
        db.update_user_xp(target.id, {"megacrew": 1})

        bot.reply_to(
            message,
            f"👑 **MegaCrew Added**\n\n{target.first_name} now has admin access.",
            parse_mode="Markdown"
        )

    @bot.message_handler(commands=["removemegacrew"])
    def remove_megacrew(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "⛔ Only the MegaGrok Admin can manage MegaCrew.")
            return

        if not message.reply_to_message:
            bot.reply_to(message, "Reply to a user with /removemegacrew")
            return

        target = message.reply_to_message.from_user
        db.update_user_xp(target.id, {"megacrew": 0})

        bot.reply_to(
            message,
            f"🧹 **MegaCrew Removed**\n\n{target.first_name} no longer has admin access.",
            parse_mode="Markdown"
        )
