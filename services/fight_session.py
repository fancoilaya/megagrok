# services/fight_session.py
from __future__ import annotations
import random
import time
import json
import os
from typing import Dict, Any, List, Optional, Tuple

# Balance constants
BASE_PLAYER_HP = 100
BASE_MOB_HP = 100
MAX_TURNS = 60

# Action keys
ACTION_ATTACK = "attack"
ACTION_BLOCK = "block"
ACTION_DODGE = "dodge"
ACTION_CHARGE = "charge"
ACTION_AUTO = "auto"  # client-side request to toggle auto-mode

# Persistence file for sessions (optional)
_SESSIONS_FILE = "data/battle_sessions.json"


def _safe_load_sessions() -> Dict[str, Any]:
    try:
        if os.path.exists(_SESSIONS_FILE):
            with open(_SESSIONS_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _safe_save_sessions(sessions: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(_SESSIONS_FILE), exist_ok=True)
        with open(_SESSIONS_FILE, "w") as f:
            json.dump(sessions, f, indent=2)
    except Exception:
        # best effort only — ignore file errors
        pass


class FightEvent:
    def __init__(self, turn: int, actor: str, action: str, target: str,
                 damage: int = 0, dodged: bool = False, crit: bool = False,
                 actor_hp: int = 0, target_hp: int = 0):
        self.ts = int(time.time())
        self.turn = turn
        self.actor = actor
        self.action = action
        self.target = target
        self.damage = damage
        self.dodged = dodged
        self.crit = crit
        self.actor_hp = actor_hp
        self.target_hp = target_hp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "turn": self.turn,
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "damage": self.damage,
            "dodged": self.dodged,
            "crit": self.crit,
            "actor_hp": self.actor_hp,
            "target_hp": self.target_hp,
        }


