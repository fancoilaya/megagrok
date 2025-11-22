# bot/images.py
import os
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ASSET_DIR = "assets"

# Template / sprite filenames (relative to ASSET_DIR)
PROFILE_BASE_FN = "profile_base.png"
LEADERBOARD_BASE_FN = "leaderboard_base.png"
SPRITES = {
    "Tadpole": "tadpole.png",
    "Hopper": "hopper.png",
    "Ascended": "ascended.png",
    "Ascended Hopper": "ascended.png",
}

# Font filenames expected in assets/
FONT_BOLD_FN = "Roboto-Bold.ttf"
FONT_REG_FN = "Roboto-Regular.ttf"
FONT_LIGHT_FN = "Roboto-Light.ttf"


# ---------------------------
# Utilities: loading & measuring
# ---------------------------
def _asset_path(name: str) -> Optional[str]:
    """Return the path to an asset inside ASSET_DIR if it exists (fallback to raw path)."""
    p = os.path.join(ASSET_DIR, name)
    if os.path.exists(p):
        return p
    # fallback to raw name (some environments may place files in cwd)
    if os.path.exists(name):
        return name
    return None


def _load_image(name: str, mode: str = "RGBA") -> Optional[Image.Image]:
    p = _asset_path(name)
    if not p:
        return None
    try:
        return Image.open(p).convert(mode)
    except Exception:
        return None


def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    p = _asset_path(name)
    try:
        if p:
            return ImageFont.truetype(p, size)
    except Exception:
        pass
    # fallback to default
    return ImageFont.load_default()


# Pillow-10 safe text helpers
def text_bbox(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int, int, int]:
    """
    Return text bbox (left, top, right, bottom) in a Pillow-10-compatible way.
    """
    try:
        return draw.textbbox((0, 0), text, font=font)
    except Exception:
        # very old Pillow fallback (shouldn't hit on runtime)
        w = draw.textlength(text, font=font) if hasattr(draw, "textlength") else font.getsize(text)[0]
        h = getattr(font, "size", 20)
        return (0, 0, int(w), int(h))


