# bot/images.py
import os
import math
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

ASSET_DIR = "assets"

# Expected asset filenames (must exist in assets/ or /mnt/data)
PROFILE_BASE = "profile_base.png"
LEADERBOARD_BASE = "leaderboard_base.png"
TADPOLE = "tadpole.png"
HOPPER = "hopper.png"
ASCENDED = "ascended.png"

FONT_FILES = {
    "bold": "Roboto-Bold.ttf",
    "regular": "Roboto-Regular.ttf",
    "light": "Roboto-Light.ttf"
}

# -------------------------
# Font loader with fallback
# -------------------------
def _font_path_candidates(name: str) -> List[str]:
    return [
        os.path.join(ASSET_DIR, name),
        os.path.join("/mnt/data", name),
        name
    ]

def load_font_with_fallback(font_name: str, size: int):
    from PIL import ImageFont
    for p in _font_path_candidates(font_name):
        try:
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

TITLE_FONT = load_font_with_fallback(FONT_FILES["bold"], 72)
USERNAME_FONT = load_font_with_fallback(FONT_FILES["regular"], 44)
LABEL_FONT = load_font_with_fallback(FONT_FILES["regular"], 32)
BIG_NUM_FONT = load_font_with_fallback(FONT_FILES["bold"], 72)
SMALL_FONT = load_font_with_fallback(FONT_FILES["regular"], 26)
FOOTER_FONT = load_font_with_fallback(FONT_FILES["light"], 22)

# -------------------------
# Asset helpers
# -------------------------
def _asset_path(name: str) -> Optional[str]:
    p = os.path.join(ASSET_DIR, name)
    if os.path.exists(p):
        return p
    alt = os.path.join("/mnt/data", name)
    if os.path.exists(alt):
        return alt
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

# -------------------------
# Evolution mapping
# -------------------------
FORM_TO_SPRITE = {
    "Tadpole": TADPOLE,
    "Hopper": HOPPER,
    "Ascended": ASCENDED,
    "Ascended Hopper": ASCENDED
}

def load_form_image(form_name: str) -> Optional[Image.Image]:
    fname = FORM_TO_SPRITE.get(form_name, TADPOLE)
    return _load_image(fname, mode="RGBA")

# -------------------------
# Drawing helpers
# -------------------------
def draw_outline_text(draw: ImageDraw.Draw, xy, text: str, font: ImageFont.FreeTypeFont,
                      fill=(0,0,0), outline=(255,255,255), stroke=3, anchor=None):
    try:
        draw.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=outline, anchor=anchor)
    except TypeError:
        x, y = xy
        offs = [-stroke, 0, stroke]
        for ox in offs:
            for oy in offs:
                draw.text((x+ox, y+oy), text, font=font, fill=outline)
        draw.text(xy, text, font=font, fill=fill)

def _centered_x_for_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, left: int, right: int) -> int:
    try:
        bbox = draw.textbbox((0,0), text, font=font)
        tw = bbox[2] - bbox[0]
    except Exception:
        tw, _ = draw.textsize(text, font=font)
    return left + ( (right - left) - tw ) // 2