class FightSession:
    """
    Fight session state. Each active interactive fight gets one of these.
    Keyed by initiating user_id (int).
    """

    def __init__(self, user_id: int, player: Dict[str, Any], mob: Dict[str, Any], session_id: Optional[str] = None):
        self.session_id = session_id or f"{user_id}-{int(time.time())}"
        self.user_id = user_id
        self.player = dict(player)  # shallow copy of raw stats dict
        self.mob = dict(mob)
        # compute starting HP
        self.player_hp = int(self.player.get("current_hp", self.player.get("hp", BASE_PLAYER_HP)))
        self.mob_hp = int(self.mob.get("hp", self.mob.get("max_hp", BASE_MOB_HP)))
        self.turn = 1
        self.events: List[Dict[str, Any]] = []
        self.auto_mode: bool = False
        self.started_at = int(time.time())
        self.ended: bool = False
        self.winner: Optional[str] = None  # "player", "mob", or None
        self.last_action_by_user: Optional[str] = None  # last action (attack/block/dodge/charge)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "player": self.player,
            "mob": self.mob,
            "player_hp": self.player_hp,
            "mob_hp": self.mob_hp,
            "turn": self.turn,
            "events": self.events,
            "auto_mode": self.auto_mode,
            "started_at": self.started_at,
            "ended": self.ended,
            "winner": self.winner,
            "last_action_by_user": self.last_action_by_user,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FightSession":
        sess = cls(int(data["user_id"]), data["player"], data["mob"], session_id=data.get("session_id"))
        sess.player_hp = int(data.get("player_hp", sess.player_hp))
        sess.mob_hp = int(data.get("mob_hp", sess.mob_hp))
        sess.turn = int(data.get("turn", sess.turn))
        sess.events = data.get("events", [])
        sess.auto_mode = bool(data.get("auto_mode", sess.auto_mode))
        sess.started_at = int(data.get("started_at", sess.started_at))
        sess.ended = bool(data.get("ended", sess.ended))
        sess.winner = data.get("winner", sess.winner)
        sess.last_action_by_user = data.get("last_action_by_user", sess.last_action_by_user)
        return sess

    # ----- event helpers -----
    def _append_event(self, ev: FightEvent):
        self.events.append(ev.to_dict())

    # ----- combat helpers -----
    def _random_check(self, prob: float) -> bool:
        return random.random() < float(prob)

    def _calc_base_damage(self, attacker: Dict[str, Any], defender: Dict[str, Any]) -> Tuple[int, bool]:
        """Return (base_damage, maybe_crit_bool)"""
        attack = float(attacker.get("attack", 10))
        defense = float(defender.get("defense", 5))
        base = attack - (defense * 0.5)
        base = max(1, int(round(base)))
        crit = False
        if self._random_check(attacker.get("crit_chance", 0.05)):
            base = int(base * 2)
            crit = True
        return base, crit

    def resolve_player_action(self, action: str) -> Dict[str, Any]:
        """
        Resolve one player action + an immediate counter-attack from mob (if alive).
        Returns a small summary dict.
        """
        if self.ended:
            return {"error": "fight_already_ended"}

        player_name = self.player.get("username", "You")
        mob_name = self.mob.get("name", "Mob")
        self.last_action_by_user = action

        # Player action resolution
        if action == ACTION_ATTACK:
            dmg, crit = self._calc_base_damage(self.player, self.mob)
            # mob dodge
            if self._random_check(self.mob.get("dodge_chance", 0.01)):
                ev = FightEvent(self.turn, player_name, ACTION_ATTACK, mob_name, damage=0, dodged=True, crit=False, actor_hp=self.player_hp, target_hp=self.mob_hp)
                self._append_event(ev)
            else:
                # include charge bonus if present
                charge_bonus = int(self.player.get("_charge_bonus", 0))
                total_dmg = max(1, dmg + charge_bonus)
                self.mob_hp = max(0, self.mob_hp - total_dmg)
                ev = FightEvent(self.turn, player_name, ACTION_ATTACK, mob_name, damage=total_dmg, dodged=False, crit=crit, actor_hp=self.player_hp, target_hp=self.mob_hp)
                self._append_event(ev)
                # consume charge bonus
                if "_charge_bonus" in self.player:
                    self.player["_charge_bonus"] = 0

        elif action == ACTION_BLOCK:
            ev = FightEvent(self.turn, player_name, ACTION_BLOCK, mob_name, damage=0, dodged=False, crit=False, actor_hp=self.player_hp, target_hp=self.mob_hp)
            self._append_event(ev)

        elif action == ACTION_DODGE:
            ev = FightEvent(self.turn, player_name, ACTION_DODGE, mob_name, damage=0, dodged=False, crit=False, actor_hp=self.player_hp, target_hp=self.mob_hp)
            self._append_event(ev)

        elif action == ACTION_CHARGE:
            charge_bonus = int(self.player.get("attack", 10) * 0.5)
            self.player["_charge_bonus"] = self.player.get("_charge_bonus", 0) + charge_bonus
            ev = FightEvent(self.turn, player_name, ACTION_CHARGE, mob_name, damage=0, dodged=False, crit=False, actor_hp=self.player_hp, target_hp=self.mob_hp)
            self._append_event(ev)

        else:
            ev = FightEvent(self.turn, player_name, "unknown", mob_name, damage=0, dodged=False, crit=False, actor_hp=self.player_hp, target_hp=self.mob_hp)
            self._append_event(ev)

        # Check if mob dead after player's action
        if self.mob_hp <= 0:
            self.ended = True
            self.winner = "player"
            return {"winner": "player", "events": self.events, "player_hp": self.player_hp, "mob_hp": self.mob_hp}

        # Mob retaliates (unless ended)
        mob_attack = float(self.mob.get("attack", 6))
        mob_def = float(self.player.get("defense", 5))

        base_mob_damage = max(1, int(round(mob_attack - (mob_def * 0.5))))
        mob_crit = False
        if self._random_check(self.mob.get("crit_chance", 0.02)):
            base_mob_damage = int(base_mob_damage * 2)
            mob_crit = True

        # Adjustments based on player's action
        if action == ACTION_BLOCK:
            base_mob_damage = int(base_mob_damage * 0.4)  # block reduces to 40%
        elif action == ACTION_DODGE:
            if self._random_check(self.player.get("dodge_chance", 0.25)):
                ev = FightEvent(self.turn, self.mob.get("name"), "attack", self.player.get("username", "You"), damage=0, dodged=True, crit=False, actor_hp=self.mob_hp, target_hp=self.player_hp)
                self._append_event(ev)
                self.turn += 1
                return {"events": self.events, "player_hp": self.player_hp, "mob_hp": self.mob_hp}

        # apply mob damage
        self.player_hp = max(0, int(self.player_hp - base_mob_damage))
        ev = FightEvent(self.turn, self.mob.get("name"), "attack", self.player.get("username", "You"), damage=base_mob_damage, dodged=False, crit=mob_crit, actor_hp=self.mob_hp, target_hp=self.player_hp)
        self._append_event(ev)

        # Check end
        if self.player_hp <= 0:
            self.ended = True
            self.winner = "mob"

        self.turn += 1
        # Safety cap
        if self.turn > MAX_TURNS:
            self.ended = True
            if self.player_hp > self.mob_hp:
                self.winner = "player"
            elif self.mob_hp > self.player_hp:
                self.winner = "mob"
            else:
                self.winner = None

        return {"events": self.events, "player_hp": self.player_hp, "mob_hp": self.mob_hp, "ended": self.ended, "winner": self.winner}

    def resolve_auto_turn(self) -> Dict[str, Any]:
        """
        If auto_mode is on, decide a simple policy and take a step.
        Policy: Attack if mob_hp is low, else use a chance to dodge/block occasionally.
        """
        if self.ended:
            return {"ended": True, "winner": self.winner}
        # Simple heuristic
        if self.mob_hp <= max(6, int(self.player.get("attack", 10) * 1.2)):
            action = ACTION_ATTACK
        else:
            r = random.random()
            if r < 0.65:
                action = ACTION_ATTACK
            elif r < 0.8:
                action = ACTION_DODGE
            else:
                action = ACTION_BLOCK
        return self.resolve_player_action(action)


