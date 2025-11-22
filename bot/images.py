# bot/images.py
import os
from time import time
from PIL import Image, ImageDraw, ImageFont

ASSET_DIR = "assets"

# -------------------------
# DEFAULT FONT (safe)
# -------------------------
def font(size: int):
    """Returns Pillow font. Uses Roboto if available, otherwise Pillow default."""
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "fonts", "Roboto-Bold.ttf"), size)
    except Exception:
        return ImageFont.load_default()

# -------------------------
# EVOLUTION SPRITES
# -------------------------
def load_sprite(form):
    """Load one of the evolution PNGs from assets; case-insensitive."""
    if not form:
        form = "tadpole"
    form = str(form).lower()
    mapping = {
        "tadpole": "tadpole.png",
        "hopper": "hopper.png",
        "ascended": "ascended.png"
    }
    filename = mapping.get(form, "tadpole.png")
    path = os.path.join(ASSET_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None

# ======================================================
# PROFILE CARD GENERATOR (uses profile_base.png)
# ======================================================
def generate_profile_image(user: dict):
    """
    Draws overlay text & sprite ON TOP of profile_base.png.

    Accepts a user dict with optional keys:
      user_id, username, form, level, wins, mobs_defeated, rituals, xp_total, tg, ca
    """
    # --- safe extraction with fallbacks ---
    if user is None:
        user = {}

    user_id = user.get("user_id")
    uid_str = str(user_id) if user_id is not None else None

    username = user.get("username")
    if not username:
        username = f"User{uid_str}" if uid_str else "Unknown User"

    form = user.get("form", "Tadpole")
    try:
        level = int(user.get("level", 1))
    except Exception:
        level = 1
    try:
        wins = int(user.get("wins", 0))
    except Exception:
        wins = 0
    fights = user.get("fights", user.get("mobs_defeated", 0))
    try:
        fights = int(fights)
    except Exception:
        fights = 0
    try:
        rituals = int(user.get("rituals", 0))
    except Exception:
        rituals = 0
    xp_total = int(user.get("xp_total", 0) or 0)

    # --- load base template ---
    base_path = os.path.join(ASSET_DIR, "profile_base.png")
    if not os.path.exists(base_path):
        raise FileNotFoundError("profile_base.png missing from assets folder")

    base = Image.open(base_path).convert("RGBA")
    draw = ImageDraw.Draw(base)

    # -------------------------
    # FONT SIZES
    # -------------------------
    TITLE = font(64)
    USER_FONT = font(48)
    STAT_FONT = font(42)
    SMALL = font(34)

    # canvas dims
    w, h = base.size

    # --- helper to measure text safely ---
    def measure(draw_obj, text, fnt):
        try:
            # Preferred: draw.textbbox for accurate bounds
            bbox = draw_obj.textbbox((0, 0), text, font=fnt)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            try:
                # Fallback to font.getsize
                return fnt.getsize(text)
            except Exception:
                # Ultimate fallback
                return (len(text) * (fnt.size if hasattr(fnt, "size") else 10), fnt.size if hasattr(fnt, "size") else 10)

    # -------------------------
    # Title (center top)
    # -------------------------
    title_text = "MEGAGROK"
    tw, th = measure(draw, title_text, TITLE)
    draw.text(((w - tw) // 2, 80), title_text, fill="black", font=TITLE)

    # -------------------------
    # Username centered below title
    # -------------------------
    uw, uh = measure(draw, username, USER_FONT)
    draw.text(((w - uw) // 2, 180), username, fill="black", font=USER_FONT)

    # -------------------------
    # LEFT COLUMN (Level, Fights/Wins, Rituals)
    # -------------------------
    left_x = 80
    left_y = 350

    # LEVEL
    draw.text((left_x, left_y), "LEVEL", fill="black", font=STAT_FONT)
    draw.text((left_x, left_y + 55), str(level), fill="black", font=STAT_FONT)

    # FIGHTS / WINS label + numbers
    draw.text((left_x, left_y + 160), "FIGHTS / WINS", fill="black", font=STAT_FONT)
    draw.text((left_x, left_y + 215), f"{fights} / {wins}", fill="black", font=STAT_FONT)

    # RITUALS
    draw.text((left_x, left_y + 330), "RITUALS", fill="black", font=STAT_FONT)
    draw.text((left_x, left_y + 385), str(rituals), fill="black", font=STAT_FONT)

    # -------------------------
    # TG + CA FOOTER (use provided if present)
    # -------------------------
    tg_text = user.get("tg", "TG: t.me/megagrok")
    ca_text = user.get("ca", user.get("contract_address", "CA: FZL2K9TBybDh32KfJWQBhMtQ71PExyNXiry8Y5e2pump"))

    draw.text((80, h - 180), tg_text, fill="black", font=SMALL)
    draw.text((80, h - 130), ca_text, fill="black", font=SMALL)

    # -------------------------
    # SPRITE (evolution PNG placed inside right frame)
    # -------------------------
    sprite = load_sprite(form)
    if sprite:
        sprite_w = int(min(520, w * 0.42))
        sprite_h = sprite_w
        try:
            sp = sprite.resize((sprite_w, sprite_h)).convert("RGBA")
            paste_x = w - sprite_w - 100
            paste_y = 360
            base.paste(sp, (paste_x, paste_y), sp)
        except Exception:
            pass

    # -------------------------
    # Output file: prefer stable name when user_id exists, otherwise use timestamp
    # -------------------------
    if uid_str:
        out = f"/tmp/profile_{uid_str}.png"
    else:
        out = f"/tmp/profile_{int(time())}.png"

    base.save(out)
    return out


# ======================================================
# LEADERBOARD GENERATOR (uses leaderboard_base.png)
# ======================================================
def generate_leaderboard_image(users=None):
    """
    Accepts list of dict users = get_top_users()
    Draws 5 rows of overlay text.
    """
    if users is None:
        from bot.db import get_top_users
        users = get_top_users(5)

    base_path = os.path.join(ASSET_DIR, "leaderboard_base.png")
    if not os.path.exists(base_path):
        raise FileNotFoundError("leaderboard_base.png missing from assets folder")

    im = Image.open(base_path).convert("RGBA")
    draw = ImageDraw.Draw(im)

    # Y positions for rows; adapt if your template size differs
    ROW_Y = [375, 650, 925, 1200, 1475]
    NAME_FONT = font(58)
    DATA_FONT = font(48)

    for i, row in enumerate(users[:5]):
        if i >= len(ROW_Y):
            break
        y = ROW_Y[i]

        uid = row.get("user_id")
        uname = row.get("username") or (f"User{uid}" if uid is not None else "Unknown")
        xp = row.get("xp_total", 0)
        wins = row.get("wins", 0)
        fights = row.get("fights", row.get("mobs_defeated", 0))

        # draw username
        draw.text((250, y), str(uname), fill="black", font=NAME_FONT)

        # draw XP and F/W
        draw.text((250, y + 90), f"XP: {xp}     F/W: {fights} / {wins}", fill="black", font=DATA_FONT)

    out = "/tmp/leaderboard.png"
    im.save(out)
    return out
