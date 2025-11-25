# services/fightsystem.py
from __future__ import annotations
import random
from typing import Dict, Any, List, Tuple, Union

# Import your models / helpers
from utils.models import (
    Player,
    Mob,
    calculate_damage,
    apply_pve_reward,
    compute_pvp_xp_transfer,
)

# Configuration
MAX_TURNS = 50  # safety cap


# ---------------------------
# Types
# ---------------------------
Actor = Union[Player, Mob]


# ---------------------------
# Internal helpers
# ---------------------------
def _log_event(events: List[Dict[str, Any]], turn: int, actor_name: str, target_name: str,
               action: str, damage: int, was_dodged: bool, was_crit: bool, target_hp_after: int) -> None:
    """Append a structured event to the events list."""
    ev = {
        "turn": turn,
        "actor": actor_name,
        "target": target_name,
        "action": action,
        "damage": damage,
        "dodged": was_dodged,
        "crit": was_crit,
        "target_hp": target_hp_after,
    }
    events.append(ev)


def _is_dead_hp(hp: int) -> bool:
    return hp <= 0


# ---------------------------
# Fight engine core
# ---------------------------
def run_pve_fight(player: Player, mob: Mob, attacker_first: bool = True) -> Dict[str, Any]:
    """
    Run a PvE fight between 'player' and 'mob'.

    - Mutates player.current_hp (and player.xp/level via apply_pve_reward).
    - Does NOT persist changes to disk; caller should save user data after.
    - Returns a result dict with structured logs and xp info.

    attacker_first is ignored for PvE by default — attacker (player) hits first unless specified otherwise.
    """
    # Local HP copies so we can leave the Mob/Player object's hp fields consistent except current_hp.
    p_hp = int(player.current_hp)
    m_hp = int(mob.hp)  # mobs may use mob.hp as base HP

    events: List[Dict[str, Any]] = []
    turn = 1

    # In PvE we default to player attacking first unless caller overrides
    attacker_is_player = bool(attacker_first)

    while turn <= MAX_TURNS and p_hp > 0 and m_hp > 0:
        if attacker_is_player:
            # Player attacks Mob
            dmg, dodged, crit = calculate_damage(player, mob)
            if dodged:
                _log_event(events, turn, player.username, mob.name, "attack", 0, True, False, m_hp)
            else:
                m_hp -= dmg
                m_hp = max(0, m_hp)
                _log_event(events, turn, player.username, mob.name, "attack", dmg, False, crit, m_hp)

            if _is_dead_hp(m_hp):
                break  # mob died, player wins

            # Mob retaliates
            dmg, dodged, crit = calculate_damage(mob, player)
            if dodged:
                _log_event(events, turn, mob.name, player.username, "attack", 0, True, False, p_hp)
            else:
                p_hp -= dmg
                p_hp = max(0, p_hp)
                _log_event(events, turn, mob.name, player.username, "attack", dmg, False, crit, p_hp)

            if _is_dead_hp(p_hp):
                break

        else:
            # Mob attacks first (rare path)
            dmg, dodged, crit = calculate_damage(mob, player)
            if dodged:
                _log_event(events, turn, mob.name, player.username, "attack", 0, True, False, p_hp)
            else:
                p_hp -= dmg
                p_hp = max(0, p_hp)
                _log_event(events, turn, mob.name, player.username, "attack", dmg, False, crit, p_hp)

            if _is_dead_hp(p_hp):
                break

            dmg, dodged, crit = calculate_damage(player, mob)
            if dodged:
                _log_event(events, turn, player.username, mob.name, "attack", 0, True, False, m_hp)
            else:
                m_hp -= dmg
                m_hp = max(0, m_hp)
                _log_event(events, turn, player.username, mob.name, "attack", dmg, False, crit, m_hp)

            if _is_dead_hp(m_hp):
                break

        turn += 1

    # Apply results
    player.current_hp = max(0, p_hp)  # update player's hp
    mob_hp_remaining = max(0, m_hp)

    if m_hp <= 0 and p_hp > 0:
        # Player won PvE
        xp_gained, leveled_up, levels_gained = apply_pve_reward(player, mob)
        result = {
            "type": "pve",
            "winner": "player",
            "player_id": player.user_id,
            "player_username": player.username,
            "xp_gained": xp_gained,
            "leveled_up": leveled_up,
            "levels_gained": levels_gained,
            "player_hp": player.current_hp,
            "mob_hp": mob_hp_remaining,
            "events": events,
            "turns": turn,
        }
    elif p_hp <= 0 and m_hp > 0:
        # Player lost
        result = {
            "type": "pve",
            "winner": "mob",
            "player_id": player.user_id,
            "player_username": player.username,
            "xp_gained": 0,
            "leveled_up": False,
            "levels_gained": 0,
            "player_hp": player.current_hp,
            "mob_hp": mob_hp_remaining,
            "events": events,
            "turns": turn,
        }
    else:
        # Draw / max turns reached
        result = {
            "type": "pve",
            "winner": None,
            "player_id": player.user_id,
            "player_username": player.username,
            "xp_gained": 0,
            "leveled_up": False,
            "levels_gained": 0,
            "player_hp": player.current_hp,
            "mob_hp": mob_hp_remaining,
            "events": events,
            "turns": turn,
            "note": "max_turns_or_draw",
        }

    return result


