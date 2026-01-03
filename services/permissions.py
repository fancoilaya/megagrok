import os
import bot.db as db

# -------------------------------------------------
# Admin authority (ENV-BASED)
# -------------------------------------------------

_ADMIN_ID_RAW = os.getenv("MEGAGROK_ADMIN_ID")

if not _ADMIN_ID_RAW:
    raise RuntimeError("MEGAGROK_ADMIN_ID environment variable is NOT set")

try:
    MEGAGROK_ADMIN_ID = int(_ADMIN_ID_RAW)
except ValueError:
    raise RuntimeError("MEGAGROK_ADMIN_ID must be an integer Telegram user ID")


def is_admin(user_id: int) -> bool:
    return user_id == MEGAGROK_ADMIN_ID


def is_megacrew(user_id: int) -> bool:
    user = db.get_user(user_id)
    return bool(user and user.get("megacrew", 0))
