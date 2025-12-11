# services/fight_session_battle.py
# Finalized migration: session_id, mob_full, and evolution-driven player stats (reset per-battle).
# Minimal, backwards-compatible persistence (legacy user key + sid:<session_id>).
# Player stats derive from level + evolutions.get_fight_bonus (no DB changes required).
#
# NOTE: persistent HP is planned for the future (VIP/coin integration). For now HP resets every battle.

import json
import random
import time
import secrets
from typing import Optional, Dict, Any

import bot.db as db
import bot.evolutions as evolutions

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
        # combat-only player/mob stats (numbers used in resolution)
        self.player = player_stats or {"hp": 100, "attack": 10, "defense": 2, "crit_chance": 0.05}
        self.mob = mob_stats or {"name": "Mob", "hp": 80, "attack": 8, "defense": 1}
        # full mob metadata from mobs.py (name, min_xp, max_xp, drops, etc.)
        self.mob_full = mob_full or {}
        self.turn = 1
        self.ended = False
        self.winner: Optional[str] = None
        self.events = []  # newest-first list of event dicts
        self.auto_mode = False

        # runtime HP values (player_hp is reset at session creation using derived stats)
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
            "mob_full": self.mob_full,
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

    def log(self, who: str, action: str, dmg: Optional[int] = None, note: str = ""):
        self.events.insert(0, {"actor": who, "action": action, "damage": dmg, "note": note, "turn": self.turn, "ts": int(time.time())})
        # keep a bounded log
        if len(self.events) > 40:
            self.events = self.events[:40]

    # Combat resolution (unchanged logic)
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
        # Derive player stats (hp/attack/defense) from user's level + evolutions fight_bonus
        user = db.get_user(user_id)
        level = int(user.get("level", 1))
        fight_bonus = evolutions.get_fight_bonus(level)

        # Derived stats (Option B)
        derived = {
            "hp": max(20, int(120 + level * 8 + fight_bonus * 15)),
            "attack": max(1, int(10 + level * 2 + fight_bonus * 2)),
            "defense": max(0, int(4 + level * 1 + fight_bonus * 1)),
            "crit_chance": round(0.05 + level * 0.001, 3)
        }
        sess = BattleSession(user_id, derived, mob_stats, mob_full)
        # persist both legacy and sid keys
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

    # load by sid
    def load_session_by_sid(self, sid: str) -> Optional[BattleSession]:
        data = self._sessions.get(f"sid:{sid}")
        if not data:
            return None
        sess = BattleSession.from_dict(data)
        sess._last_msg = data.get("_last_msg")
        return sess

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
# Utilities: stat builders (kept for external use)
# -----------------------
def build_player_stats_from_user(user: Optional[Dict[str, Any]], username_fallback: str = None) -> Dict[str, Any]:
    """
    Derive combat stats from the user's level and evolution fight bonus.
    Player HP is NOT persisted (reset per-battle). For persistent HP later, store 'hp_current' in DB.
    """
    if not user:
        return {"hp": 120, "attack": 10, "defense": 4, "crit_chance": 0.05}
    level = int(user.get("level", 1))
    fight_bonus = evolutions.get_fight_bonus(level)
    return {
        "hp": max(20, int(120 + level * 8 + fight_bonus * 15)),
        "attack": max(1, int(10 + level * 2 + fight_bonus * 2)),
        "defense": max(0, int(4 + level * 1 + fight_bonus * 1)),
        "crit_chance": round(0.05 + level * 0.001, 3)
    }

def build_mob_stats_from_mob(mob: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not mob:
        return {"hp": 80, "attack": 8, "defense": 1, "crit_chance": 0.03}
    return {
        "hp": int(mob.get("hp", mob.get("hp_max", 80))),
        "attack": int(mob.get("attack", mob.get("atk", 8))),
        "defense": int(mob.get("defense", mob.get("armor", 1))),
        "crit_chance": float(mob.get("crit_chance", 0.03))
    }
