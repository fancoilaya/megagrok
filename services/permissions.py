import os
import bot.db as db

# -------------------------------------------------
# Admin authority (ENV-BASED, SAFE)
# -------------------------------------------------

_ADMIN_ID_RAW = os.getenv("MEGAGROK_ADMIN_ID")

MEGAGROK_ADMIN_ID = None
if _ADMIN_ID_RAW:
    try:
        MEGAGROK_ADMIN_ID = int(_ADMIN_ID_RAW)
    except ValueError:
        MEGAGROK_ADMIN_ID = None


def is_admin(user_id: int) -> bool:
    """
    Returns True only if MEGAGROK_ADMIN_ID is configured
    and matches the user_id.
    """
    return MEGAGROK_ADMIN_ID is not None and user_id == MEGAGROK_ADMIN_ID


def is_megacrew(user_id: int) -> bool:
    """
    MegaCrew membership is DB-backed.
    """
    user = db.get_user(user_id)
    return bool(user and user.get("megacrew", 0))
