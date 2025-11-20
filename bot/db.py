import sqlite3
import datetime

DB_PATH = "grok.db"

# --------------------------
# DB INIT
# --------------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    form TEXT DEFAULT 'Tadpole'
)
""")

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
# Evolution System
# --------------------------

EVOLUTIONS = [
    (1, "Tadpole"),
    (5, "Hopper"),
    (10, "Ascended")
]

def calculate_level(xp):
    return xp // 200 + 1

def get_form(level):
    for lvl, form in reversed(EVOLUTIONS):
        if level >= lvl:
            return form
    return "Tadpole"


# --------------------------
# USERS
# --------------------------

def get_user(user_id):
    cursor.execute("SELECT user_id, xp, level, form FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return get_user(user_id)

    return {
        "user_id": row[0],
        "xp": row[1],
        "level": row[2],
        "form": row[3]
    }


def add_xp(user_id, amount):
    user = get_user(user_id)

    new_xp = max(user["xp"] + amount, 0)
    new_level = calculate_level(new_xp)
    new_form = get_form(new_level)

    cursor.execute("""
        UPDATE users
        SET xp = ?, level = ?, form = ?
        WHERE user_id = ?
    """, (new_xp, new_level, new_form, user_id))

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

    # Reset on new day
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
