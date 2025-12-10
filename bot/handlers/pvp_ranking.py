# bot/handlers/pvp_ranking.py
# PvP Ranking System — Rank badges based on ELO.

from telebot import TeleBot
import bot.db as db


# ------------------------------
# Rank thresholds
# ------------------------------
RANKS = [
    ("Legend",        2300),
    ("Grandmaster",   2000),
    ("Master",        1800),
    ("Diamond",       1600),
    ("Platinum",      1400),
    ("Gold",          1200),
    ("Silver",        1000),
    ("Bronze",        0),
]


def elo_to_rank(elo: int):
    for rank, threshold in RANKS:
        if elo >= threshold:
            return rank, threshold
    return "Bronze", 0


def get_display_name(user):
    if not user:
        return "Unknown"
    if user.get("display_name"):
        return user["display_name"]
    if user.get("username"):
        return "@" + user["username"]
    return f"User{user.get('user_id')}"


def setup(bot: TeleBot):

    @bot.message_handler(commands=["pvp_ranking"])
    def cmd_pvp_ranking(message):

        # Determine target user
        target_id = message.from_user.id

        # If user replied to someone
        if message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
        else:
            # If command has an argument
            parts = message.text.split()
            if len(parts) > 1:
                q = parts[1]
                if q.startswith("@"):
                    row = db.get_user_by_username(q)
                    if row:
                        target_id = row[0] if isinstance(row, (list, tuple)) else row
                else:
                    matches = db.search_users_by_name(q)
                    if matches:
                        target_id = matches[0][0]

        # Fetch user
        user = db.get_user(target_id)
        if not user:
            return bot.reply_to(message, "User not found in the database.")

        name = get_display_name(user)
        elo = user.get("elo_pvp", 1000)

        rank, threshold = elo_to_rank(elo)

        # Find next rank (if any)
        next_rank = None
        for r, th in RANKS:
            if th > threshold:
                next_rank = (r, th)
                break

        if next_rank:
            nr_name, nr_threshold = next_rank
            progress = round((elo - threshold) / (nr_threshold - threshold) * 100, 1)
            next_line = f"➡️ Next Rank: *{nr_name}* at {nr_threshold} ELO\nProgress: *{progress}%*"
        else:
            next_line = "👑 You are at the *highest rank!*"

        text = (
            f"🏆 *PvP Ranking for {name}*\n\n"
            f"• 🏅 *Rank:* {rank}\n"
            f"• ⭐ *ELO:* {elo}\n"
            f"\n"
            f"{next_line}\n"
        )

        bot.reply_to(message, text, parse_mode="Markdown")
