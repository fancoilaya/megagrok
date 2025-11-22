# bot/images.py
import os
from typing import Dict, Any, Optional, List
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

ASSET_DIR = "assets"

# Expected asset names (we will look in ASSET_DIR then /mnt/data)
PROFILE_BASE = "profile_base.png"
LEADERBOARD_BASE = "leaderboard_base.png"
TADPOLE = "tadpole.png"
HOPPER = "hopper.png"
ASCENDED = "ascended.png"

# Fonts (try these names in assets/ then /mnt/data)
FONT_FILES = {
    "bold": "Roboto-Bold.ttf",
    "regular": "Roboto-Regular.ttf",
    "light": "Roboto-Light.ttf"
}

# ---------------------------
# Utility: Path helpers
# ---------------------------
def _asset_try_paths(name: str) -> List[str]:
    """Return candidate paths where an asset or font might live."""
    return [
        os.path.join(ASSET_DIR, name),
        os.path.join("/mnt/data", name),
        name
    ]

def _asset_path(name: str) -> Optional[str]:
    """Return the first existing path for name, or None."""
    for p in _asset_try_paths(name):
        if p and os.path.exists(p):
            return p
    return None

# ---------------------------
# Fonts (robust loader)
# ---------------------------
def _load_font(name: str, size: int):
    from PIL import ImageFont
    for p in _asset_try_paths(name):
        try:
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
        except Exception:
            continue
    # final fallback
    return ImageFont.load_default()

# Preload common font sizes
TITLE_FONT = _load_font(FONT_FILES["bold"], 72)
USERNAME_FONT = _load_font(FONT_FILES["regular"], 44)
LABEL_FONT = _load_font(FONT_FILES["regular"], 36)
BIG_NUM_FONT = _load_font(FONT_FILES["bold"], 72)
SMALL_FONT = _load_font(FONT_FILES["regular"], 26)
FOOTER_FONT = _load_font(FONT_FILES["light"], 22)

# ---------------------------
# Sprite loader
# ---------------------------
FORM_TO_SPRITE = {
    "Tadpole": TADPOLE,
    "Hopper": HOPPER,
    "Ascended": ASCENDED,
    "Ascended Hopper": ASCENDED
}

def load_form_image(form_name: str) -> Optional[Image.Image]:
    fname = FORM_TO_SPRITE.get(form_name, TADPOLE)
    p = _asset_path(fname)
    if not p:
        return None
    try:
        return Image.open(p).convert("RGBA")
    except Exception:
        return None

# ---------------------------
# Text helpers
# ---------------------------
def draw_outline_text(draw: ImageDraw.Draw, xy, text: str, font: ImageFont.FreeTypeFont,
                      fill=(0,0,0), outline=(255,255,255), stroke=3, anchor=None):
    """
    Draw text with stroke. Pillow supports stroke_width/stroke_fill on modern versions.
    Fallback draws multiple offset copies if needed.
    """
    try:
        draw.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=outline, anchor=anchor)
    except TypeError:
        # fallback - crude outline
        x, y = xy
        offs = [-stroke, 0, stroke]
        for ox in offs:
            for oy in offs:
                draw.text((x+ox, y+oy), text, font=font, fill=outline)
        draw.text(xy, text, font=font, fill=fill)

def centered_x_for_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, left: int, right: int) -> int:
    try:
        bbox = draw.textbbox((0,0), text, font=font)
        w = bbox[2] - bbox[0]
    except Exception:
        w, _ = draw.textsize(text, font=font)
    return left + ( (right - left) - w ) // 2

# ---------------------------
# Exact geometry from template (pixel coords extracted from provided base)
# ---------------------------
# NOTE: these coords were extracted from the profile_base.png you provided.
PROFILE_COORDS = {
    "width_expected": 1536,  # some templates may be this size
    "header": {"top": 0, "bottom": 215, "left": 64, "right": 1472},
    "main_box": {"left": 64, "top": 215, "right": 1472, "bottom": 1505},
    "bottom_boxes": {
        "level": {"left": 62, "top": 1505, "right": 512, "bottom": 1732},
        "wins": {"left": 512, "top": 1505, "right": 1024, "bottom": 1732},
        "rituals": {"left": 1024, "top": 1505, "right": 1472, "bottom": 1732}
    },
    "footer": {"left": 64, "top": 1732, "right": 1472, "bottom": 1980}
}

# Sprite width choice: per your request A -> 600 px
SPRITE_TARGET_WIDTH = 600

