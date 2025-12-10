# bot/handlers/pvp_infographic.py
# Visual infographic overview of the PvP system (ASCII-based)

from telebot import TeleBot

def setup(bot: TeleBot):

    @bot.message_handler(commands=["pvp_infographic"])
    def infographic(message):

        text = (
            "🎨 *MEGAGROK PvP INFOGRAPHIC*\n"
            "A visual guide to how raids work.\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "⚔️ *PvP FLOW OVERVIEW*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "          ┌──────────────┐\n"
            "          │   Attacker    │\n"
            "          └───────┬──────┘\n"
            "                  │ starts raid\n"
            "                  ▼\n"
            "        ┌─────────────────────┐\n"
            "        │ Defender (AI control)│\n"
            "        └─────────────────────┘\n"
            "                  ▼\n"
            "         Battle begins in chat\n"
            "                  ▼\n"
            "  Attacker uses actions: Attack / Block / Dodge / Charge / Auto\n"
            "                  ▼\n"
            "   Defender AI counters with tactics\n"
            "                  ▼\n"
            "        Outcome: Win or Loss\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🧱 *ACTION SYSTEM*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🗡 Attack      → Deal damage (crit possible)\n"
            "🛡 Block       → Reduce incoming damage\n"
            "💨 Dodge       → Chance to avoid & counter\n"
            "⚡ Charge      → Power up next attack (x3)\n"
            "▶ Auto Mode   → Bot fights for you\n"
            "✖ Forfeit     → Immediate loss\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🤖 *DEFENDER AI LOGIC*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "The AI evaluates:\n"
            "• HP% (if low → more block/dodge)\n"
            "• Your attack patterns\n"
            "• Defender stats (dodge/defense)\n"
            "• Random unpredictability\n\n"

            "AI Behavior Matrix:\n"
            "┌───────────────┬───────────────┐\n"
            "│ Situation      │ AI Tendency   │\n"
            "├───────────────┼───────────────┤\n"
            "│ High HP        │ Attack more   │\n"
            "│ Mid HP         │ Mix actions   │\n"
            "│ Low HP (<30%)  │ Dodge/Block   │\n"
            "└───────────────┴───────────────┘\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "💰 *XP STEALING DIAGRAM*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Attacker Wins → Steals XP\n"
            "    │\n"
            "    ▼\n"
            "  7% of defender total XP\n"
            "  Minimum 20 XP\n\n"
            "Attacker Loses → Loses XP\n"
            "    │\n"
            "    ▼\n"
            "  5% XP given to defender\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🏆 *ELO RANKING FLOW*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "                     ┌──────────────┐\n"
            "                     │    You        │\n"
            "                     └─────┬────────┘\n"
            "                           │ Win/Loss\n"
            "                           ▼\n"
            "   ELO adjusts based on opponent strength\n"
            "                           ▼\n"
            "             Higher ELO → Higher rank\n"
            "                     Use `/pvp_top`\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🛡 *SHIELD SYSTEM*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Defender loses → gains *3-hour shield*:\n"
            "• Cannot be attacked during shield\n"
            "• Prevents spam-raiding\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "⭐ *VIP ACCESS (COMING LATER)*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "PvP is currently free.\n"
            "Later: Requires holding MegaGrok tokens.\n\n"

            "Use `/pvp_help` for full text version.\n"
            "Use `/attack` to begin a raid.\n"
        )

        bot.reply_to(message, text, parse_mode="Markdown")
