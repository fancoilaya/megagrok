# bot/db.py
import sqlite3
import datetime
import math
from typing import Dict, Any

DB_PATH = "grok.db"

# --------------------------
# DB INIT
# --------------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# --- ORIGINAL USERS TABLE (ensure exists) ---
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    form TEXT DEFAULT 'Tadpole'
)
""")

# --- Automatic schema upgrades (safe migrations) ---
existing_cols = [c[1] for c in cursor.execute("PRAGMA table_info(users)").fetchall()]

def add_column_if_missing(col: str, definition: str):
    if col not in existing_cols:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")

# New columns for upgraded XP system & stats
add_column_if_missing("xp_total", "INTEGER DEFAULT 0")
add_column_if_missing("xp_current", "INTEGER DEFAULT 0")
add_column_if_missing("xp_to_next_level", "INTEGER DEFAULT 200")
add_column_if_missing("level_curve_factor", "FLOAT DEFAULT 1.15")
add_column_if_missing("last_xp_change", "TEXT")

# New stat columns (wins, mobs_defeated, rituals)
add_column_if_missing("wins", "INTEGER DEFAULT 0")
add_column_if_missing("mobs_defeated", "INTEGER DEFAULT 0")
add_column_if_missing("rituals", "INTEGER DEFAULT 0")

# --- DAILY QUESTS TABLE ---
cursor.execute("""
CREATE TABLE IF NOT EXISTS daily_quests (
    user_id INTEGER PRIMARY KEY,
    quest_hop INTEGER DEFAULT 0,
    quest_hopium INTEGER DEFAULT 0,
    quest_fight INTEGER DEFAULT 0,
    reset_date TEXT
)
""")

conn.commit()


# --------------------------
# LEVEL CURVE
# --------------------------
def xp_needed_for_level(level: int, factor: float = 1.15) -> int:
    """Return dynamic XP needed for a given level."""
    base = 200
    return int(base * (factor ** (level - 1)))


# --------------------------
# EVOLUTION SYSTEM
# --------------------------
EVOLUTIONS = [
    (1, "Tadpole"),
    (5, "Hopper"),
    (10, "Ascended")
]

def get_form(level: int) -> str:
    for lvl, form in reversed(EVOLUTIONS):
        if level >= lvl:
            return form
    return "Tadpole"


# --------------------------
# USER OPERATIONS
# --------------------------
def get_user(user_id: int) -> Dict[str, Any]:
    """
    Returns the upgraded user row including stats. Creates user if missing.
    """
    cursor.execute("""
        SELECT user_id, xp_total, xp_current, xp_to_next_level,
               level, form, level_curve_factor, last_xp_change,
               wins, mobs_defeated, rituals
        FROM users WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()

    if not row:
        # Initialize new user with upgraded schema (preserve compatibility)
        cursor.execute("""
            INSERT INTO users (
                user_id, xp_total, xp_current, xp_to_next_level, level, form,
                wins, mobs_defeated, rituals
            ) VALUES (?, 0, 0, 200, 1, 'Tadpole', 0, 0, 0)
        """, (user_id,))
        conn.commit()
        return get_user(user_id)

    return {
        "user_id": row[0],
        "xp_total": row[1] or 0,
        "xp_current": row[2] or 0,
        "xp_to_next_level": row[3] or 200,
        "level": row[4] or 1,
        "form": row[5] or get_form(row[4] or 1),
        "level_curve_factor": row[6] or 1.15,
        "last_xp_change": row[7],
        "wins": row[8] or 0,
        "mobs_defeated": row[9] or 0,
        "rituals": row[10] or 0
    }


def update_user_xp(user_id: int, data: Dict[str, Any]) -> None:
    """Updates XP, level, form, and timestamp. Keeps stats untouched."""
    new_form = get_form(data["level"])
    now = datetime.datetime.utcnow().isoformat()

    cursor.execute("""
        UPDATE users
        SET xp_total = ?, xp_current = ?, xp_to_next_level = ?,
            level = ?, form = ?, last_xp_change = ?
        WHERE user_id = ?
    """, (
        data["xp_total"], data["xp_current"], data["xp_to_next_level"],
        data["level"], new_form, now,
        user_id
    ))
    conn.commit()


# --------------------------
# STAT OPERATIONS (new)
# --------------------------
def increment_win(user_id: int, count: int = 1) -> None:
    """
    Record wins. Per your rule, each win counts as one mob defeated.
    This function increments both wins and mobs_defeated by `count`.
    """
    if count <= 0:
        return

    cursor.execute("""
        INSERT INTO users (user_id, wins, mobs_defeated)
        SELECT ?, ?, ?
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE user_id = ?)
    """, (user_id, count, count, user_id))
    # The INSERT ... SELECT ... WHERE NOT EXISTS ensures user row exists,
    # but in most flows get_user is called first so row will exist.

    cursor.execute("""
        UPDATE users
        SET wins = COALESCE(wins, 0) + ?,
            mobs_defeated = COALESCE(mobs_defeated, 0) + ?
        WHERE user_id = ?
    """, (count, count, user_id))
    conn.commit()


def increment_ritual(user_id: int, count: int = 1) -> None:
    """Increment ritual counter (used for /hop)."""
    if count <= 0:
        return

    cursor.execute("""
        INSERT INTO users (user_id, rituals)
        SELECT ?, ?
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE user_id = ?)
    """, (user_id, count, user_id))

    cursor.execute("""
        UPDATE users
        SET rituals = COALESCE(rituals, 0) + ?
        WHERE user_id = ?
    """, (count, user_id))
    conn.commit()


# --------------------------
# LEADERBOARD
# --------------------------
def get_top_users(limit: int = 10):
    """
    Returns top users ordered by xp_total (lifetime XP).
    """
    cursor.execute("""
        SELECT user_id, xp_total, xp_current, xp_to_next_level, level, form,
               wins, mobs_defeated, rituals
        FROM users
        ORDER BY xp_total DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    result = []

    for row in rows:
        result.append({
            "user_id": row[0],
            "xp_total": row[1] or 0,
            "xp_current": row[2] or 0,
            "xp_to_next_level": row[3] or 200,
            "level": row[4] or 1,
            "form": row[5] or get_form(row[4] or 1),
            "wins": row[6] or 0,
            "mobs_defeated": row[7] or 0,
            "rituals": row[8] or 0
        })

    return result


# --------------------------
# DAILY QUESTS (unchanged)
# --------------------------
def get_quests(user_id: int):
    today = datetime.date.today().isoformat()

    cursor.execute("SELECT * FROM daily_quests WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("""
            INSERT INTO daily_quests (user_id, reset_date)
            VALUES (?, ?)
        """, (user_id, today))
        conn.commit()
        return {"hop": 0, "hopium": 0, "fight": 0}

    _, hop, hopium, fight, reset_date = row

    # Reset daily counters if needed
    if reset_date != today:
        cursor.execute("""
            UPDATE daily_quests
            SET quest_hop = 0,
                quest_hopium = 0,
                quest_fight = 0,
                reset_date = ?
            WHERE user_id = ?
        """, (today, user_id))
        conn.commit()

        return {"hop": 0, "hopium": 0, "fight": 0}

    return {"hop": hop, "hopium": hopium, "fight": fight}


def record_quest(user_id: int, quest_name: str) -> None:
    column = f"quest_{quest_name}"

    cursor.execute(f"""
        UPDATE daily_quests
        SET {column} = 1
        WHERE user_id = ?
    """, (user_id,))

    conn.commit()
