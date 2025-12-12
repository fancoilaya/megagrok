# services/pvp_targets.py
# Helpers: recommended targets, revenge targets, power calculation

from typing import List, Dict, Any, Tuple
import time
import bot.db as db
import bot.handlers.pvp_ranking as ranking_module  # your uploaded ranking helper. :contentReference[oaicite:3]{index=3}

# config
MAX_RECOMMENDED = 6
RECENT_ACTIVE_SECONDS = 48 * 3600  # 48 hours
LEVEL_DELTA = 4

def calculate_power(stats: Dict[str, Any]) -> int:
    # Power = HP * 0.4 + Attack * 1.2 + Defense * 1.0  (rounded)
    hp = int(stats.get("hp", 100))
    atk = int(stats.get("attack", 10))
    dfs = int(stats.get("defense", 5))
    power = int(round(hp * 0.4 + atk * 1.2 + dfs * 1.0))
    return power

def _user_minimal(u: Dict[str, Any]) -> Dict[str, Any]:
    # Normalize db user row to minimal display dict
    return {
        "user_id": u.get("user_id"),
        "username": u.get("username"),
        "display_name": u.get("display_name") or u.get("username"),
        "level": int(u.get("level", 1)),
        "elo_pvp": int(u.get("elo_pvp", 1000)),
        "last_active": int(u.get("last_active", 0)),
        "shield_until": int(u.get("pvp_shield_until", 0)),
        # include current combat stats if stored (fallback to balanced builder in pvp)
        "hp": int(u.get("current_hp", u.get("hp", 100))),
        "attack": int(u.get("attack", 10)),
        "defense": int(u.get("defense", 5)),
    }

def get_revenge_targets(user_id: int) -> List[Dict[str, Any]]:
    """
    Returns list of recent attackers against user_id, sorted by most recent.
    Assumes DB function `get_users_who_attacked_you(defender_id, limit)` exists.
    If not, replace with your table query.
    """
    try:
        rows = db.get_users_who_attacked_you(user_id, limit=10)  # should return list of (attacker_id, ts, xp_stolen, result)
    except Exception:
        # fallback: empty
        rows = []

    results = []
    now = int(time.time())
    for r in rows:
        attacker_id = r.get("attacker_id") if isinstance(r, dict) else r[0]
        ts = r.get("ts", now) if isinstance(r, dict) else r[1]
        xp = r.get("xp_stolen", 0) if isinstance(r, dict) else r[2] if len(r) > 2 else 0
        result = r.get("result", "") if isinstance(r, dict) else (r[3] if len(r) > 3 else "")

        u = db.get_user(attacker_id) or {"user_id": attacker_id}
        mu = _user_minimal(u)
        mu["since"] = now - int(ts)
        mu["xp_stolen"] = int(xp)
        mu["result"] = result
        results.append(mu)

    return results

def get_recommended_targets(user_id: int) -> List[Dict[str, Any]]:
    """
    Returns recommended targets near user's level/power and not shielded.
    Uses db.get_recent_active_users(limit) or falls back to db.search_users_by_activity
    """
    me = db.get_user(user_id) or {}
    me_level = int(me.get("level", 1))
    candidates = []
    try:
        rows = db.get_recent_active_users(limit=200)  # if you have this function
    except Exception:
        # fallback: all users (be careful)
        rows = db.get_all_users() if hasattr(db, "get_all_users") else []

    now = int(time.time())
    for u in rows:
        if not u:
            continue
        uid = u.get("user_id", u.get("id") or None)
        if uid is None or uid == user_id:
            continue
        shield = int(u.get("pvp_shield_until", 0))
        if shield and shield > now:
            continue
        last_active = int(u.get("last_active", 0))
        # skip very inactive
        if now - last_active > RECENT_ACTIVE_SECONDS:
            continue
        level = int(u.get("level", 1))
        if abs(level - me_level) > LEVEL_DELTA:
            continue
        # compute power using stored stats (if any) else use db fields
        stats = {
            "hp": int(u.get("current_hp", u.get("hp", 100))),
            "attack": int(u.get("attack", 10)),
            "defense": int(u.get("defense", 5))
        }
        power = calculate_power(stats)
        candidates.append((uid, u, power))

    # sort by closeness of power to player
    my_stats = {"hp": int(me.get("current_hp", me.get("hp", 100))), "attack": int(me.get("attack", 10)), "defense": int(me.get("defense", 5))}
    my_power = calculate_power(my_stats)
    candidates.sort(key=lambda t: abs(t[2] - my_power))

    # produce top-N minimal dicts
    results = []
    for uid, u, power in candidates[:MAX_RECOMMENDED]:
        mu = _user_minimal(u)
        mu["power"] = power
        # compute rank label using ranking helper
        try:
            rank_name, _ = ranking_module.elo_to_rank(int(mu.get("elo_pvp", 1000)))
        except Exception:
            rank_name = "Unknown"
        mu["rank"] = rank_name
        results.append(mu)
    return results
