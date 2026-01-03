from telebot import TeleBot, types
from services.permissions import is_megacrew, is_admin


def setup(bot: TeleBot):

    @bot.message_handler(commands=["admin"])
    def admin_panel(message):
        if not is_megacrew(message.from_user.id):
            bot.reply_to(message, "⛔ MegaCrew access required.")
            return

        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("📣 Notifications", callback_data="admin_notify"),
            types.InlineKeyboardButton("📘 Command Help", callback_data="admin_help"),
        )

        if is_admin(message.from_user.id):
            kb.add(types.InlineKeyboardButton("👥 MegaCrew Management", callback_data="admin_crew"))

        kb.add(types.InlineKeyboardButton("❌ Close", callback_data="admin_close"))

        bot.send_message(
            message.chat.id,
            "👑 **MegaCrew Control Panel**",
            reply_markup=kb,
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_"))
    def admin_callbacks(call):
        if call.data == "admin_notify":
            bot.send_message(
                call.message.chat.id,
                "📣 **Announcements**\n\n"
                "`/notifyall Your message`\n\n"
                "Preview → Confirm → Publish",
                parse_mode="Markdown"
            )

        elif call.data == "admin_help":
            bot.send_message(
                call.message.chat.id,
                "📘 **Commands**\n\n"
                "/notifyall\n/editlast\n/addmegacrew\n/removemegacrew",
                parse_mode="Markdown"
            )

        elif call.data == "admin_crew":
            bot.send_message(
                call.message.chat.id,
                "👥 **MegaCrew**\n\n"
                "Reply to a user:\n/addmegacrew\n/removemegacrew",
                parse_mode="Markdown"
            )

        elif call.data == "admin_close":
            bot.delete_message(call.message.chat.id, call.message.message_id)

        bot.answer_callback_query(call.id)
