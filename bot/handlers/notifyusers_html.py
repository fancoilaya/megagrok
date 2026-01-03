import time
from telebot import TeleBot, types
import bot.db as db
from services.permissions import is_admin, is_megacrew
from services.audit_log import log_admin_action

RATE_DELAY = 0.05  # ~20 msgs/sec
DRAFTS = {}


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

        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("🧪 Test (DM to me)", callback_data="notifyusers_test"),
            types.InlineKeyboardButton("✅ Send to Users", callback_data="notifyusers_send"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="notifyusers_cancel"),
        )

        bot.send_message(
            message.chat.id,
            "🧪 <b>Preview — User Notification</b><br><br>" + html,
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

        # ❌ Cancel
        if call.data == "notifyusers_cancel":
            DRAFTS.pop(uid, None)
            bot.edit_message_text(
                "❌ User notification cancelled.",
                call.message.chat.id,
                call.message.message_id
            )
            return

        # 🧪 Test (DM to admin)
        if call.data == "notifyusers_test":
            bot.send_message(
                uid,
                "🧪 <b>TEST NOTIFICATION (ADMIN ONLY)</b><br><br>" + html,
                parse_mode="HTML"
            )
            bot.answer_callback_query(call.id, "Test DM sent.")
            return

        # ✅ Send to users
        if call.data == "notifyusers_send":
            sent = 0
            failed = 0

            users = db.get_all_users()

            for u in users:
                user_id = u.get("id")
                if not user_id:
                    continue

                try:
                    bot.send_message(
                        user_id,
                        html,
                        parse_mode="HTML"
                    )
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
                f"✅ <b>User notification sent</b><br><br>"
                f"Delivered: {sent}<br>"
                f"Failed: {failed}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML"
            )

            DRAFTS.pop(uid, None)

        bot.answer_callback_query(call.id)
