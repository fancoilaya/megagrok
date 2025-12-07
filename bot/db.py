# -----------------------------------------------------------
# MegaGrok Database Layer (Persistent Disk Compatible)
# Handles:
# - User profiles
# - XP & leveling
# - Quests (hop / fight / battle)
# - Wins, rituals
# - Cooldowns
# - Leaderboards (with Display Name support)
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
            display_name TEXT,                   -- NEW FIELD
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

# Ensure new column exists for older databases
def _add_column_if_missing(col: str, type_: str):
    cursor.execute("PRAGMA table_info(users)")
    cols = [c[1].lower() for c in cursor.fetchall()]
    if col.lower() not in cols:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {type_}")
        conn.commit()

_add_column_if_missing("display_name", "TEXT")


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
                user_id, username, display_name, level, xp_total, xp_current,
                xp_to_next_level, level_curve_factor, wins,
                mobs_defeated, rituals, quests, cooldowns, evolution_multiplier
            )
            VALUES (?, ?, ?, 1, 0, 0, 100, 1.35, 0, 0, 0, ?, ?, 1.0)
        """, (user_id, "", "", json.dumps({}), json.dumps({})))
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
# DISPLAY NAME MANAGEMENT
# -----------------------------------------------------------
def update_display_name(user_id: int, display_name: str):
    """
    Store first_name + last_name as Telegram display name.
    Never empty. Trim whitespace.
    """
    if not display_name or not display_name.strip():
        return
    
    clean = display_name.strip()
    cursor.execute(
        "UPDATE users SET display_name=? WHERE user_id=?",
        (clean, user_id)
    )
    conn.commit()


# -----------------------------------------------------------
# USERNAME MANAGEMENT
# -----------------------------------------------------------
def update_username(user_id: int, username: str):
    """
    Ensures usernames are stored consistently:
    - Never empty
    - Always prefixed with '@'
    - Lowercased for consistency
    """
    if not username or not username.strip():
        return

    uname = username.strip().lower()
    if not uname.startswith("@"):
        uname = "@" + uname

    cursor.execute("UPDATE users SET username=? WHERE user_id=?", (uname, user_id))
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
# COOLDOWN SYSTEM
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
# LEADERBOARD — NOW USES DISPLAY NAME
# -----------------------------------------------------------
def get_top_users(limit: int = 10) -> List[Dict[str, Any]]:
    cursor.execute("""
        SELECT
            user_id,
            username,
            display_name,
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
        username = r[1]
        display_name = r[2]

        # Priority:
        # 1️⃣ display_name
        # 2️⃣ username
        # 3️⃣ fallback User123
        if display_name and display_name.strip():
            name = display_name.strip()
        elif username and username.strip():
            name = username.strip()
        else:
            name = f"User{user_id}"

        out.append({
            "user_id": user_id,
            "display_name": name,
            "username": username,
            "xp_total": r[3] or 0,
            "level": r[4] or 1,
            "wins": r[5] or 0,
            "kills": r[6] or 0,
            "rituals": r[7] or 0,
        })

    return out
