import sqlite3
import datetime
import math

DB_PATH = "grok.db"

# --------------------------
# DB INIT
# --------------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# --- USERS TABLE MIGRATION / CREATION ---
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    form TEXT DEFAULT 'Tadpole'
)
""")

# New upgraded columns (added safely if missing)
cursor.execute("ALTER TABLE users ADD COLUMN xp_total INTEGER DEFAULT 0") if "xp_total" not in [c[1] for c in cursor.execute("PRAGMA table_info(users)")] else None
cursor.execute("ALTER TABLE users ADD COLUMN xp_current INTEGER DEFAULT 0") if "xp_current" not in [c[1] for c in cursor.execute("PRAGMA table_info(users)")] else None
cursor.execute("ALTER TABLE users ADD COLUMN xp_to_next_level INTEGER DEFAULT 200") if "xp_to_next_level" not in [c[1] for c in cursor.execute("PRAGMA table_info(users)")] else None
cursor.execute("ALTER TABLE users ADD COLUMN level_curve_factor FLOAT DEFAULT 1.15") if "level_curve_factor" not in [c[1] for c in cursor.execute("PRAGMA table_info(users)")] else None
cursor.execute("ALTER TABLE users ADD COLUMN last_xp_change TEXT") if "last_xp_change" not in [c[1] for c in cursor.execute("PRAGMA table_info(users)")] else None

# DAILY QUESTS TABLE
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

def get_form(level):
    for lvl, form in reversed(EVOLUTIONS):
        if level >= lvl:
            return form
    return "Tadpole"


# --------------------------
# USER OPERATIONS
# --------------------------
def get_user(user_id):
    cursor.execute("""
        SELECT user_id, xp_total, xp_current, xp_to_next_level, level,
               form, level_curve_factor, last_xp_change
        FROM users WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()

    # Create new user with upgraded structure
    if not row:
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


def update_user_xp(user_id, u):
    """Updates user XP, level, form and timestamps."""
    new_form = get_form(u["level"])
    now = datetime.datetime.utcnow().isoformat()

    cursor.execute("""
        UPDATE users
        SET xp_total = ?, xp_current = ?, xp_to_next_level = ?,
            level = ?, form = ?, last_xp_change = ?
        WHERE user_id = ?
    """, (
        u["xp_total"], u["xp_current"], u["xp_to_next_level"],
        u["level"], new_form, now,
        user_id
    ))
    conn.commit()


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

    # Daily reset
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
