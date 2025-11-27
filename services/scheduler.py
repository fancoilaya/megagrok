# services/scheduler.py
"""
Grokpedia Auto-Poster Scheduler

Runs a background thread that posts a Grokpedia fact
every X hours to a configured Telegram channel or group.

Environment variable required:
    GROKPEDIA_CHANNEL_ID    (e.g. "-1001234567890")

Usage in main.py:
    from services import scheduler
    scheduler.start_grokpedia_autopost(bot)
"""

import os
import time
import threading
import traceback

from services import grokpedia_service


# How often to post a new Grokpedia fact (in seconds)
POST_INTERVAL = 1 * 15 * 60   # 3 hours


def _poster_loop(bot, channel_id: str):
    """
    Background loop that posts a new Grokpedia fact every POST_INTERVAL seconds.
    Runs in its own daemon thread.
    """
    print(f"[GROKPEDIA] Auto-post thread started. Interval={POST_INTERVAL}s → Channel={channel_id}")

    while True:
        try:
            fact = grokpedia_service.get_random()
            text = _format_fact(fact)

            bot.send_message(channel_id, text)
            print(f"[GROKPEDIA] Posted fact #{fact.get('id')} to {channel_id}")

        except Exception as e:
            print("⚠ [GROKPEDIA] Error while auto-posting:")
            traceback.print_exc()

        # Sleep regardless of errors to avoid rapid loops
        time.sleep(POST_INTERVAL)


# Borrow the same formatting the handler uses
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


def _format_fact(fact: dict) -> str:
    """
    Formats a Grokpedia fact for sending to Telegram.
    This duplicates the handler version so scheduler can run independently.
    """
    category = fact.get("category")
    emoji = CATEGORY_EMOJIS.get(category, "📘")

    header = f"{emoji} Grokpedia Fact #{fact.get('id', '??')}"
    if fact.get("title"):
        header += f" — {fact['title']}"

    body = fact.get("text", "")
    return f"{header}\n\n{body}"


def start_grokpedia_autopost(bot):
    """
    Called from main.py

    Starts the Grokpedia auto-poster IF both:
    - channel ID environment variable exists
    - bot instance is valid

    Does nothing if GROKPEDIA_CHANNEL_ID is missing.
    """
    channel_id = os.getenv("GROKPEDIA_CHANNEL_ID")

    if not channel_id:
        print("⚠ GROKPEDIA_CHANNEL_ID not set — auto-post disabled.")
        return

    print(f"✔ GROKPEDIA auto-poster enabled → will post every 3 hours to {channel_id}")

    t = threading.Thread(
        target=_poster_loop,
        args=(bot, channel_id),
        daemon=True
    )
    t.start()
