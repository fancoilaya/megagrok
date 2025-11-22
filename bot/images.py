# bot/images.py
import os
import math
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

# If your project stores assets under a different path, update this.
ASSET_DIR = "assets"

# Template filenames expected in assets/ (you already created these)
PROFILE_BASE = "profile_base.png"       # blank trading-card background (no text)
LEADERBOARD_BASE = "leaderboard_base.png"
TADPOLE = "tadpole.png"
HOPPER = "hopper.png"
ASCENDED = "ascended.png"

# Font filenames we agreed on (you uploaded these to /mnt/data, but we also try assets/)
FONT_FILES = {
    "bold": "Roboto-Bold.ttf",
    "regular": "Roboto-Regular.ttf",
    "light": "Roboto-Light.ttf"
}

# ====================================================
# Utility: robust font loader (tries ASSET_DIR then /mnt/data as fallback)
# ====================================================
def _font_path_candidates(name: str) -> List[str]:
    """Return possible absolute paths where font may live."""
    candidates = []
    # prefer ASSET_DIR relative path
    candidates.append(os.path.join(ASSET_DIR, name))
    # also try absolute uploaded location (some environments e.g. /mnt/data)
    candidates.append(os.path.join("/mnt/data", name))
    # lastly, try the raw name (current working dir)
    candidates.append(name)
    return candidates

def load_font_with_fallback(font_name: str, size: int):
    """Try a list of candidate paths and fall back to ImageFont.load_default()."""
    from PIL import ImageFont
    for p in _font_path_candidates(font_name):
        try:
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
        except Exception:
            continue
    # final fallback
    return ImageFont.load_default()

# Preload a few font sizes used across the module
TITLE_FONT = load_font_with_fallback(FONT_FILES["bold"], 72)
USERNAME_FONT = load_font_with_fallback(FONT_FILES["regular"], 44)
LABEL_FONT = load_font_with_fallback(FONT_FILES["regular"], 36)
BIG_NUM_FONT = load_font_with_fallback(FONT_FILES["bold"], 72)
SMALL_FONT = load_font_with_fallback(FONT_FILES["regular"], 26)
FOOTER_FONT = load_font_with_fallback(FONT_FILES["light"], 22)

# ====================================================
# Helper: load asset image safely
# ====================================================
def _asset_path(name: str) -> Optional[str]:
    """Return an existing path for a named asset or None."""
    cand = os.path.join(ASSET_DIR, name)
    if os.path.exists(cand):
        return cand
    alt = os.path.join("/mnt/data", name)
    if os.path.exists(alt):
        return alt
    # try raw name
    if os.path.exists(name):
        return name
    return None

def _load_image(name: str, mode: str = "RGBA") -> Optional[Image.Image]:
    p = _asset_path(name)
    if not p:
        return None
    try:
        img = Image.open(p).convert(mode)
        return img
    except Exception:
        return None

# ====================================================
# Evolution form -> sprite mapping
# ====================================================
FORM_TO_SPRITE = {
    "Tadpole": TADPOLE,
    "Hopper": HOPPER,
    "Ascended": ASCENDED,
    # fallback alias
    "Ascended Hopper": ASCENDED
}

def load_form_image(form_name: str) -> Optional[Image.Image]:
    fname = FORM_TO_SPRITE.get(form_name, TADPOLE)
    return _load_image(fname, mode="RGBA")

# ====================================================
# Text drawing helpers
# ====================================================
def draw_outline_text(draw: ImageDraw.Draw, xy, text: str, font: ImageFont.FreeTypeFont,
                      fill=(0,0,0), outline=(255,255,255), stroke=3, anchor=None):
    """
    Draw text using Pillow stroke parameters (works on modern Pillow).
    If stroke not supported, fallback to drawing the outline manually.
    """
    try:
        draw.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=outline, anchor=anchor)
    except TypeError:
        # older pillow fallback: draw text multiple times for outline
        x, y = xy
        offs = [-stroke, 0, stroke]
        for ox in offs:
            for oy in offs:
                draw.text((x+ox, y+oy), text, font=font, fill=outline)
        draw.text(xy, text, font=font, fill=fill)

def _centered_x_for_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, container_left: int, container_right: int) -> int:
    """Return x such that text is horizontally centered in the container region."""
    try:
        bbox = draw.textbbox((0,0), text, font=font)
        text_w = bbox[2] - bbox[0]
    except Exception:
        text_w, _ = draw.textsize(text, font=font)
    container_w = container_right - container_left
    return container_left + (container_w - text_w) // 2

