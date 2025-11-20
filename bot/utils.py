import os

def safe_send_gif(bot, chat_id, gif_filename):
    """
    Sends a GIF if it exists in /assets/gifs, otherwise sends fallback text.
    """

    # Adjust this path to match your repo structure
    gif_path = os.path.join("assets", "gifs", gif_filename)

    # If file doesn't exist → fallback
    if not os.path.exists(gif_path):
        bot.send_message(chat_id, "⚔️ (GIF missing) The battle begins!")
        return

    try:
        with open(gif_path, "rb") as f:
            bot.send_animation(chat_id, f)
    except Exception as e:
        # Render sometimes fails with SSL/connection reset errors
        bot.send_message(chat_id, f"⚠️ Could not load GIF, but the fight continues!\nError: {e}")

