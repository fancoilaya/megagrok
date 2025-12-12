# services/pvp_stats.py
# PvP stat builder (balanced formula - Option A)
# Exports: build_pvp_stats(user_dict)
#
# Formula:
#   HP      = 100 + level * 4
#   Attack  = 10 + level * 1.5
#   Defense = 5  + level * 0.8
#   Crit    = 0.04 + level * 0.001  (stored as fraction)

from typing import Dict, Any

def build_pvp_stats(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a balanced PvP stat dictionary for the given user row (dict).
    Expects keys like 'level', 'user_id', 'username', 'display_name' may exist.
    Returns a dict containing hp, attack, defense, crit_chance and identity fields.
    """
    lvl = int(user.get("level", 1))
    hp = int(100 + lvl * 4)
    attack = float(10 + lvl * 1.5)
    defense = float(5 + lvl * 0.8)
    crit_chance = float(0.04 + lvl * 0.001)  # 4% base + 0.1% per level

    return {
        "hp": hp,
        "max_hp": hp,
        "attack": attack,
        "defense": defense,
        "crit_chance": crit_chance,
        # identity
        "user_id": int(user.get("user_id", 0)),
        "username": user.get("username"),
        "display_name": user.get("display_name") or user.get("username"),
        "level": lvl,
        "elo_pvp": int(user.get("elo_pvp", 1000)),
    }
