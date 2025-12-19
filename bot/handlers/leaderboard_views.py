# bot/handlers/leaderboard_views.py
#
# UI renderers for leaderboards.
# NO database logic. NO bot calls.
# Pure formatting only.

from typing import List, Dict, Optional


def render_grok_evolution_leaderboard(
    top_users: List[Dict],
    current_user: Optional[Dict] = None
) -> str:
    """
    Renders the Grok Evolution Leaderboard (XP / Level based)

    Expected keys per user dict:
    - display_name
    - level
    - xp_total
    - evolution (optional)
    - rank (for current_user)
    - xp_to_top10 (optional, current_user)
    """

    lines: List[str] = []

    # -------------------------------------------------
    # HEADER
    # -------------------------------------------------
    lines.append(
        "🧬 <b>GROK EVOLUTION LEADERBOARD</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "The most evolved Groks in the world.\n"
        "Forged through training and time.\n"
    )

    # -------------------------------------------------
    # TOP 3 (HERO SECTION)
    # -------------------------------------------------
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(top_users[:3]):
        lines.append(
            f"{medals[i]} <b>#{i + 1}  {u['display_name']}</b>\n"
            f"🧬 {u.get('evolution', 'Unknown Form')}\n"
            f"⚡ Level {u['level']} · {u['xp_total']:,} XP\n"
        )

    # -------------------------------------------------
    # REST OF TOP 10
    # -------------------------------------------------
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    for i, u in enumerate(top_users[3:10], start=4):
        lines.append(
            f"#{i:<2}  {u['display_name']:<14} "
            f"⚡ Lv {u['level']} · {u['xp_total']:,} XP"
        )

    # -------------------------------------------------
    # PERSONAL CONTEXT
    # -------------------------------------------------
    if current_user:
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(
            f"📍 <b>Your Rank:</b> #{current_user['rank']}\n"
            f"⚡ Level {current_user['level']} · {current_user['xp_total']:,} XP"
        )

        if current_user.get("xp_to_top10"):
            lines.append(
                f"⬆️ {current_user['xp_to_top10']:,} XP to reach Top 10"
            )

    # -------------------------------------------------
    # FOOTER / CTA
    # -------------------------------------------------
    lines.append(
        "\n━━━━━━━━━━━━━━━━━━━━━━\n"
        "🧠 Train daily in the Training Grounds\n"
        "to evolve your Grok and climb higher."
    )

    return "\n".join(lines)
