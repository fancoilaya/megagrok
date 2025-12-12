# services/fight_session_pvp.py
# Patched PvP session manager: adds session_id, sid:<session_id> persistence,
# load_session_by_sid and end_session_by_sid helpers.
#
# Minimal behavioral changes. Backwards-compatible with legacy attacker_id-keyed sessions.

import json
import random
import time
import secrets
from typing import Optional, Dict, Any

import bot.db as db

SESSIONS_FILE = "data/fight_sessions_pvp.json"

# PvP action constants (keep in sync with handler)
ACTION_ATTACK = "attack"
ACTION_BLOCK = "block"
ACTION_SPECIAL = "special"
ACTION_FLEE = "flee"
ACTION_ACCEPT = "accept"
ACTION_DECLINE = "decline"

# -----------------------
# PvP Fight Session
# -----------------------
class PvPFightSession:
    def __init__(self,
                 attacker_id: int,
                 defender_id: int,
                 attacker_stats: Optional[Dict[str, Any]] = None,
                 defender_stats: Optional[Dict[str, Any]] = None,
                 session_id: Optional[str] = None):
        self.attacker_id = attacker_id
        self.defender_id = defender_id
        self.attacker = attacker_stats or {"hp": 100, "attack": 10, "defense": 1}
        self.defender = defender_stats or {"hp": 100, "attack": 10, "defense": 1}
        self.turn = 1
        self.ended = False
        self.winner: Optional[str] = None
        self.events = []  # newest-first
        self._last_msg = None
        # NEW: stable session id (compact)
        self.session_id = session_id or secrets.token_hex(6)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attacker_id": self.attacker_id,
            "defender_id": self.defender_id,
            "attacker": self.attacker,
            "defender": self.defender,
            "turn": self.turn,
            "ended": self.ended,
            "winner": self.winner,
            "events": self.events,
            "_last_msg": self._last_msg,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PvPFightSession":
        sess = cls(
            data["attacker_id"],
            data["defender_id"],
            data.get("attacker"),
            data.get("defender"),
            session_id=data.get("session_id"),
        )
        sess.turn = data.get("turn", 1)
        sess.ended = data.get("ended", False)
        sess.winner = data.get("winner")
        sess.events = data.get("events", [])
        sess._last_msg = data.get("_last_msg")
        return sess

    def log(self, who: str, action: str, dmg: Optional[int] = None, note: str = ""):
        self.events.insert(0, {"actor": who, "action": action, "damage": dmg, "note": note, "turn": self.turn, "ts": int(time.time())})
        if len(self.events) > 60:
            self.events = self.events[:60]

    # Simple resolution example (you probably already had similar logic)
    def resolve_attacker_action(self, action: str):
        if self.ended:
            return
        a = self.attacker; d = self.defender
        a.setdefault("attack", 10); d.setdefault("defense", 0)
        if action == ACTION_ATTACK:
            dmg = max(1, int(a["attack"]) - int(d.get("defense", 0)))
            d["hp"] = d.get("hp", 100) - dmg
            self.log("attacker", "attack", dmg)
        elif action == ACTION_BLOCK:
            self.log("attacker", "block", None)
        elif action == ACTION_SPECIAL:
            dmg = max(1, int(a["attack"]) + 3 - int(d.get("defense", 0)))
            d["hp"] = d.get("hp", 100) - dmg
            self.log("attacker", "special", dmg)

        # simple defender reply (turn-based)
        if d.get("hp", 0) <= 0:
            self.ended = True; self.winner = "attacker"; return

        # defender AI / auto-response (keep simple)
        dmg = max(1, int(d.get("attack", 8)) - int(a.get("defense", 0)))
        a["hp"] = a.get("hp", 100) - dmg
        self.log("defender", "attack", dmg)

        if a.get("hp", 0) <= 0:
            self.ended = True; self.winner = "defender"

        self.turn += 1

# -----------------------
# Manager
# -----------------------
class PvPManager:
    def __init__(self, storage_file: str = SESSIONS_FILE):
        self.storage_file = storage_file
        self._sessions: Dict[str, Dict[str, Any]] = {}
        try:
            with open(self.storage_file, "r") as f:
                self._sessions = json.load(f) or {}
        except Exception:
            self._sessions = {}

    def save(self):
        try:
            with open(self.storage_file, "w") as f:
                json.dump(self._sessions, f)
        except Exception:
            pass

    # Create a new PvP session and persist under both legacy attacker key and sid key
    def create_pvp_session(self, attacker_id: int, defender_id: int, attacker_stats: Dict[str, Any], defender_stats: Dict[str, Any]) -> PvPFightSession:
        sess = PvPFightSession(attacker_id, defender_id, attacker_stats, defender_stats)
        # legacy key: attacker id (string)
        self._sessions[str(attacker_id)] = sess.to_dict()
        # new key: sid:<session_id>
        self._sessions[f"sid:{sess.session_id}"] = sess.to_dict()
        self.save()
        return sess

    def save_session(self, sess: PvPFightSession):
        self._sessions[str(sess.attacker_id)] = sess.to_dict()
        self._sessions[f"sid:{sess.session_id}"] = sess.to_dict()
        self.save()

    # legacy load by attacker id
    def load_session(self, attacker_id: int) -> Optional[ PvPFightSession ]:
        data = self._sessions.get(str(attacker_id))
        if not data:
            return None
        sess = PvPFightSession.from_dict(data)
        sess._last_msg = data.get("_last_msg")
        return sess

    # NEW: load by sid
    def load_session_by_sid(self, sid: str) -> Optional[ PvPFightSession ]:
        data = self._sessions.get(f"sid:{sid}")
        if not data:
            return None
        sess = PvPFightSession.from_dict(data)
        sess._last_msg = data.get("_last_msg")
        return sess

    # legacy end by attacker id
    def end_session(self, attacker_id: int):
        k = str(attacker_id)
        to_delete = []
        for key, val in list(self._sessions.items()):
            try:
                if isinstance(val, dict) and val.get("attacker_id") == attacker_id and key.startswith("sid:"):
                    to_delete.append(key)
            except:
                continue
        for sd in to_delete:
            self._sessions.pop(sd, None)
        if k in self._sessions:
            del self._sessions[k]
        self.save()

    # NEW: end by sid
    def end_session_by_sid(self, sid: str):
        key = f"sid:{sid}"
        data = self._sessions.get(key)
        if data and isinstance(data, dict):
            legacy = str(data.get("attacker_id"))
            self._sessions.pop(legacy, None)
        self._sessions.pop(key, None)
        self.save()

# Singleton manager
manager = PvPManager()
