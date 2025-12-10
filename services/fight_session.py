# services/fight_session.py
# Complete Fight Session Engine for MegaGrok PvP (attacker vs AI defender)
# Fully compatible with updated pvp.py

import json
import random
import time
from typing import Dict, Any, Optional
from bot import db


SESSIONS_FILE = "data/fight_sessions.json"


# ============================================================
# Player Stat Builder (used by pvp.py)
# ============================================================
def build_player_stats_from_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """Convert DB user row into combat-ready stats."""
    return {
        "hp": user.get("current_hp", user.get("hp", 100)),
        "attack": user.get("attack", 10),
        "defense": user.get("defense", 2),
        "crit_chance": float(user.get("crit_chance", 0.05)),
        "dodge_chance": float(user.get("dodge_chance", 0.05)),
        "_charge_stacks": 0,
        "_dodging": False,
        "_blocking": False,
    }


# ============================================================
# FIGHT SESSION CLASS
# ============================================================
class FightSession:
    def __init__(
        self,
        attacker_id: int,
        defender_id: int,
        attacker_stats: Dict[str, Any],
        defender_stats: Dict[str, Any],
        pvp: bool = True,
    ):
        self.attacker_id = attacker_id
        self.defender_id = defender_id
        self.turn = 1
        self.ended = False
        self.winner: Optional[str] = None  # "attacker" or "defender"
        self.auto_mode = False

        # event log (most recent first)
        self.events = []

        # full user objects (for names, display_name)
        self.pvp_attacker: Optional[Dict[str, Any]] = db.get_user(attacker_id)
        self.pvp_defender: Optional[Dict[str, Any]] = db.get_user(defender_id)

        # separate combat stats
        self.pvp_attacker_stats = attacker_stats
        self.pvp_defender_stats = defender_stats

        # dynamic HP values
        self.attacker_hp = attacker_stats.get("hp", 100)
        self.defender_hp = defender_stats.get("hp", 100)

        # allow pvp.py to store chat+message pointer
        self._last_msg: Optional[Dict[str, int]] = None

        self.pvp = pvp

    # --------------------------------------------------------
    # Serialize
    # --------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "attacker_id": self.attacker_id,
            "defender_id": self.defender_id,
            "turn": self.turn,
            "ended": self.ended,
            "winner": self.winner,
            "events": self.events,
            "auto_mode": self.auto_mode,
            "attacker_hp": self.attacker_hp,
            "defender_hp": self.defender_hp,
            "pvp_attacker": self.pvp_attacker,
            "pvp_defender": self.pvp_defender,
            "pvp_attacker_stats": self.pvp_attacker_stats,
            "pvp_defender_stats": self.pvp_defender_stats,
            "_last_msg": self._last_msg,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        sess = cls(
            data["attacker_id"],
            data["defender_id"],
            data.get("pvp_attacker_stats", {}),
            data.get("pvp_defender_stats", {}),
            pvp=True,
        )
        sess.turn = data.get("turn", 1)
        sess.ended = data.get("ended", False)
        sess.winner = data.get("winner")
        sess.events = data.get("events", [])
        sess.auto_mode = data.get("auto_mode", False)
        sess.attacker_hp = data.get("attacker_hp")
        sess.defender_hp = data.get("defender_hp")
        sess.pvp_attacker = data.get("pvp_attacker")
        sess.pvp_defender = data.get("pvp_defender")
        sess.pvp_attacker_stats = data.get("pvp_attacker_stats", {})
        sess.pvp_defender_stats = data.get("pvp_defender_stats", {})
        sess._last_msg = data.get("_last_msg")
        return sess

    # ============================================================
    # EVENT LOGGING
    # ============================================================
    def log_event(self, actor: str, action: str, damage=None, note=""):
        self.events.insert(
            0,
            {
                "actor": actor,
                "action": action,
                "damage": damage,
                "note": note,
                "turn": self.turn,
            },
        )

    # ============================================================
    # BATTLE MECHANICS
    # ============================================================
    def resolve_attacker_action(self, action: str):
        """Main combat handler for attacker inputs."""

        if self.ended:
            return

        A = self.pvp_attacker_stats
        D = self.pvp_defender_stats

        # Ensure stat keys exist
        A.setdefault("attack", 10)
        A.setdefault("defense", 2)
        A.setdefault("crit_chance", 0.05)
        A.setdefault("dodge_chance", 0.05)
        A.setdefault("_charge_stacks", 0)

        D.setdefault("attack", 8)
        D.setdefault("defense", 1)
        D.setdefault("crit_chance", 0.03)
        D.setdefault("dodge_chance", 0.03)
        D.setdefault("_charge_stacks", 0)

        # Reset defensive flags
        A["_dodging"] = False
        A["_blocking"] = False

        # ------------------------------
        # ACTION HANDLING
        # ------------------------------
        if action == "attack":
            dmg = self._calculate_attack(A, D)
            self.defender_hp -= dmg

        elif action == "block":
            A["_blocking"] = True
            self.log_event("attacker", "block")

        elif action == "dodge":
            A["_dodging"] = True
            self.log_event("attacker", "dodge")

        elif action == "charge":
            A["_charge_stacks"] = min(3, A["_charge_stacks"] + 1)
            self.log_event("attacker", "charge", note=f"x{A['_charge_stacks']}")

        # Defender dies?
        if self.defender_hp <= 0:
            self.ended = True
            self.winner = "attacker"
            return

        # Defender takes their turn
        self.resolve_defender_ai()

        # Attacker dies?
        if self.attacker_hp <= 0:
            self.ended = True
            self.winner = "defender"

        # turn increment
        self.turn += 1

    # ------------------------------
    # DEFENDER AI
    # ------------------------------
    def resolve_defender_ai(self):
        if self.ended:
            return

        A = self.pvp_attacker_stats
        D = self.pvp_defender_stats

        # Reset flags for D
        D["_dodging"] = False
        D["_blocking"] = False

        roll = random.random()

        if roll < 0.65:
            dmg = self._calculate_attack(D, A)
            self.attacker_hp -= dmg

        elif roll < 0.85:
            D["_blocking"] = True
            self.log_event("defender", "block")

        else:
            D["_dodging"] = True
            self.log_event("defender", "dodge")

    # ------------------------------
    # ATTACK CALCULATION
    # ------------------------------
    def _calculate_attack(self, attacker_stats, defender_stats) -> int:
        base = attacker_stats["attack"]

        # Charge stacks increase attack
        base *= 1 + 0.5 * attacker_stats.get("_charge_stacks", 0)
        attacker_stats["_charge_stacks"] = 0  # reset

        # Crit chance
        crit = attacker_stats.get("crit_chance", 0.05)
        note = ""
        if random.random() < crit:
            base *= 1.8
            note = "(CRIT!)"

        # Dodge?
        if defender_stats.get("_dodging", False):
            if random.random() < defender_stats.get("dodge_chance", 0.05):
                self.log_event(
                    "defender",
                    "dodge",
                    note="(Dodged)",
                )
                return 0

        dmg = max(1, int(base - defender_stats.get("defense", 0)))

        self.log_event(
            "attacker" if attacker_stats is self.pvp_attacker_stats else "defender",
            "attack",
            dmg,
            note,
        )

        return dmg

    # ============================================================
    # AUTO MODE
    # ============================================================
    def resolve_auto_attacker_turn(self):
        if self.ended:
            return
        action = random.choice(["attack", "attack", "charge", "block"])
        self.resolve_attacker_action(action)


