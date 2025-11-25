# utils/models.py
from __future__ import annotations
import random
import math
from typing import Dict, Any, Tuple


# ---------------------------
# Configuration / balance
# ---------------------------
BASE_HP = 100
HP_PER_LEVEL = 20

# PvP steal/loss ranges (percent of target's XP)
PVP_STEAL_MIN = 5    # percent
PVP_STEAL_MAX = 15   # percent
PVP_LOSE_MIN = 5     # percent (when attacker loses)
PVP_LOSE_MAX = 10    # percent


# ---------------------------
# Helper XP / Level formulas
# ---------------------------
def xp_for_level(level: int) -> int:
    """
    Total cumulative XP required to *be* at `level`.
    We use a simple quadratic progression:
        xp_required = 100 * level^2
    (This is cumulative threshold; change to your balance)
    """
    if level < 1:
        return 0
    return 100 * (level ** 2)


def level_for_xp(xp: int) -> int:
    """Return level for a given cumulative XP."""
    lvl = 1
    while xp_for_level(lvl + 1) <= xp:
        lvl += 1
    return lvl


def xp_to_next_level(level: int) -> int:
    """XP needed to go from `level` to `level + 1` (incremental)."""
    return xp_for_level(level + 1) - xp_for_level(level)


# ---------------------------
# Player model
# ---------------------------
class Player:
    def __init__(self, user_id: int, username: str):
        # Identity
        self.user_id: int = user_id
        self.username: str = username

        # Progression (cumulative XP stored in xp)
        self.level: int = 1
        self.xp: int = 0  # cumulative XP

        # Scaled HP
        self.max_hp: int = self.calculate_max_hp()
        self.current_hp: int = self.max_hp

        # Combat stats (base, constant)
        self.attack: int = 10
        self.defense: int = 5
        self.crit_chance: float = 0.05
        self.dodge_chance: float = 0.03

    # ---------- HP / Level ----------
    def calculate_max_hp(self) -> int:
        return BASE_HP + (self.level * HP_PER_LEVEL)

    def recalc_hp(self) -> None:
        """
        Recalculate max_hp (e.g., after leveling) while preserving current HP percentage.
        """
        old_max = self.max_hp
        old_percent = (self.current_hp / old_max) if old_max > 0 else 1.0
        self.max_hp = self.calculate_max_hp()
        self.current_hp = max(1, int(self.max_hp * old_percent))

    # ---------- XP / Level management ----------
    def add_xp(self, amount: int) -> Tuple[bool, int]:
        """
        Add XP (cumulative). Returns (leveled_up, levels_gained).
        """
        if amount <= 0:
            return False, 0
        self.xp += int(amount)
        new_level = level_for_xp(self.xp)
        if new_level > self.level:
            gained = new_level - self.level
            self.level = new_level
            self.recalc_hp()
            return True, gained
        return False, 0

    def remove_xp(self, amount: int) -> None:
        """
        Remove XP, floor at 0, then recalc level and HP.
        """
        self.xp = max(0, int(self.xp - amount))
        new_level = level_for_xp(self.xp)
        if new_level < self.level:
            self.level = new_level
            self.recalc_hp()

    # ---------- Serialization ----------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "level": self.level,
            "xp": self.xp,
            "max_hp": self.max_hp,
            "current_hp": self.current_hp,
            "attack": self.attack,
            "defense": self.defense,
            "crit_chance": self.crit_chance,
            "dodge_chance": self.dodge_chance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Player":
        p = cls(int(data["user_id"]), str(data.get("username", "")))
        p.level = int(data.get("level", p.level))
        p.xp = int(data.get("xp", p.xp))
        # recalc HP based on level
        p.max_hp = p.calculate_max_hp()
        p.current_hp = int(data.get("current_hp", p.max_hp))
        p.attack = int(data.get("attack", p.attack))
        p.defense = int(data.get("defense", p.defense))
        p.crit_chance = float(data.get("crit_chance", p.crit_chance))
        p.dodge_chance = float(data.get("dodge_chance", p.dodge_chance))
        return p


# ---------------------------
# Mob model
# ---------------------------
class Mob:
    def __init__(
        self,
        name: str,
        level: int,
        hp: int,
        attack: int,
        defense: int,
        crit_chance: float,
        dodge_chance: float,
        xp_reward: int,
    ):
        self.name: str = name
        self.level: int = level
        self.hp: int = hp
        self.attack: int = attack
        self.defense: int = defense
        self.crit_chance: float = crit_chance
        self.dodge_chance: float = dodge_chance
        self.xp_reward: int = xp_reward

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "level": self.level,
            "hp": self.hp,
            "attack": self.attack,
            "defense": self.defense,
            "crit_chance": self.crit_chance,
            "dodge_chance": self.dodge_chance,
            "xp_reward": self.xp_reward,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Mob":
        return cls(
            name=str(data["name"]),
            level=int(data.get("level", 1)),
            hp=int(data.get("hp", 50)),
            attack=int(data.get("attack", 5)),
            defense=int(data.get("defense", 2)),
            crit_chance=float(data.get("crit_chance", 0.01)),
            dodge_chance=float(data.get("dodge_chance", 0.0)),
            xp_reward=int(data.get("xp_reward", 10)),
        )


# ---------------------------
# Combat helpers
# ---------------------------
def calculate_damage(attacker, defender) -> Tuple[int, bool, bool]:
    """
    Calculate damage from attacker -> defender.

    Returns (damage:int, was_dodged:bool, was_crit:bool).

    Note: attacker/defender can be Player or Mob (must have attack/defense/crit_chance/dodge_chance).
    """
    # Dodge check
    if random.random() < defender.dodge_chance:
        return 0, True, False

    base = attacker.attack - (defender.defense * 0.5)
    base = max(1, base)

    was_crit = random.random() < attacker.crit_chance
    if was_crit:
        base = int(base * 2)

    return int(base), False, was_crit


# ---------------------------
# PvP XP transfer helpers
# ---------------------------
def compute_pvp_xp_transfer(attacker: Player, defender: Player, attacker_won: bool) -> Tuple[int, int]:
    """
    Compute XP changes for PvP result.
    Returns (attacker_xp_delta, defender_xp_delta) where deltas can be positive or negative.
    """

    if attacker_won:
        # Attacker steals a percent of defender's XP (current cumulative)
        percent = random.randint(PVP_STEAL_MIN, PVP_STEAL_MAX)
        stolen = max(1, int(defender.xp * percent / 100.0))
        return stolen, -stolen
    else:
        # Attacker loses a percent of their own XP (to defender)
        percent = random.randint(PVP_LOSE_MIN, PVP_LOSE_MAX)
        lost = max(1, int(attacker.xp * percent / 100.0))
        return -lost, lost


# ---------------------------
# PvE XP helper
# ---------------------------
def apply_pve_reward(player: Player, mob: Mob) -> Tuple[int, bool, int]:
    """
    Apply PvE XP reward (mob.xp_reward) to player.
    Returns (xp_given, leveled_up, levels_gained)
    """
    xp = mob.xp_reward
    leveled, gained = player.add_xp(xp)
    return xp, leveled, gained


# ---------------------------
# Small utility for display
# ---------------------------
def player_progress_str(player: Player) -> str:
    """Return short progress text for player (current XP vs next level)."""
    current_level_total = xp_for_level(player.level)
    next_level_total = xp_for_level(player.level + 1)
    current_into_level = player.xp - current_level_total
    need = next_level_total - player.xp
    return f"Lv {player.level} — XP: {player.xp} (+{current_into_level} into level), need {need} XP to next level"

