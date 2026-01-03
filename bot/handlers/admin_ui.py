from telebot import TeleBot, types
from services.permissions import is_megacrew, is_admin


def setup(bot: TeleBot):

    # -------------------------------------------------
    # /admin entry point
    # -------------------------------------------------
    @bot.message_handler(commands=["admin"])
    def admin_panel(message):
        if not is_megacrew(message.from_user.id):
            bot.reply_to(message, "⛔ MegaCrew access required.")
            return

        show_main_menu(bot, message.chat.id, message.from_user.id)

    # -------------------------------------------------
    # Main menu
    # -------------------------------------------------
    def show_main_menu(bot, chat_id, user_id):
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
            "Use the menu below to manage MegaGrok.\n"
            "All actions start here 👇",
            reply_markup=kb,
            parse_mode="Markdown"
        )

    # -------------------------------------------------
    # Callback router
    # -------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_"))
    def admin_callbacks(call):
        uid = call.from_user.id
        cid = call.message.chat.id

        if not is_megacrew(uid):
            bot.answer_callback_query(call.id, "Access denied.")
            return

        # 📣 ANNOUNCEMENTS
        if call.data == "admin_announcements":
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(
                types.InlineKeyboardButton("✏️ Create Announcement", callback_data="admin_announce_start"),
                types.InlineKeyboardButton("🧪 Example", callback_data="admin_announce_example"),
                types.InlineKeyboardButton("⬅️ Back", callback_data="admin_back"),
            )

            bot.send_message(
                cid,
                "📣 **Announcements**\n\n"
                "Announcements are published to the **MegaGrok channel**.\n"
                "They always go through **Preview → Confirm → Publish**.",
                reply_markup=kb,
                parse_mode="Markdown"
            )

        elif call.data == "admin_announce_start":
            bot.send_message(
                cid,
                "✏️ **Create Announcement**\n\n"
                "**Step 1:** Type the command below with your message\n\n"
                "`/notifyall Your announcement text`\n\n"
                "You will see a **preview** before anything is published.",
                parse_mode="Markdown"
            )

        elif call.data == "admin_announce_example":
            bot.send_message(
                cid,
                "🧪 **Example Announcement**\n\n"
                "`/notifyall ⚔️ PvP Arena v2 is now LIVE! Enter with /arena`\n\n"
                "This will:\n"
                "• Show a preview\n"
                "• Ask for confirmation\n"
                "• Publish to the channel",
                parse_mode="Markdown"
            )

        # 📜 ADMIN LOGS
        elif call.data == "admin_logs":
            bot.send_message(
                cid,
                "📜 **Admin Audit Logs**\n\n"
                "View all admin actions (publish, edit, pin, etc).\n\n"
                "**Usage:**\n"
                "`/adminlog`\n"
                "`/adminlog 2` (older entries)",
                parse_mode="Markdown"
            )

        # 👥 MEGACREW (ADMIN ONLY)
        elif call.data == "admin_crew":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "Admin only.")
                return

            bot.send_message(
                cid,
                "👥 **MegaCrew Management**\n\n"
                "**Add MegaCrew:**\n"
                "1️⃣ Reply to a user\n"
                "2️⃣ Send `/addmegacrew`\n\n"
                "**Remove MegaCrew:**\n"
                "1️⃣ Reply to a user\n"
                "2️⃣ Send `/removemegacrew`",
                parse_mode="Markdown"
            )

        elif call.data == "admin_back":
            show_main_menu(bot, cid, uid)

        elif call.data == "admin_close":
            bot.delete_message(cid, call.message.message_id)

        bot.answer_callback_query(call.id)
