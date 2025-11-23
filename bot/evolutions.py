# evolutions.py  (Phase 2 upgrade)
from typing import Dict, Optional, Tuple

# Stage indices:
# 0 = Tadpole
# 1 = Hopper
# 2 = Battle Hopper
# 3 = Void Hopper
# 4 = Titan
# 5 = Celestial
# 6 = OmniGrok

EVOLUTION_DATA = {
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
        "min_level": 20,
        "xp_multiplier": 1.3,
        "fight_bonus": 3,
        "ritual_bonus": 3,
        "frame": "void_frame.png",
        "aura": "void_aura.png",
    },
    4: {
        "stage": 4,
        "name": "Titan",
        "min_level": 30,
        "xp_multiplier": 1.45,
        "fight_bonus": 5,
        "ritual_bonus": 5,
        "frame": "titan_frame.png",
        "aura": "gold_aura.png",
    },
    5: {
        "stage": 5,
        "name": "Celestial",
        "min_level": 40,
        "xp_multiplier": 1.6,
        "fight_bonus": 7,
        "ritual_bonus": 7,
        "frame": "celestial_frame.png",
        "aura": "starlight.png",
    },
    6: {
        "stage": 6,
        "name": "OmniGrok",
        "min_level": 50,
        "xp_multiplier": 2.0,
        "fight_bonus": 10,
        "ritual_bonus": 10,
        "frame": "omni_frame.png",
        "aura": "omni_aura.png",
    },
}


def get_stage_for_level(level: int) -> int:
    """
    Return highest evolution stage whose min_level <= level.
    """
    best_stage = 0
    for stage, data in EVOLUTION_DATA.items():
        if level >= data["min_level"] and data["min_level"] >= EVOLUTION_DATA[best_stage]["min_level"]:
            best_stage = stage
    return best_stage


def get_evolution_for_level(level: int) -> Dict:
    """
    Return the full evolution data dict for the given level.
    """
    stage = get_stage_for_level(level)
    return EVOLUTION_DATA[stage].copy()


def get_stage_data(stage: int) -> Optional[Dict]:
    """
    Return the data for a specific stage index or None if invalid.
    """
    return EVOLUTION_DATA.get(stage)


def determine_evolution_event(old_stage: int, new_level: int) -> Tuple[bool, Dict]:
    """
    Given user's old_stage and new_level, determine whether an evolution event triggers.
    Returns (evolved: bool, new_stage_data: dict).
    """
    new_stage = get_stage_for_level(new_level)
    evolved = new_stage > old_stage
    return evolved, EVOLUTION_DATA[new_stage].copy()


# convenience accessors
def get_xp_multiplier_for_level(level: int) -> float:
    return get_evolution_for_level(level)["xp_multiplier"]


def get_name_for_level(level: int) -> str:
    return get_evolution_for_level(level)["name"]
