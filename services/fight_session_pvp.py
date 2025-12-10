# services/fight_session_pvp.py
import json, random, time
from typing import Optional, Dict, Any
import bot.db as db

SESSIONS_FILE = "data/fight_sessions_pvp.json"

class PvPFightSession:
    def __init__(self, attacker_id: int, defender_id: int, attacker_stats: Optional[Dict[str, Any]] = None, defender_stats: Optional[Dict[str, Any]] = None):
        self.attacker_id = attacker_id; self.defender_id = defender_id; self.turn = 1; self.ended = False; self.winner = None; self.events = []; self.auto_mode = False
        self.pvp_attacker = None; self.pvp_defender = None
        self.pvp_attacker_stats = attacker_stats or {}; self.pvp_defender_stats = defender_stats or {}
        self.attacker_hp = int(self.pvp_attacker_stats.get("hp", 100)); self.defender_hp = int(self.pvp_defender_stats.get("hp", 100))
        self._last_msg = None

    def to_dict(self):
        return {"attacker_id": self.attacker_id, "defender_id": self.defender_id, "turn": self.turn, "ended": self.ended, "winner": self.winner, "events": self.events, "auto_mode": self.auto_mode, "pvp_attacker": self.pvp_attacker, "pvp_defender": self.pvp_defender, "pvp_attacker_stats": self.pvp_attacker_stats, "pvp_defender_stats": self.pvp_defender_stats, "attacker_hp": self.attacker_hp, "defender_hp": self.defender_hp, "_last_msg": self._last_msg}

    @classmethod
    def from_dict(cls, data):
        sess = cls(data["attacker_id"], data["defender_id"], data.get("pvp_attacker_stats", {}), data.get("pvp_defender_stats", {}))
        sess.turn = data.get("turn", 1); sess.ended = data.get("ended", False); sess.winner = data.get("winner"); sess.events = data.get("events", []); sess.auto_mode = data.get("auto_mode", False); sess.pvp_attacker = data.get("pvp_attacker"); sess.pvp_defender = data.get("pvp_defender"); sess.attacker_hp = data.get("attacker_hp", sess.attacker_hp); sess.defender_hp = data.get("defender_hp", sess.defender_hp); sess._last_msg = data.get("_last_msg"); return sess

    def log(self, who, action, dmg=None, note=""):
        self.events.insert(0, {"actor": who, "action": action, "damage": dmg, "note": note, "turn": self.turn})
        if len(self.events) > 60: self.events = self.events[:60]

    def resolve_attacker_action(self, action: str):
        if self.ended: return
        a = self.pvp_attacker_stats; d = self.pvp_defender_stats
        a.setdefault("attack", 10); a.setdefault("defense", 0); a.setdefault("crit_chance", 0.05); a.setdefault("_charge_stacks", 0)
        d.setdefault("attack", 8); d.setdefault("defense", 0); d.setdefault("crit_chance", 0.03)
        note = ""; dmg = 0
        if action == "attack":
            base = int(a["attack"] * (1 + 0.5 * a.get("_charge_stacks", 0))); a["_charge_stacks"] = 0
            if random.random() < float(a.get("crit_chance", 0)): base = int(base * 1.8); note="(CRIT!)"
            dmg = max(1, base - int(d.get("defense", 0))); self.defender_hp -= dmg; self.log("attacker", "attack", dmg, note)
        elif action == "block": a["_blocking"] = True; self.log("attacker", "block")
        elif action == "dodge": a["_dodging"] = True; self.log("attacker", "dodge")
        elif action == "charge": a["_charge_stacks"] = min(3, int(a.get("_charge_stacks", 0)) + 1); self.log("attacker", "charge", None, f'x{a["_charge_stacks"]}')
        if self.defender_hp <= 0: self.ended = True; self.winner = "attacker"; return
        self.resolve_defender_ai(); self.turn += 1
        if self.attacker_hp <= 0: self.ended = True; self.winner = "defender"

    def resolve_defender_ai(self):
        if self.ended: return
        d = self.pvp_defender_stats; a = self.pvp_attacker_stats
        r = random.random()
        note = ""   # <-- fixed: ensure `note` always defined
        if r < 0.65:
            base = int(d["attack"])
            if random.random() < float(d.get("crit_chance", 0)): base = int(base * 1.8); note="(CRIT!)"
            dmg = max(1, base - int(a.get("defense", 0))); self.attacker_hp -= dmg; self.log("defender", "attack", dmg, note)
        elif r < 0.85:
            d["_blocking"] = True; self.log("defender", "block")
        else:
            d["_dodging"] = True; self.log("defender", "dodge")

    def resolve_auto_attacker_turn(self):
        if self.ended: return
        choice = random.choice(["attack","attack","charge","block"]); self.resolve_attacker_action(choice)

class PvPManager:
    def __init__(self, storage_file: str = SESSIONS_FILE):
        self.storage_file = storage_file; self._sessions = {}
        try:
            with open(self.storage_file, 'r') as f:
                self._sessions = json.load(f) or {}
        except:
            self._sessions = {}

    def save(self):
        try:
            with open(self.storage_file, 'w') as f: json.dump(self._sessions, f)
        except: pass

    def create_pvp_session(self, attacker_id, attacker_stats, defender_id, defender_stats):
        sess = PvPFightSession(attacker_id, defender_id, attacker_stats or {}, defender_stats or {})
        try: sess.pvp_attacker = db.get_user(attacker_id) or {'user_id': attacker_id}
        except: sess.pvp_attacker = {'user_id': attacker_id}
        try: sess.pvp_defender = db.get_user(defender_id) or {'user_id': defender_id}
        except: sess.pvp_defender = {'user_id': defender_id}
        self._sessions[str(attacker_id)] = sess.to_dict(); self.save(); return sess

    def save_session(self, sess): self._sessions[str(sess.attacker_id)] = sess.to_dict(); self.save()
    def load_session(self, attacker_id):
        data = self._sessions.get(str(attacker_id)); 
        if not data: return None
        sess = PvPFightSession.from_dict(data)
        try: sess.pvp_attacker = db.get_user(sess.attacker_id) or data.get('pvp_attacker')
        except: sess.pvp_attacker = data.get('pvp_attacker')
        try: sess.pvp_defender = db.get_user(sess.defender_id) or data.get('pvp_defender')
        except: sess.pvp_defender = data.get('pvp_defender')
        sess._last_msg = data.get('_last_msg'); return sess
    def end_session(self, attacker_id):
        k = str(attacker_id); 
        if k in self._sessions: del self._sessions[k]; self.save()

manager = PvPManager()
