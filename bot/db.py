# db.py
# MegaGrok Database Layer (Clean unified)
# - User profiles
# - XP & leveling
# - Quests (hop / fight / battle)
# - Wins, rituals
# - Cooldowns
# - Leaderboards (with Display Name support)
# - PvP columns & helpers
# - VIP placeholder (swap for Redis later)
#
# IMPORTANT: DB_PATH should be a persistent path on the host/container:
#            default: /var/data/megagrok.db

import sqlite3
import json
import time
from typing import Dict, Any, List, Tuple, Optional

# ---------------------------
# Config
# ---------------------------
DB_PATH = "/var/data/megagrok.db"

# ---------------------------
# DB CONNECTION
# ---------------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# ---------------------------
# CREATE TABLES IF THEY DO NOT EXIST
# ---------------------------
def init_db():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            display_name TEXT,
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
            -- PvP columns will be added later via _add_column_if_missing
        )
    """)
    # Create a simple VIP table placeholder for future shared store usage
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vip_users (
            user_id INTEGER PRIMARY KEY,
            wallet_address TEXT,
            token_balance REAL DEFAULT 0,
            vip_until INTEGER,
            last_verified INTEGER
        )
    """)
    conn.commit()

init_db()

# ---------------------------
# Schema helper: add column if missing
# ---------------------------
def _add_column_if_missing(col: str, type_: str):
    cursor.execute("PRAGMA table_info(users)")
    cols = [c[1].lower() for c in cursor.fetchall()]
    if col.lower() not in cols:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {type_}")
        conn.commit()

# Ensure historically-added column(s)
_add_column_if_missing("display_name", "TEXT")

# ---------------------------
# Ensure PvP columns exist (safe, idempotent)
# ---------------------------
_add_column_if_missing("elo_pvp", "INTEGER DEFAULT 1000")
_add_column_if_missing("pvp_wins", "INTEGER DEFAULT 0")
_add_column_if_missing("pvp_losses", "INTEGER DEFAULT 0")
_add_column_if_missing("pvp_fights_started", "INTEGER DEFAULT 0")
_add_column_if_missing("pvp_fights_defended", "INTEGER DEFAULT 0")
_add_column_if_missing("pvp_successful_defenses", "INTEGER DEFAULT 0")
_add_column_if_missing("pvp_failed_defenses", "INTEGER DEFAULT 0")
_add_column_if_missing("pvp_challenges_received", "INTEGER DEFAULT 0")
_add_column_if_missing("pvp_shield_until", "INTEGER DEFAULT 0")

# ---------------------------
# GET OR CREATE USER
# ---------------------------
def get_user(user_id: int) -> Dict[str, Any]:
    """
    Returns a dict representing the user row. Creates the user row if missing.
    The dict keys match the table columns (cursor.description is used).
    """
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row:
        # Insert a default row (quests and cooldowns are JSON strings)
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

    desc = [d[0] for d in cursor.description]
    return {desc[i]: row[i] for i in range(len(desc))}

# ---------------------------
# UPDATE USER XP / LEVEL
# ---------------------------
def update_user_xp(user_id: int, data: Dict[str, Any]):
    """
    Update any xp-related fields or level fields. `data` is a dict of column: value.
    """
    if not data:
        return
    fields = []
    values = []
    for key, val in data.items():
        fields.append(f"{key}=?")
        values.append(val)
    values.append(user_id)
    cursor.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id=?", values)
    conn.commit()

# ---------------------------
# DISPLAY NAME MANAGEMENT
# ---------------------------
def update_display_name(user_id: int, display_name: str):
    if not display_name or not display_name.strip():
        return
    clean = display_name.strip()
    cursor.execute("UPDATE users SET display_name=? WHERE user_id=?", (clean, user_id))
    conn.commit()

# ---------------------------
# USERNAME MANAGEMENT
# ---------------------------
def update_username(user_id: int, username: str):
    """
    Ensures usernames are stored consistently:
    - Not empty
    - Prefixed with '@'
    - Lowercased
    """
    if not username or not username.strip():
        return
    uname = username.strip().lower()
    if not uname.startswith("@"):
        uname = "@" + uname
    cursor.execute("UPDATE users SET username=? WHERE user_id=?", (uname, user_id))
    conn.commit()

