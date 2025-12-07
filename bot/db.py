# -----------------------------------------------------------
# MegaGrok Database Layer (Persistent Disk Compatible)
# Handles:
# - User profiles
# - XP & leveling
# - Quests (hop / fight / battle)
# - Wins, rituals
# - Cooldowns
# - Leaderboards
# -----------------------------------------------------------

import sqlite3
import json
from typing import Dict, Any, List

# -----------------------------------------------------------
# DATABASE PATH — MUST POINT TO PERSISTENT DISK ON RENDER
# -----------------------------------------------------------
DB_PATH = "/var/data/megagrok.db"   # <--- IMPORTANT


# -----------------------------------------------------------
# DB CONNECTION
# -----------------------------------------------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()


# -----------------------------------------------------------
# CREATE TABLES IF THEY DO NOT EXIST
# -----------------------------------------------------------
def init_db():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            level INTEGER DEFAULT 1,
            xp_total INTEGER DEFAULT 0,
            xp_current INTEGER DEFAULT 0,
            xp_to_next_level INTEGER DEFAULT 100,
            level_curve_factor REAL DEFAULT 1.35,
            wins INTEGER DEFAULT 0,
            mobs_defeated INTEGER DEFAULT 0,
            rituals INTEGER DEFAULT 0,
            quests TEXT,
            cooldowns TEXT,
            evolution_multiplier REAL DEFAULT 1.0
        )
    """)
    conn.commit()


# Run table initialization
init_db()


# -----------------------------------------------------------
# SAFE COLUMN ADDER (AUTO MIGRATION)
# -----------------------------------------------------------
def _add_column_if_missing(col: str, type_: str):
    cursor.execute("PRAGMA table_info(users)")
    cols = [c[1].lower() for c in cursor.fetchall()]
    if col.lower() not in cols:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {type_}")
        conn.commit()


# -----------------------------------------------------------
# GET OR CREATE USER
# -----------------------------------------------------------
def get_user(user_id: int) -> Dict[str, Any]:
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    # If user does not exist → create new row
    if not row:
        cursor.execute("""
            INSERT INTO users (
                user_id, username, level, xp_total, xp_current,
                xp_to_next_level, level_curve_factor, wins,
                mobs_defeated, rituals, quests, cooldowns, evolution_multiplier
            )
            VALUES (?, ?, 1, 0, 0, 100, 1.35, 0, 0, 0, ?, ?, 1.0)
        """, (user_id, "", json.dumps({}), json.dumps({})))
        conn.commit()
        return get_user(user_id)

    # Convert row into dictionary
    desc = [d[0] for d in cursor.description]
    return {desc[i]: row[i] for i in range(len(desc))}


# -----------------------------------------------------------
# UPDATE USER XP / LEVEL
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
# QUEST SYSTEM (hop / fight / battle)
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
    quests[quest_key] = 1

    cursor.execute(
        "UPDATE users SET quests=? WHERE user_id=?",
        (json.dumps(quests), user_id)
    )
    conn.commit()


# -----------------------------------------------------------
# WINS & RITUAL COUNT
# -----------------------------------------------------------
def increment_win(user_id: int):
    cursor.execute("UPDATE users SET wins = wins + 1 WHERE user_id=?", (user_id,))
    conn.commit()


def increment_ritual(user_id: int):
    cursor.execute("UPDATE users SET rituals = rituals + 1 WHERE user_id=?", (user_id,))
    conn.commit()


# -----------------------------------------------------------
# COOLDOWN SYSTEM (battle cooldown uses this)
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
# LEADERBOARD
# -----------------------------------------------------------
def get_top_users(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Returns top users sorted by xp_total.
    Ensures username is valid and never empty.
    """
    cursor.execute("""
        SELECT
            user_id,
            username,
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
        raw_username = r[1]

        # FIX: empty string or whitespace → fallback
        if raw_username and raw_username.strip():
            username = raw_username.strip()
        else:
            username = f"User{user_id}"

        out.append({
            "user_id": user_id,
            "username": username,
            "xp_total": r[2] or 0,
            "level": r[3] or 1,
            "wins": r[4] or 0,
            "kills": r[5] or 0,
            "rituals": r[6] or 0,
        })

    return out


# -----------------------------------------------------------
# UPDATE USERNAME  (FIXED & IMPROVED)
# -----------------------------------------------------------
def update_username(user_id: int, username: str):
    """
    Ensures usernames are stored consistently:
    - Never empty
    - Always prefixed with '@'
    - Lowercased for consistency
    """
    if not username or not username.strip():
        return  # Ignore invalid usernames

    uname = username.strip().lower()

    # Normalize to @username style
    if not uname.startswith("@"):
        uname = "@" + uname

    cursor.execute("UPDATE users SET username=? WHERE user_id=?", (uname, user_id))
    conn.commit()
