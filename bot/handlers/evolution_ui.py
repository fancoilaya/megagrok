# bot/handlers/evolution_ui.py
# Static Evolution Codex — SAFE VERSION
# Zero DB access
# Zero dependency on evolutions.py internals

from telebot import TeleBot, types


def show_evolution_ui(bot: TeleBot, chat_id: int, message_id: int, uid=None):
    """
    Static, knowledge-only Evolution Codex.
    No user state. No DB. No dynamic logic.
    """

    text = (
        "🧬 <b>GROK EVOLUTION SYSTEM</b>\n\n"
        "Groks evolve automatically as they gain levels.\n"
        "Each evolution increases XP efficiency and power.\n"
        "Higher forms unlock deeper game potential.\n\n"
        "━━━━━━━━━━━━━━\n\n"

        "<b>🐸 TADPOLE</b>\n"
        "Unlocks at Level <b>1</b>\n"
        "XP Multiplier: <b>x1.00</b>\n\n"
        "The earliest Grok form.\n"
        "Focused on learning, survival, and steady growth.\n\n"

        "━━━━━━━━━━━━━━\n\n"

        "<b>🐊 HOPPER</b>\n"
        "Unlocks at Level <b>5</b>\n"
        "XP Multiplier: <b>x1.10</b>\n\n"
        "A faster, more agile Grok.\n"
        "XP gains accelerate as training intensifies.\n\n"

        "━━━━━━━━━━━━━━\n\n"

        "<b>⚔️ BATTLE HOPPER</b>\n"
        "Unlocks at Level <b>10</b>\n"
        "XP Multiplier: <b>x1.25</b>\n\n"
        "A combat-oriented evolution.\n"
        "Prepared for PvP and competitive encounters.\n\n"

        "━━━━━━━━━━━━━━\n\n"

        "<b>🌌 VOID HOPPER</b>\n"
        "Unlocks at Level <b>18</b>\n"
        "XP Multiplier: <b>x1.45</b>\n\n"
        "A Grok touched by the Void.\n"
        "XP efficiency and power rise significantly.\n\n"

        "━━━━━━━━━━━━━━\n\n"

        "<b>🗿 TITAN</b>\n"
        "Unlocks at Level <b>28</b>\n"
        "XP Multiplier: <b>x1.70</b>\n\n"
        "A massive and dominant form.\n"
        "Built to overwhelm opponents in the arena.\n\n"

        "━━━━━━━━━━━━━━\n\n"

        "<b>✨ CELESTIAL</b>\n"
        "Unlocks at Level <b>40</b>\n"
        "XP Multiplier: <b>x2.00</b>\n\n"
        "A cosmic evolution.\n"
        "Only elite Groks ever reach this form.\n\n"

        "━━━━━━━━━━━━━━\n\n"

        "<b>👁 OMNIGROK</b>\n"
        "Unlocks at Level <b>55</b>\n"
        "XP Multiplier: <b>x2.20</b>\n\n"
        "The final evolution.\n"
        "A Grok that has mastered every system."
    )

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton(
            "🔙 Back to XP Hub",
            callback_data="__xphub__:home"
        )
    )

    bot.edit_message_text(
        text,
        chat_id,
        message_id,
        reply_markup=kb,
        parse_mode="HTML"
    )
