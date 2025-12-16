# bot/handlers/pvp_commands.py
# PvP Navigation Command: /pvpcommands
# Clean Markdown-safe version

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
            "• `/pvp` — Start the PvP menu.\n"
            "  Engage in battles, browse targets,\n"
            "  check revenge, stats, and more.\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🛡 *Battle Actions*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "During a PvP match, use action buttons:\n"
            "• 🗡 *Attack* — Deal damage.\n"
            "• 🛡 *Block* — Reduce next incoming damage.\n"
            "• 💨 *Dodge* — Chance to avoid the next hit.\n"
            "• ⚡ *Charge* — Power up your next attack.\n"
            "• 💉 *Heal* — Restore *20%* of max HP.\n"
            "• ❌ *Forfeit* — End the match.\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "📊 *PvP Stats Commands*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• `/pvp_stat` — View your PvP stats.\n"
            "• `/pvp_stat @username` — View another player's stats.\n"
            "Shows wins, losses, ELO, raids, win rate.\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🏆 *Rank & Division Commands*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• `/pvp_ranking` — Shows your rank tier\n"
            "  (Bronze → Legend), ELO rating, and progress.\n"
            "• `/pvp_ranking @username` — Check another player.\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🏅 *Leaderboards*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• `/pvp_top` — Top 10 players by ELO.\n"
            "• `/pvp_leaderboard` — Full division-split ranking:\n"
            "  👑 Legend\n"
            "  💠 Grandmaster\n"
            "  🔥 Master\n"
            "  💎 Diamond\n"
            "  🔷 Platinum\n"
            "  🥇 Gold\n"
            "  🥈 Silver\n"
            "  🥉 Bronze\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🧩 *Tips*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• Use *Dodge* when you expect an attack.\n"
            "• Use *Charge* before big burst damage.\n"
            "• Use *Block* when low HP to survive longer.\n"
            "• Higher-ELO opponents give larger rewards.\n\n"

            "🔥 *Good luck in the arena, Grok Warrior!*"
        )

        bot.reply_to(message, text, parse_mode="Markdown")
