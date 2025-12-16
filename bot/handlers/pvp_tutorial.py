# bot/handlers/pvp_tutorial.py
# MEGAGROK PvP Tutorial — Improved UI + Progress Indicators

from telebot import TeleBot, types

# -------------------------------------------------
# PROGRESS BAR BUILDER
# -------------------------------------------------
def build_progress(current, total):
    filled = "● " * current
    empty = "○ " * (total - current)
    return f"*Progress:* {filled}{empty}".strip()


# -------------------------------------------------
# REGISTER TUTORIAL HANDLERS
# -------------------------------------------------
def setup(bot: TeleBot):

    TOTAL_STEPS = 5  # Attack, Block, Dodge, Charge, Heal

    # -------------------------------------------------
    # START COMMAND
    # -------------------------------------------------
    @bot.message_handler(commands=["pvp_tutorial"])
    def start_tutorial_cmd(message):
        show_tutorial_intro(bot, message)

    # -------------------------------------------------
    # MAIN INTRO (called from /pvp or menu)
    # -------------------------------------------------
    def show_tutorial_intro(bot, message):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("▶ Begin Lesson 1", callback_data="pvp_tut:step1"))

        bot.send_message(
            message.chat.id,
            "🎓 *MEGAGROK PvP ACADEMY*\n\n"
            "Welcome, warrior! This training will teach you how PvP raids work:\n"
            "• 🗡 Attacking\n"
            "• 🛡 Blocking\n"
            "• 💨 Dodging\n"
            "• ⚡ Charging\n"
            "• 💉 Healing\n\n"
            "Tap below to begin your journey!",
            parse_mode="Markdown",
            reply_markup=kb
        )

    # -------------------------------------------------
    # LESSON 1 — ATTACK
    # -------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "pvp_tut:step1")
    def tut_step1(call):
        progress = build_progress(1, TOTAL_STEPS)

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("➡ Next: Blocking", callback_data="pvp_tut:step2"))

        bot.edit_message_text(
            "🗡 *Lesson 1 — Attacking*\n\n"
            "Attacking deals direct damage to your opponent.\n\n"
            "• Stronger attack = higher damage\n"
            "• Critical hits happen randomly\n"
            "• Power difference increases impact\n\n"
            f"{progress}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=kb
        )

    # -------------------------------------------------
    # LESSON 2 — BLOCK
    # -------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "pvp_tut:step2")
    def tut_step2(call):
        progress = build_progress(2, TOTAL_STEPS)

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="pvp_tut:step1"))
        kb.add(types.InlineKeyboardButton("➡ Next: Dodging", callback_data="pvp_tut:step3"))

        bot.edit_message_text(
            "🛡 *Lesson 2 — Blocking*\n\n"
            "Blocking reduces incoming damage drastically.\n\n"
            "• Perfect vs ⚡ Charge\n"
            "• Weak vs 💨 Dodge\n"
            "• Use when predicting heavy attacks\n\n"
            f"{progress}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=kb
        )

    # -------------------------------------------------
    # LESSON 3 — DODGE
    # -------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "pvp_tut:step3")
    def tut_step3(call):
        progress = build_progress(3, TOTAL_STEPS)

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="pvp_tut:step2"))
        kb.add(types.InlineKeyboardButton("➡ Next: Charge", callback_data="pvp_tut:step4"))

        bot.edit_message_text(
            "💨 *Lesson 3 — Dodging*\n\n"
            "Dodging avoids all incoming damage if timed right.\n\n"
            "• Perfect counter to 🗡 Attack\n"
            "• Weak vs ⚡ Charge\n"
            "• Sets up guaranteed crits next turn\n\n"
            f"{progress}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=kb
        )

    # -------------------------------------------------
    # LESSON 4 — CHARGE
    # -------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "pvp_tut:step4")
    def tut_step4(call):
        progress = build_progress(4, TOTAL_STEPS)

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="pvp_tut:step3"))
        kb.add(types.InlineKeyboardButton("➡ Next: Healing", callback_data="pvp_tut:step5"))

        bot.edit_message_text(
            "⚡ *Lesson 4 — Charge*\n\n"
            "Charge stores energy to boost your next attack dramatically.\n\n"
            "• Perfect when predicting defensive moves\n"
            "• Counters 💨 Dodge\n"
            "• But loses to 🛡 Block\n\n"
            f"{progress}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=kb
        )

    # -------------------------------------------------
    # LESSON 5 — HEAL
    # -------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "pvp_tut:step5")
    def tut_step5(call):
        progress = build_progress(5, TOTAL_STEPS)

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="pvp_tut:step4"))
        kb.add(types.InlineKeyboardButton("🏁 Finish Tutorial", callback_data="pvp_tut:finish"))

        bot.edit_message_text(
            "💉 *Lesson 5 — Healing*\n\n"
            "Healing restores **20% of max HP**.\n\n"
            "• Useful when behind on HP\n"
            "• Strong when predicting a defensive enemy\n"
            "• Helps reset momentum\n\n"
            f"{progress}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=kb
        )

    # -------------------------------------------------
    # FINISH SCREEN
    # -------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "pvp_tut:finish")
    def tut_finish(call):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(
            "⬅ Back to PvP Menu",
            callback_data=f"pvp:menu:main:{call.from_user.id}"
        ))

        bot.edit_message_text(
            "🎉 *Tutorial Complete!*\n\n"
            "You've mastered the basics of MEGAGROK PvP combat.\n"
            "Now enter the arena and dominate your foes! ⚔️🔥",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=kb
        )

