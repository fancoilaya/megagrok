import time
import json
import bot.db as db

def log_admin_action(actor_id: int, action: str, data: dict | None = None):
    db.cursor.execute(
        "INSERT INTO admin_logs (actor_id, action, data, timestamp) VALUES (?, ?, ?, ?)",
        (actor_id, action, json.dumps(data or {}), int(time.time()))
    )
    db.conn.commit()
