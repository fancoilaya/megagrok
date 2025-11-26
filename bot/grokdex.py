# bot/grokdex.py
# Unified GrokDex powered by the 25-mob master database.

from bot.mobs import MOBS, TIERS

def get_grokdex_list():
    """
    Returns a dictionary grouped by tier:
    {
        1: [mob1, mob2, ...],
        2: [...],
        ...
    }
    """
    grouped = {tier: [] for tier in TIERS.keys()}
    for mob_key, mob in MOBS.items():
        tier = mob.get("tier", 1)
        grouped[tier].append(mob)
    return grouped

def search_mob(name: str):
    """Case-insensitive lookup by mob name or key."""
    if not name:
        return None
    name = name.strip().lower()

    for key, mob in MOBS.items():
        if key.lower() == name or mob["name"].lower() == name:
            return mob
    return None
