# bot/handlers/grokpedia.py
"""
TeleBot-compatible handler for Grokpedia.

Provides:
 - /grokpedia [category]
 - /grokfact  (alias)
 - /grokpedia_help

Loads data from services/grokpedia_service.py

This module exposes setup(bot), which is required
by your main.py modular handler loader.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Category-specific emojis
CATEGORY_EMOJIS = {
    "megagrok": "💥",
    "villains": "😈",
    "grokcity": "🏙️",
    "artifacts": "🔮",
    "physics": "🌌",
    "community": "🫂",
    "mysteries": "🕵️‍♂️",
    "events": "🎉"
}


def _get_service():
    """
    Lazy-loads the Grokpedia service to prevent import errors on boot.
    """
    try:
        from services import grokpedia_service  # type: ignore
        return grokpedia_service
    except Exception as e:
        logger.exception("Failed to import grokpedia_service: %s", e)
        return None


def _format_fact(fact: dict) -> str:
    """
    Converts a raw fact dict into a formatted Telegram message.
    """
    category = fact.get("category")
    emoji = CATEGORY_EMOJIS.get(category, "📘")

    header = f"{emoji} Grokpedia Fact #{fact.get('id', '??')}"
    if fact.get("title"):
        header += f" — {fact['title']}"

    body = fact.get("text", "")
    return f"{header}\n\n{body}"


def _handle_grokpedia(message, bot, args_text: Optional[str]):
    """
    Logic shared between /grokpedia and /grokfact.
    """
    svc = _get_service()
    if svc is None:
        bot.reply_to(message, "Grokpedia service unavailable.")
        return

    # Extract category if specified
    category = args_text.strip() if args_text else None

    try:
        fact = svc.get_random(category)
    except ValueError as e:
        # Invalid category
        bot.reply_to(message, str(e))
        return
    except Exception as e:
        logger.exception("Error fetching Grokpedia fact: %s", e)
        bot.reply_to(message, "Error fetching Grokpedia fact.")
        return

    text = _format_fact(fact)
    bot.send_message(message.chat.id, text)


# ==========================================================
# SETUP (called automatically by your modular loader)
# ==========================================================
def setup(bot):
    """
    Registers all Grokpedia commands with the TeleBot instance.
    """

    @bot.message_handler(commands=["grokpedia"])
    def cmd_grokpedia(message):
        text = message.text or ""
        parts = text.split(None, 1)
        args_text = parts[1] if len(parts) > 1 else None
        _handle_grokpedia(message, bot, args_text)

    @bot.message_handler(commands=["grokfact"])
    def cmd_grokfact(message):
        text = message.text or ""
        parts = text.split(None, 1)
        args_text = parts[1] if len(parts) > 1 else None
        _handle_grokpedia(message, bot, args_text)

    @bot.message_handler(commands=["grokpedia_help"])
    def cmd_help(message):
        svc = _get_service()
        if svc and hasattr(svc, "get_categories"):
            try:
                cats = svc.get_categories()
                categories = ", ".join(sorted(cats)) if cats else "(none)"
            except Exception:
                categories = "error"
        else:
            categories = "unavailable"

        help_text = (
            "📘 *Grokpedia Commands*\n"
            "/grokpedia [category] — get a random Grokpedia fact\n"
            "/grokfact — alias for /grokpedia\n"
            "/grokpedia_help — show this help\n\n"
            f"*Available categories:* {categories}"
        )

        # No Markdown V2 escapes — TeleBot handles plaintext safely
        bot.reply_to(message, help_text)

    logger.info("✔ Grokpedia handlers loaded.")
