from telebot import TeleBot, types
from services.permissions import is_megacrew, is_admin


def setup(bot: TeleBot):

    # -------------------------------------------------
    # /megaadmin entry point
    # -------------------------------------------------
    @bot.message_handler(commands=["megaadmin"])
    def admin_panel(message):
        uid = message.from_user.id

        # ✅ ADMIN OR MEGACREW IS ALLOWED
        if not (is_admin(uid) or is_megacrew(uid)):
            bot.reply_to(message, "⛔ MegaCrew access required.")
            return

        show_main_menu(message.chat.id, uid)

    # -------------------------------------------------
    # Main menu
    # -------------------------------------------------
    def show_main_menu(chat_id, user_id):
        kb = types.InlineKeyboardMarkup(row_width=1)

        kb.add(
            types.InlineKeyboardButton("📣 Announcements", callback_data="admin_announcements"),
            types.InlineKeyboardButton("📜 Admin Logs", callback_data="admin_logs"),
        )

        # 👑 Only the real admin sees crew management
        if is_admin(user_id):
            kb.add(types.InlineKeyboardButton("👥 MegaCrew Management", callback_data="admin_crew"))

        kb.add(types.InlineKeyboardButton("❌ Close", callback_data="admin_close"))

        bot.send_message(
            chat_id,
            "👑 **MegaCrew Control Panel**\n\n"
            "Welcome to the MegaGrok admin console.\n"
            "All admin actions start here 👇",
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

        # ✅ ADMIN OR MEGACREW IS ALLOWED
        if not (is_admin(uid) or is_megacrew(uid)):
            bot.answer_callback_query(call.id, "Access denied.")
            return

        # -------------------------
        # 📣 ANNOUNCEMENTS
        # -------------------------
        if call.data == "admin_announcements":
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(
                types.InlineKeyboardButton("✏️ Create Announcement", callback_data="admin_announce_start"),
                types.InlineKeyboardButton("🧪 How Test Mode Works", callback_data="admin_announce_testinfo"),
                types.InlineKeyboardButton("🧪 Example", callback_data="admin_announce_example"),
                types.InlineKeyboardButton("⬅️ Back", callback_data="admin_back"),
            )

            bot.send_message(
                cid,
                "📣 **Announcements**\n\n"
                "Announcements follow this flow:\n"
                "🧪 Test in Admin Chat → ✅ Publish to Channel",
                reply_markup=kb,
                parse_mode="Markdown"
            )

        elif call.data == "admin_announce_start":
            bot.send_message(
                cid,
                "✏️ **Create Announcement**\n\n"
                "Type:\n"
                "`/notifyall Your announcement text`\n\n"
                "You will see a preview before publishing.",
                parse_mode="Markdown"
            )

        elif call.data == "admin_announce_testinfo":
            bot.send_message(
                cid,
                "🧪 **Test Mode**\n\n"
                "• Sends message ONLY to this admin chat\n"
                "• Safe to test formatting & links\n"
                "• Nothing is public until Publish is pressed",
                parse_mode="Markdown"
            )

        elif call.data == "admin_announce_example":
            bot.send_message(
                cid,
                "🧪 **Example**\n\n"
                "`/notifyall ⚔️ PvP Arena v2 is now LIVE!`\n\n"
                "Test → Publish → Done",
                parse_mode="Markdown"
            )

        # -------------------------
        # 📜 ADMIN LOGS
        # -------------------------
        elif call.data == "admin_logs":
            bot.send_message(
                cid,
                "📜 **Admin Audit Logs**\n\n"
                "Usage:\n"
                "`/adminlog`\n"
                "`/adminlog 2`",
                parse_mode="Markdown"
            )

        # -------------------------
        # 👥 MEGACREW (ADMIN ONLY)
        # -------------------------
        elif call.data == "admin_crew":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "Admin only.")
                return

            bot.send_message(
                cid,
                "👥 **MegaCrew Management**\n\n"
                "Reply to a user and send:\n"
                "`/addmegacrew`\n"
                "`/removemegacrew`",
                parse_mode="Markdown"
            )

        # -------------------------
        # NAVIGATION
        # -------------------------
        elif call.data == "admin_back":
            show_main_menu(cid, uid)

        elif call.data == "admin_close":
            bot.delete_message(cid, call.message.message_id)

        bot.answer_callback_query(call.id)