# ---------------------------
# QUEST SYSTEM
# ---------------------------
def get_quests(user_id: int) -> Dict[str, Any]:
    _add_column_if_missing("quests", "TEXT")
    cursor.execute("SELECT quests FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row or not row[0]:
        return {}
    try:
        return json.loads(row[0])
    except Exception:
        return {}

def record_quest(user_id: int, quest_key: str):
    quests = get_quests(user_id)
    quests[quest_key] = 1
    cursor.execute("UPDATE users SET quests=? WHERE user_id=?", (json.dumps(quests), user_id))
    conn.commit()

# ---------------------------
# WINS & RITUAL COUNT
# ---------------------------
def increment_win(user_id: int):
    cursor.execute("UPDATE users SET wins = coalesce(wins,0) + 1 WHERE user_id=?", (user_id,))
    conn.commit()

def increment_ritual(user_id: int):
    cursor.execute("UPDATE users SET rituals = coalesce(rituals,0) + 1 WHERE user_id=?", (user_id,))
    conn.commit()

# ---------------------------
# COOLDOWN SYSTEM
# ---------------------------
def get_cooldowns(user_id: int) -> Dict[str, Any]:
    _add_column_if_missing("cooldowns", "TEXT")
    cursor.execute("SELECT cooldowns FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row or not row[0]:
        return {}
    try:
        return json.loads(row[0])
    except Exception:
        return {}

def set_cooldowns(user_id: int, cooldowns: Dict[str, Any]):
    cursor.execute("UPDATE users SET cooldowns=? WHERE user_id=?", (json.dumps(cooldowns), user_id))
    conn.commit()

# ---------------------------
# LEADERBOARD (XP)
# ---------------------------
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
        if display_name and str(display_name).strip():
            name = str(display_name).strip()
        elif username and str(username).strip():
            name = str(username).strip()
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

# ---------------------------
# NAME / USERNAME SEARCH HELPERS (for PvP targeting)
# ---------------------------
def search_users_by_name(query: str, limit: int = 10) -> List[Tuple[int, Optional[str], Optional[str]]]:
    """
    Fuzzy search users by username or display_name. Returns list of tuples:
    (user_id, username, display_name)
    """
    q = f"%{query.lower()}%"
    cursor.execute("""
        SELECT user_id, username, display_name
        FROM users
        WHERE lower(username) LIKE ? OR lower(display_name) LIKE ?
        LIMIT ?
    """, (q, q, limit))
    return cursor.fetchall()

def get_user_by_username(username: str) -> Optional[Tuple[int, Optional[str], Optional[str]]]:
    """
    Exact lookup by username (case-insensitive). Accepts with or without leading '@'.
    Returns tuple (user_id, username, display_name) or None.
    """
    if not username:
        return None
    uname = username.strip().lower()
    if not uname.startswith("@"):
        uname = "@" + uname
    cursor.execute("SELECT user_id, username, display_name FROM users WHERE lower(username)=?", (uname.lower(),))
    row = cursor.fetchone()
    return row

# ---------------------------
# PvP HELPERS
# ---------------------------
def get_pvp_stats(user_id: int) -> Dict[str, Any]:
    usr = get_user(user_id)
    return {
        "elo": usr.get("elo_pvp", 1000),
        "wins": usr.get("pvp_wins", 0),
        "losses": usr.get("pvp_losses", 0),
        "started": usr.get("pvp_fights_started", 0),
        "defended": usr.get("pvp_fights_defended", 0),
        "successful_def": usr.get("pvp_successful_defenses", 0),
        "failed_def": usr.get("pvp_failed_defenses", 0),
        "challenges": usr.get("pvp_challenges_received", 0),
        "shield_until": usr.get("pvp_shield_until", 0),
    }

def update_elo(user_id: int, new_elo: int):
    cursor.execute("UPDATE users SET elo_pvp=? WHERE user_id=?", (new_elo, user_id))
    conn.commit()

def increment_pvp_field(user_id: int, field: str):
    # only allow known fields for safety
    allowed = {
        "pvp_wins", "pvp_losses", "pvp_fights_started", "pvp_fights_defended",
        "pvp_successful_defenses", "pvp_failed_defenses", "pvp_challenges_received"
    }
    if field not in allowed:
        raise ValueError("Field not allowed for increment")
    cursor.execute(f"UPDATE users SET {field} = COALESCE({field},0) + 1 WHERE user_id=?", (user_id,))
    conn.commit()

def set_pvp_shield(user_id: int, until_ts: int):
    cursor.execute("UPDATE users SET pvp_shield_until=? WHERE user_id=?", (until_ts, user_id))
    conn.commit()

def is_pvp_shielded(user_id: int) -> bool:
    stats = get_user(user_id)
    shield = stats.get("pvp_shield_until", 0) or 0
    try:
        return int(time.time()) < int(shield)
    except Exception:
        return False

def get_top_pvp(limit: int = 10) -> List[Dict[str, Any]]:
    cursor.execute("""
        SELECT user_id, username, display_name, coalesce(elo_pvp,1000) as elo, coalesce(pvp_wins,0) as wins, coalesce(pvp_losses,0) as losses
        FROM users
        ORDER BY elo DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    out = []
    rank = 1
    for r in rows:
        uid, uname, display, elo, wins, losses = r
        name = (display or uname) or f"User{uid}"
        out.append({
            "rank": rank,
            "user_id": uid,
            "name": name,
            "username": uname,
            "elo": elo or 1000,
            "wins": wins or 0,
            "losses": losses or 0
        })
        rank += 1
    return out

# ---------------------------
# VIP placeholder helper
# ---------------------------
def is_vip(user_id: int) -> bool:
    """
    Placeholder for VIP check.
    Currently returns True for compatibility / free-mode testing.
    Replace this function body with a Redis lookup (or shared DB/API) later.
    Example replacement:
      val = redis.get(f"vip:{user_id}:token_balance")
      return float(val or 0) >= VIP_MIN_TOKENS
    """
    # default behavior: return True (we will gate via env var in pvp module)
    return True

# ---------------------------
# Convenience: ensure safe close / reopen (if needed)
# ---------------------------
def close_db():
    try:
        conn.commit()
        conn.close()
    except Exception:
        pass

def reopen_db():
    global conn, cursor
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()

# ---------------------------
# End of db.py
# ---------------------------
