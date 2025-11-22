# bot/db.py
import sqlite3
import datetime
import os
from typing import Dict, Any, List

# Path to DB (relative to repo root). Adjust if you prefer a different location.
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "grok.db"))

# --------------------------
# DB CONNECTION & INIT
# --------------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Ensure foreign keys and sensible pragmas (not strictly needed here but good practice)
cursor.execute("PRAGMA foreign_keys = ON;")
cursor.execute("PRAGMA journal_mode = WAL;")
cursor.execute("PRAGMA synchronous = NORMAL;")

# --- Create base users table if missing (legacy compat) ---
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    form TEXT DEFAULT 'Tadpole'
)
""")
conn.commit()

# Utility: read existing columns for safe migrations
def _existing_user_columns() -> List[str]:
    cursor.execute("PRAGMA table_info(users)")
    rows = cursor.fetchall()
    return [r[1] for r in rows]

_existing_cols = _existing_user_columns()

def _add_column_if_missing(col_name: str, col_def: str):
    global _existing_cols
    if col_name not in _existing_cols:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
        conn.commit()
        _existing_cols = _existing_user_columns()

# Add upgraded columns (safe migrations)
_add_column_if_missing("xp_total", "INTEGER DEFAULT 0")
_add_column_if_missing("xp_current", "INTEGER DEFAULT 0")
_add_column_if_missing("xp_to_next_level", "INTEGER DEFAULT 200")
_add_column_if_missing("level_curve_factor", "REAL DEFAULT 1.15")
_add_column_if_missing("last_xp_change", "TEXT")
_add_column_if_missing("wins", "INTEGER DEFAULT 0")
_add_column_if_missing("mobs_defeated", "INTEGER DEFAULT 0")
_add_column_if_missing("rituals", "INTEGER DEFAULT 0")
_add_column_if_missing("contract_address", "TEXT")
_add_column_if_missing("tg_handle", "TEXT")

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
# LEVEL / XP CURVE helpers
# --------------------------
def xp_needed_for_level(level: int, factor: float = 1.15, base: int = 200) -> int:
    """
    Returns required XP for `level`.
    Exponential curve: base * factor^(level-1)
    """
    if level <= 1:
        return base
    return int(base * (factor ** (level - 1)))

# --------------------------
# EVOLUTION MAPPING
# --------------------------
EVOLUTIONS = [
    (1, "Tadpole"),
    (5, "Hopper"),
    (10, "Ascended"),
]

def get_form(level: int) -> str:
    for lvl, form in reversed(EVOLUTIONS):
        if level >= lvl:
            return form
    return "Tadpole"


# --------------------------
# CORE USER HELPERS
# --------------------------
def _ensure_user_row(user_id: int):
    """
    Ensure a row exists for the user. Does not overwrite existing non-null columns.
    """
    cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute("""
            INSERT INTO users (
                user_id, username, xp_total, xp_current, xp_to_next_level, level, form,
                level_curve_factor, wins, mobs_defeated, rituals
            ) VALUES (?, ?, 0, 0, 200, 1, 'Tadpole', 1.15, 0, 0, 0)
        """, (user_id, f"User{user_id}"))
        conn.commit()

# --------------------------
# PUBLIC DB API
# --------------------------
def get_user(user_id: int) -> Dict[str, Any]:
    """
    Return an up-to-date dictionary for the user.
    If the user does not exist, create a default row and return it.
    """
    _ensure_user_row(user_id)

    cursor.execute("""
        SELECT user_id, username, xp_total, xp_current, xp_to_next_level,
               level, form, level_curve_factor, last_xp_change,
               wins, mobs_defeated, rituals, contract_address, tg_handle
        FROM users WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    if not row:
        # This should not happen due to _ensure_user_row, but fallback:
        return {
            "user_id": user_id,
            "username": f"User{user_id}",
            "xp_total": 0,
            "xp_current": 0,
            "xp_to_next_level": 200,
            "level": 1,
            "form": "Tadpole",
            "level_curve_factor": 1.15,
            "last_xp_change": None,
            "wins": 0,
            "mobs_defeated": 0,
            "rituals": 0,
            "contract_address": None,
            "tg_handle": None
        }

    return {
        "user_id": row[0],
        "username": row[1] or f"User{row[0]}",
        "xp_total": row[2] or 0,
        "xp_current": row[3] or 0,
        "xp_to_next_level": row[4] or 200,
        "level": row[5] or 1,
        "form": row[6] or get_form(row[5] or 1),
        "level_curve_factor": float(row[7]) if row[7] is not None else 1.15,
        "last_xp_change": row[8],
        "wins": row[9] or 0,
        "mobs_defeated": row[10] or 0,
        "rituals": row[11] or 0,
        "contract_address": row[12],
        "tg_handle": row[13]
    }

