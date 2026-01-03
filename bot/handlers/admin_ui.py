from telebot import TeleBot, types
from services.permissions import is_megacrew, is_admin


def setup(bot: TeleBot):

    # -------------------------------
    # /megaadmin entry (reset UI)
    # -------------------------------
    @bot.message_handler(commands=["megaadmin"])
    def admin_panel(message):
        uid = message.from_user.id
        if not (is_admin(uid) or is_megacrew(uid)):
            bot.reply_to(message, "⛔ MegaCrew access required.")
            return

        send_main_menu(message.chat.id, uid)

    # -------------------------------
    # UI SCREENS
    # -------------------------------
    def send_main_menu(chat_id, user_id):
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("📣 Announcements (Channel)", callback_data="ui_announce"),
            types.InlineKeyboardButton("🔔 Notify Users (DM)", callback_data="ui_notifyusers"),
            types.InlineKeyboardButton("📜 Admin Logs", callback_data="ui_logs"),
        )

        if is_admin(user_id):
            kb.add(types.InlineKeyboardButton("👥 MegaCrew Management", callback_data="ui_crew"))

        kb.add(types.InlineKeyboardButton("❌ Close", callback_data="ui_close"))

        bot.send_message(
            chat_id,
            "👑 <b>MegaGrok Admin Console</b>\n\n"
            "Choose how you want to communicate:",
            reply_markup=kb,
            parse_mode="HTML"
        )

    def edit_ui(call, text, kb):
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="HTML"
        )

    def back_close_kb(back_cb):
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("⬅ Back", callback_data=back_cb),
            types.InlineKeyboardButton("❌ Close", callback_data="ui_close"),
        )
        return kb

    # -------------------------------
    # CALLBACK ROUTER
    # -------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("ui_"))
    def ui_router(call):
        uid = call.from_user.id

        if not (is_admin(uid) or is_megacrew(uid)):
            bot.answer_callback_query(call.id, "Access denied.")
            return

        # MAIN MENU
        if call.data == "ui_main":
            send_main_menu(call.message.chat.id, uid)
            return

        # 📣 ANNOUNCEMENTS
        if call.data == "ui_announce":
            edit_ui(
                call,
                "📣 <b>Announcements (Channel)</b>\n\n"
                "Posts an official announcement to the channel and pins it.\n\n"
                "<b>Example:</b>\n"
                "<code>/announce_html &lt;b&gt;🚀 Update&lt;/b&gt;\n"
                "PvP Arena is now live!\n"
                "&lt;a href='https://example.com'&gt;Read more&lt;/a&gt;</code>\n\n"
                "• HTML supported\n"
                "• Permanent\n"
                "• Pinned",
                back_close_kb("ui_main")
            )

        # 🔔 NOTIFY USERS
        elif call.data == "ui_notifyusers":
            edit_ui(
                call,
                "🔔 <b>Notify Users (Direct Messages)</b>\n\n"
                "Sends a private message to all users who started the bot.\n\n"
                "<b>Example:</b>\n"
                "<code>/notifyusers &lt;b&gt;🚨 Important&lt;/b&gt;\n"
                "Servers restart in 10 minutes.\n"
                "Please finish battles.</code>\n\n"
                "<b>Flow:</b>\n"
                "1️⃣ Preview\n"
                "2️⃣ 🧪 Test (DM to yourself)\n"
                "3️⃣ 🚨 Final confirmation\n"
                "4️⃣ Sent as real notifications",
                back_close_kb("ui_main")
            )

        # 📜 LOGS
        elif call.data == "ui_logs":
            edit_ui(
                call,
                "📜 <b>Admin Logs</b>\n\n"
                "View recent admin actions.\n\n"
                "<code>/adminlog</code>\n"
                "<code>/adminlog 2</code>",
                back_close_kb("ui_main")
            )

        # 👥 MEGACREW
        elif call.data == "ui_crew":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "Admin only.")
                return

            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(
                types.InlineKeyboardButton("➕ Add MegaCrew", switch_inline_query_current_chat="/addmegacrew"),
                types.InlineKeyboardButton("➖ Remove MegaCrew", switch_inline_query_current_chat="/removemegacrew"),
                types.InlineKeyboardButton("📋 List MegaCrew", switch_inline_query_current_chat="/listmegacrew"),
                types.InlineKeyboardButton("⬅ Back", callback_data="ui_main"),
                types.InlineKeyboardButton("❌ Close", callback_data="ui_close"),
            )

            edit_ui(
                call,
                "👥 <b>MegaCrew Management</b>\n\n"
                "Reply to a user, then tap an action:",
                kb
            )

        # CLOSE
        elif call.data == "ui_close":
            bot.delete_message(call.message.chat.id, call.message.message_id)

        bot.answer_callback_query(call.id)
