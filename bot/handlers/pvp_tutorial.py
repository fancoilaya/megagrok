# bot/handlers/pvp_tutorial.py
# MegaGrok PvP Tutorial — Paginated Version (SAFE + SELF-CONTAINED)

from telebot import TeleBot, types

# ----------------------------------------
# TUTORIAL STEPS (edit freely)
# ----------------------------------------
TUTORIAL_STEPS = [
    {
        "title": "Welcome to the PvP Tutorial",
        "text": (
            "🔥 *Welcome to MegaGrok PvP!*\n\n"
            "In this tutorial, you will learn:\n"
            "• How raids work\n"
            "• How actions affect combat\n"
            "• How ELO & ranks function\n"
            "• How to improve your win rate\n\n"
            "Press *Next ▶* to begin."
        )
    },
    {
        "title": "How Raids Work",
        "text": (
            "⚔️ *Raids Explained*\n\n"
            "• You attack another player.\n"
            "• Combat is turn-based.\n"
            "• You choose an action each turn.\n"
            "• Battle ends when one side reaches 0 HP.\n\n"
            "Your goal: *win efficiently*."
        )
    },
    {
        "title": "Combat Actions",
        "text": (
            "🛡 *Actions Overview*\n\n"
            "• 🗡 *Attack* — Deal damage.\n"
            "• 🛡 *Block* — Reduce incoming damage.\n"
            "• 💨 *Dodge* — Chance to avoid next hit.\n"
            "• ⚡ *Charge* — Boost your next attack.\n"
            "• 💉 *Heal* — Restore 20% max HP.\n"
            "• ❌ *Forfeit* — End immediately.\n\n"
            "Master these to control every fight."
        )
    },
    {
        "title": "ELO & Ranks",
        "text": (
            "🏅 *Rank System*\n\n"
            "You earn or lose ELO after each PvP match.\n\n"
            "Higher ranks give better rewards.\n\n"
            "Tiers include:\n"
            "🥉 Bronze → 🥈 Silver → 🥇 Gold → 💎 Diamond → 🔥 Master → 💠 Grandmaster → 👑 Legend"
        )
    },
    {
        "title": "Revenge & Shields",
        "text": (
            "🛡 *Revenge / Shield Mechanics*\n\n"
            "• You can take *revenge* on attackers.\n"
            "• Victims get an automatic *Shield* after losing.\n"
            "• Shield prevents further raids temporarily.\n"
            "• Revenge clears the attacker from your log.\n\n"
            "Use this for strategic counter-raids."
        )
    },
    {
        "title": "Recommended Targets",
        "text": (
            "🎯 *Recommended Targets*\n\n"
            "The system suggests fair fights based on:\n"
            "• Level\n"
            "• Power\n"
            "• Recent activity\n\n"
            "Use this menu to farm ELO safely."
        )
    },
    {
        "title": "Advanced Tips",
        "text": (
            "🎓 *Pro Tips*\n\n"
            "• Dodge right before enemy attacks.\n"
            "• Charge for huge burst damage.\n"
            "• Block to survive low HP moments.\n"
            "• Focus on favorable matchups.\n\n"
            "Winning is *information + timing*."
        )
    },
    {
        "title": "Tutorial Complete",
        "text": (
            "🎉 *You've completed the PvP Tutorial!*\n\n"
            "You now understand:\n"
            "• Raids\n"
            "• Actions\n"
            "• Ranks\n"
            "• Strategy\n\n"
            "You are ready for the arena. ⚔️"
        )
    },
]

TOTAL_STEPS = len(TUTORIAL_STEPS)


# ----------------------------------------
# BUILD STEP MESSAGE
# ----------------------------------------
def build_step_message(step: int):
    data = TUTORIAL_STEPS[step]
    title = data["title"]
    text = data["text"]
    progress = f"*Step {step+1}/{TOTAL_STEPS} — {title}*\n\n"
    return progress + text


# ----------------------------------------
# KEYBOARD BUILDER
# ----------------------------------------
def tutorial_keyboard(step: int):
    kb = types.InlineKeyboardMarkup(row_width=2)
    buttons = []

    if step > 0:
        buttons.append(
            types.InlineKeyboardButton("◀️ Prev", callback_data=f"pvp_tutorial:step:{step-1}")
        )
    if step < TOTAL_STEPS - 1:
        buttons.append(
            types.InlineKeyboardButton("Next ▶️", callback_data=f"pvp_tutorial:step:{step+1}")
        )

    if buttons:
        kb.add(*buttons)

    kb.add(
        types.InlineKeyboardButton("🔙 Exit Tutorial", callback_data="pvp_tutorial:exit")
    )
    return kb


# ----------------------------------------
# EXPORTED FUNCTION (Fixes your crash)
# ----------------------------------------
def show_tutorial_for_user(bot: TeleBot, chat_id: int, start_step: int = 0):
    """
    SAFE ENTRY POINT called from pvp.py
    """
    step = max(0, min(start_step, TOTAL_STEPS - 1))
    msg = build_step_message(step)
    kb = tutorial_keyboard(step)

    bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=kb)


# ----------------------------------------
# SETUP (Callbacks)
# ----------------------------------------
def setup(bot: TeleBot):

    # Command handler
    @bot.message_handler(commands=["pvp_tutorial"])
    def cmd_pvp_tutorial(message):
        show_tutorial_for_user(bot, message.chat.id, 0)

    # Pagination handler
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pvp_tutorial:step"))
    def cb_step(call):
        _, _, step_str = call.data.split(":")
        step = int(step_str)

        msg = build_step_message(step)
        kb = tutorial_keyboard(step)

        bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=kb
        )
        bot.answer_callback_query(call.id)

    # Exit handler
    @bot.callback_query_handler(func=lambda c: c.data == "pvp_tutorial:exit")
    def cb_exit(call):
        bot.edit_message_text(
            "📘 *Exited the PvP Tutorial.*",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "Closed.")
