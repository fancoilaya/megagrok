import datetime
from bot.db import get_db

def reset_daily_quests(user_id):
    today = datetime.date.today().isoformat()
    conn, cursor = get_db()
    cursor.execute("""
        UPDATE daily_quests
        SET quest_hop = 0, quest_hopium = 0, quest_fight = 0, reset_date = ?
        WHERE user_id = ?
    """, (today, user_id))
    conn.commit()
    conn.close()

def get_quests(user_id):
    today = datetime.date.today().isoformat()
    conn, cursor = get_db()
    cursor.execute("SELECT * FROM daily_quests WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO daily_quests (user_id, reset_date) VALUES (?, ?)", (user_id, today))
        conn.commit()
        conn.close()
        return get_quests(user_id)
    _, hop, hopium, fight, reset_date = row
    if reset_date != today:
        reset_daily_quests(user_id)
        conn, cursor = get_db()
        cursor.execute("SELECT * FROM daily_quests WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    conn.close()
    return {"hop": hop, "hopium": hopium, "fight": fight}
