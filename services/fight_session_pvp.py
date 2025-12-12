# services/fight_session_pvp.py
# PvP session manager + smart fight engine
# - session_id support (sid:<hex>) and legacy attacker-key compatibility
# - stores full attacker/defender dicts (identity + stats)
# - smart dynamic damage: variability, crits, dodge, block, charge, counter
# - auto-turn helper
#
# Usage:
#   from services.fight_session_pvp import manager
#   sess = manager.create_pvp_session(attacker_id, defender_id, attacker_dict, defender_dict)
#   sess.resolve_attacker_action("attack")  # or "block","dodge","charge"
#   manager.save_session(sess)
#
# File persistence: data/fight_sessions_pvp.json

import json
import random
import time
import secrets
from typing import Optional, Dict, Any

SESSIONS_FILE = "data/fight_sessions_pvp.json"

# action constants used by handler
ACTION_ATTACK = "attack"
ACTION_BLOCK = "block"
ACTION_DODGE = "dodge"
ACTION_CHARGE = "charge"
ACTION_AUTO = "auto"
ACTION_FORFEIT = "forfeit"

# Minimal RNG helper
def _randf(a=0.0, b=1.0):
    return random.uniform(a, b)

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
        """
        attacker_stats / defender_stats are dicts that MUST contain:
          - hp, attack, defense, crit_chance
        They can also include identity fields:
          - user_id, username, display_name
        This object keeps in-memory runtime fields and logs events.
        """
        self.attacker_id = int(attacker_id)
        self.defender_id = int(defender_id)

        # attacker & defender dicts (store identity + combat stats)
        # clone to avoid external mutation
        self.attacker = dict(attacker_stats or {})
        self.defender = dict(defender_stats or {})

        # ensure identity fields exist
        if "user_id" not in self.attacker:
            self.attacker["user_id"] = self.attacker_id
        if "user_id" not in self.defender:
            self.defender["user_id"] = self.defender_id

        # runtime hp stored inside dicts for convenience
        self.attacker.setdefault("hp", int(self.attacker.get("hp", 100)))
        self.defender.setdefault("hp", int(self.defender.get("hp", 100)))

        # support optional short runtime state flags inside dicts:
        # attacker["charged"], attacker["block_active"], attacker["dodge_active"]
        self.turn = 1
        self.ended = False
        self.winner: Optional[str] = None
        self.events = []  # newest-first events
        self._last_msg = None
        self._last_ui_edit = 0.0

        # session id (unguessable)
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
            "_last_ui_edit": self._last_ui_edit,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PvPFightSession":
        sess = cls(
            data["attacker_id"],
            data["defender_id"],
            attacker_stats=data.get("attacker", {}),
            defender_stats=data.get("defender", {}),
            session_id=data.get("session_id"),
        )
        sess.turn = data.get("turn", 1)
        sess.ended = data.get("ended", False)
        sess.winner = data.get("winner")
        sess.events = data.get("events", []) or []
        sess._last_msg = data.get("_last_msg")
        sess._last_ui_edit = data.get("_last_ui_edit", 0.0)
        return sess

    # Logging helper (newest-first)
    def log(self, who: str, action: str, dmg: Optional[int] = None, note: str = ""):
        self.events.insert(0, {"actor": who, "action": action, "damage": dmg, "note": note, "turn": self.turn, "ts": int(time.time())})
        if len(self.events) > 80:
            self.events = self.events[:80]

    # -----------------------
    # Smart dynamic attacker action resolution
    # -----------------------
    def resolve_attacker_action(self, action: str):
        """
        Runs one attacker action and a defender counter (turn-based).
        Supported actions: "attack", "block", "dodge", "charge"
        Sets self.ended and self.winner when match finishes.
        """
        if self.ended:
            return

        a = self.attacker
        d = self.defender

        # ensure numeric fields
        a["hp"] = int(a.get("hp", 100))
        d["hp"] = int(d.get("hp", 100))
        a_atk = float(a.get("attack", 10))
        a_def = float(a.get("defense", 1))
        a_crit = float(a.get("crit_chance", 0.05))

        d_atk = float(d.get("attack", 8))
        d_def = float(d.get("defense", 1))
        d_crit = float(d.get("crit_chance", 0.03))

        # read previous states
        charged = bool(a.get("charged", False))
        # reset charged (one-turn effect)
        a["charged"] = False

        # prepare note
        note = ""

        dmg_to_def = 0

        if action == ACTION_ATTACK:
            # base randomness ±15%
            raw = a_atk * random.uniform(0.85, 1.15)

            if charged:
                raw *= 1.5
                note += "Charged! "

            # defense mitigates 70% of its value
            dmg = raw - d_def * 0.7
            dmg = max(1.0, dmg)

            # crit check
            if random.random() < a_crit:
                dmg *= 1.75
                note += "CRIT! "

            dmg_to_def = int(dmg)

            if dmg_to_def > 0:
                d["hp"] = d["hp"] - dmg_to_def
                self.log("attacker", "attack", dmg_to_def, note)

        elif action == ACTION_BLOCK:
            # set a temporary flag that will reduce incoming damage this turn
            a["block_active"] = True
            self.log("attacker", "block", None, "prepares to block")

        elif action == ACTION_DODGE:
            a["dodge_active"] = True
            self.log("attacker", "dodge", None, "attempts to dodge")

        elif action == ACTION_CHARGE:
            a["charged"] = True
            self.log("attacker", "charge", None, "powers up for next attack")

        else:
            # unknown action: treat as light attack
            raw = a_atk * random.uniform(0.9, 1.05)
            dmg = max(1.0, raw - d_def * 0.7)
            if random.random() < a_crit:
                dmg *= 1.5
            dmg_to_def = int(dmg)
            if dmg_to_def > 0:
                d["hp"] = d["hp"] - dmg_to_def
                self.log("attacker", "attack", dmg_to_def, "light")

        # check defender death
        if d["hp"] <= 0:
            self.ended = True
            self.winner = "attacker"
            # ensure hp not negative
            d["hp"] = max(0, d["hp"])
            return

        # -----------------------
        # Defender counter / retaliation
        # -----------------------
        # defender's raw counter attack varies ±15%
        counter_raw = d_atk * random.uniform(0.85, 1.15)
        # mitigated by attacker's defense (70% mitigation weighting)
        counter = counter_raw - a_def * 0.7
        counter = max(0.0, counter)

        counter_note = ""

        # defender crit check (lower than attacker by default)
        if random.random() < d_crit:
            counter *= 1.6
            counter_note += "CRIT! "

        # if attacker blocked: reduce counter damage
        if a.get("block_active", False):
            counter *= 0.65
            counter_note += "(blocked) "
            a["block_active"] = False  # consumed

        # if attacker dodged: chance to fully evade
        if a.get("dodge_active", False):
            if random.random() < 0.40:
                # full evade
                counter = 0.0
                counter_note = "Dodged! "
            a["dodge_active"] = False  # consumed

        # small 10% chance defender does stronger hit
        if random.random() < 0.10:
            counter *= 1.15

        counter_dmg = int(max(0, round(counter)))
        if counter_dmg > 0:
            a["hp"] = a["hp"] - counter_dmg
            self.log("defender", "attack", counter_dmg, counter_note)

        if a["hp"] <= 0:
            self.ended = True
            self.winner = "defender"
            a["hp"] = max(0, a["hp"])

        # increment turn
        self.turn = int(self.turn) + 1

    # convenience auto-turn used by handlers
    def resolve_auto_attacker_turn(self):
        if self.ended:
            return
        choice = random.choices(
            population=[ACTION_ATTACK, ACTION_ATTACK, ACTION_CHARGE, ACTION_BLOCK, ACTION_DODGE],
            weights=[0.45, 0.25, 0.15, 0.1, 0.05],
            k=1
        )[0]
        self.resolve_attacker_action(choice)


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

    def create_pvp_session(self, attacker_id: int, defender_id: int, attacker_stats: Dict[str, Any], defender_stats: Dict[str, Any]) -> PvPFightSession:
        """
        Create a new PvP session. Stores under both legacy attacker key and sid key.
        attacker_stats and defender_stats should already include identity metadata.
        """
        sess = PvPFightSession(attacker_id, defender_id, attacker_stats, defender_stats)
        # persist under both keys
        self._sessions[str(attacker_id)] = sess.to_dict()
        self._sessions[f"sid:{sess.session_id}"] = sess.to_dict()
        self.save()
        return sess

    def save_session(self, sess: PvPFightSession):
        # update both keys
        self._sessions[str(sess.attacker_id)] = sess.to_dict()
        self._sessions[f"sid:{sess.session_id}"] = sess.to_dict()
        self.save()

    def load_session(self, attacker_id: int) -> Optional[PvPFightSession]:
        data = self._sessions.get(str(attacker_id))
        if not data:
            return None
        sess = PvPFightSession.from_dict(data)
        sess._last_msg = data.get("_last_msg")
        sess._last_ui_edit = data.get("_last_ui_edit", 0.0)
        return sess

    def load_session_by_sid(self, sid: str) -> Optional[PvPFightSession]:
        data = self._sessions.get(f"sid:{sid}")
        if not data:
            return None
        sess = PvPFightSession.from_dict(data)
        sess._last_msg = data.get("_last_msg")
        sess._last_ui_edit = data.get("_last_ui_edit", 0.0)
        return sess

    def end_session(self, attacker_id: int):
        # remove legacy + sid keys for sessions belonging to this attacker
        k = str(attacker_id)
        to_delete = []
        for key, val in list(self._sessions.items()):
            try:
                if isinstance(val, dict) and val.get("attacker_id") == attacker_id and key.startswith("sid:"):
                    to_delete.append(key)
            except Exception:
                continue
        for sd in to_delete:
            self._sessions.pop(sd, None)
        if k in self._sessions:
            del self._sessions[k]
        self.save()

    def end_session_by_sid(self, sid: str):
        key = f"sid:{sid}"
        data = self._sessions.get(key)
        if data and isinstance(data, dict):
            legacy = str(data.get("attacker_id"))
            self._sessions.pop(legacy, None)
        self._sessions.pop(key, None)
        self.save()


# singleton manager
manager = PvPManager()