# -------------------------
# Session manager (global)
# -------------------------
class SessionManager:
    """
    Simple in-process session manager. Keeps active sessions in memory and persists to disk occasionally.
    Use get_session(user_id) to retrieve or create.
    """
    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = _safe_load_sessions()

    def create_session(self, user_id: int, player: Dict[str, Any], mob: Dict[str, Any]) -> FightSession:
        sess = FightSession(user_id, player, mob)
        self._sessions[str(user_id)] = sess.to_dict()
        _safe_save_sessions(self._sessions)
        return sess

    def load_session(self, user_id: int) -> Optional[FightSession]:
        data = self._sessions.get(str(user_id))
        if data:
            return FightSession.from_dict(data)
        return None

    def save_session(self, sess: FightSession) -> None:
        self._sessions[str(sess.user_id)] = sess.to_dict()
        _safe_save_sessions(self._sessions)

    def end_session(self, user_id: int) -> None:
        s = self._sessions.get(str(user_id))
        if s:
            s["ended"] = True
            self._sessions[str(user_id)] = s
            _safe_save_sessions(self._sessions)
            try:
                del self._sessions[str(user_id)]
            except Exception:
                pass

    def list_active_sessions(self) -> List[str]:
        return list(self._sessions.keys())


# single global manager instance (import this)
manager = SessionManager()

# Optional tiny helper to create player/mob stat dicts from your user/mob shapes:
def build_player_stats_from_user(user: Dict[str, Any], username_fallback: str = "You") -> Dict[str, Any]:
    return {
        "username": user.get("username", username_fallback),
        "current_hp": user.get("current_hp", user.get("hp", BASE_PLAYER_HP)),
        "attack": user.get("attack", 10),
        "defense": user.get("defense", 5),
        "crit_chance": user.get("crit_chance", 0.05),
        "dodge_chance": user.get("dodge_chance", 0.03),
        "xp_total": user.get("xp_total", 0),
    }


def build_mob_stats_from_mob(mob: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": mob.get("name", "Mob"),
        "hp": mob.get("hp", mob.get("max_hp", BASE_MOB_HP)),
        "attack": mob.get("attack", 6),
        "defense": mob.get("defense", 3),
        "crit_chance": mob.get("crit_chance", 0.02),
        "dodge_chance": mob.get("dodge_chance", 0.01),
        "min_xp": mob.get("min_xp", 10),
        "max_xp": mob.get("max_xp", 25)
    }
