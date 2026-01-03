from telebot import TeleBot, types
from services.permissions import is_megacrew, is_admin


def setup(bot: TeleBot):

    @bot.message_handler(commands=["megaadmin"])
    def admin_panel(message):
        uid = message.from_user.id
        if not (is_admin(uid) or is_megacrew(uid)):
            bot.reply_to(message, "⛔ MegaCrew access required.")
            return

        show_main_menu(message.chat.id, uid)

    def show_main_menu(chat_id, user_id):
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("📣 Announcements", callback_data="admin_announcements"),
            types.InlineKeyboardButton("📜 Admin Logs", callback_data="admin_logs"),
        )

        if is_admin(user_id):
            kb.add(types.InlineKeyboardButton("👥 MegaCrew Management", callback_data="admin_crew"))

        kb.add(types.InlineKeyboardButton("❌ Close", callback_data="admin_close"))

        bot.send_message(
            chat_id,
            "👑 **MegaCrew Control Panel**\n\n"
            "All admin actions start here 👇",
            reply_markup=kb,
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_"))
    def admin_callbacks(call):
        uid = call.from_user.id
        cid = call.message.chat.id

        if not (is_admin(uid) or is_megacrew(uid)):
            bot.answer_callback_query(call.id, "Access denied.")
            return

        if call.data == "admin_announcements":
            bot.send_message(
                cid,
                "📣 **Announcements**\n\n"
                "**How it works:**\n"
                "1️⃣ Type `/notifyall Your message`\n"
                "2️⃣ Preview appears\n"
                "3️⃣ 🧪 Test in Admin Chat (button)\n"
                "4️⃣ ✅ Publish to Channel\n\n"
                "**Important:**\n"
                "• Test Mode is **NOT a command**\n"
                "• Only the 🧪 button triggers it",
                parse_mode="Markdown"
            )

        elif call.data == "admin_logs":
            bot.send_message(
                cid,
                "📜 **Admin Logs**\n\n"
                "Use:\n"
                "`/adminlog`\n"
                "`/adminlog 2`",
                parse_mode="Markdown"
            )

        elif call.data == "admin_crew":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "Admin only.")
                return

            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(
                types.InlineKeyboardButton("➕ Add MegaCrew", switch_inline_query_current_chat="/addmegacrew"),
                types.InlineKeyboardButton("➖ Remove MegaCrew", switch_inline_query_current_chat="/removemegacrew"),
                types.InlineKeyboardButton("📋 List MegaCrew", switch_inline_query_current_chat="/listmegacrew"),
                types.InlineKeyboardButton("⬅️ Back", callback_data="admin_back"),
            )

            bot.send_message(
                cid,
                "👥 **MegaCrew Management**\n\n"
                "Reply to a user, then tap a button below:",
                reply_markup=kb,
                parse_mode="Markdown"
            )

        elif call.data == "admin_back":
            show_main_menu(cid, uid)

        elif call.data == "admin_close":
            bot.delete_message(cid, call.message.message_id)

        bot.answer_callback_query(call.id)
