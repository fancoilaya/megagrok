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
            types.InlineKeyboardButton("📣 Announcements (Channel)", callback_data="admin_announce"),
            types.InlineKeyboardButton("🔔 Notify Users (DM)", callback_data="admin_notifyusers"),
            types.InlineKeyboardButton("📜 Admin Logs", callback_data="admin_logs"),
        )

        if is_admin(user_id):
            kb.add(types.InlineKeyboardButton("👥 MegaCrew Management", callback_data="admin_crew"))

        kb.add(types.InlineKeyboardButton("❌ Close", callback_data="admin_close"))

        bot.send_message(
            chat_id,
            "👑 <b>MegaGrok Admin Console</b>\n\n"
            "Choose how you want to communicate:",
            reply_markup=kb,
            parse_mode="HTML"
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_"))
    def admin_callbacks(call):
        uid = call.from_user.id
        cid = call.message.chat.id

        if not (is_admin(uid) or is_megacrew(uid)):
            bot.answer_callback_query(call.id, "Access denied.")
            return

        # 📣 ANNOUNCEMENTS
        if call.data == "admin_announce":
            bot.send_message(
                cid,
                "📣 <b>Announcements (Channel)</b>\n\n"
                "Posts an official announcement and pins it.\n\n"
                "<b>Example:</b>\n"
                "<code>/announce_html &lt;b&gt;🚀 Update&lt;/b&gt;\n"
                "PvP Arena is now live!\n"
                "&lt;a href='https://example.com'&gt;Read more&lt;/a&gt;</code>\n\n"
                "• HTML supported\n"
                "• Permanent\n"
                "• Pinned",
                parse_mode="HTML"
            )

        # 🔔 NOTIFY USERS
        elif call.data == "admin_notifyusers":
            bot.send_message(
                cid,
                "🔔 <b>Notify Users (Direct Messages)</b>\n\n"
                "Sends a private message to <b>all users who started the bot</b>.\n\n"
                "<b>Example:</b>\n"
                "<code>/notifyusers &lt;b&gt;🚨 Important&lt;/b&gt;\n"
                "Servers restart in 10 minutes.\n"
                "Please finish battles.</code>\n\n"
                "<b>Flow:</b>\n"
                "1️⃣ Preview\n"
                "2️⃣ 🧪 Test (DM to yourself)\n"
                "3️⃣ 🚨 Final confirmation\n"
                "4️⃣ Sent as real notifications\n\n"
                "<b>Uses the SAME HTML rules as /announce_html</b>",
                parse_mode="HTML"
            )

        elif call.data == "admin_logs":
            bot.send_message(
                cid,
                "📜 <b>Admin Logs</b>\n\n"
                "<code>/adminlog</code>\n"
                "<code>/adminlog 2</code>",
                parse_mode="HTML"
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
                "👥 <b>MegaCrew Management</b>\n\n"
                "Reply to a user, then tap a button:",
                reply_markup=kb,
                parse_mode="HTML"
            )

        elif call.data == "admin_back":
            show_main_menu(cid, uid)

        elif call.data == "admin_close":
            bot.delete_message(cid, call.message.message_id)

        bot.answer_callback_query(call.id)
