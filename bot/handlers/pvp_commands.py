# bot/handlers/pvp_commands.py
# PvP Navigation Command: /pvp_commands
# Gives users a clear overview of all PvP functionality.

from telebot import TeleBot

def setup(bot: TeleBot):

    @bot.message_handler(commands=["pvpcommands"])
    def cmd_pvp_commands(message):

        text = (
            "🗡 *MegaGrok PvP Command Guide*\n"
            "A complete overview of all PvP features.\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "⚔️ *Basic Combat Commands*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• `/pvp` — Start a PvP raid.\n"
            "   This will start the PvP menu\n"
            "   where you can engage in fights\n\n"


            "━━━━━━━━━━━━━━━━━━\n"
            "🛡 *Battle Actions*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "During a PvP match, use the buttons:\n"
            "• 🗡 *Attack* — Deal damage.\n"
            "• 🛡 *Block* — Reduce next incoming damage.\n"
            "• 💨 *Dodge* — Chance to avoid the next hit.\n"
            "• ⚡ *Charge* — Increases next attack damage.\n"
            "• ▶ *Heal* — Heals 20% of max HP*.\n"
            "• ❌ *Forfeit* — Immediately end the match.\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "📊 *PvP Stats Commands*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• `/pvp_stat` — View your personal PvP performance.\n"
            "• `/pvp_stat @username` — View PvP stats for someone else.\n"
            "• Shows wins, losses, ELO, raids, win rate.\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🏆 *Rank & Division Commands*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• `/pvp_ranking` — Shows your current\n"
            "  rank tier (Bronze → Legend), ELO score,\n"
            "  and progress to the next rank.\n\n"
            "• `/pvp_ranking @username` — Check another player.\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🏅 *Leaderboards*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• `/pvp_top` — Top 10 PvP players by ELO.\n"
            "• `/pvp_leaderboard` — Ranking split into divisions:\n"
            "  • 👑 Legend\n"
            "  • 💠 Grandmaster\n"
            "  • 🔥 Master\n"
            "  • 💎 Diamond\n"
            "  • 🔷 Platinum\n"
            "  • 🥇 Gold\n"
            "  • 🥈 Silver\n"
            "  • 🥉 Bronze\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🧩 *Tips*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• Use Dodge right before opponent attacks.\n"
            "• Use Charge for massive burst damage.\n"
            "• Block when low HP to survive one more turn.\n"
            "• High ELO opponents give bigger ELO gains.\n\n"

            "🔥 *Good luck in the arena!*"
        )

        bot.reply_to(message, text, parse_mode="Markdown")
