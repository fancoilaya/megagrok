# services/pvp_targets.py
# -------------------------------------------
# Recommended Targets + Revenge Targets
# MegaGrok PvP Targeting & Ranking Helper
#
# This version:
#   ✔ DOES NOT use last_active
#   ✔ Filters ONLY by level range & shield
#   ✔ Supports revenge feed via db.get_users_who_attacked_you()
#   ✔ Uses your ranking module (elo_to_rank)
#   ✔ Computes power score for fair match suggestions
# -------------------------------------------

from typing import List, Dict, Any
import time

import bot.db as db
import bot.handlers.pvp_ranking as ranking_module  # your ranking system


# -------------------------------------------
# Power Score Calculation
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
    Takes a DB user row from db.get_all_users() and standardizes keys for UI.
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

        # Stats for power calculation (fallback capability)
        "hp": int(u.get("hp", 100)),
        "attack": int(u.get("attack", 10)),
        "defense": int(u.get("defense", 5)),
    }


# -------------------------------------------
# Revenge Targets
# -------------------------------------------
def get_revenge_targets(user_id: int) -> List[Dict[str, Any]]:
    """
    Returns a list of players who recently attacked user_id.
    Pulls from the db.pvp_attack_log table.
    """
    rows = db.get_users_who_attacked_you(user_id, limit=10)
    now = int(time.time())
    revenge_list = []

    for r in rows:
        attacker_id = r["attacker_id"]
        attacker_row = db.get_user(attacker_id)

        if not attacker_row:
            continue

        attacker = _normalize_user_dict(attacker_row)
        attacker["since"] = now - int(r["ts"])
        attacker["xp_stolen"] = int(r["xp_stolen"])
        attacker["result"] = r["result"]

        revenge_list.append(attacker)

    return revenge_list


# -------------------------------------------
# Recommended PvP Targets
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
            continue  # level too far

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

    # Add rank label from your ranking system
    results = []
    for c in candidates[:6]:  # top 6 recommended
        try:
            rank_label, _ = ranking_module.elo_to_rank(c["elo_pvp"])
        except:
            rank_label = "Unknown"

        c["rank"] = rank_label
        results.append(c)

    return results
