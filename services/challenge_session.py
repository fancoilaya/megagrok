# services/challenge_session.py
# Core engine for Challenge Mode (turn-based PvP)
# Pure logic — NO Telegram code

import time
import uuid
import random
from typing import Dict

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

TURN_SECONDS = 25
MAX_ACCEPT_SECONDS = 30

# -------------------------------------------------------------------
# IN-MEMORY STORES
# -------------------------------------------------------------------

SESSIONS: Dict[str, dict] = {}
USER_TO_SESSION: Dict[int, str] = {}

# -------------------------------------------------------------------
# STATES
# -------------------------------------------------------------------

STATE_WAITING = "WAITING_FOR_ACCEPT"
STATE_TURN_P1 = "TURN_P1"
STATE_TURN_P2 = "TURN_P2"
STATE_FINISHED = "FINISHED"
STATE_CANCELLED = "CANCELLED"

# -------------------------------------------------------------------
# SESSION CREATION
# -------------------------------------------------------------------

def create_challenge(p1_id: int, p2_id: int) -> dict:
    """
    Create a new challenge session.
    """
    if p1_id in USER_TO_SESSION or p2_id in USER_TO_SESSION:
        raise ValueError("One of the players is already in a session")

    session_id = str(uuid.uuid4())

    session = {
        "id": session_id,
        "p1": p1_id,
        "p2": p2_id,
        "state": STATE_WAITING,
        "turn_owner": None,
        "turn_deadline": None,
        "created_at": time.time(),
        "hp": {
            p1_id: 100,
            p2_id: 100,
        },
        "defending": set(),
        "log": [],
    }

    SESSIONS[session_id] = session
    USER_TO_SESSION[p1_id] = session_id
    USER_TO_SESSION[p2_id] = session_id

    return session

# -------------------------------------------------------------------
# ACCEPT / DECLINE
# -------------------------------------------------------------------

def accept_challenge(session_id: str) -> bool:
    session = SESSIONS.get(session_id)
    if not session:
        return False

    if session["state"] != STATE_WAITING:
        return False

    session["state"] = STATE_TURN_P1
    session["turn_owner"] = session["p1"]
    session["turn_deadline"] = time.time() + TURN_SECONDS
    session["log"].append("Challenge accepted. Battle started.")

    return True


def decline_challenge(session_id: str):
    session = SESSIONS.get(session_id)
    if not session:
        return

    session["state"] = STATE_CANCELLED
    cleanup_session(session_id)

# -------------------------------------------------------------------
# TURN HELPERS
# -------------------------------------------------------------------

def is_turn_expired(session: dict) -> bool:
    return session["turn_deadline"] and time.time() > session["turn_deadline"]


def switch_turn(session: dict):
    p1, p2 = session["p1"], session["p2"]
    session["turn_owner"] = p2 if session["turn_owner"] == p1 else p1
    session["turn_deadline"] = time.time() + TURN_SECONDS

# -------------------------------------------------------------------
# TIMEOUT HANDLING
# -------------------------------------------------------------------

def handle_turn_timeout(session: dict) -> bool:
    """
    Auto-action when a player times out.
    """
    if session["state"] not in (STATE_TURN_P1, STATE_TURN_P2):
        return False

    if not is_turn_expired(session):
        return False

    attacker = session["turn_owner"]
    defender = session["p2"] if attacker == session["p1"] else session["p1"]

    dmg = random.randint(6, 10)  # weaker auto-attack
    if defender in session["defending"]:
        dmg = int(dmg * 0.5)
        session["defending"].remove(defender)

    session["hp"][defender] -= dmg
    session["log"].append(
        f"⏱️ Player {attacker} timed out — auto-attack for {dmg} dmg"
    )

    end_turn(session)
    return True


def tick():
    """
    Enforce timers on all active sessions.
    """
    for session in list(SESSIONS.values()):
        if session["state"] in (STATE_TURN_P1, STATE_TURN_P2):
            handle_turn_timeout(session)

# -------------------------------------------------------------------
# ACTION VALIDATION
# -------------------------------------------------------------------

def ensure_active_turn(session: dict, player: int) -> bool:
    if session["turn_owner"] != player:
        return False

    if is_turn_expired(session):
        handle_turn_timeout(session)
        return False

    return True

# -------------------------------------------------------------------
# ACTIONS
# -------------------------------------------------------------------

def attack(session: dict, attacker: int) -> bool:
    if not ensure_active_turn(session, attacker):
        return False

    defender = session["p2"] if attacker == session["p1"] else session["p1"]

    dmg = random.randint(8, 12)
    if defender in session["defending"]:
        dmg = int(dmg * 0.5)
        session["defending"].remove(defender)

    session["hp"][defender] -= dmg
    session["log"].append(f"{attacker} attacks for {dmg} dmg")

    return True


def defend(session: dict, player: int) -> bool:
    if not ensure_active_turn(session, player):
        return False

    session["defending"].add(player)
    session["log"].append(f"{player} is defending")

    return True

# -------------------------------------------------------------------
# TURN END & RESOLUTION
# -------------------------------------------------------------------

def end_turn(session: dict):
    p1, p2 = session["p1"], session["p2"]

    if session["hp"][p1] <= 0 or session["hp"][p2] <= 0:
        session["state"] = STATE_FINISHED
        winner = p1 if session["hp"][p1] > 0 else p2
        session["log"].append(f"Winner: {winner}")
        cleanup_session(session["id"])
        return

    switch_turn(session)

# -------------------------------------------------------------------
# CLEANUP
# -------------------------------------------------------------------

def cleanup_session(session_id: str):
    session = SESSIONS.pop(session_id, None)
    if not session:
        return

    USER_TO_SESSION.pop(session["p1"], None)
    USER_TO_SESSION.pop(session["p2"], None)
