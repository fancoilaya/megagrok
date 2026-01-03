from telebot import TeleBot
import json
import time
import bot.db as db
from services.permissions import is_admin


LOG_PAGE_SIZE = 10


def _format_ts(ts: int) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    except Exception:
        return str(ts)


def setup(bot: TeleBot):

    @bot.message_handler(commands=["adminlog"])
    def view_admin_log(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "⛔ Admin only.")
            return

        parts = message.text.split()
        page = 1
        if len(parts) > 1:
            try:
                page = max(1, int(parts[1]))
            except ValueError:
                page = 1

        offset = (page - 1) * LOG_PAGE_SIZE

        db.cursor.execute("""
            SELECT actor_id, action, data, timestamp
            FROM admin_logs
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """, (LOG_PAGE_SIZE, offset))

        rows = db.cursor.fetchall()

        if not rows:
            bot.reply_to(message, "📭 No admin log entries found.")
            return

        lines = []
        for actor_id, action, data, ts in rows:
            try:
                data_obj = json.loads(data) if data else {}
                data_str = ", ".join(f"{k}={v}" for k, v in data_obj.items())
            except Exception:
                data_str = data or ""

            line = (
                f"👤 `{actor_id}`\n"
                f"• **{action}**\n"
                f"• {data_str}\n"
                f"• ⏱ {_format_ts(ts)}"
            )
            lines.append(line)

        text = (
            f"📜 **Admin Audit Log** (page {page})\n\n"
            + "\n\n".join(lines)
        )

        bot.send_message(
            message.chat.id,
            text,
            parse_mode="Markdown"
        )
