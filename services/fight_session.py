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
# SESSION STORAGE — use /var/data (writable on your runtime)
# ============================================================
_SESSIONS_FILE = "/var/data/battle_sessions.json"


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
        os.makedirs(os.path.dirname(_SESSIONS_FILE) or "/tmp", exist_ok=True)
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
                 actor_hp: int = 0, target_hp: int = 0, note: Optional[str] = None):
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
        self.note = note

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
            "target_hp": self.target_hp,
            "note": self.note
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

        # ** internal transient states **
        self.player["_charge_stacks"] = int(self.player.get("_charge_stacks", 0))
        self.player["_next_attack_guaranteed_crit"] = bool(self.player.get("_next_attack_guaranteed_crit", False))
        self.player["_perfect_block_ready"] = bool(self.player.get("_perfect_block_ready", False))

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
        # ensure internal transient flags exist
        s.player["_charge_stacks"] = int(s.player.get("_charge_stacks", 0))
        s.player["_next_attack_guaranteed_crit"] = bool(s.player.get("_next_attack_guaranteed_crit", False))
        s.player["_perfect_block_ready"] = bool(s.player.get("_perfect_block_ready", False))
        return s

    # ---- event helper ----

    def _append_event(self, ev: FightEvent):
        self.events.insert(0, ev.to_dict())  # newest first
        # cap events to last 12 to avoid blowup
        self.events = self.events[:12]

    # ---- damage / checks ----

    def _random_check(self, prob: float) -> bool:
        return random.random() < prob

    def _calc_base_damage(self, attacker: Dict[str, Any], defender: Dict[str, Any], force_crit: bool = False) -> Tuple[int, bool]:
        attack = float(attacker.get("attack", 10))
        defense = float(defender.get("defense", 5))

        base = max(1, round(attack - defense * 0.5))

        crit = False
        crit_chance = attacker.get("crit_chance", 0.05)
        if force_crit or self._random_check(crit_chance):
            base = int(base * 2.0)
            crit = True

        low = max(1, int(base * 0.75))
        high = max(low, int(base * 1.25))

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
            force_crit = bool(self.player.get("_next_attack_guaranteed_crit", False))
            dmg, crit = self._calc_base_damage(self.player, self.mob, force_crit=force_crit)

            stacks = int(self.player.get("_charge_stacks", 0))
            if stacks > 0:
                bonus = int(self.player.get("attack", 10) * 0.5 * stacks)
                dmg += bonus
                note = f"Charge x{stacks} (+{bonus})"
            else:
                note = None

            mob_dodged = False
            # if mob is currently evading (transient flag), increase dodge chance
            mob_dodge_chance = float(self.mob.get("dodge_chance", 0.01)) + (0.15 if self.mob.get("_is_evading") else 0)
            if self._random_check(mob_dodge_chance):
                mob_dodged = True
                self._append_event(FightEvent(self.turn, p_name, ACTION_ATTACK, m_name,
                                              damage=0, dodged=True,
                                              actor_hp=self.player_hp,
                                              target_hp=self.mob_hp,
                                              note="Mob dodged"))
            else:
                # consider if mob is blocking (transient)
                if self.mob.get("_is_blocking"):
                    # reduce incoming by 50%
                    dmg = max(1, int(dmg * 0.5))
                    note = (note or "") + " (mob blocking)"
                    # clear flag
                    self.mob["_is_blocking"] = False

                self.mob_hp = max(0, self.mob_hp - dmg)
                self._append_event(FightEvent(self.turn, p_name, ACTION_ATTACK, m_name,
                                              damage=dmg, crit=crit,
                                              actor_hp=self.player_hp,
                                              target_hp=self.mob_hp,
                                              note=note))

            # consume charge stacks and guaranteed crit flag
            self.player["_charge_stacks"] = 0
            self.player["_next_attack_guaranteed_crit"] = False
            self.player["_perfect_block_ready"] = False  # consumed

        elif action == ACTION_BLOCK:
            pb_ready = False
            if int(self.player.get("_charge_stacks", 0)) > 0:
                pb_ready = True
                self.player["_perfect_block_ready"] = True

            self._append_event(FightEvent(self.turn, p_name, ACTION_BLOCK, m_name,
                                          damage=0, actor_hp=self.player_hp,
                                          target_hp=self.mob_hp,
                                          note="Perfect block ready" if pb_ready else "Blocking"))

        elif action == ACTION_DODGE:
            dodge_chance = float(self.player.get("dodge_chance", 0.25))
            if self._random_check(dodge_chance):
                cnt_dmg, cnt_crit = self._calc_base_damage(self.player, self.mob, force_crit=False)
                cnt_dmg = max(1, int(cnt_dmg * 0.4))
                self.mob_hp = max(0, self.mob_hp - cnt_dmg)
                self.player["_next_attack_guaranteed_crit"] = True
                self._append_event(FightEvent(self.turn, p_name, ACTION_DODGE, m_name,
                                              damage=cnt_dmg, crit=False,
                                              actor_hp=self.player_hp,
                                              target_hp=self.mob_hp,
                                              note="Dodge success — counter"))
            else:
                self._append_event(FightEvent(self.turn, p_name, ACTION_DODGE, m_name,
                                              damage=0,
                                              actor_hp=self.player_hp,
                                              target_hp=self.mob_hp,
                                              note="Dodge failed"))

        elif action == ACTION_CHARGE:
            cur = int(self.player.get("_charge_stacks", 0))
            if cur < 3:
                self.player["_charge_stacks"] = cur + 1
            self._append_event(FightEvent(self.turn, p_name, ACTION_CHARGE, m_name,
                                          damage=0, actor_hp=self.player_hp,
                                          target_hp=self.mob_hp,
                                          note=f"Charge stacks: {self.player.get('_charge_stacks', 0)}"))

        # Mob defeated?
        if self.mob_hp <= 0:
            self.ended = True
            self.winner = "player"
            return {"winner": "player"}

        # ---- MOB TURN: smarter behavior ----
        mob_behavior = self._decide_mob_action()
        mob_action = mob_behavior.get("action", "attack")

        if mob_action == "attack":
            force_crit = False
            mob_dmg, mob_crit = self._calc_base_damage(self.mob, self.player, force_crit=force_crit)

            # If player had perfect block ready (block after charge), negate and reflect
            if self.player.get("_perfect_block_ready", False):
                reflect_pct = 0.15
                reflected = max(1, int(mob_dmg * reflect_pct))
                self.mob_hp = max(0, self.mob_hp - reflected)
                self._append_event(FightEvent(self.turn, self.mob.get("name", "Mob"), "attack", self.player.get("username", "You"),
                                              damage=0, crit=False,
                                              actor_hp=self.mob_hp,
                                              target_hp=self.player_hp,
                                              note=f"Perfect Block! Reflected {reflected}"))
                self.player["_perfect_block_ready"] = False
            else:
                if self.last_action_by_user == ACTION_BLOCK:
                    mob_dmg = int(mob_dmg * 0.35)
                    note = "Blocked"
                elif self.last_action_by_user == ACTION_DODGE:
                    # punish failed dodge: if player's last dodge event exists and had note "Dodge failed"
                    # simple approach: assume failure means punish
                    # We'll inspect most recent event for user dodge success/fail (if present)
                    last_user_ev = None
                    for e in self.events:
                        if e.get("actor") == self.player.get("username") and e.get("action") == ACTION_DODGE:
                            last_user_ev = e
                            break
                    if last_user_ev and last_user_ev.get("note") == "Dodge failed":
                        mob_dmg = int(mob_dmg * 1.2)
                        note = "Dodge failed (punished)"
                    else:
                        note = None
                else:
                    note = None

                self.player_hp = max(0, self.player_hp - mob_dmg)
                self._append_event(FightEvent(self.turn, self.mob.get("name", "Mob"), "attack", self.player.get("username", "You"),
                                              damage=mob_dmg, crit=mob_crit,
                                              actor_hp=self.mob_hp,
                                              target_hp=self.player_hp,
                                              note=note))

        elif mob_action == "block":
            self.mob["_is_blocking"] = True
            self._append_event(FightEvent(self.turn, self.mob.get("name", "Mob"), "block", self.player.get("username", "You"),
                                          damage=0, actor_hp=self.mob_hp,
                                          target_hp=self.player_hp,
                                          note="Mob is blocking"))

        elif mob_action == "dodge":
            self.mob["_is_evading"] = True
            self._append_event(FightEvent(self.turn, self.mob.get("name", "Mob"), "dodge", self.player.get("username", "You"),
                                          damage=0, actor_hp=self.mob_hp,
                                          target_hp=self.player_hp,
                                          note="Mob evasion prep"))

        if self.player_hp <= 0:
            self.ended = True
            self.winner = "mob"

        self.turn += 1

        # anti-stalemate
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
    # AUTO MODE: improved AI (single-call)
    # ============================================================

    def resolve_auto_turn(self):
        if self.ended:
            return {"ended": True}

        player_hp = self.player_hp
        mob_hp = self.mob_hp
        p_max = int(self.player.get("current_hp", self.player.get("hp", 100)))

        probable_attack = int(self.player.get("attack", 10) * (1 + 0.5 * self.player.get("_charge_stacks", 0)))
        if mob_hp <= probable_attack * 1.4:
            act = ACTION_ATTACK
        elif player_hp <= int(p_max * 0.20):
            act = ACTION_DODGE if random.random() < 0.7 else ACTION_BLOCK
        elif player_hp <= int(p_max * 0.40):
            r = random.random()
            if r < 0.5: act = ACTION_DODGE
            elif r < 0.8: act = ACTION_BLOCK
            else: act = ACTION_ATTACK
        elif mob_hp >= int(p_max * 0.7):
            act = ACTION_CHARGE if random.random() < 0.6 else ACTION_ATTACK
        else:
            r = random.random()
            if r < 0.65: act = ACTION_ATTACK
            elif r < 0.82: act = ACTION_DODGE
            elif r < 0.95: act = ACTION_BLOCK
            else: act = ACTION_CHARGE

        return self.resolve_player_action(act)

    # ============================================================
    # MOB AI scaling by tier (1..5)
    # ============================================================
    def _decide_mob_action(self) -> Dict[str, Any]:
        tier = int(self.mob.get("tier", 1))
        hp_pct = self.mob_hp / max(1, int(self.mob.get("hp", BASE_MOB_HP)))

        attack_p = 0.70
        block_p = 0.15
        dodge_p = 0.15

        if tier == 2:
            attack_p += 0.05
            dodge_p += 0.05
        elif tier == 3:
            attack_p += 0.10
            dodge_p += 0.05
            block_p -= 0.05
        elif tier == 4:
            attack_p += 0.15
            dodge_p += 0.10
            block_p -= 0.05
        elif tier == 5:
            attack_p += 0.20
            dodge_p += 0.15
            block_p -= 0.05

        if hp_pct < 0.30:
            attack_p -= 0.20
            block_p += 0.10
            dodge_p += 0.10

        # Normalize
        total = attack_p + block_p + dodge_p
        attack_p /= total
        block_p /= total
        dodge_p /= total

        r = random.random()
        if r < attack_p:
            return {"action": "attack"}
        elif r < attack_p + block_p:
            return {"action": "block"}
        else:
            return {"action": "dodge"}


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
        "dodge_chance": user.get("dodge_chance", 0.25),
        "xp_total": user.get("xp_total", 0),
        # transient defaults
        "_charge_stacks": 0,
        "_next_attack_guaranteed_crit": False,
        "_perfect_block_ready": False
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
        "tier": mob.get("tier", 1)
    }
