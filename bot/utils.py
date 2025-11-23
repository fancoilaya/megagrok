import os

def safe_send_gif(bot, chat_id, gif_path):
    """
    Sends a GIF using an absolute path (correct behavior for all commands).
    """

    # If file doesn't exist → fallback message
    if not os.path.exists(gif_path):
        bot.send_message(chat_id, "⚔️ (GIF missing) The battle begins!")
        return

    try:
        with open(gif_path, "rb") as f:
            bot.send_animation(chat_id, f)
    except Exception as e:
        bot.send_message(
            chat_id,
            f"⚠️ Could not load GIF, but the fight continues!\nError: {e}"
        )