# ---------------------------
# Generate profile image
# ---------------------------
def generate_profile_image(user: Dict[str, Any]) -> str:
    """
    Generate a profile image PNG based on the provided user dict.
    Returns path to generated PNG in /tmp.
    Expected keys in user:
      user_id, username, form, level, xp_total, xp_current, xp_to_next_level,
      wins, fights (or mobs_defeated), rituals, tg, ca
    """
    uid = str(user.get("user_id", "unknown"))
    username = str(user.get("username", f"User {uid}"))
    form = str(user.get("form", "Tadpole"))
    level = int(user.get("level", 1))
    xp_total = int(user.get("xp_total", 0))
    xp_current = int(user.get("xp_current", 0))
    xp_to_next = int(user.get("xp_to_next_level", 200))
    wins = int(user.get("wins", 0))
    fights = int(user.get("fights", user.get("mobs_defeated", 0)))
    rituals = int(user.get("rituals", 0))
    tg_text = user.get("tg", "")
    ca_text = user.get("ca", "")

    # Load base template (preferred)
    base_p = _asset_path(PROFILE_BASE)
    if base_p:
        card = Image.open(base_p).convert("RGBA")
    else:
        # fallback 900x1280 with warm paper
        card = Image.new("RGBA", (900, 1280), (255,249,230,255))

    W, H = card.size
    draw = ImageDraw.Draw(card)

    # Header area (use header left/right inside canvas)
    header_left = PROFILE_COORDS["header"]["left"]
    header_right = PROFILE_COORDS["header"]["right"]

    # Title "MEGAGROK" centered in header band
    title_text = "MEGAGROK"
    tx = centered_x_for_text(draw, title_text, TITLE_FONT, header_left, header_right)
    draw_outline_text(draw, (tx, 18), title_text, TITLE_FONT, fill=(20,20,20), outline=(255,220,120), stroke=6)

    # Username below title
    uname_y = 18 + 72 + 8  # roughly under title
    ux = centered_x_for_text(draw, username, USERNAME_FONT, header_left, header_right)
    draw_outline_text(draw, (ux, uname_y), username, USERNAME_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)

    # Main sprite area
    main = PROFILE_COORDS["main_box"]
    center_left, center_top, center_right, center_bottom = main["left"], main["top"], main["right"], main["bottom"]
    center_w = center_right - center_left
    center_h = center_bottom - center_top

    # Load sprite and resize to target width (600 px) preserving aspect ratio
    sprite = load_form_image(form)
    if sprite:
        target_w = SPRITE_TARGET_WIDTH
        sprite_aspect = sprite.height / sprite.width
        target_h = int(target_w * sprite_aspect)
        sprite_resized = sprite.resize((target_w, target_h), resample=Image.LANCZOS)
        # Place centered horizontally in main box but slightly right (as examples showed)
        sx = center_left + (center_w // 2) - (sprite_resized.width // 2) + int(center_w * 0.12)
        sy = center_top + (center_h // 2) - (sprite_resized.height // 2)
        card.paste(sprite_resized, (sx, sy), sprite_resized)

    # Bottom stat boxes (LEVEL | WINS | RITUALS)
    left_box = PROFILE_COORDS["bottom_boxes"]["level"]
    mid_box = PROFILE_COORDS["bottom_boxes"]["wins"]
    right_box = PROFILE_COORDS["bottom_boxes"]["rituals"]

    # Draw labels and numbers (text positioned with small padding)
    pad_x = 18
    # Level
    lvl_label_y = left_box["top"] + 12
    lvl_num_y = lvl_label_y + 48
    draw_outline_text(draw, (left_box["left"] + pad_x, lvl_label_y), "LEVEL", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)
    draw_outline_text(draw, (left_box["left"] + pad_x, lvl_num_y), str(level), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=4)
    # Wins
    wins_label_y = mid_box["top"] + 12
    wins_num_y = wins_label_y + 48
    draw_outline_text(draw, (mid_box["left"] + pad_x, wins_label_y), "WINS", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)
    draw_outline_text(draw, (mid_box["left"] + pad_x, wins_num_y), str(wins), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=4)
    # Rituals
    rit_label_y = right_box["top"] + 12
    rit_num_y = rit_label_y + 48
    draw_outline_text(draw, (right_box["left"] + pad_x, rit_label_y), "RITUALS", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)
    draw_outline_text(draw, (right_box["left"] + pad_x, rit_num_y), str(rituals), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=4)

    # Left small stats block in main area: FIGHTS / WINS
    stats_x = center_left + 18
    stats_y = center_top + 22
    draw.text((stats_x, stats_y), "FIGHTS / WINS", font=SMALL_FONT, fill=(20,20,20))
    draw.text((stats_x, stats_y + 34), f"{fights} / {wins}", font=LABEL_FONT, fill=(20,20,20))

    # Footer: TG and CA (centered if present)
    footer = PROFILE_COORDS["footer"]
    footer_top = footer["top"] + 12
    if tg_text:
        tdisplay = f"TG: {tg_text}"
        tx = centered_x_for_text(draw, tdisplay, FOOTER_FONT, footer["left"] + 8, footer["right"] - 8)
        draw.text((tx, footer_top), tdisplay, font=FOOTER_FONT, fill=(18,18,18))
    if ca_text:
        ca_display = f"CA: {ca_text}"
        ca_y = footer_top + 26
        tx2 = centered_x_for_text(draw, ca_display, FOOTER_FONT, footer["left"] + 8, footer["right"] - 8)
        draw.text((tx2, ca_y), ca_display, font=FOOTER_FONT, fill=(18,18,18))

    out_path = f"/tmp/profile_{uid}.png"
    card.save(out_path)
    return out_path

# ---------------------------
# Leaderboard generator
# ---------------------------
def generate_leaderboard_image() -> str:
    """
    Generate a top-5 leaderboard PNG. Reads get_top_users() if available in bot.db.
    """
    # Try to import real leaderboard data
    try:
        from bot.db import get_top_users
        rows = get_top_users(limit=5)
    except Exception:
        # placeholder rows
        rows = [
            {"user_id": 1001, "username": "Example1", "xp_total": 3450, "mobs_defeated": 70, "wins": 50, "form": "Hopper"},
            {"user_id": 1002, "username": "Example2", "xp_total": 3020, "mobs_defeated": 65, "wins": 45, "form": "Hopper"},
            {"user_id": 1003, "username": "Example3", "xp_total": 2800, "mobs_defeated": 60, "wins": 40, "form": "Hopper"},
            {"user_id": 1004, "username": "Example4", "xp_total": 2550, "mobs_defeated": 55, "wins": 35, "form": "Tadpole"},
            {"user_id": 1005, "username": "Example5", "xp_total": 2400, "mobs_defeated": 50, "wins": 30, "form": "Tadpole"}
        ]

    # Load base template
    base_p = _asset_path(LEADERBOARD_BASE)
    if base_p:
        img = Image.open(base_p).convert("RGBA")
    else:
        # fallback
        img = Image.new("RGBA", (1000, 1600), (255, 249, 230, 255))
    W, H = img.size
    draw = ImageDraw.Draw(img)

    # Title at top
    header_left = int(W * 0.06)
    header_right = int(W * 0.94)
    title = "TOP 5 LEADERBOARD"
    tx = centered_x_for_text(draw, title, TITLE_FONT, header_left, header_right)
    draw_outline_text(draw, (tx, 24), title, TITLE_FONT, fill=(255,200,60), outline=(10,10,40), stroke=6)

    # Rows area
    rows_top = int(H * 0.20)
    rows_left = int(W * 0.06)
    rows_right = int(W * 0.94)
    row_height = int((H - rows_top - 60) / 5)

    for i, r in enumerate(rows):
        rank = i + 1
        y = rows_top + i * row_height
        # rank number area
        rank_x = rows_left + 10
        rank_box_size = int(row_height * 0.6)
        # draw rank number (we overlay; template might already include circles)
        num_text = str(rank)
        try:
            bbox = draw.textbbox((0,0), num_text, font=BIG_NUM_FONT)
            w = bbox[2] - bbox[0]; h = bbox[3] - bbox[1]
        except Exception:
            w, h = draw.textsize(num_text, font=BIG_NUM_FONT)
        num_x = rank_x + (rank_box_size - w) // 2
        num_y = y + (row_height - rank_box_size) // 2 + (rank_box_size - h) // 2
        draw.text((num_x, num_y), num_text, font=BIG_NUM_FONT, fill=(10,10,10))

        # sprite area to right of rank
        sprite = load_form_image(r.get("form", "Tadpole"))
        if sprite:
            sp_w = int(rank_box_size * 0.9)
            asp = sprite.height / sprite.width
            sp_h = int(sp_w * asp)
            sp = sprite.resize((sp_w, sp_h), resample=Image.LANCZOS)
            sp_x = rank_x + rank_box_size + 18
            sp_y = y + (row_height - sp_h) // 2
            img.paste(sp, (sp_x, sp_y), sp)

        # text block to right of sprite
        text_block_x = rank_x + rank_box_size + 18 + (rank_box_size)
        text_block_y = y + int(row_height * 0.14)
        name = r.get("username", f"User{r.get('user_id', rank)}")
        draw_outline_text(draw, (text_block_x, text_block_y), name, USERNAME_FONT, fill=(10,10,10), outline=(255,255,255), stroke=3)

        # second line: XP + FIGHTS / WINS
        line2_y = text_block_y + 54
        xp = r.get("xp_total", r.get("xp", 0))
        fights = r.get("mobs_defeated", r.get("fights", 0))
        wins = r.get("wins", 0)
        line2 = f"XP: {xp}   FIGHTS / WINS: {fights} / {wins}"
        draw.text((text_block_x, line2_y), line2, font=LABEL_FONT, fill=(10,10,10))

    out = "/tmp/leaderboard.png"
    img.save(out)
    return out

# ---------------------------
# When executed as a script, create demo previews
# ---------------------------
if __name__ == "__main__":
    demo_user = {
        "user_id": 12345,
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
    print("Generating demo profile -> /tmp/profile_demo.png")
    p = generate_profile_image(demo_user)
    print("Profile generated:", p)
    print("Generating demo leaderboard -> /tmp/leaderboard.png")
    l = generate_leaderboard_image()
    print("Leaderboard generated:", l)
