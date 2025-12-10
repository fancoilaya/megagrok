# services/fight_session.py
# FightSession manager for MegaGrok PvP / PvE
# Stores both full user objects and separate combat stats.
# Drop-in replacement compatible with bot/handlers/pvp.py

import json
import random
import time
from typing import Optional, Dict, Any

# import your project's db interface
import bot.db as db

SESSIONS_FILE = "data/fight_sessions.json"


class FightSession:
    """
    Represents a single fight session (PvP).
    - attacker_id / defender_id: user ids
    - pvp_attacker / pvp_defender: full user dicts (for display_name, username, xp, level, etc)
    - pvp_attacker_stats / pvp_defender_stats: pure numeric combat stats used by engine
    - attacker_hp / defender_hp: runtime HP
    - events: list of recent actions (newest first). Each event: dict{actor, action, damage, note, turn}
    - auto_mode: bool
    - _last_msg: dict {"chat": chat_id, "msg": message_id} - used to send final card to correct chat
    """
    def __init__(self,
                 attacker_id: int,
                 defender_id: int,
                 attacker_stats: Optional[Dict[str, Any]] = None,
                 defender_stats: Optional[Dict[str, Any]] = None,
                 pvp: bool = True):
        self.attacker_id = attacker_id
        self.defender_id = defender_id
        self.turn = 1
        self.ended = False
        self.winner: Optional[str] = None  # "attacker" or "defender"
        self.events = []  # newest first
        self.auto_mode = False
        self.pvp = pvp

        # full user objects (populated on creation/load)
        self.pvp_attacker: Optional[Dict[str, Any]] = None
        self.pvp_defender: Optional[Dict[str, Any]] = None

        # combat stats (numbers used by engine)
        self.pvp_attacker_stats = attacker_stats or {}
        self.pvp_defender_stats = defender_stats or {}

        # runtime HP
        self.attacker_hp = int(self.pvp_attacker_stats.get("hp", 100))
        self.defender_hp = int(self.pvp_defender_stats.get("hp", 100))

        # pointer to last message (saved)
        self._last_msg: Optional[Dict[str, int]] = None

    # ---------------------
    # serialization helpers
    # ---------------------
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
            # denormalized user object + stats for persistence
            "pvp_attacker": self.pvp_attacker,
            "pvp_defender": self.pvp_defender,
            "pvp_attacker_stats": self.pvp_attacker_stats,
            "pvp_defender_stats": self.pvp_defender_stats,
            "_last_msg": self._last_msg
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        sess = cls(
            data["attacker_id"],
            data["defender_id"],
            data.get("pvp_attacker_stats", {}) or {},
            data.get("pvp_defender_stats", {}) or {},
            pvp=True
        )
        sess.turn = data.get("turn", 1)
        sess.ended = data.get("ended", False)
        sess.winner = data.get("winner")
        sess.events = data.get("events", []) or []
        sess.auto_mode = data.get("auto_mode", False)
        sess.attacker_hp = data.get("attacker_hp", sess.attacker_hp)
        sess.defender_hp = data.get("defender_hp", sess.defender_hp)
        sess.pvp_attacker = data.get("pvp_attacker")
        sess.pvp_defender = data.get("pvp_defender")
        sess.pvp_attacker_stats = data.get("pvp_attacker_stats", {}) or {}
        sess.pvp_defender_stats = data.get("pvp_defender_stats", {}) or {}
        sess._last_msg = data.get("_last_msg")
        return sess

    # ---------------------
    # event logging
    # ---------------------
    def log_event(self, actor: str, action: str, damage: Optional[int] = None, note: str = ""):
        # Prepend newest events
        ev = {
            "actor": actor,
            "action": action,
            "damage": damage,
            "note": note,
            "turn": self.turn
        }
        self.events.insert(0, ev)
        # keep event list bounded (avoid huge growth)
        if len(self.events) > 40:
            self.events = self.events[:40]

    # ---------------------
    # combat resolution
    # ---------------------
    def resolve_attacker_action(self, action: str):
        """Resolve attacker's action, then run defender AI unless fight ended."""
        if self.ended:
            return

        a = self.pvp_attacker_stats
        d = self.pvp_defender_stats

        # ensure default keys
        a.setdefault("attack", 10)
        a.setdefault("defense", 0)
        a.setdefault("crit_chance", 0.05)
        a.setdefault("dodge_chance", 0.05)
        a.setdefault("_charge_stacks", 0)

        d.setdefault("attack", 8)
        d.setdefault("defense", 0)
        d.setdefault("crit_chance", 0.03)
        d.setdefault("dodge_chance", 0.03)

        note = ""
        dmg = 0

        if action == "attack":
            base = int(a["attack"])
            # charge stacks amplify damage: +50% per stack
            stacks = int(a.get("_charge_stacks", 0))
            if stacks:
                base = int(base * (1 + 0.5 * stacks))
            a["_charge_stacks"] = 0
            # crit roll
            if random.random() < float(a.get("crit_chance", 0)):
                base = int(base * 1.8)
                note = "(CRIT!)"
            dmg = max(1, base - int(d.get("defense", 0)))
            self.defender_hp -= dmg
            self.log_event("attacker", "attack", dmg, note)

        elif action == "block":
            a["_blocking"] = True
            self.log_event("attacker", "block", None, "")

        elif action == "dodge":
            a["_dodging"] = True
            self.log_event("attacker", "dodge", None, "")

        elif action == "charge":
            a["_charge_stacks"] = min(3, int(a.get("_charge_stacks", 0)) + 1)
            self.log_event("attacker", "charge", None, f"x{a['_charge_stacks']}")

        # check defender death
        if self.defender_hp <= 0:
            self.ended = True
            self.winner = "attacker"
            return

        # defender AI turn
        self.resolve_defender_ai()

        # increment turn and check attacker death
        self.turn += 1
        if self.attacker_hp <= 0:
            self.ended = True
            self.winner = "defender"

        # clear temporary flags per-turn (blocking/dodging handled only on the turn they are set)
        for s in (self.pvp_attacker_stats, self.pvp_defender_stats):
            if "_blocking" in s:
                s.pop("_blocking", None)
            if "_dodging" in s:
                s.pop("_dodging", None)

    def resolve_defender_ai(self):
        """Simple defender AI: mostly attack, sometimes block/dodge."""
        if self.ended:
            return

        d = self.pvp_defender_stats
        a = self.pvp_attacker_stats

        d.setdefault("attack", 8)
        d.setdefault("crit_chance", 0.03)
        a.setdefault("defense", 0)

        r = random.random()
        note = ""
        dmg = 0

        if r < 0.65:
            base = int(d["attack"])
            if random.random() < float(d.get("crit_chance", 0)):
                base = int(base * 1.8)
                note = "(CRIT!)"
            dmg = max(1, base - int(a.get("defense", 0)))
            self.attacker_hp -= dmg
            self.log_event("defender", "attack", dmg, note)
        elif r < 0.85:
            d["_blocking"] = True
            self.log_event("defender", "block", None, "")
        else:
            d["_dodging"] = True
            self.log_event("defender", "dodge", None, "")

    def resolve_auto_attacker_turn(self):
        if self.ended:
            return
        # prefer attack, occasionally charge/block
        choice = random.choices(["attack", "attack", "attack", "charge", "block", "dodge"], k=1)[0]
        self.resolve_attacker_action(choice)


