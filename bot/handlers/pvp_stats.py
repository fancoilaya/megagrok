# bot/handlers/pvp_stats.py
# PvP Stats + PvP Top Leaderboard (fully compatible with new PvP system)

from telebot import TeleBot, types
import bot.db as db


def get_display_name(user):
    if not user:
        return "Unknown"
    if user.get("display_name"):
        return user["display_name"]
    if user.get("username"):
        return "@" + user["username"]
    return f"User{user.get('user_id')}"


def setup(bot: TeleBot):

    # ==========================================
    # /pvp_stat — Show personal PvP stats
    # ==========================================
    @bot.message_handler(commands=["pvp_stat"])
    def cmd_pvp_stat(message):
        uid = message.from_user.id
        user = db.get_user(uid)

        if not user:
            return bot.reply_to(message, "User not found in database.")

        name = get_display_name(user)

        wins = user.get("pvp_wins", 0)
        losses = user.get("pvp_losses", 0)
        started = user.get("pvp_fights_started", 0)
        received = user.get("pvp_challenges_received", 0)
        elo = user.get("elo_pvp", 1000)

        text = (
            f"🏟 *PvP Stats for {name}*\n\n"
            f"• 🏅 *ELO:* {elo}\n"
            f"• 🥇 *Wins:* {wins}\n"
            f"• 💀 *Losses:* {losses}\n"
            f"• ⚔️ *Raids Started:* {started}\n"
            f"• 🛡 *Raids Defended:* {received}\n"
            f"\n"
            f"Win Rate: {round((wins / max(1, wins + losses)) * 100, 1)}%\n"
        )

        bot.reply_to(message, text, parse_mode="Markdown")

    # ==========================================
    # /pvp_top — Global PvP leaderboard
    # ==========================================
    @bot.message_handler(commands=["pvp_top"])
    def cmd_pvp_top(message):

        # Fetch top 10 players by ELO
        try:
            rows = db.cursor.execute(
                """
                SELECT user_id, display_name, username, elo_pvp, pvp_wins, pvp_losses, xp_total
                FROM users
                ORDER BY elo_pvp DESC, xp_total DESC
                LIMIT 10
                """
            ).fetchall()
        except Exception as e:
            return bot.reply_to(message, f"Database error:\n`{e}`", parse_mode="Markdown")

        if not rows:
            return bot.reply_to(message, "No PvP data available yet.")

        text = "🏆 *Top PvP Players*\n\n"

        rank = 1
        for row in rows:
            uid, disp, uname, elo, wins, losses, xp = row

            name = disp or (f"@{uname}" if uname else f"User{uid}")
            wr = round((wins / max(1, wins + losses)) * 100, 1)

            text += (
                f"*{rank}. {name}*\n"
                f"   🏅 ELO: {elo}\n"
                f"   🥇 Wins: {wins}   💀 Losses: {losses}\n"
                f"   🎯 WR: {wr}%\n\n"
            )
            rank += 1

        bot.reply_to(message, text, parse_mode="Markdown")
