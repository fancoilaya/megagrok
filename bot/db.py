import sqlite3
import datetime

DB_PATH = "grok.db"

# --------------------------
# DB INIT
# --------------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()


# --- USERS TABLE (original) ---
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

def add_column_if_missing(col, definition):
    if col not in existing_cols:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")

add_column_if_missing("xp_total", "INTEGER DEFAULT 0")
add_column_if_missing("xp_current", "INTEGER DEFAULT 0")
add_column_if_missing("xp_to_next_level", "INTEGER DEFAULT 200")
add_column_if_missing("level_curve_factor", "FLOAT DEFAULT 1.15")
add_column_if_missing("last_xp_change", "TEXT")


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
def xp_needed_for_level(level: int, factor: float = 1.15):
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

def get_form(level):
    for lvl, form in reversed(EVOLUTIONS):
        if level >= lvl:
            return form
    return "Tadpole"


# --------------------------
# USER OPERATIONS
# --------------------------
def get_user(user_id):
    """
    Returns the full upgraded user row.
    If the user does not exist, it is created with full new XP system fields.
    """
    cursor.execute("""
        SELECT user_id, xp_total, xp_current, xp_to_next_level,
               level, form, level_curve_factor, last_xp_change
        FROM users WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()

    if not row:
        # NEW USER INIT (full new XP system)
        cursor.execute("""
            INSERT INTO users (user_id, xp_total, xp_current, xp_to_next_level, level, form)
            VALUES (?, 0, 0, 200, 1, 'Tadpole')
        """, (user_id,))
        conn.commit()
        return get_user(user_id)

    return {
        "user_id": row[0],
        "xp_total": row[1],
        "xp_current": row[2],
        "xp_to_next_level": row[3],
        "level": row[4],
        "form": row[5],
        "level_curve_factor": row[6],
        "last_xp_change": row[7]
    }


def update_user_xp(user_id, data):
    """Updates XP, level, form, and timestamp."""
    new_form = get_form(data["level"])
    now = datetime.datetime.utcnow().isoformat()

    cursor.execute("""
        UPDATE users
        SET xp_total = ?, xp_current = ?, xp_to_next_level = ?,
            level = ?, form = ?, level_curve_factor = level_curve_factor,
            last_xp_change = ?
        WHERE user_id = ?
    """, (
        data["xp_total"], data["xp_current"], data["xp_to_next_level"],
        data["level"], new_form, now, user_id
    ))
    conn.commit()


# --------------------------
# LEADERBOARD
# --------------------------
def get_top_users(limit=10):
    """
    Returns top users ordered by xp_total (lifetime XP).
    Used by profile images and leaderboard.
    """
    cursor.execute("""
        SELECT user_id, xp_total, xp_current, xp_to_next_level, level, form
        FROM users
        ORDER BY xp_total DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    result = []

    for row in rows:
        result.append({
            "user_id": row[0],
            "xp_total": row[1],
            "xp_current": row[2],
            "xp_to_next_level": row[3],
            "level": row[4],
            "form": row[5]
        })

    return result


# --------------------------
# DAILY QUESTS
# --------------------------
def get_quests(user_id):
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


def record_quest(user_id, quest_name):
    column = f"quest_{quest_name}"

    cursor.execute(f"""
        UPDATE daily_quests
        SET {column} = 1
        WHERE user_id = ?
    """, (user_id,))

    conn.commit()