def run_pvp_fight(attacker: Player, defender: Player, attacker_first: bool = True) -> Dict[str, Any]:
    """
    Run a PvP fight between two Player objects.

    - Mutates attacker.current_hp and defender.current_hp.
    - Mutates attacker.xp and defender.xp according to compute_pvp_xp_transfer.
    - Returns a structured result dict with xp deltas and events.
    """
    a_hp = int(attacker.current_hp)
    d_hp = int(defender.current_hp)

    events: List[Dict[str, Any]] = []
    turn = 1
    attacker_turn = bool(attacker_first)  # attacker hits first when True

    while turn <= MAX_TURNS and a_hp > 0 and d_hp > 0:
        if attacker_turn:
            # Attacker attacks defender
            dmg, dodged, crit = calculate_damage(attacker, defender)
            if dodged:
                _log_event(events, turn, attacker.username, defender.username, "attack", 0, True, False, d_hp)
            else:
                d_hp -= dmg
                d_hp = max(0, d_hp)
                _log_event(events, turn, attacker.username, defender.username, "attack", dmg, False, crit, d_hp)

            if _is_dead_hp(d_hp):
                break

        else:
            # Defender attacks back
            dmg, dodged, crit = calculate_damage(defender, attacker)
            if dodged:
                _log_event(events, turn, defender.username, attacker.username, "attack", 0, True, False, a_hp)
            else:
                a_hp -= dmg
                a_hp = max(0, a_hp)
                _log_event(events, turn, defender.username, attacker.username, "attack", dmg, False, crit, a_hp)

            if _is_dead_hp(a_hp):
                break

        # alternate turns
        attacker_turn = not attacker_turn
        turn += 1

    # Determine winner
    if d_hp <= 0 and a_hp > 0:
        winner = "attacker"
        attacker_won = True
    elif a_hp <= 0 and d_hp > 0:
        winner = "defender"
        attacker_won = False
    else:
        winner = None
        attacker_won = None  # draw

    # Apply HP changes back to Player objects
    attacker.current_hp = max(0, a_hp)
    defender.current_hp = max(0, d_hp)

    # XP adjustments (only if there is a winner)
    attacker_xp_delta = 0
    defender_xp_delta = 0
    leveled_up_attacker = False
    levels_gained_attacker = 0
    leveled_up_defender = False
    levels_gained_defender = 0

    if attacker_won is True:
        attacker_xp_delta, defender_xp_delta = compute_pvp_xp_transfer(attacker, defender, attacker_won=True)
    elif attacker_won is False:
        attacker_xp_delta, defender_xp_delta = compute_pvp_xp_transfer(attacker, defender, attacker_won=False)
    else:
        # Draw: no XP transfer
        attacker_xp_delta, defender_xp_delta = 0, 0

    # Apply XP changes (positive -> add_xp, negative -> remove_xp)
    if attacker_xp_delta > 0:
        leveled_up_attacker, levels_gained_attacker = attacker.add_xp(attacker_xp_delta)
    elif attacker_xp_delta < 0:
        attacker.remove_xp(abs(attacker_xp_delta))

    if defender_xp_delta > 0:
        leveled_up_defender, levels_gained_defender = defender.add_xp(defender_xp_delta)
    elif defender_xp_delta < 0:
        defender.remove_xp(abs(defender_xp_delta))

    result = {
        "type": "pvp",
        "winner": winner,
        "attacker_id": attacker.user_id,
        "attacker_username": attacker.username,
        "defender_id": defender.user_id,
        "defender_username": defender.username,
        "attacker_hp": attacker.current_hp,
        "defender_hp": defender.current_hp,
        "attacker_xp_delta": attacker_xp_delta,
        "defender_xp_delta": defender_xp_delta,
        "attacker_leveled_up": leveled_up_attacker,
        "attacker_levels_gained": levels_gained_attacker,
        "defender_leveled_up": leveled_up_defender,
        "defender_levels_gained": levels_gained_defender,
        "events": events,
        "turns": turn,
    }

    return result


# ---------------------------
# Convenience / utility functions
# ---------------------------
def choose_mob_for_player(player: Player, mobs: List[Mob], level_tolerance: int = 2) -> Mob:
    """
    Simple helper: choose a mob from a list that is near the player's level.
    - level_tolerance controls how far from player's level we allow.
    - If no mobs match, picks a random mob.
    """
    suitable = [m for m in mobs if abs(m.level - player.level) <= level_tolerance]
    if suitable:
        return random.choice(suitable)
    return random.choice(mobs)


# ---------------------------
# Example quick-run (for local testing)
# ---------------------------
if __name__ == "__main__":
    # Quick smoke test when running this file directly.
    # Create two dummy players and a mob and run fights.
    p1 = Player(1, "GrokA")
    p2 = Player(2, "GrokB")
    p2.attack = 8
    p2.defense = 4

    test_mob = Mob("Wild Grok", level=1, hp=80, attack=6, defense=3, crit_chance=0.02, dodge_chance=0.01, xp_reward=25)

    print("=== PvE Test ===")
    p1.current_hp = p1.max_hp
    res_pve = run_pve_fight(p1, test_mob)
    print(res_pve["winner"], "events:", len(res_pve["events"]), "xp:", res_pve.get("xp_gained"))

    print("\n=== PvP Test ===")
    # reset HP
    p1.current_hp = p1.max_hp
    p2.current_hp = p2.max_hp
    res_pvp = run_pvp_fight(p1, p2)
    print("winner:", res_pvp["winner"], "attacker_xp_delta:", res_pvp["attacker_xp_delta"])
