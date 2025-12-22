# services/pvp_targets.py
# -------------------------------------------
# Recommended Targets + Revenge Targets
# MegaGrok PvP Targeting & Ranking Helper
#
# This version:
#   ✔ Keeps ALL your original recommended-target logic
#   ✔ Adds deduped revenge feed (max 5)
#   ✔ Adds improved time formatting ("3m ago", "2h ago", etc.)
#   ✔ Adds clear_revenge_for() hook
#   ✔ Fully compatible with pvp.py and fight_session_pvp.py patches
#   ✔ FIXES revenge not clearing (argument order bug)
# -------------------------------------------

from typing import List, Dict, Any
import time

import bot.db as db
import bot.handlers.pvp_ranking as ranking_module  # your ranking system


# -------------------------------------------
# Power Score Calculation (your original)
# -------------------------------------------
def calculate_power(stats: Dict[str, Any]) -> int:
    """
    Simple, readable power score formula:
        Power = HP * 0.4 + ATK * 1.2 + DEF * 1.0
    """
    hp = int(stats.get("hp", 100))
    atk = int(stats.get("attack", 10))
    dfs = int(stats.get("defense", 5))

    return int(round(hp * 0.4 + atk * 1.2 + dfs * 1.0))


# -------------------------------------------
# Internal helper: normalize user record
# -------------------------------------------
def _normalize_user_dict(u: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standardizes fields for UI.
    """
    uid = u.get("user_id")
    username = u.get("username")
    display_name = u.get("display_name") or username or f"User{uid}"

    return {
        "user_id": uid,
        "username": username,
        "display_name": display_name,
        "level": int(u.get("level", 1)),
        "elo_pvp": int(u.get("elo_pvp", 1000)),
        "shield_until": int(u.get("pvp_shield_until", 0)),

        # Stats (fallback)
        "hp": int(u.get("hp", 100)),
        "attack": int(u.get("attack", 10)),
        "defense": int(u.get("defense", 5)),
    }


# -------------------------------------------
# Time Formatter (new)
# -------------------------------------------
def _format_time_since(ts: int) -> str:
    now = int(time.time())
    diff = now - ts

    if diff < 60:
        return "<1m ago"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


# -------------------------------------------
# REVENGE TARGETS (fully upgraded)
# -------------------------------------------
def get_revenge_targets(user_id: int) -> List[Dict[str, Any]]:
    """
    Returns a clean revenge list:
        ✔ Deduped by attacker
        ✔ Sorted newest-first
        ✔ Limited to 5 newest attackers
        ✔ Time formatting improved
    """
    raw_logs = db.get_users_who_attacked_you(user_id, limit=50)
    if not raw_logs:
        return []

    # Deduplicate: keep only most recent entry per attacker
    latest = {}
    for row in raw_logs:
        atk = row["attacker_id"]
        ts = int(row["ts"])
        if atk not in latest or ts > latest[atk]["ts"]:
            latest[atk] = row

    entries = list(latest.values())

    # Sort newest-first
    entries.sort(key=lambda r: -int(r["ts"]))

    # Limit to 5 attackers
    entries = entries[:5]

    out = []
    for r in entries:
        atk_id = r["attacker_id"]
        attacker_row = db.get_user(atk_id)
        if not attacker_row:
            continue

        attacker = _normalize_user_dict(attacker_row)
        attacker["time_ago"] = _format_time_since(int(r["ts"]))
        attacker["xp_stolen"] = int(r.get("xp_stolen", 0))
        attacker["result"] = r.get("result", "unknown")

        out.append(attacker)

    return out


# -------------------------------------------
# Clear revenge log AFTER revenge attack
# -------------------------------------------
def clear_revenge_for(attacker_id: int, defender_id: int):
    """
    Removes all revenge log rows for this specific matchup.
    Called when user successfully initiates revenge via /pvp.

    IMPORTANT:
    Order MUST be (attacker_id, defender_id)
    """
    try:
        db.clear_revenge_for(attacker_id, defender_id)
    except Exception:
        pass


# -------------------------------------------
# RECOMMENDED TARGETS (your untouched original logic)
# -------------------------------------------
def get_recommended_targets(user_id: int) -> List[Dict[str, Any]]:
    """
    Produces a list of recommended PvP targets based on:
        ✔ Level proximity (±4 levels)
        ✔ Not shielded
        ✔ Power-score similarity
    Does NOT use last_active filtering.
    """
    me = db.get_user(user_id)
    if not me:
        return []

    me_level = int(me.get("level", 1))

    # Get all users from database
    all_users = db.get_all_users()
    now = int(time.time())

    candidates = []

    # Compute my power for sorting later
    my_stats = {
        "hp": int(me.get("hp", 100)),
        "attack": int(me.get("attack", 10)),
        "defense": int(me.get("defense", 5)),
    }
    my_power = calculate_power(my_stats)

    for u in all_users:
        uid = u.get("user_id")
        if not uid or uid == user_id:
            continue  # skip myself

        shield = int(u.get("pvp_shield_until", 0))
        if shield > now:
            continue  # skip shielded players

        level = int(u.get("level", 1))
        if abs(level - me_level) > 4:
            continue  # too far level difference

        normalized = _normalize_user_dict(u)

        stats = {
            "hp": normalized["hp"],
            "attack": normalized["attack"],
            "defense": normalized["defense"],
        }
        power = calculate_power(stats)

        normalized["power"] = power
        candidates.append(normalized)

    # Sort by closeness to player's power
    candidates.sort(key=lambda c: abs(c["power"] - my_power))

    # Add rank label from ranking system
    results = []
    for c in candidates[:6]:  # top 6 recommended
        try:
            rank_label, _ = ranking_module.elo_to_rank(c["elo_pvp"])
        except Exception:
            rank_label = "Unknown"

        c["rank"] = rank_label
        results.append(c)

    return results