class FightSessionManager:
    """Manager that persists sessions to a JSON file and provides create/load/save operations."""

    def __init__(self, storage_file: str = SESSIONS_FILE):
        self.storage_file = storage_file
        self._sessions: Dict[str, Any] = {}
        # load existing sessions if file exists
        try:
            with open(self.storage_file, "r") as f:
                raw = json.load(f) or {}
                # raw is a dict mapping attacker_id -> session-dict
                self._sessions = raw
        except Exception:
            self._sessions = {}

    def save(self):
        try:
            # ensure folder exists
            with open(self.storage_file, "w") as f:
                json.dump(self._sessions, f)
        except Exception:
            # don't crash the bot if disk writes fail
            pass

    def create_pvp_session(self,
                           attacker_id: int,
                           attacker_stats: Optional[Dict[str, Any]],
                           defender_id: int,
                           defender_stats: Optional[Dict[str, Any]]) -> FightSession:
        """
        Creates a FightSession and immediately stores it in memory (and persists).
        attacker_stats/defender_stats are expected to be dicts returned by build_player_stats_from_user.
        """
        sess = FightSession(attacker_id, defender_id, attacker_stats or {}, defender_stats or {}, pvp=True)

        # populate full user objects from DB (preferred) — these provide display_name/username
        try:
            sess.pvp_attacker = db.get_user(attacker_id) or {"user_id": attacker_id}
        except Exception:
            sess.pvp_attacker = {"user_id": attacker_id}

        try:
            sess.pvp_defender = db.get_user(defender_id) or {"user_id": defender_id}
        except Exception:
            sess.pvp_defender = {"user_id": defender_id}

        # ensure stats are present
        sess.pvp_attacker_stats = attacker_stats or sess.pvp_attacker_stats or {"hp": 100, "attack": 10, "defense": 2, "crit_chance": 0.05}
        sess.pvp_defender_stats = defender_stats or sess.pvp_defender_stats or {"hp": 100, "attack": 8, "defense": 1, "crit_chance": 0.03}

        sess.attacker_hp = int(sess.pvp_attacker_stats.get("hp", sess.attacker_hp))
        sess.defender_hp = int(sess.pvp_defender_stats.get("hp", sess.defender_hp))

        # persist in-memory representation as plain dict
        self._sessions[str(attacker_id)] = sess.to_dict()
        self.save()
        return sess

    def save_session(self, sess: FightSession):
        # update dict and persist
        self._sessions[str(sess.attacker_id)] = sess.to_dict()
        self.save()

    def load_session(self, attacker_id: int) -> Optional[FightSession]:
        data = self._sessions.get(str(attacker_id))
        if not data:
            return None
        sess = FightSession.from_dict(data)
        # try refreshing user objects from DB for freshest display_name
        try:
            sess.pvp_attacker = db.get_user(sess.attacker_id) or data.get("pvp_attacker")
        except Exception:
            sess.pvp_attacker = data.get("pvp_attacker")
        try:
            sess.pvp_defender = db.get_user(sess.defender_id) or data.get("pvp_defender")
        except Exception:
            sess.pvp_defender = data.get("pvp_defender")
        sess._last_msg = data.get("_last_msg")
        return sess

    def end_session(self, attacker_id: int):
        # remove session from memory and persist
        key = str(attacker_id)
        if key in self._sessions:
            del self._sessions[key]
            self.save()


