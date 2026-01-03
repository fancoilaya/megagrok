import time
from telebot import TeleBot, types
import bot.db as db
from services.permissions import is_admin, is_megacrew
from services.audit_log import log_admin_action

RATE_DELAY = 0.05
DRAFTS = {}
PENDING_CONFIRM = {}


def setup(bot: TeleBot):

    @bot.message_handler(commands=["notifyusers"])
    def preview(message):
        uid = message.from_user.id

        if not (is_admin(uid) or is_megacrew(uid)):
            bot.reply_to(message, "⛔ MegaCrew access required.")
            return

        html = message.text.replace("/notifyusers", "").strip()
        if not html:
            bot.reply_to(
                message,
                "Usage:\n"
                "/notifyusers <b>HTML message</b>\n\n"
                "Uses the SAME HTML rules as /announce_html."
            )
            return

        DRAFTS[uid] = html
        PENDING_CONFIRM.pop(uid, None)

        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("🧪 Test (DM to me)", callback_data="notifyusers_test"),
            types.InlineKeyboardButton("📤 Proceed to Send", callback_data="notifyusers_prepare"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="notifyusers_cancel"),
        )

        bot.send_message(
            message.chat.id,
            "🧪 <b>Preview — User Notification</b>\n\n" + html,
            reply_markup=kb,
            parse_mode="HTML"
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("notifyusers_"))
    def handle_notifyusers(call):
        uid = call.from_user.id

        if not (is_admin(uid) or is_megacrew(uid)):
            bot.answer_callback_query(call.id, "Access denied.")
            return

        html = DRAFTS.get(uid)
        if not html:
            bot.answer_callback_query(call.id, "No draft found.")
            return

        if call.data == "notifyusers_cancel":
            DRAFTS.pop(uid, None)
            PENDING_CONFIRM.pop(uid, None)
            bot.edit_message_text(
                "❌ User notification cancelled.",
                call.message.chat.id,
                call.message.message_id
            )
            return

        if call.data == "notifyusers_test":
            bot.send_message(
                uid,
                "🧪 <b>TEST NOTIFICATION (ADMIN ONLY)</b>\n\n" + html,
                parse_mode="HTML"
            )
            bot.answer_callback_query(call.id, "Test DM sent.")
            return

        if call.data == "notifyusers_prepare":
            PENDING_CONFIRM[uid] = True

            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton("🚨 YES, SEND NOW", callback_data="notifyusers_send"),
                types.InlineKeyboardButton("❌ Cancel", callback_data="notifyusers_cancel"),
            )

            bot.edit_message_text(
                "🚨 <b>FINAL CONFIRMATION</b>\n\n"
                "You are about to send a <b>DIRECT MESSAGE</b> to <b>ALL USERS</b> who started the bot.\n\n"
                "This will trigger real Telegram notifications.\n\n"
                "<b>This action cannot be undone.</b>",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
            return

        if call.data == "notifyusers_send":
            if not PENDING_CONFIRM.get(uid):
                bot.answer_callback_query(call.id, "Confirmation required.")
                return

            sent = 0
            failed = 0
            users = db.get_all_users()

            for u in users:
                user_id = u.get("id")
                if not user_id:
                    continue

                try:
                    bot.send_message(user_id, html, parse_mode="HTML")
                    sent += 1
                    time.sleep(RATE_DELAY)
                except Exception:
                    failed += 1

            log_admin_action(
                uid,
                "notify_users_html",
                {"sent": sent, "failed": failed}
            )

            bot.edit_message_text(
                f"✅ <b>User notification sent</b>\n\n"
                f"Delivered: {sent}\n"
                f"Failed: {failed}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML"
            )

            DRAFTS.pop(uid, None)
            PENDING_CONFIRM.pop(uid, None)

        bot.answer_callback_query(call.id)
