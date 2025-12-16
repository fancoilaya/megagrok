# bot/handlers/pvp_help.py
# Explains how the MegaGrok PvP raid system works

from telebot import TeleBot

def setup(bot: TeleBot):

    @bot.message_handler(commands=["pvphelp"])
    def pvp_help(message):

        text = (
            "⚔️ *MEGAGROK PvP RAID SYSTEM*\n\n"
            "Challenge other players in asynchronous raids where *you* fight manually\n"
            "and the opponent is defended by a smart AI.\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🎯 *HOW TO START A RAID*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Start journey with `/pvp`\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "⚔️ *ATTACKER ACTIONS*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🗡 *Attack* — Strike the defender (can crit)\n"
            "🛡 *Block* — Reduce the next hit\n"
            "💨 *Dodge* — 25% chance to evade + counterattack\n"
            "⚡ *Charge* — Boost next attack (stacks up to 3)\n"
            "▶️ *Heal* — Heals 20% of your max HP\n"
            "✖ *Forfeit* — Give up the raid\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🤖 *DEFENDER AI (OPPONENT)*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• Makes intelligent decisions each turn\n"
            "• Can dodge, block, or counter\n"
            "• Scales with defender stats\n"
            "• Behaves like a Tier 3–5 mob, but smarter\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "💰 *XP STEALING RULES*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "If the *attacker wins*:\n"
            "• Steals *7% of defender XP*, minimum *20 XP*\n\n"
            "If the *attacker loses*:\n"
            "• Loses 5% XP (defender gains it)\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🏆 *PvP RANKING (ELO)*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• All PvP battles adjust ELO score\n"
            "• Higher ELO = higher rank in `/pvp_top`\n"
            "• K-factor = 32 (moderate ranking movement)\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🛡 *SHIELDS*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• Losing a raid grants a *3-hour shield*\n"
            "• Shielded players cannot be attacked\n"
            "• Prevents raid spam/abuse\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "⭐ *VIP ACCESS*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• PvP is currently in *FREE MODE*\n"
            "• Later: Requires holding MegaGrok tokens\n"
            "• Wallet verification handled by MegaForge VIP system\n\n"

            "Use `/pvphelp` anytime to review the rules."
        )

        bot.reply_to(message, text, parse_mode="Markdown")
