# services/fight_session_pvp.py
# PvP session manager + tuned fight engine (medium variance) + Heal action
# Persistence file: data/fight_sessions_pvp.json

import json
import random
import time
import secrets
from typing import Optional, Dict, Any

SESSIONS_FILE = "data/fight_sessions_pvp.json"

ACTION_ATTACK = "attack"
ACTION_BLOCK = "block"
ACTION_DODGE = "dodge"
ACTION_CHARGE = "charge"
ACTION_HEAL = "heal"
ACTION_FORFEIT = "forfeit"


class PvPFightSession:
    def __init__(self,
                 attacker_id: int,
                 defender_id: int,
                 attacker_stats: Optional[Dict[str, Any]] = None,
                 defender_stats: Optional[Dict[str, Any]] = None,
                 session_id: Optional[str] = None,
                 revenge_fury: bool = False):
        """
        New param added: `revenge_fury` controls full-fight revenge buff.
        """
        self.attacker_id = int(attacker_id)
        self.defender_id = int(defender_id)

        self.attacker = dict(attacker_stats or {})
        self.defender = dict(defender_stats or {})

        # Identity fallbacks
        self.attacker.setdefault("user_id", self.attacker_id)
        self.defender.setdefault("user_id", self.defender_id)

        # Runtime HP
        self.attacker.setdefault("hp", int(self.attacker.get("hp", 100)))
        self.defender.setdefault("hp", int(self.defender.get("hp", 100)))

        # Max HP for heal calculations — added
        if "max_hp" not in self.attacker:
            self.attacker["max_hp"] = int(self.attacker.get("hp", 100))
        if "max_hp" not in self.defender:
            self.defender["max_hp"] = int(self.defender.get("hp", 100))

        # Internal runtime flags
        self.attacker.setdefault("_heal_used", False)
        self.attacker.setdefault("_charge_stacks", 0)
        self.defender.setdefault("_charge_stacks", 0)

        self.turn = 1
        self.ended = False
        self.winner: Optional[str] = None
        self.events = []   # newest-first
        self._last_msg = None
        self._last_ui_edit = 0.0
        self.session_id = session_id or secrets.token_hex(6)

        # ----------------------------------------
        # APPLY REVENGE FURY BONUS (full fight buff)
        # ----------------------------------------
        self.revenge_fury = bool(revenge_fury)
        if self.revenge_fury:
            # +10% ATK, +5% DEF, +2% Crit
            self.attacker["attack"] = float(self.attacker.get("attack", 10)) * 1.10
            self.attacker["defense"] = float(self.attacker.get("defense", 5)) * 1.05
            self.attacker["crit_chance"] = float(self.attacker.get("crit_chance", 0.05)) + 0.02

            # First event log entry
            self.events.insert(0, {
                "actor": "attacker",
                "action": "buff",
                "damage": None,
                "note": "🔥⚡️💥 Revenge Fury ignites your power! (+10% ATK, +5% DEF, +2% Crit)",
                "turn": self.turn,
                "ts": int(time.time())
            })

    # ----------------------------------------
    # Serialization helpers
    # ----------------------------------------
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
            "revenge_fury": self.revenge_fury
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PvPFightSession":
        sess = cls(
            data["attacker_id"],
            data["defender_id"],
            attacker_stats=data.get("attacker", {}),
            defender_stats=data.get("defender", {}),
            session_id=data.get("session_id"),
            revenge_fury=data.get("revenge_fury", False)
        )
        sess.turn = data.get("turn", 1)
        sess.ended = data.get("ended", False)
        sess.winner = data.get("winner")
        sess.events = data.get("events", []) or []
        sess._last_msg = data.get("_last_msg")
        sess._last_ui_edit = data.get("_last_ui_edit", 0.0)
        return sess

    # ----------------------------------------
    # Log Entry
    # ----------------------------------------
    def log(self, who: str, action: str, dmg: Optional[int] = None, note: str = ""):
        self.events.insert(0, {
            "actor": who,
            "action": action,
            "damage": dmg,
            "note": note,
            "turn": self.turn,
            "ts": int(time.time())
        })
        if len(self.events) > 120:
            self.events = self.events[:120]

    # ----------------------------------------
    # Resolve attacker action
    # ----------------------------------------
    def resolve_attacker_action(self, action: str):
        if self.ended:
            return

        a = self.attacker
        d = self.defender

        # Normalize numeric values
        a["hp"] = int(a.get("hp", 100))
        d["hp"] = int(d.get("hp", 100))

        a_atk = float(a.get("attack", 10))
        a_def = float(a.get("defense", 1))
        a_crit = float(a.get("crit_chance", 0.05))

        d_atk = float(d.get("attack", 8))
        d_def = float(d.get("defense", 1))
        d_crit = float(d.get("crit_chance", 0.01))

        charged = int(a.get("_charge_stacks", 0))
        a["_charge_stacks"] = 0  # consumed

        note = ""
        dmg_to_def = 0

        # ----------- ATTACK ACTIONS -----------
        if action == ACTION_ATTACK:
            raw = a_atk * random.uniform(0.70, 1.30)
            if charged > 0:
                raw *= 1.0 + 0.30 * charged
                note += f"Charged x{charged}! "
            dmg = raw - d_def * 0.7
            dmg = max(1.0, dmg)
            if random.random() < a_crit:
                dmg *= 2.0; note += "CRIT! "
            dmg_to_def = int(round(dmg))
            d["hp"] -= dmg_to_def
            self.log("attacker", "attack", dmg_to_def, note)

        elif action == ACTION_BLOCK:
            a["_block_active"] = True
            self.log("attacker", "block", None, "prepares to block")

        elif action == ACTION_DODGE:
            a["_dodge_active"] = True
            self.log("attacker", "dodge", None, "tries to dodge")

        elif action == ACTION_CHARGE:
            a["_charge_stacks"] = min(3, int(a.get("_charge_stacks", 0)) + 1)
            self.log("attacker", "charge", None, f'x{a["_charge_stacks"]}')

        elif action == ACTION_HEAL:
            if a.get("_heal_used", False):
                self.log("attacker", "heal", None, "Heal already used")
            else:
                max_hp = int(a.get("max_hp", a["hp"]))
                amount = max(1, int(round(max_hp * 0.20)))
                a["hp"] = min(max_hp, a["hp"] + amount)
                a["_heal_used"] = True
                self.log("attacker", "heal", amount, f"+{amount} HP (20% max)")

        else:
            raw = a_atk * random.uniform(0.85, 1.05)
            if random.random() < a_crit:
                raw *= 1.5; note = "CRIT! "
            dmg = max(1.0, raw - d_def * 0.7)
            dmg_to_def = int(round(dmg))
            d["hp"] -= dmg_to_def
            self.log("attacker", "attack", dmg_to_def, note)

        # Check defender death
        if d["hp"] <= 0:
            d["hp"] = max(0, d["hp"])
            self.ended = True
            self.winner = "attacker"
            return

        # ----------- DEFENDER AI -----------
        ai_roll = random.random()
        if ai_roll < 0.05:
            d_action = ACTION_CHARGE
        elif ai_roll < 0.15:
            d_action = ACTION_DODGE
        elif ai_roll < 0.25:
            d_action = ACTION_BLOCK
        else:
            d_action = ACTION_ATTACK

        # 70% chance to counter
        if random.random() >= 0.70:
            self.log("defender", "idle", None, "defender did not counter")
        else:
            if d_action == ACTION_BLOCK:
                d["_block_active"] = True
                self.log("defender", "block", None, "defender prepares to block")

            elif d_action == ACTION_DODGE:
                d["_dodge_active"] = True
                self.log("defender", "dodge", None, "defender attempts dodge")

            elif d_action == ACTION_CHARGE:
                d["_charge_stacks"] = min(3, int(d.get("_charge_stacks", 0)) + 1)
                self.log("defender", "charge", None, f'x{d["_charge_stacks"]}')

            else:
                raw_c = d_atk * random.uniform(0.70, 1.10) * 0.85
                counter = raw_c - a_def * 0.7
                counter = max(0.0, counter)
                note_c = ""
                if random.random() < d_crit:
                    counter *= 1.6
                    note_c += "CRIT! "
                if a.get("_block_active", False):
                    counter *= 0.65
                    note_c += "(blocked) "
                    a["_block_active"] = False
                if a.get("_dodge_active", False):
                    if random.random() < 0.40:
                        counter = 0.0; note_c = "Dodged!"
                    a["_dodge_active"] = False
                dmg_back = int(round(counter))
                if dmg_back > 0:
                    a["hp"] -= dmg_back
                    self.log("defender", "attack", dmg_back, note_c)

        # Death check
        if a["hp"] <= 0:
            a["hp"] = max(0, a["hp"])
            self.ended = True
            self.winner = "defender"

        # Reset defender flags
        d.pop("_block_active", None)
        d.pop("_dodge_active", None)

        # Next turn
        self.turn += 1

    # ----------------------------------------
    # Auto attacker for future extensions
    # ----------------------------------------
    def resolve_auto_attacker_turn(self):
        if self.ended:
            return
        choice = random.choices(
            population=[ACTION_ATTACK, ACTION_ATTACK, ACTION_CHARGE, ACTION_BLOCK, ACTION_DODGE],
            weights=[0.45, 0.25, 0.15, 0.10, 0.05],
            k=1
        )[0]
        self.resolve_attacker_action(choice)


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

    def create_pvp_session(self, attacker_id: int, defender_id: int,
                           attacker_stats: Dict[str, Any], defender_stats: Dict[str, Any],
                           revenge_fury: bool = False) -> PvPFightSession:
        """
        New param `revenge_fury` used by pvp.py.
        """
        sess = PvPFightSession(attacker_id, defender_id,
                               attacker_stats, defender_stats,
                               revenge_fury=revenge_fury)
        self._sessions[str(attacker_id)] = sess.to_dict()
        self._sessions[f"sid:{sess.session_id}"] = sess.to_dict()
        self.save()
        return sess

    def save_session(self, sess: PvPFightSession):
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
        k = str(attacker_id)
        to_del = []
        for key, val in list(self._sessions.items()):
            try:
                if isinstance(val, dict) and val.get("attacker_id") == attacker_id and key.startswith("sid:"):
                    to_del.append(key)
            except Exception:
                continue
        for sd in to_del:
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


manager = PvPManager()
