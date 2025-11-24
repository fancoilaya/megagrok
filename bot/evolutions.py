# bot/evolutions.py — Phase 2 Evolution System Rewrite
#
# This version is cleaner, more flexible, and built for future phases:
# - Full 7-tier evolution ladder
# - XP multipliers, bonuses, frames, auras
# - Guaranteed correct fallback logic
# - Supports future “mutation events”
# - All functions safe & predictable
#
# Import path stays:  import bot.evolutions as evolutions

from typing import Dict, Optional, Tuple

# ============================================================
# EVOLUTION TIERS — FINAL 7-TIER SYSTEM
# ============================================================

EVOLUTION_TIERS: Dict[int, Dict] = {
    0: {
        "stage": 0,
        "name": "Tadpole",
        "min_level": 1,
        "xp_multiplier": 1.0,
        "fight_bonus": 0,
        "ritual_bonus": 0,
        "frame": "tadpole_frame.png",
        "aura": None,
    },
    1: {
        "stage": 1,
        "name": "Hopper",
        "min_level": 5,
        "xp_multiplier": 1.1,
        "fight_bonus": 1,
        "ritual_bonus": 1,
        "frame": "hopper_frame.png",
        "aura": "blue_glow.png",
    },
    2: {
        "stage": 2,
        "name": "Battle Hopper",
        "min_level": 10,
        "xp_multiplier": 1.2,
        "fight_bonus": 2,
        "ritual_bonus": 2,
        "frame": "battle_frame.png",
        "aura": "red_glow.png",
    },
    3: {
        "stage": 3,
        "name": "Void Hopper",
        "min_level": 18,
        "xp_multiplier": 1.35,
        "fight_bonus": 3,
        "ritual_bonus": 3,
        "frame": "void_frame.png",
        "aura": "void_aura.png",
    },
    4: {
        "stage": 4,
        "name": "Titan",
        "min_level": 28,
        "xp_multiplier": 1.55,
        "fight_bonus": 5,
        "ritual_bonus": 5,
        "frame": "titan_frame.png",
        "aura": "gold_aura.png",
    },
    5: {
        "stage": 5,
        "name": "Celestial",
        "min_level": 40,
        "xp_multiplier": 1.8,
        "fight_bonus": 7,
        "ritual_bonus": 7,
        "frame": "celestial_frame.png",
        "aura": "starlight.png",
    },
    6: {
        "stage": 6,
        "name": "OmniGrok",
        "min_level": 55,
        "xp_multiplier": 2.2,
        "fight_bonus": 12,
        "ritual_bonus": 10,
        "frame": "omni_frame.png",
        "aura": "omni_aura.png",
    },
}


# ============================================================
# CORE LOOKUP FUNCTIONS
# ============================================================

def get_stage_for_level(level: int) -> int:
    """
    Return the highest evolution stage whose min_level <= level.
    Guaranteed to return a valid stage index (0–6).
    """
    best = 0
    for stage, data in EVOLUTION_TIERS.items():
        if level >= data["min_level"] and data["min_level"] >= EVOLUTION_TIERS[best]["min_level"]:
            best = stage
    return best


def get_stage_data(stage: int) -> Dict:
    """Safe accessor — always returns a copy."""
    return EVOLUTION_TIERS.get(stage, EVOLUTION_TIERS[0]).copy()


def get_evolution_for_level(level: int) -> Dict:
    """Return full evolution data for the given level."""
    stage = get_stage_for_level(level)
    return get_stage_data(stage)


# ============================================================
# EVOLUTION EVENT LOGIC
# ============================================================

def determine_evolution_event(old_stage: int, new_level: int) -> Tuple[bool, Dict]:
    """
    Returns (evolved: bool, new_stage_data: dict).
    Trigger condition: user reached a stage higher than their previous one.
    """
    new_stage = get_stage_for_level(new_level)
    evolved = new_stage > old_stage
    return evolved, get_stage_data(new_stage)


# ============================================================
# CONVENIENCE ACCESSORS FOR BOT HANDLERS
# ============================================================

def get_xp_multiplier_for_level(level: int) -> float:
    return get_evolution_for_level(level)["xp_multiplier"]


def get_name_for_level(level: int) -> str:
    return get_evolution_for_level(level)["name"]


def get_frame_for_level(level: int) -> Optional[str]:
    return get_evolution_for_level(level)["frame"]


def get_aura_for_level(level: int) -> Optional[str]:
    return get_evolution_for_level(level)["aura"]


def get_fight_bonus(level: int) -> int:
    return get_evolution_for_level(level)["fight_bonus"]


def get_ritual_bonus(level: int) -> int:
    return get_evolution_for_level(level)["ritual_bonus"]


# ============================================================
# PHASE 3 READY: MUTATION HOOKS (currently dormant)
# ============================================================

def roll_mutation_event(level: int) -> Tuple[bool, Optional[str]]:
    """
    Placeholder for Phase 3 mutations (Lucky, Variant Colors, Power Surge, etc.)
    Always returns no mutation for now.
    """
    return False, None