# ============================================================
# SESSION MANAGER
# ============================================================
class FightSessionManager:
    def __init__(self, storage_file: str = SESSIONS_FILE):
        self.storage_file = storage_file
        try:
            with open(self.storage_file, "r") as f:
                self._sessions = json.load(f)
        except Exception:
            self._sessions = {}

    def save(self):
        try:
            with open(self.storage_file, "w") as f:
                json.dump(self._sessions, f)
        except Exception:
            pass

    # --------------------------------------------------------
    # CREATE SESSION
    # --------------------------------------------------------
    def create_pvp_session(
        self,
        attacker_id: int,
        attacker_stats: Dict[str, Any],
        defender_id: int,
        defender_stats: Dict[str, Any],
    ) -> FightSession:
        sess = FightSession(attacker_id, defender_id, attacker_stats, defender_stats, pvp=True)
        self._sessions[str(attacker_id)] = sess.to_dict()
        self.save()
        return sess

    # --------------------------------------------------------
    # LOAD SESSION
    # --------------------------------------------------------
    def load_session(self, attacker_id: int) -> Optional[FightSession]:
        data = self._sessions.get(str(attacker_id))
        if not data:
            return None
        sess = FightSession.from_dict(data)

        # Refresh user objects in case user renamed or updated HP
        sess.pvp_attacker = db.get_user(sess.attacker_id) or sess.pvp_attacker
        sess.pvp_defender = db.get_user(sess.defender_id) or sess.pvp_defender

        return sess

    # --------------------------------------------------------
    # SAVE SESSION
    # --------------------------------------------------------
    def save_session(self, sess: FightSession):
        self._sessions[str(sess.attacker_id)] = sess.to_dict()
        self.save()

    # --------------------------------------------------------
    # END SESSION
    # --------------------------------------------------------
    def end_session(self, attacker_id: int):
        if str(attacker_id) in self._sessions:
            del self._sessions[str(attacker_id)]
            self.save()


# Instantiate a global manager
manager = FightSessionManager()
