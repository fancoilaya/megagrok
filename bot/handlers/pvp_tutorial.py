# bot/handlers/pvp_tutorial.py
# Interactive PvP Tutorial for MegaGrok

from telebot import TeleBot, types

def setup(bot: TeleBot):

    @bot.message_handler(commands=["pvp_tutorial"])
    def pvp_tutorial_start(message):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("▶ Start Tutorial", callback_data="pvp_tut:start"))
        bot.reply_to(message, 
            "🎓 *MEGAGROK PvP TUTORIAL*\n\n"
            "Learn how raids work in an interactive step-by-step guide.\n"
            "Click below to begin!", 
            parse_mode="Markdown", reply_markup=kb
        )


    # ====================================================
    # STEP HANDLERS
    # ====================================================
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp_tut:"))
    def pvp_tutorial_steps(call):
        step = call.data.split(":")[1]
        chat_id = call.message.chat.id
        msg_id = call.message.message_id

        if step == "start":
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Next ➡", callback_data="pvp_tut:flow"))
            bot.edit_message_text(
                "⚔️ *What is PvP Raid?*\n\n"
                "PvP in MegaGrok is asynchronous:\n"
                "You attack another player manually, and the defender is controlled by a smart AI.\n\n"
                "You can attack ANY user:\n"
                "• By replying → `/attack`\n"
                "• By username → `/attack @name`\n"
                "• By searching → `/attack name`\n"
                "• From leaderboard → `/pvp_top`\n\n"
                "Press *Next* to continue.",
                chat_id, msg_id, parse_mode="Markdown", reply_markup=kb
            )

        elif step == "flow":
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Next ➡", callback_data="pvp_tut:actions"))
            bot.edit_message_text(
                "🧭 *PvP Flow Overview*\n\n"
                "`Attacker` → starts raid\n"
                "`Defender` → controlled by AI\n"
                "Both sides act turn-by-turn until someone wins.\n\n"
                "You will see HP bars, actions, and results in realtime.\n\n"
                "Press *Next* to learn about actions.",
                chat_id, msg_id, parse_mode="Markdown", reply_markup=kb
            )

        elif step == "actions":
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Next ➡", callback_data="pvp_tut:ai"))
            bot.edit_message_text(
                "🎮 *Your Actions in PvP*\n\n"
                "🗡 *Attack* → Deal damage\n"
                "🛡 *Block* → Reduce next hit\n"
                "💨 *Dodge* → Evade + counterattack\n"
                "⚡ *Charge* → Buff next attack (up to x3)\n"
                "▶ *Auto Mode* → Bot plays for you\n"
                "✖ *Forfeit* → End raid early\n\n"
                "Press *Next* to learn about the AI.",
                chat_id, msg_id, parse_mode="Markdown", reply_markup=kb
            )

        elif step == "ai":
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Next ➡", callback_data="pvp_tut:xp"))
            bot.edit_message_text(
                "🤖 *Defender AI Logic*\n\n"
                "The AI adapts to the situation:\n"
                "• High HP → more attacking\n"
                "• Low HP → more dodging/blocking\n"
                "• Reads your patterns\n"
                "• Uses defender stats (dodge, crit, etc.)\n\n"
                "It behaves similarly to high-tier mobs.\n\n"
                "Press *Next* to continue.",
                chat_id, msg_id, parse_mode="Markdown", reply_markup=kb
            )

        elif step == "xp":
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Next ➡", callback_data="pvp_tut:elo"))
            bot.edit_message_text(
                "💰 *XP Stealing Rules*\n\n"
                "If attacker *wins*:\n"
                "• Steals *7%* of defender XP\n"
                "• Minimum *20 XP*\n\n"
                "If attacker *loses*:\n"
                "• Loses *5%* XP\n\n"
                "Press *Next* to continue.",
                chat_id, msg_id, parse_mode="Markdown", reply_markup=kb
            )

        elif step == "elo":
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Next ➡", callback_data="pvp_tut:shields"))
            bot.edit_message_text(
                "🏆 *ELO Ranking System*\n\n"
                "Every PvP battle adjusts your ELO.\n"
                "• Defeat strong players → large gain\n"
                "• Lose to weaker players → large loss\n"
                "• K-factor = 32\n\n"
                "Rankings visible in `/pvp_top`.\n\n"
                "Press *Next*.",
                chat_id, msg_id, parse_mode="Markdown", reply_markup=kb
            )

        elif step == "shields":
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Next ➡", callback_data="pvp_tut:practice_intro"))
            bot.edit_message_text(
                "🛡 *PvP Shields*\n\n"
                "When a defender loses:\n"
                "• They gain a *3-hour shield*\n"
                "• Shielded players cannot be attacked\n\n"
                "This prevents raid spam.\n\n"
                "Press *Next* to try a practice fight!",
                chat_id, msg_id, parse_mode="Markdown", reply_markup=kb
            )

        # -----------------------------------------------------
        # PRACTICE MODE
        # -----------------------------------------------------
        elif step == "practice_intro":
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Start Practice Fight ⚔️", callback_data="pvp_tut:practice_start"))
            bot.edit_message_text(
                "🎯 *Practice Fight*\n\n"
                "You'll now try a short practice fight against a dummy AI.\n"
                "This battle:\n"
                "• Does NOT affect real XP\n"
                "• Does NOT affect ELO\n"
                "• Lets you test actions safely\n\n"
                "Press the button below to begin!",
                chat_id, msg_id, parse_mode="Markdown", reply_markup=kb
            )

        elif step == "practice_start":
            # Minimal embedded fight logic for tutorial
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("🗡 Attack", callback_data="pvp_tut:pf_attack"),
                types.InlineKeyboardButton("💨 Dodge", callback_data="pvp_tut:pf_dodge"),
            )
            kb.add(
                types.InlineKeyboardButton("🛡 Block", callback_data="pvp_tut:pf_block"),
                types.InlineKeyboardButton("⚡ Charge", callback_data="pvp_tut:pf_charge"),
            )
            kb.add(types.InlineKeyboardButton("⏭ Skip Practice", callback_data="pvp_tut:end"))

            bot.edit_message_text(
                "⚔️ *Practice Fight Started*\n"
                "Choose an action to see how it works.",
                chat_id, msg_id, parse_mode="Markdown", reply_markup=kb
            )

        # Simple explanations for each practice action
        elif step.startswith("pf_"):
            action = step[3:]
            explanations = {
                "attack": "🗡 *Attack:* Deals damage based on Attack - Defense, plus chance to crit.",
                "dodge": "💨 *Dodge:* 25% chance to avoid and counterattack.",
                "block": "🛡 *Block:* Reduces next incoming damage heavily.",
                "charge": "⚡ *Charge:* Increases next attack by 50% per stack (max 3).",
            }
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("Try Another", callback_data="pvp_tut:practice_start"),
                types.InlineKeyboardButton("Continue ➡", callback_data="pvp_tut:end"),
            )
            bot.edit_message_text(
                explanations[action],
                chat_id, msg_id, parse_mode="Markdown", reply_markup=kb
            )

        elif step == "end":
            bot.edit_message_text(
                "🎉 *Tutorial Complete!*\n\n"
                "You now know how to:\n"
                "• Start raids\n"
                "• Use actions\n"
                "• Understand AI\n"
                "• Read XP/ELO mechanics\n\n"
                "Start your first raid by replying to someone with:\n"
                "`/attack`",
                chat_id, msg_id, parse_mode="Markdown"
            )
