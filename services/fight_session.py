# services/fight_session.py
from __future__ import annotations
import random
import time
import json
import os
from typing import Dict, Any, List, Optional, Tuple

# Battle defaults
BASE_PLAYER_HP = 100
BASE_MOB_HP = 100
MAX_TURNS = 60

# Action keys
ACTION_ATTACK = "attack"
ACTION_BLOCK = "block"
ACTION_DODGE = "dodge"
ACTION_CHARGE = "charge"

# ============================================================
# SESSION STORAGE — use /tmp (Render Worker writable)
# ============================================================
_SESSIONS_FILE = "/tmp/battle_sessions.json"


# ============================================================
# SAFE LOAD / SAVE
# ============================================================

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
        os.makedirs("/tmp", exist_ok=True)
        with open(_SESSIONS_FILE, "w") as f:
            json.dump(sessions, f, indent=2)
    except Exception:
        pass


# ============================================================
# FIGHT EVENT
# ============================================================

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

    def to_dict(self):
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
            "target_hp": self.target_hp
        }


# ============================================================
# FIGHT SESSION
# ============================================================

class FightSession:
    """Represents an active battle session."""

    def __init__(self, user_id: int, player: Dict[str, Any], mob: Dict[str, Any], session_id: Optional[str] = None):
        self.session_id = session_id or f"{user_id}-{int(time.time())}"
        self.user_id = user_id

        self.player = dict(player)
        self.mob = dict(mob)

        self.player_hp = int(self.player.get("current_hp", self.player.get("hp", BASE_PLAYER_HP)))
        self.mob_hp = int(self.mob.get("hp", self.mob.get("max_hp", BASE_MOB_HP)))

        self.turn = 1
        self.events: List[Dict] = []
        self.auto_mode = False
        self.started_at = int(time.time())
        self.ended = False
        self.winner: Optional[str] = None
        self.last_action_by_user: Optional[str] = None

    # ---- serialization ----

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
    def from_dict(cls, data: Dict[str, Any]):
        s = cls(
            data["user_id"],
            data["player"],
            data["mob"],
            session_id=data.get("session_id")
        )
        s.player_hp = data.get("player_hp", s.player_hp)
        s.mob_hp = data.get("mob_hp", s.mob_hp)
        s.turn = data.get("turn", s.turn)
        s.events = data.get("events", [])
        s.auto_mode = data.get("auto_mode", False)
        s.started_at = data.get("started_at", s.started_at)
        s.ended = data.get("ended", False)
        s.winner = data.get("winner", None)
        s.last_action_by_user = data.get("last_action_by_user")
        return s

    # ---- event helper ----

    def _append_event(self, ev: FightEvent):
        self.events.append(ev.to_dict())

    # ---- damage ----

    def _random_check(self, prob: float) -> bool:
        return random.random() < prob

    def _calc_base_damage(self, attacker: Dict[str, Any], defender: Dict[str, Any]) -> Tuple[int, bool]:
        attack = float(attacker.get("attack", 10))
        defense = float(defender.get("defense", 5))

        base = max(1, round(attack - defense * 0.5))

        crit = False
        if self._random_check(attacker.get("crit_chance", 0.05)):
            base *= 2
            crit = True

        low = max(1, int(base * 0.7))
        high = max(low, int(base * 1.3))

        return random.randint(low, high), crit

    # ============================================================
    # PLAYER ACTION RESOLUTION
    # ============================================================

    def resolve_player_action(self, action: str):
        if self.ended:
            return {"error": "ended"}

        p_name = self.player.get("username", "You")
        m_name = self.mob.get("name", "Mob")

        self.last_action_by_user = action

        # ---- PLAYER TURN ----

        if action == ACTION_ATTACK:
            dmg, crit = self._calc_base_damage(self.player, self.mob)

            # Mob dodge
            if self._random_check(self.mob.get("dodge_chance", 0.01)):
                self._append_event(FightEvent(self.turn, p_name, action, m_name,
                                              damage=0, dodged=True,
                                              actor_hp=self.player_hp,
                                              target_hp=self.mob_hp))
            else:
                charge = int(self.player.get("_charge_bonus", 0))
                total = max(1, dmg + charge)

                self.mob_hp = max(0, self.mob_hp - total)
                self._append_event(FightEvent(self.turn, p_name, action, m_name,
                                              damage=total, crit=crit,
                                              actor_hp=self.player_hp,
                                              target_hp=self.mob_hp))
                self.player["_charge_bonus"] = 0

        elif action == ACTION_BLOCK:
            self._append_event(FightEvent(self.turn, p_name, ACTION_BLOCK, m_name,
                                          damage=0, actor_hp=self.player_hp,
                                          target_hp=self.mob_hp))

        elif action == ACTION_DODGE:
            self._append_event(FightEvent(self.turn, p_name, ACTION_DODGE, m_name,
                                          damage=0, actor_hp=self.player_hp,
                                          target_hp=self.mob_hp))

        elif action == ACTION_CHARGE:
            bonus = int(self.player.get("attack", 10) * 0.5)
            self.player["_charge_bonus"] = self.player.get("_charge_bonus", 0) + bonus

            self._append_event(FightEvent(self.turn, p_name, ACTION_CHARGE, m_name,
                                          damage=0, actor_hp=self.player_hp,
                                          target_hp=self.mob_hp))

        # Mob defeated?
        if self.mob_hp <= 0:
            self.ended = True
            self.winner = "player"
            return {"winner": "player"}

        # ---- MOB TURN ----
        mob_attack = float(self.mob.get("attack", 6))
        mob_defense = float(self.player.get("defense", 5))

        base = max(1, round(mob_attack - mob_defense * 0.5))

        low = max(1, int(base * 0.7))
        high = max(low, int(base * 1.3))

        mob_dmg = random.randint(low, high)

        if action == ACTION_BLOCK:
            mob_dmg = int(mob_dmg * 0.4)

        if action == ACTION_DODGE:
            if self._random_check(self.player.get("dodge_chance", 0.25)):
                self._append_event(FightEvent(self.turn, m_name, "attack", p_name,
                                              damage=0, dodged=True,
                                              actor_hp=self.mob_hp,
                                              target_hp=self.player_hp))
                self.turn += 1
                return {}

        self.player_hp = max(0, self.player_hp - mob_dmg)

        self._append_event(FightEvent(self.turn, m_name, "attack", p_name,
                                      damage=mob_dmg,
                                      actor_hp=self.mob_hp,
                                      target_hp=self.player_hp))

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
            "player_hp": self.player_hp,
            "mob_hp": self.mob_hp,
            "ended": self.ended,
            "winner": self.winner
        }

    # ============================================================
    # AUTO MODE
    # ============================================================

    def resolve_auto_turn(self):
        if self.ended:
            return {"ended": True}

        player_hp = self.player_hp
        mob_hp = self.mob_hp
        p_max = int(self.player.get("current_hp", self.player.get("hp", 100)))

        if mob_hp <= int(self.player.get("attack", 10) * 1.4):
            act = ACTION_ATTACK

        elif player_hp <= int(p_max * 0.20):
            act = ACTION_DODGE if random.random() < 0.6 else ACTION_BLOCK

        elif player_hp <= int(p_max * 0.35):
            r = random.random()
            if r < 0.45: act = ACTION_DODGE
            elif r < 0.70: act = ACTION_BLOCK
            else: act = ACTION_ATTACK

        elif mob_hp >= int(p_max * 0.70):
            act = ACTION_CHARGE if random.random() < 0.50 else ACTION_ATTACK

        else:
            r = random.random()
            if r < 0.70: act = ACTION_ATTACK
            elif r < 0.85: act = ACTION_DODGE
            else: act = ACTION_BLOCK

        return self.resolve_player_action(act)