# -------------------------
# PROFILE GENERATOR
# -------------------------
def generate_profile_image(user: Dict[str, Any]) -> str:
    """
    user keys:
      user_id, username, form, level, xp_total, xp_current, xp_to_next_level,
      wins, fights, rituals, tg (optional), ca (optional)
    """
    uid = str(user.get("user_id", "unknown"))
    username = str(user.get("username", f"User{uid}"))
    form = str(user.get("form", "Tadpole"))
    level = int(user.get("level", 1))
    xp_total = int(user.get("xp_total", 0))
    xp_current = int(user.get("xp_current", 0))
    xp_to_next = int(user.get("xp_to_next_level", max(200, 200)))
    wins = int(user.get("wins", 0))
    fights = int(user.get("fights", user.get("mobs_defeated", 0)))
    rituals = int(user.get("rituals", 0))
    tg_text = user.get("tg", "") or ""
    ca_text = user.get("ca", "") or ""

    base_path = _asset_path(PROFILE_BASE)
    if base_path:
        card = Image.open(base_path).convert("RGBA")
    else:
        # fallback card (same aspect as your template)
        card = Image.new("RGBA", (900, 1280), (255, 249, 230, 255))

    WIDTH, HEIGHT = card.size
    draw = ImageDraw.Draw(card)

    # Header area: use the top yellow band (we center in the full width minus safe margins)
    header_left = int(WIDTH * 0.05)
    header_right = int(WIDTH * 0.95)
    title_text = "MEGAGROK"
    title_x = _centered_x_for_text(draw, title_text, TITLE_FONT, header_left, header_right)
    title_y = int(HEIGHT * 0.02)  # small offset from very top
    draw_outline_text(draw, (title_x, title_y), title_text, TITLE_FONT, fill=(20,20,20), outline=(255,220,120), stroke=6)

    # Username centered under MEGAGROK (inside same header band visually)
    uname_text = username
    uname_x = _centered_x_for_text(draw, uname_text, USERNAME_FONT, header_left, header_right)
    uname_y = title_y + int(TITLE_FONT.size * 0.9)  # place directly beneath
    draw_outline_text(draw, (uname_x, uname_y), uname_text, USERNAME_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)

    # Center art box coordinates (we try to align with your template)
    # These fractions match the profile_base layout you provided
    center_left = int(WIDTH * 0.07)
    center_right = int(WIDTH * 0.93)
    center_top = int(HEIGHT * 0.12)
    center_bottom = int(HEIGHT * 0.67)
    center_w = center_right - center_left
    center_h = center_bottom - center_top

    # Sprite placement: scale to ~50% of center width and place slightly right (per brief)
    sprite = load_form_image(form)
    if sprite:
        target_w = int(center_w * 0.5)
        aspect = sprite.height / sprite.width if sprite.width else 1.0
        target_h = int(target_w * aspect)
        sprite_resized = sprite.resize((target_w, target_h), resample=Image.LANCZOS)
        sx = center_left + (center_w // 2) - (sprite_resized.width // 2) + int(center_w * 0.12)
        sy = center_top + (center_h // 2) - (sprite_resized.height // 2)
        card.paste(sprite_resized, (sx, sy), sprite_resized)

    # Bottom stats boxes positions (match template proportions)
    bottom_area_top = int(HEIGHT * 0.68)
    bottom_area_left = int(WIDTH * 0.07)
    bottom_area_right = int(WIDTH * 0.93)
    total_bottom_w = bottom_area_right - bottom_area_left
    gutter = int(total_bottom_w * 0.02)

    left_w = int(total_bottom_w * 0.22)
    mid_w = int(total_bottom_w * 0.48)
    right_w = total_bottom_w - left_w - mid_w - (2 * gutter)

    left_bbox = (bottom_area_left, bottom_area_top, bottom_area_left + left_w, bottom_area_top + int(HEIGHT * 0.12))
    mid_bbox = (left_bbox[2] + gutter, bottom_area_top, left_bbox[2] + gutter + mid_w, bottom_area_top + int(HEIGHT * 0.12))
    right_bbox = (mid_bbox[2] + gutter, bottom_area_top, bottom_area_right, bottom_area_top + int(HEIGHT * 0.12))

    # LEVEL
    lvl_label_y = left_bbox[1] + 10
    lvl_num_y = lvl_label_y + 38
    draw_outline_text(draw, (left_bbox[0] + 18, lvl_label_y), "LEVEL", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)
    draw_outline_text(draw, (left_bbox[0] + 18, lvl_num_y), str(level), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=4)

    # WINS
    wins_label_y = mid_bbox[1] + 10
    wins_num_y = wins_label_y + 38
    draw_outline_text(draw, (mid_bbox[0] + 18, wins_label_y), "WINS", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)
    draw_outline_text(draw, (mid_bbox[0] + 18, wins_num_y), str(wins), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=4)

    # RITUALS
    rit_label_y = right_bbox[1] + 10
    rit_num_y = rit_label_y + 38
    draw_outline_text(draw, (right_bbox[0] + 18, rit_label_y), "RITUALS", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)
    draw_outline_text(draw, (right_bbox[0] + 18, rit_num_y), str(rituals), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=4)

    # LEFT-side stats block inside center box (FIGHTS / WINS) — placed near top-left of center box
    stats_x = center_left + 18
    stats_y = center_top + 18
    draw_outline_text(draw, (stats_x, stats_y), "FIGHTS / WINS", SMALL_FONT, fill=(10,10,10), outline=(255,255,255), stroke=2)
    draw_outline_text(draw, (stats_x, stats_y + 30), f"{fights} / {wins}", LABEL_FONT, fill=(10,10,10), outline=(255,255,255), stroke=2)

    # Footer: TG (one line) and CA (below) centered in footer box (one line above bottom frame)
    footer_top = int(HEIGHT * 0.83)
    footer_left = bottom_area_left
    footer_right = bottom_area_right
    if tg_text:
        ft = f"TG: {tg_text}"
        tx = _centered_x_for_text(draw, ft, FOOTER_FONT, footer_left + 8, footer_right - 8)
        draw.text((tx, footer_top + 6), ft, font=FOOTER_FONT, fill=(18,18,18))
    if ca_text:
        ca_display = f"CA: {ca_text}"
        tx2 = _centered_x_for_text(draw, ca_display, FOOTER_FONT, footer_left + 8, footer_right - 8)
        draw.text((tx2, footer_top + 30), ca_display, font=FOOTER_FONT, fill=(18,18,18))

    out = f"/tmp/profile_{uid}.png"
    card.save(out)
    return out

# -------------------------
# LEADERBOARD GENERATOR
# -------------------------
def generate_leaderboard_image() -> str:
    try:
        from bot.db import get_top_users
    except Exception:
        def get_top_users(limit=5):
            return [
                {"user_id": 1001, "username": "Alpha", "xp_total": 3450, "level": 12, "form": "Hopper", "wins": 50, "mobs_defeated": 70},
                {"user_id": 1002, "username": "Bravo", "xp_total": 3020, "level": 11, "form": "Hopper", "wins": 45, "mobs_defeated": 65},
                {"user_id": 1003, "username": "Charlie", "xp_total": 2800, "level": 10, "form": "Hopper", "wins": 40, "mobs_defeated": 60},
                {"user_id": 1004, "username": "Delta", "xp_total": 2550, "level": 9, "form": "Tadpole", "wins": 35, "mobs_defeated": 55},
                {"user_id": 1005, "username": "Echo", "xp_total": 2400, "level": 8, "form": "Tadpole", "wins": 30, "mobs_defeated": 50},
            ]

    rows = get_top_users(limit=5)

    base_path = _asset_path(LEADERBOARD_BASE)
    if base_path:
        img = Image.open(base_path).convert("RGBA")
    else:
        img = Image.new("RGBA", (1000, 1600), (22,18,40,255))

    WIDTH, HEIGHT = img.size
    draw = ImageDraw.Draw(img)

    # Header title (centered)
    header_left = int(WIDTH * 0.05)
    header_right = int(WIDTH * 0.95)
    title = "TOP 5 LEADERBOARD"
    tx = _centered_x_for_text(draw, title, TITLE_FONT, header_left, header_right)
    draw_outline_text(draw, (tx, int(HEIGHT*0.02)), title, TITLE_FONT, fill=(255,200,60), outline=(10,10,40), stroke=6)

    # Rows area
    rows_top = int(HEIGHT * 0.18)
    rows_left = int(WIDTH * 0.06)
    rows_right = int(WIDTH * 0.94)
    row_height = int((HEIGHT - rows_top - 60) / 5)

    for i, r in enumerate(rows):
        rank = i + 1
        y = rows_top + i * row_height

        # rank number area (left)
        rank_circle_x = rows_left + 10
        rank_box_size = int(row_height * 0.6)
        # draw rank number using BIG_NUM_FONT, approximate centering inside circle area
        num_text = str(rank)
        try:
            bbox = draw.textbbox((0,0), num_text, font=BIG_NUM_FONT)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        except Exception:
            w, h = draw.textsize(num_text, font=BIG_NUM_FONT)
        num_x = rank_circle_x + (rank_box_size - w) // 2
        num_y = y + (rank_box_size - h) // 2 + int(row_height * 0.08)
        draw.text((num_x, num_y), num_text, font=BIG_NUM_FONT, fill=(10,10,10))

        # sprite area to the right of rank
        sprite = load_form_image(r.get("form", "Tadpole"))
        if sprite:
            sp_w = int(rank_box_size * 0.9)
            asp = sprite.height / sprite.width if sprite.width else 1.0
            sp_h = int(sp_w * asp)
            sp = sprite.resize((sp_w, sp_h), resample=Image.LANCZOS)
            sp_x = rank_circle_x + rank_box_size + 18
            sp_y = y + (row_height - sp_h) // 2
            img.paste(sp, (sp_x, sp_y), sp)
        else:
            sp_x = rank_circle_x + rank_box_size + 18

        # text block to the right
        text_block_x = rank_circle_x + rank_box_size + 18 + int(rank_box_size)
        text_block_y = y + int(row_height * 0.12)
        name = r.get("username", f"User{r.get('user_id', rank)}")
        draw_outline_text(draw, (text_block_x, text_block_y), name, USERNAME_FONT, fill=(10,10,10), outline=(255,255,255), stroke=3)

        # second line: XP + FIGHTS / WINS
        line2_y = text_block_y + 46
        xp = r.get("xp_total", r.get("xp", 0))
        fights = r.get("mobs_defeated", r.get("fights", 0))
        wins = r.get("wins", 0)
        line2 = f"XP: {xp}   FIGHTS / WINS: {fights} / {wins}"
        draw.text((text_block_x, line2_y), line2, font=LABEL_FONT, fill=(10,10,10))

    out = "/tmp/leaderboard.png"
    img.save(out)
    return out

# -------------------------
# Demo preview generator if run directly
# -------------------------
if __name__ == "__main__":
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
    p = generate_profile_image(sample_user)
    print("Profile written:", p)
    print("Writing demo leaderboard to /tmp/leaderboard_demo.png ...")
    l = generate_leaderboard_image()
    print("Leaderboard written:", l)
