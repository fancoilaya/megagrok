# bot/handlers/evolution_ui.py
# Static Evolution Codex (Knowledge Screen)
# - NO database access
# - NO user-specific state
# - Pure educational UX
# - Safe for concurrent Telegram callbacks

from telebot import TeleBot, types
import bot.evolutions as evolutions


def show_evolution_ui(bot: TeleBot, chat_id: int, message_id: int, uid: int | None = None):
    """
    Static Evolution Codex.
    uid is accepted for interface compatibility but NOT used.
    """

    tiers = evolutions.EVOLUTION_TIERS

    parts = []

    # ----------------------------
    # Header / Explanation
    # ----------------------------
    parts.append("🧬 <b>GROK EVOLUTION SYSTEM</b>")
    parts.append(
        "Groks evolve automatically as they gain levels.\n"
        "Each evolution increases XP efficiency and power.\n"
        "Higher forms unlock deeper game potential."
    )

    parts.append("━━━━━━━━━━━━━━")

    # ----------------------------
    # Evolution Path (Static)
    # ----------------------------
    for tier in tiers:
        name = tier["name"]
        min_level = tier["min_level"]
        xp_mult = tier.get("xp_multiplier", 1.0)

        # Short, readable descriptions (codex-style)
        description = _evolution_description(name)

        parts.append(
            f"<b>{name}</b>\n"
            f"Unlocks at Level <b>{min_level}</b>\n"
            f"XP Multiplier: <b>x{xp_mult:.2f}</b>\n\n"
            f"{description}"
        )
        parts.append("━━━━━━━━━━━━━━")

    text = "\n\n".join(parts)

    # ----------------------------
    # Navigation
    # ----------------------------
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="__xphub__:home")
    )

    bot.edit_message_text(
        text,
        chat_id,
        message_id,
        reply_markup=kb,
        parse_mode="HTML"
    )


# ----------------------------
# Internal helpers
# ----------------------------
def _evolution_description(name: str) -> str:
    """
    Static lore / explanation per evolution stage.
    Kept short on purpose for Telegram readability.
    """
    descriptions = {
        "Tadpole": (
            "The earliest Grok form.\n"
            "Focused on learning, survival, and steady growth."
        ),
        "Hopper": (
            "A faster, more agile Grok.\n"
            "XP gains accelerate as training intensifies."
        ),
        "Battle Hopper": (
            "A combat-oriented evolution.\n"
            "Prepared for PvP and competitive encounters."
        ),
        "Void Hopper": (
            "A Grok touched by the Void.\n"
            "XP efficiency and power rise significantly."
        ),
        "Titan": (
            "A massive and dominant form.\n"
            "Built to overwhelm opponents in the arena."
        ),
        "Celestial": (
            "A cosmic evolution.\n"
            "Elite-tier Groks reach this form."
        ),
        "OmniGrok": (
            "The final evolution.\n"
            "A Grok that has mastered every system."
        ),
    }

    return descriptions.get(
        name,
        "An evolved Grok form.\nIts power grows with experience."
    )
