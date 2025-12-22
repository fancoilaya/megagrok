# services/challenge_session.py
# Challenge session engine — stable, auto-cleaning

import time
import uuid

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

MAX_ACCEPT_SECONDS = 30
TURN_SECONDS = 20

STATE_WAITING = "WAITING"
STATE_TURN_P1 = "TURN_P1"
STATE_TURN_P2 = "TURN_P2"
STATE_FINISHED = "FINISHED"
STATE_CANCELLED = "CANCELLED"

SESSIONS = {}
USER_TO_SESSION = {}


# -------------------------------------------------------------------
# SESSION LIFECYCLE
# -------------------------------------------------------------------

def create_challenge(p1: int, p2: int):
    if p1 in USER_TO_SESSION or p2 in USER_TO_SESSION:
        raise ValueError("User busy")

    sid = str(uuid.uuid4())

    session = {
        "id": sid,
        "p1": p1,
        "p2": p2,
        "state": STATE_WAITING,
        "created_at": time.time(),
        "turn_owner": None,
        "turn_deadline": None,
        "hp": {p1: 100, p2: 100},
        "log": [],
        "winner": None,
    }

    SESSIONS[sid] = session
    USER_TO_SESSION[p1] = sid
    USER_TO_SESSION[p2] = sid

    return session


def accept_challenge(session_id: str) -> bool:
    session = SESSIONS.get(session_id)
    if not session or session["state"] != STATE_WAITING:
        return False

    session["state"] = STATE_TURN_P1
    session["turn_owner"] = session["p1"]
    session["turn_deadline"] = time.time() + TURN_SECONDS
    return True


def decline_challenge(session_id: str):
    session = SESSIONS.get(session_id)
    if not session:
        return

    session["state"] = STATE_CANCELLED
    cleanup_session(session_id)


# -------------------------------------------------------------------
# TURN LOGIC
# -------------------------------------------------------------------

def attack(session: dict, uid: int) -> bool:
    if uid != session["turn_owner"]:
        return False

    opponent = session["p2"] if uid == session["p1"] else session["p1"]
    session["hp"][opponent] -= 20

    if session["hp"][opponent] <= 0:
        session["state"] = STATE_FINISHED
        session["winner"] = uid

    return True


def defend(session: dict, uid: int) -> bool:
    if uid != session["turn_owner"]:
        return False
    return True


def end_turn(session: dict):
    if session["state"] == STATE_FINISHED:
        cleanup_session(session["id"])
        return

    session["turn_owner"] = (
        session["p2"] if session["turn_owner"] == session["p1"] else session["p1"]
    )
    session["turn_deadline"] = time.time() + TURN_SECONDS


# -------------------------------------------------------------------
# TIMEOUTS & CLEANUP
# -------------------------------------------------------------------

def handle_turn_timeout(session: dict):
    if time.time() < session["turn_deadline"]:
        return

    opponent = (
        session["p2"] if session["turn_owner"] == session["p1"] else session["p1"]
    )
    session["hp"][opponent] -= 10

    if session["hp"][opponent] <= 0:
        session["state"] = STATE_FINISHED
        session["winner"] = session["turn_owner"]
        cleanup_session(session["id"])
        return

    end_turn(session)


def is_accept_expired(session: dict) -> bool:
    return (
        session["state"] == STATE_WAITING
        and time.time() > session["created_at"] + MAX_ACCEPT_SECONDS
    )


def tick():
    for session in list(SESSIONS.values()):

        # Auto-expire unanswered challenges
        if is_accept_expired(session):
            cleanup_session(session["id"])
            continue

        # Enforce turn timers
        if session["state"] in (STATE_TURN_P1, STATE_TURN_P2):
            handle_turn_timeout(session)


def cleanup_session(session_id: str):
    session = SESSIONS.pop(session_id, None)
    if not session:
        return

    USER_TO_SESSION.pop(session["p1"], None)
    USER_TO_SESSION.pop(session["p2"], None)
