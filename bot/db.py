# bot/db.py
# -----------------------------------------------------------
# Central MegaGrok Database Layer
# Handles Users, XP, Quests, Wins, Cooldowns & Leaderboards
# -----------------------------------------------------------

import sqlite3
import json
import time
from typing import Dict, Any, List

DB_PATH = "/var/data/megagrok.db"

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()


# -----------------------------------------------------------
# Ensure required columns exist (safe auto-migration)
# -----------------------------------------------------------

def _add_column_if_missing(col: str, type_: str):
    cursor.execute("PRAGMA table_info(users)")
    cols = [c[1].lower() for c in cursor.fetchall()]
    if col.lower() not in cols:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {type_}")
        conn.commit()


# -----------------------------------------------------------
# USER RETRIEVAL & CREATION
# -----------------------------------------------------------

def get_user(user_id: int) -> Dict[str, Any]:
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row:
        # Create new user with defaults
        cursor.execute("""
            INSERT INTO users (user_id, username, level, xp_total, xp_current,
                               xp_to_next_level, level_curve_factor, wins,
                               mobs_defeated, rituals, evolution_multiplier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, "", 1, 0, 0, 100, 1.35, 0, 0, 0, 1.0))
        conn.commit()
        return get_user(user_id)

    # Map columns → dict
    desc = [d[0] for d in cursor.description]
    return {desc[i]: row[i] for i in range(len(desc))}


# -----------------------------------------------------------
# XP / LEVEL UPDATES
# -----------------------------------------------------------

def update_user_xp(user_id: int, data: Dict[str, Any]):
    fields = []
    values = []

    for key, val in data.items():
        fields.append(f"{key}=?")
        values.append(val)

    values.append(user_id)

    cursor.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id=?", values)
    conn.commit()


# -----------------------------------------------------------
# QUEST STATE SYSTEM (fight / hop / battle)
# -----------------------------------------------------------

def get_quests(user_id: int) -> Dict[str, Any]:
    _add_column_if_missing("quests", "TEXT")

    cursor.execute("SELECT quests FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row or not row[0]:
        return {}

    try:
        return json.loads(row[0])
    except:
        return {}


def record_quest(user_id: int, quest_key: str):
    quests = get_quests(user_id)
    quests[quest_key] = 1  # mark as completed

    cursor.execute(
        "UPDATE users SET quests=? WHERE user_id=?",
        (json.dumps(quests), user_id)
    )
    conn.commit()


# -----------------------------------------------------------
# WINS / RITUAL COUNTERS
# -----------------------------------------------------------

def increment_win(user_id: int):
    cursor.execute("UPDATE users SET wins = wins + 1 WHERE user_id=?", (user_id,))
    conn.commit()


def increment_ritual(user_id: int):
    cursor.execute("UPDATE users SET rituals = rituals + 1 WHERE user_id=?", (user_id,))
    conn.commit()


# -----------------------------------------------------------
# COOLDOWN HANDLING (battle system)
# -----------------------------------------------------------

def get_cooldowns(user_id: int) -> Dict[str, Any]:
    _add_column_if_missing("cooldowns", "TEXT")

    cursor.execute("SELECT cooldowns FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row or not row[0]:
        return {}

    try:
        return json.loads(row[0])
    except:
        return {}


def set_cooldowns(user_id: int, cooldowns: Dict[str, Any]):
    cursor.execute(
        "UPDATE users SET cooldowns=? WHERE user_id=?",
        (json.dumps(cooldowns), user_id)
    )
    conn.commit()


# -----------------------------------------------------------
# LEADERBOARD (Top Players)
# -----------------------------------------------------------

def get_top_users(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Returns top players sorted by total XP.
    Shape guaranteed to match leaderboard poster v2.
    """
    cursor.execute("""
        SELECT
            user_id,
            COALESCE(username, ''),
            xp_total,
            level,
            wins,
            mobs_defeated,
            rituals
        FROM users
        ORDER BY xp_total DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    out = []

    for r in rows:
        user_id = r[0]
        username = r[1] or f"User{user_id}"
        xp_total = r[2] or 0
        level = r[3] or 1
        wins = r[4] or 0
        kills = r[5] or 0
        rituals = r[6] or 0

        out.append({
            "user_id": user_id,
            "username": username,
            "xp_total": xp_total,
            "level": level,
            "wins": wins,
            "kills": kills,
            "rituals": rituals,
        })

    return out


# -----------------------------------------------------------
# SAVE USERNAME (optional, updated auto)
# -----------------------------------------------------------

def update_username(user_id: int, username: str):
    cursor.execute("UPDATE users SET username=? WHERE user_id=?", (username, user_id))
    conn.commit()
