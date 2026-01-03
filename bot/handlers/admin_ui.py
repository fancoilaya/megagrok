from telebot import TeleBot, types
from services.permissions import is_megacrew, is_admin


def setup(bot: TeleBot):

    # -------------------------------------------------
    # /admin entry point
    # -------------------------------------------------
    @bot.message_handler(commands=["megaadmin"])
    def admin_panel(message):
        if not is_megacrew(message.from_user.id):
            bot.reply_to(message, "⛔ MegaCrew access required.")
            return

        show_main_menu(message.chat.id, message.from_user.id)

    # -------------------------------------------------
    # Main menu
    # -------------------------------------------------
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
            "All admin actions start here.\n"
            "Use the menus below to safely manage MegaGrok 👇",
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

        # -------------------------
        # 📣 ANNOUNCEMENTS MENU
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
                "Announcements are published to the **MegaGrok channel**.\n\n"
                "They always follow this flow:\n"
                "🧪 Test in Admin Chat → ✅ Publish to Channel",
                reply_markup=kb,
                parse_mode="Markdown"
            )

        # ---- Start announcement
        elif call.data == "admin_announce_start":
            bot.send_message(
                cid,
                "✏️ **Create Announcement**\n\n"
                "**Step 1:** Type the command below with your message:\n\n"
                "`/notifyall Your announcement text`\n\n"
                "**Step 2:** Choose:\n"
                "• 🧪 Test in Admin Chat\n"
                "• ✅ Publish to Channel\n\n"
                "Nothing is public until you confirm.",
                parse_mode="Markdown"
            )

        # ---- Test mode explanation
        elif call.data == "admin_announce_testinfo":
            bot.send_message(
                cid,
                "🧪 **Test Mode (Admin Only)**\n\n"
                "Test Mode lets you:\n"
                "• Preview formatting\n"
                "• Check links & emojis\n"
                "• Verify Markdown\n\n"
                "🟢 Test messages are sent **ONLY** to this admin chat.\n"
                "🔴 Nothing is posted publicly until you press **Publish**.",
                parse_mode="Markdown"
            )

        # ---- Example
        elif call.data == "admin_announce_example":
            bot.send_message(
                cid,
                "🧪 **Example Announcement**\n\n"
                "`/notifyall ⚔️ PvP Arena v2 is now LIVE!`\n\n"
                "Flow:\n"
                "1️⃣ Preview appears\n"
                "2️⃣ 🧪 Test in Admin Chat\n"
                "3️⃣ ✅ Publish to MegaGrok channel",
                parse_mode="Markdown"
            )

        # -------------------------
        # 📜 ADMIN LOGS
        # -------------------------
        elif call.data == "admin_logs":
            bot.send_message(
                cid,
                "📜 **Admin Audit Logs**\n\n"
                "View all admin actions:\n"
                "• announcements\n"
                "• edits\n"
                "• pins\n\n"
                "**Usage:**\n"
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
                "**Add MegaCrew:**\n"
                "1️⃣ Reply to a user\n"
                "2️⃣ Send `/addmegacrew`\n\n"
                "**Remove MegaCrew:**\n"
                "1️⃣ Reply to a user\n"
                "2️⃣ Send `/removemegacrew`",
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
