from telebot import TeleBot
import bot.db as db
from services.permissions import is_admin


def setup(bot: TeleBot):

    @bot.message_handler(commands=["addmegacrew"])
    def add_megacrew(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "⛔ Admin only.")
            return

        if not message.reply_to_message:
            bot.reply_to(message, "Reply to a user, then press ➕ Add MegaCrew.")
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
            bot.reply_to(message, "⛔ Admin only.")
            return

        if not message.reply_to_message:
            bot.reply_to(message, "Reply to a user, then press ➖ Remove MegaCrew.")
            return

        target = message.reply_to_message.from_user
        db.update_user_xp(target.id, {"megacrew": 0})

        bot.reply_to(
            message,
            f"🧹 **MegaCrew Removed**\n\n{target.first_name} no longer has admin access.",
            parse_mode="Markdown"
        )

    @bot.message_handler(commands=["listmegacrew"])
    def list_megacrew(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "⛔ Admin only.")
            return

        db.cursor.execute("""
            SELECT user_id, username, display_name
            FROM users
            WHERE megacrew = 1
            ORDER BY user_id
        """)
        rows = db.cursor.fetchall()

        if not rows:
            bot.reply_to(message, "👥 No MegaCrew members found.")
            return

        lines = ["👥 **MegaCrew Members**\n"]
        for uid, username, display in rows:
            name = display or username or f"User{uid}"
            lines.append(f"• {name} (`{uid}`)")

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="Markdown"
        )