def text_size(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:
    l, t, r, b = text_bbox(draw, text, font)
    return (r - l, b - t)


def center_x(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, left: int, right: int) -> int:
    tw, _ = text_size(draw, text, font)
    return left + (right - left - tw) // 2


# ---------------------------
# Preload sensible font sizes
# ---------------------------
TITLE_FONT = _load_font(FONT_BOLD_FN, 84)
USERNAME_FONT = _load_font(FONT_REG_FN, 52)
LABEL_FONT = _load_font(FONT_REG_FN, 36)
VALUE_FONT = _load_font(FONT_BOLD_FN, 70)
FOOTER_FONT = _load_font(FONT_LIGHT_FN, 28)
LEADER_NAME_FONT = _load_font(FONT_BOLD_FN, 44)
LEADER_META_FONT = _load_font(FONT_REG_FN, 30)


# ---------------------------
# Profile generator
# ---------------------------
def generate_profile_image(user: Dict[str, Any]) -> str:
    """
    Generate profile image PNG and return path.
    Expects user keys:
      user_id, username, form, level, xp_total, xp_current, xp_to_next_level,
      wins, fights (or mobs_defeated), rituals, tg, ca
    """
    # load base canvas
    base_img = _load_image(PROFILE_BASE_FN)
    if base_img is None:
        # fallback canvas size & color
        base_img = Image.new("RGBA", (900, 1280), (255, 249, 230, 255))

    draw = ImageDraw.Draw(base_img)
    W, H = base_img.size

    # read user fields with safe defaults
    uid = str(user.get("user_id", "unknown"))
    username = str(user.get("username", f"User {uid}"))
    form = str(user.get("form", "Tadpole"))
    level = int(user.get("level", 1))
    wins = int(user.get("wins", 0))
    fights = int(user.get("fights", user.get("mobs_defeated", 0)))
    rituals = int(user.get("rituals", 0))
    tg = str(user.get("tg", ""))
    ca = str(user.get("ca", ""))

    # -------------- Header (MEGAGROK + username) --------------
    title_text = "MEGAGROK"
    tx = center_x(draw, title_text, TITLE_FONT, 0, W)
    draw.text((tx, 36), title_text, font=TITLE_FONT, fill=(16, 16, 16))

    uname_y = 140
    ux = center_x(draw, username, USERNAME_FONT, 0, W)
    draw.text((ux, uname_y), username, font=USERNAME_FONT, fill=(16, 16, 16))

    # -------------- Center art box (sprite only) --------------
    # We'll place the sprite centered inside a measured center rectangle
    # Assumed margins from your template (these values were tested with your provided base)
    center_left = int(W * 0.06)
    center_right = int(W * 0.94)
    center_top = int(H * 0.16)
    center_bottom = int(H * 0.72)
    center_w = center_right - center_left
    center_h = center_bottom - center_top

    # load sprite
    sprite_name = SPRITES.get(form, SPRITES["Tadpole"])
    sprite = _load_image(sprite_name)
    if sprite:
        # scale sprite to about 45% of center width (per your request reduce ~50%)
        target_w = int(center_w * 0.45)
        aspect = sprite.height / sprite.width
        target_h = int(target_w * aspect)
        sprite = sprite.resize((target_w, target_h), Image.LANCZOS)

        sx = center_left + (center_w - target_w) // 2
        sy = center_top + (center_h - target_h) // 2
        base_img.paste(sprite, (sx, sy), sprite)

    # -------------- Bottom three stat boxes --------------
    # These box coordinates should match your template's visual areas.
    # We use relative positions that work for profile_base.png provided earlier.
    stats_top = int(H * 0.74)  # top of stats row
    stats_height = int(H * 0.10)
    stats_bottom = stats_top + stats_height

    left_box = (int(W * 0.06), stats_top, int(W * 0.32), stats_bottom)
    mid_box = (int(W * 0.34), stats_top, int(W * 0.66), stats_bottom)
    right_box = (int(W * 0.68), stats_top, int(W * 0.94), stats_bottom)

    # helper to center label and value within a box
    def draw_box_text(box: Tuple[int, int, int, int], label: str, value: str):
        x1, y1, x2, y2 = box
        # label - slightly above center
        lab_y = y1 + 6
        lab_x = center_x(draw, label, LABEL_FONT, x1, x2)
        draw.text((lab_x, lab_y), label, font=LABEL_FONT, fill=(20, 20, 20))
        # value - larger and below label
        val_y = y1 + 46
        val_x = center_x(draw, value, VALUE_FONT, x1, x2)
        draw.text((val_x, val_y), value, font=VALUE_FONT, fill=(20, 20, 20))

    # draw the three boxes text
    draw_box_text(left_box, "LEVEL", str(level))
    draw_box_text(mid_box, "FIGHTS / WINS", f"{fights} / {wins}")
    draw_box_text(right_box, "RITUALS", str(rituals))

    # -------------- Footer TG + CA --------------
    footer_top = int(H * 0.88)
    if tg:
        tline = f"TG: {tg}"
        tx = center_x(draw, tline, FOOTER_FONT, 0, W)
        draw.text((tx, footer_top), tline, font=FOOTER_FONT, fill=(18, 18, 18))

    if ca:
        cline = f"CA: {ca}"
        cx = center_x(draw, cline, FOOTER_FONT, 0, W)
        draw.text((cx, footer_top + 34), cline, font=FOOTER_FONT, fill=(18, 18, 18))

    # Save to /tmp
    out = f"/tmp/profile_{uid}.png"
    base_img.save(out)
    return out


# ---------------------------
# Leaderboard generator (Pillow-10 safe)
# ---------------------------
def generate_leaderboard_image() -> str:
    """
    Loads top users from bot.db.get_top_users() and renders the leaderboard
    using leaderboard_base.png from assets/.
    """
    # lazy import so module can still load if db not available in unit tests
    try:
        from bot.db import get_top_users
        rows = get_top_users(5)
    except Exception:
        # fallback example rows
        rows = [
            {"user_id": 1, "username": "Alpha", "xp_total": 3450, "level": 12, "form": "Hopper", "wins": 50, "mobs_defeated": 70},
            {"user_id": 2, "username": "Beta", "xp_total": 3020, "level": 11, "form": "Hopper", "wins": 45, "mobs_defeated": 65},
            {"user_id": 3, "username": "Gamma", "xp_total": 2800, "level": 10, "form": "Hopper", "wins": 40, "mobs_defeated": 60},
            {"user_id": 4, "username": "Delta", "xp_total": 2550, "level": 9, "form": "Tadpole", "wins": 35, "mobs_defeated": 55},
            {"user_id": 5, "username": "Epsilon", "xp_total": 2400, "level": 8, "form": "Tadpole", "wins": 30, "mobs_defeated": 50},
        ]

    base = _load_image(LEADERBOARD_BASE_FN)
    if base is None:
        base = Image.new("RGBA", (1000, 1600), (240, 240, 248, 255))

    draw = ImageDraw.Draw(base)
    W, H = base.size

    # Title
    title = "TOP 5 LEADERBOARD"
    tx = center_x(draw, title, TITLE_FONT, 0, W)
    draw.text((tx, 36), title, font=TITLE_FONT, fill=(18, 18, 18))

    # Row Y coordinates - spaced evenly down the template
    # if your leaderboard_base has exact rows, these values work with the provided template
    start_y = int(H * 0.18)
    row_h = int((H - start_y - 80) / 5)

    for i, user in enumerate(rows[:5]):
        y = start_y + i * row_h
        # Rank number position (left-most)
        rank_text = str(i + 1)
        r_x = int(W * 0.06)
        r_y = y + int(row_h * 0.08)
        draw.text((r_x, r_y), rank_text, font=VALUE_FONT, fill=(12, 12, 12))

        # sprite
        sprite_name = SPRITES.get(user.get("form", "Tadpole"), SPRITES["Tadpole"])
        sprite = _load_image(sprite_name)
        if sprite:
            sp_w = int(row_h * 0.6)
            aspect = sprite.height / sprite.width
            sp_h = int(sp_w * aspect)
            sp = sprite.resize((sp_w, sp_h), Image.LANCZOS)
            sp_x = int(W * 0.16)
            sp_y = y + (row_h - sp_h) // 2
            base.paste(sp, (sp_x, sp_y), sp)

        # name and meta text
        name_x = int(W * 0.34)
        name_y = y + 8
        uname = user.get("username", f"User{user.get('user_id')}")
        draw.text((name_x, name_y), uname, font=LEADER_NAME_FONT, fill=(18, 18, 18))

        meta = f"XP: {user.get('xp_total', 0)}   LEVEL: {user.get('level', 1)}   FIGHTS / WINS: {user.get('mobs_defeated', user.get('fights', 0))} / {user.get('wins', 0)}"
        draw.text((name_x, name_y + 54), meta, font=LEADER_META_FONT, fill=(40, 40, 40))

    out = "/tmp/leaderboard.png"
    base.save(out)
    return out


# ---------------------------
# If run directly produce demo outputs (optional)
# ---------------------------
if __name__ == "__main__":
    demo_user = {
        "user_id": 123,
        "username": "MegaHero",
        "form": "Hopper",
        "level": 7,
        "xp_total": 1750,
        "xp_current": 150,
        "xp_to_next_level": 250,
        "wins": 12,
        "fights": 20,
        "rituals": 3,
        "tg": "t.me/megagrok",
        "ca": "FZL2K9TBybDh32KfJWQBhMtQ71PExyNXiry8Y5e2pump"
    }
    print("Writing demo profile -> /tmp/profile_demo.png")
    generate_profile_image(demo_user)
    print("Writing demo leaderboard -> /tmp/leaderboard_demo.png")
    generate_leaderboard_image()
