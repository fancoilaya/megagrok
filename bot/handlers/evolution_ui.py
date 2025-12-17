# bot/handlers/evolution_ui.py
# Evolution Codex UI — XP Hub integrated

from telebot import TeleBot, types
from bot.db import get_user
import bot.evolutions as evolutions
import os


# ----------------------------
# Asset helpers
# ----------------------------
def _grok_image_for_stage(stage_name: str) -> str | None:
    """
    Map evolution name -> asset path.
    Falls back gracefully if image missing.
    """
    fname = stage_name.lower().replace(" ", "_") + ".png"
    path = f"assets/groks/{fname}"
    return path if os.path.exists(path) else None


def _progress_bar(cur: int, nxt: int, length: int = 12):
    if nxt <= 0:
        return "░" * length, 0
    pct = int((cur / nxt) * 100)
    filled = max(0, min(length, int((pct / 100) * length)))
    bar = "▓" * filled + "░" * (length - filled)
    return bar, pct


# ----------------------------
# MAIN UI
# ----------------------------
def show_evolution_ui(bot: TeleBot, chat_id: int, message_id: int, uid: int):
    user = get_user(uid)
    if not user:
        bot.edit_message_text("❌ No Grok found.", chat_id, message_id)
        return

    level = int(user.get("level", 1))
    cur_xp = int(user.get("xp_current", 0))
    nxt_xp = int(user.get("xp_to_next_level", 100))

    current = evolutions.get_evolution_for_level(level)
    tiers = evolutions.EVOLUTION_TIERS

    stage_idx = current["stage"]
    stage_name = current["name"]
    xp_mult = current.get("xp_multiplier", 1.0)
    fight_bonus = current.get("fight_bonus", 0)
    ritual_bonus = current.get("ritual_bonus", 0)

    # Next evolution
    next_stage = None
    if stage_idx + 1 < len(tiers):
        next_stage = tiers[stage_idx + 1]

    bar, pct = _progress_bar(cur_xp, nxt_xp)

    # Image (optional)
    img_path = _grok_image_for_stage(stage_name)
    img_note = f"\n🖼️ <i>{img_path}</i>\n" if img_path else "\n🖼️ <i>(Image locked)</i>\n"

    # ----------------------------
    # Build text
    # ----------------------------
    parts = []

    parts.append("🧬 <b>GROK EVOLUTION</b>")
    parts.append(
        "Your Grok evolves automatically as it gains levels.\n"
        "Each evolution increases power, XP gain,\n"
        "and unlocks new abilities."
    )

    parts.append("━━━━━━━━━━━━━━")
    parts.append("<b>CURRENT FORM</b>")
    parts.append(img_note)
    parts.append(
        f"<b>{stage_name}</b>\n"
        f"Stage {stage_idx} • Level {current['min_level']}+\n\n"
        f"📈 XP Multiplier: <b>x{xp_mult:.2f}</b>\n"
        f"⚔️ Fight Bonus: <b>+{fight_bonus}</b>\n"
        f"🌀 Ritual Bonus: <b>+{ritual_bonus}</b>"
    )

    if next_stage:
        parts.append("━━━━━━━━━━━━━━")
        parts.append("<b>NEXT EVOLUTION</b>")
        parts.append(
            f"{next_stage['name']}\n"
            f"Unlocks at Level <b>{next_stage['min_level']}</b>\n\n"
            f"📈 XP Multiplier: x{next_stage['xp_multiplier']:.2f}\n"
            f"⚔️ Fight Bonus: +{next_stage.get('fight_bonus', 0)}\n"
            f"🌀 Ritual Bonus: +{next_stage.get('ritual_bonus', 0)}\n\n"
            f"Progress:\n"
            f"<code>{bar}</code> {pct}%"
        )

    parts.append("━━━━━━━━━━━━━━")
    parts.append("<b>EVOLUTION PATH</b>")

    for tier in tiers:
        icon = "⭐" if tier["stage"] == stage_idx else "🔒"
        parts.append(
            f"{icon} {tier['name']} "
            f"(Lv {tier['min_level']}) "
            f"x{tier['xp_multiplier']:.2f}"
        )

    text = "\n\n".join(parts)

    # ----------------------------
    # Buttons
    # ----------------------------
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🌱 Grow", callback_data="xphub:grow"),
        types.InlineKeyboardButton("🐾 Hop", callback_data="xphub:hop"),
    )
    kb.add(
        types.InlineKeyboardButton("🔙 Back to XP Hub", callback_data="xphub:home")
    )

    bot.edit_message_text(
        text,
        chat_id,
        message_id,
        reply_markup=kb,
        parse_mode="HTML"
    )
