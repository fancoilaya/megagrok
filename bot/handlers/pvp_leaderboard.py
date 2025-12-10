# bot/handlers/pvp_leaderboard.py
# PvP Ranked Leaderboard — grouped by Rank tiers

from telebot import TeleBot
import bot.db as db


# ------------------------------
# Rank thresholds (same as pvp_ranking)
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


def get_display_name(user):
    if not user:
        return "Unknown"
    if user.get("display_name"):
        return user["display_name"]
    if user.get("username"):
        return "@" + user["username"]
    return f"User{user.get('user_id')}"


def elo_to_rank(elo: int):
    for rank, threshold in RANKS:
        if elo >= threshold:
            return rank
    return "Bronze"


def setup(bot: TeleBot):

    @bot.message_handler(commands=["pvp_leaderboard"])
    def cmd_pvp_leaderboard(message):

        # Load all users with ELO
        try:
            rows = db.cursor.execute(
                """
                SELECT user_id, display_name, username, elo_pvp, xp_total
                FROM users
                WHERE elo_pvp IS NOT NULL
                ORDER BY elo_pvp DESC, xp_total DESC
                LIMIT 200
                """
            ).fetchall()
        except Exception as e:
            return bot.reply_to(
                message,
                f"Database error:\n`{e}`",
                parse_mode="Markdown"
            )

        if not rows:
            return bot.reply_to(message, "No PvP ELO data available yet.")

        # Organize by rank groups
        leaderboard = {rank[0]: [] for rank in RANKS}

        for row in rows:
            uid, disp, uname, elo, xp = row
            rank = elo_to_rank(elo)

            name = disp or (f"@{uname}" if uname else f"User{uid}")

            leaderboard[rank].append((name, elo, xp))

        # Build output
        text = "🏆 *PvP Ranked Leaderboard*\n\n"

        RANK_EMOJI = {
            "Legend": "👑",
            "Grandmaster": "💠",
            "Master": "🔥",
            "Diamond": "💎",
            "Platinum": "🔷",
            "Gold": "🥇",
            "Silver": "🥈",
            "Bronze": "🥉",
        }

        for rank_name, threshold in RANKS:
            players = leaderboard[rank_name]
            if not players:
                continue

            emoji = RANK_EMOJI.get(rank_name, "⭐")
            text += f"{emoji} *{rank_name} Division*\n"

            for idx, (name, elo, xp) in enumerate(players, 1):
                text += f"{idx}. {name} — {elo} ELO\n"

            text += "\n"

        bot.reply_to(message, text, parse_mode="Markdown")