# ====================================================
# PROFILE IMAGE GENERATOR
# ====================================================
def generate_profile_image(user: Dict[str, Any]) -> str:
    """
    Generate profile PNG.
    Expected user keys (safe defaults used):
      user_id, username, form, level, xp_total, xp_current, xp_to_next_level,
      wins, fights, rituals
    Returns path to saved PNG.
    """
    # safe defaults
    uid = str(user.get("user_id", "unknown"))
    username = str(user.get("username", f"User {uid}"))
    form = str(user.get("form", "Tadpole"))
    level = int(user.get("level", 1))
    xp_total = int(user.get("xp_total", 0))
    xp_current = int(user.get("xp_current", 0))
    xp_to_next = int(user.get("xp_to_next_level", max(200, 200)))
    wins = int(user.get("wins", 0))
    fights = int(user.get("fights", user.get("mobs_defeated", 0)))
    rituals = int(user.get("rituals", 0))

    # Load base template
    base_path = _asset_path(PROFILE_BASE)
    if not base_path:
        # create a fallback 900x1280 card if base missing
        WIDTH, HEIGHT = 900, 1280
        card = Image.new("RGBA", (WIDTH, HEIGHT), (255, 249, 230, 255))
    else:
        card = Image.open(base_path).convert("RGBA")
        WIDTH, HEIGHT = card.size

    draw = ImageDraw.Draw(card)

    # --- Header: MEGAGROK (centered) and username below it ---
    header_top = 18  # top margin inside header band
    header_left = 40
    header_right = WIDTH - 40
    # Title
    title_text = "MEGAGROK"
    title_x = _centered_x_for_text(draw, title_text, TITLE_FONT, header_left, header_right)
    draw_outline_text(draw, (title_x, header_top+6), title_text, TITLE_FONT, fill=(20,20,20), outline=(255,220,120), stroke=6)
    # Username below title
    uname_text = username
    uname_y = header_top + 86
    uname_x = _centered_x_for_text(draw, uname_text, USERNAME_FONT, header_left, header_right)
    draw_outline_text(draw, (uname_x, uname_y), uname_text, USERNAME_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)

    # --- Center image area (sprite + background is in base template) ---
    # Determine center box roughly based on the card layout of your provided base
    # We assume the big center box has some margin; search for it visually or use fixed relative coords:
    center_left = int(WIDTH * 0.07)
    center_right = int(WIDTH * 0.93)
    center_top = int(HEIGHT * 0.12)
    center_bottom = int(HEIGHT * 0.67)
    center_w = center_right - center_left
    center_h = center_bottom - center_top

    # Load sprite and place it centered but slightly right (per your examples)
    sprite = load_form_image(form)
    if sprite:
        # reduce sprite size to 50% of available area width to match your request
        target_w = int(center_w * 0.5)
        aspect = sprite.height / sprite.width
        target_h = int(target_w * aspect)
        sprite_resized = sprite.resize((target_w, target_h), resample=Image.LANCZOS)
        # place sprite centered horizontally in the center region but slightly right
        sx = center_left + (center_w // 2) - (sprite_resized.width // 2) + int(center_w * 0.12)
        sy = center_top + (center_h // 2) - (sprite_resized.height // 2)
        card.paste(sprite_resized, (sx, sy), sprite_resized)
    # else: leave background alone

    # --- Bottom stats bar (three boxes: Level | Wins | Rituals) ---
    # We'll attempt to locate bottom boxes by relative positions (these match your base layout)
    bottom_area_top = int(HEIGHT * 0.68)
    bottom_area_left = int(WIDTH * 0.07)
    bottom_area_right = int(WIDTH * 0.93)
    total_bottom_w = bottom_area_right - bottom_area_left

    # The three boxes: left_box (level), mid_box (wins), right_box (rituals)
    # Based on your template proportions, left box is ~22% width, mid ~48%, right ~22% (approx)
    left_w = int(total_bottom_w * 0.22)
    mid_w = int(total_bottom_w * 0.48)
    right_w = total_bottom_w - left_w - mid_w - 8  # small gutter

    gutter = 8
    left_bbox = (bottom_area_left, bottom_area_top, bottom_area_left + left_w, bottom_area_top + int(HEIGHT*0.12))
    mid_bbox = (left_bbox[2] + gutter, bottom_area_top, left_bbox[2] + gutter + mid_w, bottom_area_top + int(HEIGHT*0.12))
    right_bbox = (mid_bbox[2] + gutter, bottom_area_top, bottom_area_right, bottom_area_top + int(HEIGHT*0.12))

    # Draw the big labels and numbers (use outline_text to keep comic look)
    # LEVEL box
    lvl_label_y = left_bbox[1] + 12
    lvl_num_y = lvl_label_y + 40
    draw_outline_text(draw, (left_bbox[0] + 18, lvl_label_y), "LEVEL", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)
    draw_outline_text(draw, (left_bbox[0] + 18, lvl_num_y), str(level), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=4)

    # WINS box (center)
    wins_label_y = mid_bbox[1] + 12
    wins_num_y = wins_label_y + 40
    draw_outline_text(draw, (mid_bbox[0] + 18, wins_label_y), "WINS", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)
    draw_outline_text(draw, (mid_bbox[0] + 18, wins_num_y), str(wins), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=4)

    # RITUALS box (right)
    rit_label_y = right_bbox[1] + 12
    rit_num_y = rit_label_y + 40
    draw_outline_text(draw, (right_bbox[0] + 18, rit_label_y), "RITUALS", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)
    draw_outline_text(draw, (right_bbox[0] + 18, rit_num_y), str(rituals), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=4)

    # --- Left side stats column (optional): Fights / Wins textual list near top-left of center region ---
    # We'll draw a compact stats block on the left inside the center frame
    stats_x = center_left + 18
    stats_y = center_top + 22
    draw.text((stats_x, stats_y), "FIGHTS / WINS", font=SMALL_FONT, fill=(20,20,20))
    draw.text((stats_x, stats_y + 34), f"{fights} / {wins}", font=LABEL_FONT, fill=(20,20,20))

    # --- Footer area: TG and CA placement (we keep it subtle and centered) ---
    footer_h = int(HEIGHT * 0.10)
    footer_box = (bottom_area_left, int(HEIGHT * 0.83), bottom_area_right, int(HEIGHT * 0.83) + footer_h)
    # We'll not write actual addresses by default; check for provided overlay values in user
    tg_text = user.get("tg", "")
    ca_text = user.get("ca", "")

    # If the user provided tg / ca in the dict, render them; otherwise leave blank.
    footer_text_y = footer_box[1] + 12
    if tg_text:
        footer_text = f"TG: {tg_text}"
        # center left
        tx = _centered_x_for_text(draw, footer_text, FOOTER_FONT, footer_box[0]+8, footer_box[2]-8)
        draw.text((tx, footer_text_y), footer_text, font=FOOTER_FONT, fill=(18,18,18))

    if ca_text:
        ca_y = footer_text_y + 28
        ca_display = f"CA: {ca_text}"
        tx2 = _centered_x_for_text(draw, ca_display, FOOTER_FONT, footer_box[0]+8, footer_box[2]-8)
        draw.text((tx2, ca_y), ca_display, font=FOOTER_FONT, fill=(18,18,18))

    # Save output
    out = f"/tmp/profile_{uid}.png"
    card.save(out)
    return out

# ====================================================
# LEADERBOARD GENERATOR
# ====================================================
# The generator expects a get_top_users function to exist in bot.db,
# but to keep this file self-contained we import it lazily inside the function.
def generate_leaderboard_image() -> str:
    """
    Compose top-5 leaderboard. Uses leaderboard_base.png as the background.
    Each row shows: rank number, (sprite placeholder) and text: ExampleNameX
    and a second line: "XP: 1234  FIGHTS / WINS: 70 / 50"
    Data is obtained by calling bot.db.get_top_users() if available.
    """
    # Attempt to import get_top_users
    try:
        from bot.db import get_top_users
    except Exception:
        # fallback: create placeholder dataset
        def get_top_users(limit=5):
            return [
                {"user_id": 1001, "xp_total": 3450, "level": 12, "form": "Hopper", "wins": 50, "mobs_defeated": 70, "rituals": 3},
                {"user_id": 1002, "xp_total": 3020, "level": 11, "form": "Hopper", "wins": 45, "mobs_defeated": 65, "rituals": 2},
                {"user_id": 1003, "xp_total": 2800, "level": 10, "form": "Hopper", "wins": 40, "mobs_defeated": 60, "rituals": 4},
                {"user_id": 1004, "xp_total": 2550, "level": 9, "form": "Tadpole", "wins": 35, "mobs_defeated": 55, "rituals": 1},
                {"user_id": 1005, "xp_total": 2400, "level": 8, "form": "Tadpole", "wins": 30, "mobs_defeated": 50, "rituals": 0},
            ]

    rows = get_top_users(limit=5)

    # Load the leaderboard base template
    base_path = _asset_path(LEADERBOARD_BASE)
    if not base_path:
        # fallback create 1000x1600 simple background
        WIDTH, HEIGHT = 1000, 1600
        img = Image.new("RGBA", (WIDTH, HEIGHT), (22,18,40,255))
    else:
        img = Image.open(base_path).convert("RGBA")
        WIDTH, HEIGHT = img.size

    draw = ImageDraw.Draw(img)

    # Title text: try to overlay "TOP 5 LEADERBOARD" centered in header
    header_top = 30
    header_left = 40
    header_right = WIDTH - 40
    title = "TOP 5 LEADERBOARD"
    tx = _centered_x_for_text(draw, title, TITLE_FONT, header_left, header_right)
    draw_outline_text(draw, (tx, header_top), title, TITLE_FONT, fill=(255,200,60), outline=(10,10,40), stroke=6)

    # Determine rows area
    rows_top = int(HEIGHT * 0.20)
    rows_left = int(WIDTH * 0.06)
    rows_right = int(WIDTH * 0.94)
    row_height = int((HEIGHT - rows_top - 60) / 5)

    for i, r in enumerate(rows):
        rank = i + 1
        y = rows_top + i * row_height

        # left rank circle area: small fixed x
        rank_x = rows_left + 10
        rank_y = y + int(row_height * 0.08)
        rank_box_size = int(row_height * 0.6)
        # Draw rank number (we expect the base image already has the circles; we overlay text)
        # place big number centered inside assumed circle at (rank_x + rank_box_size/2)
        num_text = str(rank)
        try:
            bbox = draw.textbbox((0,0), num_text, font=BIG_NUM_FONT)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        except Exception:
            w, h = draw.textsize(num_text, font=BIG_NUM_FONT)
        num_x = rank_x + (rank_box_size - w) // 2
        num_y = rank_y + (rank_box_size - h) // 2
        draw.text((num_x, num_y), num_text, font=BIG_NUM_FONT, fill=(10,10,10))

        # middle: sprite placeholder area - try to paste the evolution image scaled
        sprite = load_form_image(r.get("form", "Tadpole"))
        if sprite:
            sp_w = int(rank_box_size * 0.9)
            asp = sprite.height / sprite.width
            sp_h = int(sp_w * asp)
            sp = sprite.resize((sp_w, sp_h), resample=Image.LANCZOS)
            sp_x = rank_x + rank_box_size + 18
            sp_y = y + (row_height - sp_h) // 2
            img.paste(sp, (sp_x, sp_y), sp)

        # text block to the right of sprite
        text_block_x = rank_x + rank_box_size + 18 + (rank_box_size)
        text_block_y = y + int(row_height * 0.14)
        name = r.get("username", f"User{r.get('user_id', rank)}")
        # first line: name
        draw_outline_text(draw, (text_block_x, text_block_y), name, USERNAME_FONT, fill=(10,10,10), outline=(255,255,255), stroke=3)
        # second line: XP + fights/wins
        line2_y = text_block_y + 54
        xp = r.get("xp_total", r.get("xp", 0))
        fights = r.get("mobs_defeated", r.get("fights", 0))
        wins = r.get("wins", 0)
        line2 = f"XP: {xp}   FIGHTS / WINS: {fights} / {wins}"
        draw.text((text_block_x, line2_y), line2, font=LABEL_FONT, fill=(10,10,10))

    out = "/tmp/leaderboard.png"
    img.save(out)
    return out

# ====================================================
# If run as script, produce sample preview images to /tmp
# ====================================================
if __name__ == "__main__":
    # Demo preview using sample data
    sample_user = {
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
    print("Writing demo profile to /tmp/profile_demo.png ...")
    path = generate_profile_image(sample_user)
    print("Profile written:", path)
    print("Writing demo leaderboard to /tmp/leaderboard_demo.png ...")
    lpath = generate_leaderboard_image()
    print("Leaderboard written:", lpath)