def update_user_xp(user_id: int, data: Dict[str, Any]) -> None:
    """
    Update xp-related fields and update form based on level.
    Expected keys in data: xp_total, xp_current, xp_to_next_level, level
    """
    _ensure_user_row(user_id)

    # normalize values and default to current DB values if missing
    user = get_user(user_id)
    xp_total = int(data.get("xp_total", user["xp_total"]))
    xp_current = int(data.get("xp_current", user["xp_current"]))
    xp_to_next = int(data.get("xp_to_next_level", user["xp_to_next_level"]))
    level = int(data.get("level", user["level"]))

    new_form = get_form(level)
    now = datetime.datetime.utcnow().isoformat()

    cursor.execute("""
        UPDATE users
        SET xp_total = ?, xp_current = ?, xp_to_next_level = ?,
            level = ?, form = ?, last_xp_change = ?
        WHERE user_id = ?
    """, (xp_total, xp_current, xp_to_next, level, new_form, now, user_id))
    conn.commit()

def set_username(user_id: int, username: str) -> None:
    _ensure_user_row(user_id)
    cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
    conn.commit()

def set_contract_and_tg(user_id: int, contract_address: str = "", tg_handle: str = ""):
    _ensure_user_row(user_id)
    cursor.execute("UPDATE users SET contract_address = ?, tg_handle = ? WHERE user_id = ?",
                   (contract_address, tg_handle, user_id))
    conn.commit()


# --------------------------
# STAT OPERATIONS
# --------------------------
def increment_win(user_id: int, count: int = 1) -> None:
    """
    Increment wins and mobs_defeated together (per your rule).
    """
    if count <= 0:
        return
    _ensure_user_row(user_id)
    cursor.execute("""
        UPDATE users
        SET wins = COALESCE(wins, 0) + ?,
            mobs_defeated = COALESCE(mobs_defeated, 0) + ?
        WHERE user_id = ?
    """, (count, count, user_id))
    conn.commit()

def increment_fights(user_id: int, count: int = 1) -> None:
    if count <= 0:
        return
    _ensure_user_row(user_id)
    cursor.execute("""
        UPDATE users
        SET mobs_defeated = COALESCE(mobs_defeated, 0),
            -- fights may be tracked by separate column if desired; reuse mobs_defeated for now
            wins = COALESCE(wins, 0)
        WHERE user_id = ?
    """, (user_id,))
    conn.commit()

def increment_ritual(user_id: int, count: int = 1) -> None:
    if count <= 0:
        return
    _ensure_user_row(user_id)
    cursor.execute("""
        UPDATE users
        SET rituals = COALESCE(rituals, 0) + ?
        WHERE user_id = ?
    """, (count, user_id))
    conn.commit()

# --------------------------
# LEADERBOARD / QUERIES
# --------------------------
def get_top_users(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Return top users ordered by xp_total DESC.
    Each row includes fields consumed by images.py.
    """
    cursor.execute("""
        SELECT user_id, username, xp_total, xp_current, xp_to_next_level,
               level, form, wins, mobs_defeated, rituals
        FROM users
        ORDER BY xp_total DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    out = []
    for r in rows:
        out.append({
            "user_id": r[0],
            "username": r[1] or f"User{r[0]}",
            "xp_total": r[2] or 0,
            "xp_current": r[3] or 0,
            "xp_to_next_level": r[4] or 200,
            "level": r[5] or 1,
            "form": r[6] or get_form(r[5] or 1),
            "wins": r[7] or 0,
            "mobs_defeated": r[8] or 0,
            "rituals": r[9] or 0
        })
    return out

# --------------------------
# DAILY QUESTS
# --------------------------
def get_quests(user_id: int):
    today = datetime.date.today().isoformat()
    cursor.execute("SELECT quest_hop, quest_hopium, quest_fight, reset_date FROM daily_quests WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO daily_quests (user_id, reset_date) VALUES (?, ?)", (user_id, today))
        conn.commit()
        return {"hop": 0, "hopium": 0, "fight": 0}

    hop, hopium, fight, reset_date = row
    if reset_date != today:
        cursor.execute("""
            UPDATE daily_quests
            SET quest_hop = 0, quest_hopium = 0, quest_fight = 0, reset_date = ?
            WHERE user_id = ?
        """, (today, user_id))
        conn.commit()
        return {"hop": 0, "hopium": 0, "fight": 0}
    return {"hop": hop or 0, "hopium": hopium or 0, "fight": fight or 0}

def record_quest(user_id: int, quest_name: str) -> None:
    column = f"quest_{quest_name}"
    if column not in ("quest_hop", "quest_hopium", "quest_fight"):
        # ignore unknown quest names
        return
    cursor.execute(f"UPDATE daily_quests SET {column} = 1 WHERE user_id = ?", (user_id,))
    if cursor.rowcount == 0:
        # row missing — create and retry (set requested column to 1)
        today = datetime.date.today().isoformat()
        cursor.execute("INSERT OR IGNORE INTO daily_quests (user_id, reset_date) VALUES (?, ?)", (user_id, today))
        cursor.execute(f"UPDATE daily_quests SET {column} = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
