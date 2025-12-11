# services/fight_session_battle.py
# Migration: store full mob dict (mob_full) and session_id (minimal, backwards-compatible)
# Keeps existing combat logic, adds mob_full persistence for accurate final messaging.

import json
import random
import time
import secrets
from typing import Optional, Dict, Any

import bot.db as db

SESSIONS_FILE = "data/fight_sessions_battle.json"

# Actions
ACTION_ATTACK = "attack"
ACTION_BLOCK = "block"
ACTION_DODGE = "dodge"
ACTION_CHARGE = "charge"
ACTION_AUTO = "auto"
ACTION_SURRENDER = "surrender"

# -----------------------
# BattleSession
# -----------------------
class BattleSession:
    def __init__(self, user_id: int, player_stats: Optional[Dict[str, Any]] = None,
                 mob_stats: Optional[Dict[str, Any]] = None, mob_full: Optional[Dict[str, Any]] = None,
                 session_id: Optional[str] = None):
        self.user_id = user_id
        self.player = player_stats or {"hp": 100, "attack": 10, "defense": 2, "crit_chance": 0.05}
        # store combat-only mob stats (kept for runtime) and full mob metadata for final message
        self.mob = mob_stats or {"name": "Mob", "hp": 80, "attack": 8, "defense": 1}
        self.mob_full = mob_full or {}  # NEW: contains canonical mob dict from mobs.py
        self.turn = 1
        self.ended = False
        self.winner: Optional[str] = None
        self.events = []
        self.auto_mode = False

        self.player_hp = int(self.player.get("hp", 100))
        self.mob_hp = int(self.mob.get("hp", self.mob.get("hp_max", 100)))

        # internal flags
        self._player_block = False
        self._player_dodge = False
        self._player_charge = 0
        self._mob_block = False
        self._mob_dodge = False
        self._mob_charge = 0

        # last message pointer for editing
        self._last_msg = None

        # stable session id (compact)
        self.session_id = session_id or secrets.token_hex(6)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "player": self.player,
            "mob": self.mob,
            "mob_full": self.mob_full,        # NEW persisted field
            "turn": self.turn,
            "ended": self.ended,
            "winner": self.winner,
            "events": self.events,
            "auto_mode": self.auto_mode,
            "player_hp": self.player_hp,
            "mob_hp": self.mob_hp,
            "_player_block": self._player_block,
            "_player_dodge": self._player_dodge,
            "_player_charge": self._player_charge,
            "_mob_block": self._mob_block,
            "_mob_dodge": self._mob_dodge,
            "_mob_charge": self._mob_charge,
            "_last_msg": self._last_msg,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BattleSession":
        sess = cls(
            data["user_id"],
            data.get("player"),
            data.get("mob"),
            mob_full=data.get("mob_full"),
            session_id=data.get("session_id")
        )
        sess.turn = data.get("turn", 1)
        sess.ended = data.get("ended", False)
        sess.winner = data.get("winner")
        sess.events = data.get("events", [])
        sess.auto_mode = data.get("auto_mode", False)
        sess.player_hp = data.get("player_hp", sess.player_hp)
        sess.mob_hp = data.get("mob_hp", sess.mob_hp)
        sess._player_block = data.get("_player_block", False)
        sess._player_dodge = data.get("_player_dodge", False)
        sess._player_charge = data.get("_player_charge", 0)
        sess._mob_block = data.get("_mob_block", False)
        sess._mob_dodge = data.get("_mob_dodge", False)
        sess._mob_charge = data.get("_mob_charge", 0)
        sess._last_msg = data.get("_last_msg")
        return sess

    # ---------- logging + combat resolution ----------
    def log(self, who: str, action: str, dmg: Optional[int] = None, note: str = ""):
        self.events.insert(0, {"actor": who, "action": action, "damage": dmg, "note": note, "turn": self.turn})
        if len(self.events) > 40:
            self.events = self.events[:40]

    def resolve_player_action(self, action: str):
        if self.ended:
            return
        p = self.player; m = self.mob
        p.setdefault("attack", 10); p.setdefault("defense", 0); p.setdefault("crit_chance", 0.05)
        m.setdefault("attack", 8); m.setdefault("defense", 0); m.setdefault("crit_chance", 0.03)
        note = ""; dmg = 0
        if action == ACTION_ATTACK:
            base = int(p["attack"] * (1 + 0.5 * self._player_charge))
            self._player_charge = 0
            crit_chance = float(p.get("crit_chance", 0.05))
            if self._player_dodge:
                crit_chance = min(1.0, crit_chance + 0.25)
            if random.random() < crit_chance:
                base = int(base * 1.8); note = "(CRIT!)"
            dmg = max(1, base - int(m.get("defense", 0)))
            self.mob_hp -= dmg
            self.log("player", "attack", dmg, note)
        elif action == ACTION_BLOCK:
            self._player_block = True; self.log("player", "block", None, "")
        elif action == ACTION_DODGE:
            self._player_dodge = True; self.log("player", "dodge", None, "")
        elif action == ACTION_CHARGE:
            self._player_charge = min(3, self._player_charge + 1); self.log("player", "charge", None, f"x{self._player_charge}")
        elif action == ACTION_SURRENDER:
            self.ended = True; self.winner = "mob"; self.log("player", "surrender", None, "")

        if self.mob_hp <= 0:
            self.ended = True; self.winner = "player"; return

        self.resolve_mob_ai()
        self.turn += 1

        if self.player_hp <= 0:
            self.ended = True; self.winner = "mob"

        # reset temporary flags
        self._player_block = False; self._player_dodge = False; self._mob_block = False; self._mob_dodge = False

    def resolve_mob_ai(self):
        if self.ended: return
        mstat = self._mob_stats_safe()
        r = random.random()
        if r < 0.7:
            base = int(mstat["attack"] * (1 + 0.5 * self._mob_charge))
            self._mob_charge = 0
            note = ""
            if random.random() < float(mstat.get("crit_chance", 0.03)):
                base = int(base * 1.8); note = "(CRIT!)"
            dmg = max(1, base - int(self.player.get("defense", 0)))
            self.player_hp -= dmg
            self.log("mob", "attack", dmg, note)
        elif r < 0.9:
            self._mob_block = True; self.log("mob", "block", None, "")
        else:
            self._mob_dodge = True; self.log("mob", "dodge", None, "")

    def resolve_auto_turn(self):
        if self.ended: return
        choice = random.choice([ACTION_ATTACK, ACTION_ATTACK, ACTION_CHARGE, ACTION_BLOCK])
        self.resolve_player_action(choice)

    def _mob_stats_safe(self):
        m = dict(self.mob); m.setdefault("attack", 8); m.setdefault("defense", 0); m.setdefault("crit_chance", 0.03)
        return m