# ============================================================
# SESSION MANAGER
# ============================================================

class SessionManager:
    def __init__(self):
        self._sessions = _safe_load_sessions()

    def create_session(self, user_id: int, player: Dict[str, Any], mob: Dict[str, Any]):
        sess = FightSession(user_id, player, mob)
        self._sessions[str(user_id)] = sess.to_dict()
        _safe_save_sessions(self._sessions)
        return sess

    def load_session(self, user_id: int) -> Optional[FightSession]:
        data = self._sessions.get(str(user_id))
        if data:
            return FightSession.from_dict(data)
        return None

    def save_session(self, sess: FightSession):
        """
        CRITICAL FIX:
        Keep ALL metadata (including _last_sent_message)
        by merging existing store entry with new session data.
        """
        uid = str(sess.user_id)

        base_dict = sess.to_dict()
        existing = self._sessions.get(uid, {})

        for k, v in existing.items():
            if k not in base_dict:
                base_dict[k] = v

        self._sessions[uid] = base_dict
        _safe_save_sessions(self._sessions)

    def end_session(self, user_id: int):
        self._sessions.pop(str(user_id), None)
        _safe_save_sessions(self._sessions)

    def list_active_sessions(self) -> List[str]:
        return list(self._sessions.keys())


# global manager instance
manager = SessionManager()


# ============================================================
# STAT BUILDERS
# ============================================================

def build_player_stats_from_user(user: Dict[str, Any], username_fallback: str = "You"):
    return {
        "username": user.get("username", username_fallback),
        "current_hp": user.get("current_hp", user.get("hp", BASE_PLAYER_HP)),
        "attack": user.get("attack", 10),
        "defense": user.get("defense", 5),
        "crit_chance": user.get("crit_chance", 0.05),
        "dodge_chance": user.get("dodge_chance", 0.03),
        "xp_total": user.get("xp_total", 0),
    }


def build_mob_stats_from_mob(mob: Dict[str, Any]):
    return {
        "name": mob.get("name", "Mob"),
        "hp": mob.get("hp", mob.get("max_hp", BASE_MOB_HP)),
        "attack": mob.get("attack", 6),
        "defense": mob.get("defense", 3),
        "crit_chance": mob.get("crit_chance", 0.02),
        "dodge_chance": mob.get("dodge_chance", 0.01),
        "min_xp": mob.get("min_xp", 10),
        "max_xp": mob.get("max_xp", 25),
    }
