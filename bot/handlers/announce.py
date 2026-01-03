# bot/handlers/announce.py
# Admin Announcement Handler (Markdown + HTML Support + Preview)
# Posts ONLY to LEADERBOARD_CHANNEL_ID
#
# Commands:
#   /announce <text>        → Markdown announcement (pins)
#   /announce_html <html>   → HTML announcement (sanitized for Telegram, pins)
#   /announce_preview <html or markdown> → Preview only (private to admin)
#
# Safety:
# - Only admin (MEGAGROK_ADMIN_ID) OR MegaCrew may use announcement commands.
# - Posts exclusively to LEADERBOARD_CHANNEL_ID.
# - HTML is sanitized to Telegram-supported markup.

import os
import re
import traceback
from telebot import TeleBot

from services.permissions import is_megacrew

# Allowed HTML tags for Telegram
_ALLOWED_TAGS = {"b", "i", "u", "code", "pre", "a"}

# Tag normalization
_TAG_NORMALIZE = {
    "strong": "b",
    "em": "i",
}

# Regex helpers
_RE_TAG = re.compile(r"</?([a-zA-Z0-9:_-]+)(\s+[^>]*)?>", re.IGNORECASE)
_RE_A_HREF = re.compile(
    r'<a\s+[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL
)
_RE_LI = re.compile(r"<li\b[^>]*>(.*?)</li>", re.IGNORECASE | re.DOTALL)
_RE_UL = re.compile(r"<ul\b[^>]*>(.*?)</ul>", re.IGNORECASE | re.DOTALL)
_RE_P = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
_RE_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)


def _safe_href(href: str):
    if not href:
        return None
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return None


def _sanitize_html_to_telegram(html: str) -> str:
    if not html:
        return ""

    s = html

    for src, dst in _TAG_NORMALIZE.items():
        s = re.sub(
            fr"</?{src}\b",
            lambda m: m.group(0).replace(src, dst),
            s,
            flags=re.IGNORECASE,
        )

    s = _RE_BR.sub("\n", s)

    def _p_repl(m):
        inner = m.group(1).strip()
        return inner + "\n\n"

    s = _RE_P.sub(_p_repl, s)

    def _ul_repl(m):
        inner = m.group(1)
        bullets = _RE_LI.sub(
            lambda mm: "• " + mm.group(1).strip() + "\n", inner
        )
        return bullets + "\n"

    s = _RE_UL.sub(_ul_repl, s)

    def _a_repl(m):
        href = m.group(1)
        inner = m.group(2).strip()
        good = _safe_href(href)
        if good:
            return f'<a href="{good}">{inner}</a>'
        return inner

    s = _RE_A_HREF.sub(_a_repl, s)

    def _tag_repl(m):
        tag = m.group(1).lower()
        full = m.group(0)

        if full.startswith("</"):
            if tag in _ALLOWED_TAGS:
                return f"</{tag}>"
            return ""

        if tag in _ALLOWED_TAGS:
            return f"<{tag}>"

        return ""

    s = _RE_TAG.sub(_tag_repl, s)

    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    s = re.sub(r"<([biu]|code|pre)>\s*</\1>", "", s)

    return s.strip()


def setup(bot: TeleBot):
    ADMIN_ID = int(os.getenv("MEGAGROK_ADMIN_ID", "0"))
    CHANNEL_ID = os.getenv("LEADERBOARD_CHANNEL_ID")

    if not CHANNEL_ID:
        print("WARNING: LEADERBOARD_CHANNEL_ID is missing. Announcements disabled.")
        CHANNEL_ID = None

    # --------------------------------------------------------
    # /announce  (Markdown announcement)
    # --------------------------------------------------------
    @bot.message_handler(commands=["announce"])
    def announce_markdown(message):
        uid = message.from_user.id
        if uid != ADMIN_ID and not is_megacrew(uid):
            return bot.reply_to(message, "❌ MegaCrew access required.")

        if not CHANNEL_ID:
            return bot.reply_to(message, "❌ LEADERBOARD_CHANNEL_ID not set.")

        parts = message.text.split(" ", 1)
        if len(parts) < 2 or not parts[1].strip():
            return bot.reply_to(message, "Usage:\n/announce <message>")

        content = parts[1].strip()

        try:
            sent = bot.send_message(
                int(CHANNEL_ID),
                f"📢 *Announcement*\n\n{content}",
                parse_mode="Markdown",
            )

            try:
                bot.pin_chat_message(
                    chat_id=int(CHANNEL_ID),
                    message_id=sent.message_id,
                    disable_notification=True,
                )
            except Exception as e:
                bot.reply_to(
                    message,
                    f"⚠️ Announcement sent but could not pin:\n{e}",
                )

            bot.reply_to(message, "✅ Announcement posted.")

        except Exception:
            bot.reply_to(
                message,
                f"Announcement failed:\n```\n{traceback.format_exc()}\n```",
                parse_mode="Markdown",
            )

    # --------------------------------------------------------
    # /announce_html  (HTML sanitized announcement)
    # --------------------------------------------------------
    @bot.message_handler(commands=["announce_html"])
    def announce_html(message):
        uid = message.from_user.id
        if uid != ADMIN_ID and not is_megacrew(uid):
            return bot.reply_to(message, "❌ MegaCrew access required.")

        if not CHANNEL_ID:
            return bot.reply_to(message, "❌ LEADERBOARD_CHANNEL_ID not set.")

        parts = message.text.split(" ", 1)
        if len(parts) < 2 or not parts[1].strip():
            return bot.reply_to(message, "Usage:\n/announce_html <html>")

        raw_html = parts[1].strip()

        try:
            sanitized = _sanitize_html_to_telegram(raw_html)
            if not sanitized:
                return bot.reply_to(
                    message,
                    "❌ Announcement is empty after sanitization.",
                )

            payload = f"📢 <b>Announcement</b>\n\n{sanitized}"

            sent = bot.send_message(
                int(CHANNEL_ID),
                payload,
                parse_mode="HTML",
                disable_web_page_preview=False,
            )

            try:
                bot.pin_chat_message(
                    chat_id=int(CHANNEL_ID),
                    message_id=sent.message_id,
                    disable_notification=True,
                )
            except Exception as e:
                bot.reply_to(
                    message,
                    f"⚠️ Announcement sent but could not pin:\n{e}",
                )

            bot.reply_to(message, "✅ HTML announcement posted.")

        except Exception:
            bot.reply_to(
                message,
                f"HTML announcement failed:\n```\n{traceback.format_exc()}\n```",
                parse_mode="Markdown",
            )

    # --------------------------------------------------------
    # /announce_preview  (Preview only)
    # --------------------------------------------------------
    @bot.message_handler(commands=["announce_preview"])
    def announce_preview(message):
        uid = message.from_user.id
        if uid != ADMIN_ID and not is_megacrew(uid):
            return bot.reply_to(message, "❌ MegaCrew access required.")

        parts = message.text.split(" ", 1)
        if len(parts) < 2 or not parts[1].strip():
            return bot.reply_to(
                message,
                "Usage:\n/announce_preview <html or markdown text>",
            )

        raw = parts[1].strip()

        try:
            sanitized = _sanitize_html_to_telegram(raw)

            preview_payload = (
                "🧪 <b>Announcement Preview</b>\n\n"
                f"{sanitized}"
            )

            bot.send_message(
                message.chat.id,
                preview_payload,
                parse_mode="HTML",
                disable_web_page_preview=False,
            )

        except Exception:
            bot.reply_to(
                message,
                f"Preview failed:\n```\n{traceback.format_exc()}\n```",
                parse_mode="Markdown",
            )