# ---------------------------
# Utility: build player stats
# ---------------------------
def build_player_stats_from_user(user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert a DB user row to a combat stats dict.
    Fields sourced from user row if present, otherwise reasonable defaults.
    Example output:
      {
        "hp": 120,
        "attack": 12,
        "defense": 3,
        "crit_chance": 0.06,
        "dodge_chance": 0.05
      }
    """
    if not user:
        return {"hp": 100, "attack": 10, "defense": 1, "crit_chance": 0.05, "dodge_chance": 0.03}

    stats = {}
    # allow DB to supply custom stat names if you've stored them; otherwise use defaults
    stats["hp"] = int(user.get("current_hp") or user.get("hp") or user.get("max_hp") or 100)
    stats["attack"] = int(user.get("attack") or user.get("atk") or user.get("strength") or 10)
    stats["defense"] = int(user.get("defense") or user.get("def") or  user.get("armor") or 1)
    stats["crit_chance"] = float(user.get("crit_chance") or user.get("crit") or 0.05)
    stats["dodge_chance"] = float(user.get("dodge_chance") or user.get("dodge") or 0.03)
    # internal runtime fields:
    stats["_charge_stacks"] = int(user.get("_charge_stacks", 0))
    return stats


# single manager instance used by pvp.py
manager = FightSessionManager()
