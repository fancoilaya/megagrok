# services/fight_session.py
from __future__ import annotations
import random
import time
import json
import os
from typing import Dict, Any, List, Optional, Tuple

# Balance / limits
BASE_PLAYER_HP = 100
BASE_MOB_HP = 100
MAX_TURNS = 60

# Action keys (exported for handler convenience)
ACTION_ATTACK = "attack"
ACTION_BLOCK = "block"
ACTION_DODGE = "dodge"
ACTION_CHARGE = "charge"

# Sessions persistence (best-effort)
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
        # best-effort only
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
    Stateful interactive fight session for a single initiating user.
    """

    def __init__(self, user_id: int, player: Dict[str, Any], mob: Dict[str, Any], session_id: Optional[str] = None):
        self.session_id = session_id or f"{user_id}-{int(time.time())}"
        self.user_id = user_id
        self.player = dict(player)
        self.mob = dict(mob)

        self.player_hp = int(self.player.get("current_hp", self.player.get("hp", BASE_PLAYER_HP)))
        self.mob_hp = int(self.mob.get("hp", self.mob.get("max_hp", BASE_MOB_HP)))
        self.turn = 1
        self.events: List[Dict[str, Any]] = []
        self.auto_mode: bool = False
        self.started_at = int(time.time())
        self.ended: bool = False
        self.winner: Optional[str] = None
        self.last_action_by_user: Optional[str] = None

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

    # internal helpers
    def _append_event(self, ev: FightEvent):
        self.events.append(ev.to_dict())

    def _random_check(self, prob: float) -> bool:
        return random.random() < float(prob)

    def _calc_base_damage(self, attacker: Dict[str, Any], defender: Dict[str, Any]) -> Tuple[int, bool]:
        """
        Calculate base damage and crit flag. THEN we randomize the final damage within +/-30%.
        """
        attack = float(attacker.get("attack", 10))
        defense = float(defender.get("defense", 5))
        base = attack - (defense * 0.5)
        base = max(1, int(round(base)))
        crit = False
        if self._random_check(attacker.get("crit_chance", 0.05)):
            base = int(base * 2)
            crit = True

        # Randomize final damage around base ±30%
        low = max(1, int(max(1, base) * 0.7))
        high = max(low, int(base * 1.3))
        final = random.randint(low, high)
        return final, crit

    def resolve_player_action(self, action: str) -> Dict[str, Any]:
        """
        Execute one player action, then the mob retaliates (if alive).
        """
        if self.ended:
            return {"error": "fight_already_ended"}

        player_name = self.player.get("username", "You")
        mob_name = self.mob.get("name", "Mob")
        self.last_action_by_user = action

        # Player action
        if action == ACTION_ATTACK:
            dmg, crit = self._calc_base_damage(self.player, self.mob)
            if self._random_check(self.mob.get("dodge_chance", 0.01)):
                self._append_event(FightEvent(self.turn, player_name, ACTION_ATTACK, mob_name,
                                              damage=0, dodged=True, crit=False,
                                              actor_hp=self.player_hp, target_hp=self.mob_hp))
            else:
                charge_bonus = int(self.player.get("_charge_bonus", 0))
                total_dmg = max(1, dmg + charge_bonus)
                self.mob_hp = max(0, self.mob_hp - total_dmg)
                self._append_event(FightEvent(self.turn, player_name, ACTION_ATTACK, mob_name,
                                              damage=total_dmg, dodged=False, crit=crit,
                                              actor_hp=self.player_hp, target_hp=self.mob_hp))
                self.player["_charge_bonus"] = 0

        elif action == ACTION_BLOCK:
            self._append_event(FightEvent(self.turn, player_name, ACTION_BLOCK, mob_name,
                                          damage=0, dodged=False, crit=False,
                                          actor_hp=self.player_hp, target_hp=self.mob_hp))

        elif action == ACTION_DODGE:
            self._append_event(FightEvent(self.turn, player_name, ACTION_DODGE, mob_name,
                                          damage=0, dodged=False, crit=False,
                                          actor_hp=self.player_hp, target_hp=self.mob_hp))

        elif action == ACTION_CHARGE:
            charge_bonus = int(self.player.get("attack", 10) * 0.5)
            self.player["_charge_bonus"] = self.player.get("_charge_bonus", 0) + charge_bonus
            self._append_event(FightEvent(self.turn, player_name, ACTION_CHARGE, mob_name,
                                          damage=0, dodged=False, crit=False,
                                          actor_hp=self.player_hp, target_hp=self.mob_hp))

        else:
            self._append_event(FightEvent(self.turn, player_name, "unknown", mob_name,
                                          damage=0, dodged=False, crit=False,
                                          actor_hp=self.player_hp, target_hp=self.mob_hp))

        # If mob died from player's action
        if self.mob_hp <= 0:
            self.ended = True
            self.winner = "player"
            return {"winner": "player"}

        # MOB TURN
        mob_attack = float(self.mob.get("attack", 6))
        mob_def = float(self.player.get("defense", 5))

        base = mob_attack - (mob_def * 0.5)
        base = max(1, int(round(base)))

        mob_crit = False
        if self._random_check(self.mob.get("crit_chance", 0.02)):
            base = int(base * 2)
            mob_crit = True

        # Mob damage randomization
        low_m = max(1, int(base * 0.7))
        high_m = max(low_m, int(base * 1.3))
        base_mob_damage = random.randint(low_m, high_m)

        # Defensive actions
        if action == ACTION_BLOCK:
            base_mob_damage = int(base_mob_damage * 0.4)

        elif action == ACTION_DODGE:
            if self._random_check(self.player.get("dodge_chance", 0.25)):
                self._append_event(FightEvent(self.turn, mob_name, "attack", player_name,
                                              damage=0, dodged=True, crit=False,
                                              actor_hp=self.mob_hp, target_hp=self.player_hp))
                self.turn += 1
                return {"events": self.events}

        # Apply mob damage
        self.player_hp = max(0, int(self.player_hp - base_mob_damage))
        self._append_event(FightEvent(self.turn, mob_name, "attack", player_name,
                                      damage=base_mob_damage, dodged=False, crit=mob_crit,
                                      actor_hp=self.mob_hp, target_hp=self.player_hp))

        if self.player_hp <= 0:
            self.ended = True
            self.winner = "mob"

        self.turn += 1

        if self.turn > MAX_TURNS:
            self.ended = True
            if self.player_hp > self.mob_hp:
                self.winner = "player"
            elif self.mob_hp > self.player_hp:
                self.winner = "mob"
            else:
                self.winner = None

        return {
            "events": self.events,
            "player_hp": self.player_hp,
            "mob_hp": self.mob_hp,
            "ended": self.ended,
            "winner": self.winner
        }

    # ADVANCED AUTO AI
    def resolve_auto_turn(self) -> Dict[str, Any]:
        """
        Advanced AI logic for Auto Mode:
        - Smart finishing moves
        - HP-based defensive decisions
        - Tactical charging
        - Balanced risk-taking
        """

        if self.ended:
            return {"ended": True, "winner": self.winner}

        player_hp = self.player_hp
        mob_hp = self.mob_hp
        player_max = int(self.player.get("current_hp", self.player.get("hp", 100)))

        # 1) Mob nearly dead → finish them
        if mob_hp <= int(self.player.get("attack", 10) * 1.4):
            action = ACTION_ATTACK

        # 2) Very low HP → Dodge or Block
        elif player_hp <= int(player_max * 0.20):
            action = ACTION_DODGE if random.random() < 0.6 else ACTION_BLOCK

        # 3) Moderately low HP → mix defenses
        elif player_hp <= int(player_max * 0.35):
            r = random.random()
            if r < 0.45:
                action = ACTION_DODGE
            elif r < 0.70:
                action = ACTION_BLOCK
            else:
                action = ACTION_ATTACK

        # 4) Mob very healthy → consider charge strategy
        elif mob_hp >= int(player_max * 0.70):
            action = ACTION_CHARGE if random.random() < 0.50 else ACTION_ATTACK

        # 5) Normal mid-fight logic
        else:
            r = random.random()
            if r < 0.70:
                action = ACTION_ATTACK
            elif r < 0.85:
                action = ACTION_DODGE
            else:
                action = ACTION_BLOCK

        return self.resolve_player_action(action)


# Session manager (global)
class SessionManager:
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


manager = SessionManager()


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
