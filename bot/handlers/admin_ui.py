from telebot import TeleBot, types
from services.permissions import is_megacrew, is_admin
import bot.db as db
import time

# chat_id -> admin UI message_id
ADMIN_UI_MESSAGE = {}


def setup(bot: TeleBot):

    # -------------------------------------------------
    # /megaadmin — single persistent admin UI
    # -------------------------------------------------
    @bot.message_handler(commands=["megaadmin"])
    def admin_panel(message):
        uid = message.from_user.id
        chat_id = message.chat.id

        if not (is_admin(uid) or is_megacrew(uid)):
            bot.reply_to(message, "⛔ MegaCrew access required.")
            return

        msg_id = ADMIN_UI_MESSAGE.get(chat_id)

        if msg_id:
            try:
                bot.edit_message_text(
                    breadcrumb("Main") + "Choose how you want to communicate:",
                    chat_id,
                    msg_id,
                    reply_markup=main_menu_kb(uid),
                    parse_mode="HTML"
                )
                return
            except Exception:
                ADMIN_UI_MESSAGE.pop(chat_id, None)

        sent = bot.send_message(
            chat_id,
            breadcrumb("Main") + "Choose how you want to communicate:",
            reply_markup=main_menu_kb(uid),
            parse_mode="HTML"
        )
        ADMIN_UI_MESSAGE[chat_id] = sent.message_id

    # -------------------------------------------------
    # UI helpers
    # -------------------------------------------------
    def breadcrumb(title: str) -> str:
        return f"👑 <b>Admin › {title}</b>\n\n"

    def loading_text(title: str) -> str:
        return breadcrumb(title) + "⏳ Loading…"

    def main_menu_kb(user_id):
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("📣 Announcements (Channel)", callback_data="ui_announce"),
            types.InlineKeyboardButton("🔔 Notify Users (DM)", callback_data="ui_notifyusers"),
            types.InlineKeyboardButton("📜 Admin Logs", callback_data="ui_logs"),
        )
        if is_admin(user_id):
            kb.add(types.InlineKeyboardButton("👥 MegaCrew Management", callback_data="ui_crew"))
        kb.add(types.InlineKeyboardButton("❌ Close", callback_data="ui_close"))
        return kb

    def back_close_kb():
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("⬅ Back", callback_data="ui_main"),
            types.InlineKeyboardButton("❌ Close", callback_data="ui_close"),
        )
        return kb

    def edit_ui(call, text, kb):
        chat_id = call.message.chat.id
        msg_id = call.message.message_id
        ADMIN_UI_MESSAGE[chat_id] = msg_id

        bot.edit_message_text(
            text,
            chat_id,
            msg_id,
            reply_markup=kb,
            parse_mode="HTML"
        )

    # -------------------------------------------------
    # CALLBACK ROUTER
    # -------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("ui_"))
    def ui_router(call):
        uid = call.from_user.id
        chat_id = call.message.chat.id

        if not (is_admin(uid) or is_megacrew(uid)):
            bot.answer_callback_query(call.id, "Access denied.")
            return

        # ---------------------------
        # MAIN
        # ---------------------------
        if call.data == "ui_main":
            edit_ui(
                call,
                breadcrumb("Main") + "Choose how you want to communicate:",
                main_menu_kb(uid)
            )

        # ---------------------------
        # ANNOUNCEMENTS
        # ---------------------------
        elif call.data == "ui_announce":
            edit_ui(call, loading_text("Announcements"), None)
            time.sleep(0.3)

            edit_ui(
                call,
                breadcrumb("Announcements") +
                "📣 <b>Announcements (Channel)</b>\n\n"
                "Posts an official announcement and pins it.\n\n"
                "<b>Example:</b>\n"
                "<code>/announce_html &lt;b&gt;🚀 Update&lt;/b&gt;\n"
                "PvP Arena is now live!\n"
                "&lt;a href='https://example.com'&gt;Read more&lt;/a&gt;</code>",
                back_close_kb()
            )

        # ---------------------------
        # NOTIFY USERS
        # ---------------------------
        elif call.data == "ui_notifyusers":
            edit_ui(call, loading_text("Notify Users"), None)
            time.sleep(0.3)

            edit_ui(
                call,
                breadcrumb("Notify Users") +
                "🔔 <b>Notify Users (Direct Messages)</b>\n\n"
                "Sends a private message to all users who started the bot.\n\n"
                "<code>/notifyusers &lt;b&gt;🚨 Important&lt;/b&gt;\n"
                "Servers restart in 10 minutes.</code>",
                back_close_kb()
            )

        # ---------------------------
        # ADMIN LOGS
        # ---------------------------
        elif call.data == "ui_logs":
            edit_ui(call, loading_text("Admin Logs"), None)
            time.sleep(0.3)

            edit_ui(
                call,
                breadcrumb("Admin Logs") +
                "📜 <b>Admin Logs</b>\n\n"
                "<code>/adminlog</code>\n"
                "<code>/adminlog 2</code>",
                back_close_kb()
            )

        # ---------------------------
        # MEGACREW MENU
        # ---------------------------
        elif call.data == "ui_crew":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "Admin only.")
                return

            edit_ui(call, loading_text("MegaCrew"), None)
            time.sleep(0.3)

            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(
                types.InlineKeyboardButton("➕ Add MegaCrew", switch_inline_query_current_chat="/addmegacrew "),
                types.InlineKeyboardButton("➖ Remove MegaCrew", switch_inline_query_current_chat="/removemegacrew "),
                types.InlineKeyboardButton("📋 List MegaCrew", callback_data="ui_list_megacrew"),
                types.InlineKeyboardButton("⬅ Back", callback_data="ui_main"),
                types.InlineKeyboardButton("❌ Close", callback_data="ui_close"),
            )

            edit_ui(
                call,
                breadcrumb("MegaCrew") +
                "👥 <b>MegaCrew Management</b>\n\n"
                "• Reply to a user, then use <b>Add</b> or <b>Remove</b>\n"
                "• Use <b>List MegaCrew</b> to view current members",
                kb
            )

        # ---------------------------
        # LIST MEGACREW (IN-UI)
        # ---------------------------
        elif call.data == "ui_list_megacrew":
            edit_ui(call, loading_text("MegaCrew Members"), None)
            time.sleep(0.3)

            # Pull MegaCrew users directly from DB
            users = db.get_all_users()
            lines = []

            for u in users:
                if not u.get("megacrew"):
                    continue

                username = u.get("username")
                uid_str = str(u.get("id"))

                if username:
                    lines.append(f"• @{username}")
                else:
                    lines.append(f"• <code>{uid_str}</code>")

            if not lines:
                body = "No MegaCrew members found."
            else:
                body = "\n".join(lines)

            edit_ui(
                call,
                breadcrumb("MegaCrew Members") +
                "👥 <b>MegaCrew Members</b>\n\n" +
                body,
                back_close_kb()
            )

        # ---------------------------
        # CLOSE
        # ---------------------------
        elif call.data == "ui_close":
            msg_id = ADMIN_UI_MESSAGE.pop(chat_id, None)
            if msg_id:
                bot.delete_message(chat_id, msg_id)

        bot.answer_callback_query(call.id)