# -----------------------
# Manager
# -----------------------
class BattleSessionManager:
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

    # Create session and persist under legacy user key AND sid key
    def create_session(self, user_id: int, player_stats: Dict[str, Any], mob_stats: Dict[str, Any], mob_full: Dict[str, Any]) -> BattleSession:
        sess = BattleSession(user_id, player_stats, mob_stats, mob_full)
        self._sessions[str(user_id)] = sess.to_dict()
        self._sessions[f"sid:{sess.session_id}"] = sess.to_dict()
        self.save()
        return sess

    def save_session(self, sess: BattleSession):
        self._sessions[str(sess.user_id)] = sess.to_dict()
        self._sessions[f"sid:{sess.session_id}"] = sess.to_dict()
        self.save()

    # load by legacy user_id
    def load_session(self, user_id: int) -> Optional[BattleSession]:
        data = self._sessions.get(str(user_id))
        if not data:
            return None
        sess = BattleSession.from_dict(data)
        sess._last_msg = data.get("_last_msg")
        return sess

    # NEW: load by session id (sid)
    def load_session_by_sid(self, sid: str) -> Optional[BattleSession]:
        data = self._sessions.get(f"sid:{sid}")
        if not data:
            return None
        sess = BattleSession.from_dict(data)
        sess._last_msg = data.get("_last_msg")
        return sess

    # remove by legacy user_id
    def end_session(self, user_id: int):
        k = str(user_id)
        to_delete = []
        for key, val in list(self._sessions.items()):
            try:
                if isinstance(val, dict) and val.get("user_id") == user_id and key.startswith("sid:"):
                    to_delete.append(key)
            except Exception:
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
            legacy = str(data.get("user_id"))
            self._sessions.pop(legacy, None)
        self._sessions.pop(key, None)
        self.save()

manager = BattleSessionManager()

# -----------------------
# Utilities: stat builders
# -----------------------
def build_player_stats_from_user(user: Optional[Dict[str, Any]], username_fallback: str = None) -> Dict[str, Any]:
    if not user:
        return {"hp": 100, "attack": 10, "defense": 1, "crit_chance": 0.05}
    return {
        "hp": int(user.get("xp_to_next_level", 100)),  # placeholder; keep as configured
        "attack": int(user.get("attack", user.get("atk", 10)) if user else 10),
        "defense": int(user.get("defense", user.get("armor", 1)) if user else 1),
        "crit_chance": float(user.get("crit_chance", 0.05) if user else 0.05),
        "_charge_stacks": int(user.get("_charge_stacks", 0) if user else 0)
    }

def build_mob_stats_from_mob(mob: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not mob:
        return {"hp": 80, "attack": 8, "defense": 1, "crit_chance": 0.03}
    # Use the computed auto_stats in mob dict (see mobs.py), but keep minimal keys here
    return {
        "hp": int(mob.get("hp", mob.get("hp_max", 80))),
        "attack": int(mob.get("attack", mob.get("atk", 8))),
        "defense": int(mob.get("defense", mob.get("armor", 1))),
        "crit_chance": float(mob.get("crit_chance", 0.03))
    }
