# services/fight_session_pvp.py
# PvP session manager + tuned fight engine (medium variance)
# - session_id support (sid:<hex>) and legacy attacker-key compatibility
# - stores full attacker/defender dicts (identity + stats)
# - dynamic damage: variability (0.70-1.30 attacker), crits (2.0x), dodge, block, charge
# - defender AI: sometimes block/dodge/charge, 70% counter chance, softened damage
# - auto-turn helper
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
          - hp, attack, defense, crit_chance (optional)
        They should also include identity fields:
          - user_id, username, display_name
        """
        self.attacker_id = int(attacker_id)
        self.defender_id = int(defender_id)

        # clone dicts
        self.attacker = dict(attacker_stats or {})
        self.defender = dict(defender_stats or {})

        # ensure identity fields exist
        if "user_id" not in self.attacker:
            self.attacker["user_id"] = self.attacker_id
        if "user_id" not in self.defender:
            self.defender["user_id"] = self.defender_id

        # runtime hp stored inside dicts
        self.attacker.setdefault("hp", int(self.attacker.get("hp", 100)))
        self.defender.setdefault("hp", int(self.defender.get("hp", 100)))

        # runtime flags: charged, block_active, dodge_active can be stored in attacker dict
        self.turn = 1
        self.ended = False
        self.winner: Optional[str] = None
        self.events = []  # newest-first
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

    def log(self, who: str, action: str, dmg: Optional[int] = None, note: str = ""):
        """Insert newest-first event."""
        self.events.insert(0, {"actor": who, "action": action, "damage": dmg, "note": note, "turn": self.turn, "ts": int(time.time())})
        if len(self.events) > 80:
            self.events = self.events[:80]

    # -----------------------
    # Smart dynamic attacker action resolution (medium variance tuning)
    # -----------------------
    def resolve_attacker_action(self, action: str):
        """
        Runs one attacker action and a defender response (turn-based).
        Supported actions: "attack", "block", "dodge", "charge"
        """
        if self.ended:
            return

        a = self.attacker
        d = self.defender

        # Ensure numeric fields
        a["hp"] = int(a.get("hp", 100))
        d["hp"] = int(d.get("hp", 100))
        a_atk = float(a.get("attack", 10))
        a_def = float(a.get("defense", 1))
        a_crit = float(a.get("crit_chance", 0.05))

        d_atk = float(d.get("attack", 8))
        d_def = float(d.get("defense", 1))
        d_crit = float(d.get("crit_chance", 0.01))  # defender lower crit by default

        # attacker charged state (one-turn)
        charged = bool(a.get("charged", False))
        a["charged"] = False

        note = ""
        dmg_to_def = 0

        # ---------- ATTACKER ACTION ----------
        if action == ACTION_ATTACK:
            # Attacker variance: 0.70 - 1.30 (medium variance)
            raw = a_atk * random.uniform(0.70, 1.30)

            if charged:
                raw *= 1.5
                note += "Charged! "

            # Defense mitigates 70% of its value
            dmg = raw - d_def * 0.7
            dmg = max(1.0, dmg)

            # Crit check (attacker)
            if random.random() < a_crit:
                dmg *= 2.0
                note += "CRIT! "

            dmg_to_def = int(round(dmg))

            if dmg_to_def > 0:
                d["hp"] -= dmg_to_def
                self.log("attacker", "attack", dmg_to_def, note)

        elif action == ACTION_BLOCK:
            a["block_active"] = True
            self.log("attacker", "block", None, "prepares to block")

        elif action == ACTION_DODGE:
            a["dodge_active"] = True
            self.log("attacker", "dodge", None, "tries to dodge")

        elif action == ACTION_CHARGE:
            a["charged"] = True
            self.log("attacker", "charge", None, "powers up for next hit")

        else:
            # unknown actions treated as light attack
            raw = a_atk * random.uniform(0.85, 1.05)
            dmg = max(1.0, raw - d_def * 0.7)
            if random.random() < a_crit:
                dmg *= 1.75
            dmg_to_def = int(round(dmg))
            if dmg_to_def > 0:
                d["hp"] -= dmg_to_def
                self.log("attacker", "attack", dmg_to_def, "light")

        # Check defender death after attack
        if d["hp"] <= 0:
            d["hp"] = max(0, d["hp"])
            self.ended = True
            self.winner = "attacker"
            return

        # ---------- DEFENDER AI DECISION ----------
        # Defender chooses an action probabilistically:
        # 75% -> normal counter-attempt
        # 10% -> block
        # 10% -> dodge
        # 5%  -> charge
        ai_roll = random.random()
        defender_action = "attack"
        if ai_roll < 0.05:
            defender_action = ACTION_CHARGE
        elif ai_roll < 0.15:
            defender_action = ACTION_DODGE
        elif ai_roll < 0.25:
            defender_action = ACTION_BLOCK
        else:
            defender_action = ACTION_ATTACK

        # Defender may skip counter entirely with 30% chance (counter chance = 70%)
        will_counter = random.random() < 0.70

        counter_note = ""
        counter_dmg = 0

        if not will_counter:
            # Defender does nothing this turn
            self.log("defender", "idle", None, "no counter")
        else:
            # If defender decided to block/dodge/charge, set flags & possibly not hit
            if defender_action == ACTION_BLOCK:
                d["block_active"] = True
                self.log("defender", "block", None, "defender prepares to block")
            elif defender_action == ACTION_DODGE:
                d["dodge_active"] = True
                self.log("defender", "dodge", None, "defender tries to dodge")
            elif defender_action == ACTION_CHARGE:
                d["charged"] = True
                self.log("defender", "charge", None, "defender charges power")
            else:
                # Normal counter attempt: defender variance 0.70 - 1.10 and softened damage
                raw_c = d_atk * random.uniform(0.70, 1.10)
                # Soften defender damage by multiplier (weakened)
                raw_c *= 0.85
                # Mitigate by attacker's defense weight
                counter_val = raw_c - a_def * 0.7
                counter_val = max(0.0, counter_val)

                # Defender crit chance lower (d_crit)
                if random.random() < d_crit:
                    counter_val *= 1.6
                    counter_note += "CRIT! "

                # If attacker blocked: reduce incoming counter damage
                if a.get("block_active", False):
                    counter_val *= 0.65
                    counter_note += "(blocked) "
                    a["block_active"] = False  # consumed

                # If attacker dodged: chance (40%) to fully evade counter
                if a.get("dodge_active", False):
                    if random.random() < 0.40:
                        counter_val = 0.0
                        counter_note = "Dodged!"
                    a["dodge_active"] = False

                counter_dmg = int(round(max(0, counter_val)))
                if counter_dmg > 0:
                    a["hp"] -= counter_dmg
                    self.log("defender", "attack", counter_dmg, counter_note)

        # Check attacker death
        if a["hp"] <= 0:
            a["hp"] = max(0, a["hp"])
            self.ended = True
            self.winner = "defender"

        # consume any defender block/dodge flags (they applied when set)
        if d.get("block_active", False):
            d["block_active"] = False
        if d.get("dodge_active", False):
            d["dodge_active"] = False

        # increment turn
        self.turn = int(self.turn) + 1

    def resolve_auto_attacker_turn(self):
        """AI/auto chooses an action for attacker when Auto is used."""
        if self.ended:
            return
        # Weighted choices: prefer attack, occasionally charge/block/dodge
        choice = random.choices(
            population=[ACTION_ATTACK, ACTION_ATTACK, ACTION_CHARGE, ACTION_BLOCK, ACTION_DODGE],
            weights=[0.45, 0.25, 0.15, 0.10, 0.05],
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
