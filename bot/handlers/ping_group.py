from telebot import TeleBot
import bot.db as db
import os
import time
from services.permissions import is_admin, is_megacrew
from services.audit_log import log_admin_action

GROUP_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID", "0"))

# How many @mentions per message
CHUNK_SIZE = 20
DELAY = 1.0  # seconds between messages


def setup(bot: TeleBot):

    @bot.callback_query_handler(func=lambda c: c.data == "pinggroup_send")
    def send_ping(call):
        uid = call.from_user.id

        if not (is_admin(uid) or is_megacrew(uid)):
            return

        users = db.get_all_users()
        usernames = [f"@{u['username']}" for u in users if u.get("username")]

        if not usernames:
            bot.answer_callback_query(call.id, "No users with usernames to ping.")
            return

        chunks = [
            usernames[i:i + CHUNK_SIZE]
            for i in range(0, len(usernames), CHUNK_SIZE)
        ]

        sent_messages = 0
        mentioned_users = 0

        for chunk in chunks:
            text = "🚨 <b>IMPORTANT</b>\n\n" + " ".join(chunk)
            bot.send_message(GROUP_ID, text, parse_mode="HTML")
            sent_messages += 1
            mentioned_users += len(chunk)
            time.sleep(DELAY)

        log_admin_action(
            uid,
            "ping_group",
            {
                "messages_sent": sent_messages,
                "users_mentioned": mentioned_users,
            }
        )

        bot.answer_callback_query(call.id, "✅ Group ping sent.")
