# bot/images.py
import os
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# -------------------------
# Assets / filenames
# -------------------------
ASSET_DIR = "assets"
PROFILE_BASE = "profile_base.png"
LEADERBOARD_BASE = "leaderboard_base.png"
TADPOLE = "tadpole.png"
HOPPER = "hopper.png"
ASCENDED = "ascended.png"

FONT_FILES = {
    "bold": "Roboto-Bold.ttf",
    "regular": "Roboto-Regular.ttf",
    "light": "Roboto-Light.ttf",
}

# -------------------------
# Robust helpers
# -------------------------
def _asset_path(name: str) -> Optional[str]:
    """Return an existing path for a named asset or None."""
    p = os.path.join(ASSET_DIR, name)
    if os.path.exists(p):
        return p
    # fallback to /mnt/data (run environment) - we uploaded fonts there
    alt = os.path.join("/mnt/data", name)
    if os.path.exists(alt):
        return alt
    # fallback raw
    if os.path.exists(name):
        return name
    return None

def load_font(name: str, size: int):
    """Try assets folder, /mnt/data, else default font."""
    cand = _asset_path(name)
    try:
        if cand:
            return ImageFont.truetype(cand, size)
    except Exception:
        pass
    try:
        return ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()

# Preload fonts (sizes tuned for 900x1280 profile)
TITLE_FONT = load_font(FONT_FILES["bold"], 84)
USERNAME_FONT = load_font(FONT_FILES["regular"], 42)
LABEL_FONT = load_font(FONT_FILES["regular"], 34)
BIG_NUM_FONT = load_font(FONT_FILES["bold"], 64)
SMALL_FONT = load_font(FONT_FILES["regular"], 26)
FOOTER_FONT = load_font(FONT_FILES["light"], 20)

# Outline-draw helper (works with pillow stroke parameters if available)
def draw_outline_text(draw: ImageDraw.Draw, pos, text, font, fill=(0,0,0), outline=(255,255,255), stroke=3, anchor=None):
    try:
        draw.text(pos, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=outline, anchor=anchor)
    except TypeError:
        # fallback naive outline
        x,y = pos
        for ox in (-stroke,0,stroke):
            for oy in (-stroke,0,stroke):
                draw.text((x+ox, y+oy), text, font=font, fill=outline)
        draw.text(pos, text, font=font, fill=fill)

def _centered_x(draw: ImageDraw.Draw, text: str, font, left:int, right:int) -> int:
    try:
        bbox = draw.textbbox((0,0), text, font=font)
        tw = bbox[2]-bbox[0]
    except Exception:
        tw = draw.textsize(text, font=font)[0]
    return left + ( (right-left) - tw ) // 2

# -------------------------
# Sprite loader
# -------------------------
FORM_TO_SPRITE = {
    "Tadpole": TADPOLE,
    "Hopper": HOPPER,
    "Ascended": ASCENDED,
    "Ascended Hopper": ASCENDED
}

def load_form_image(form_name: str):
    fname = FORM_TO_SPRITE.get(form_name, TADPOLE)
    p = _asset_path(fname)
    if not p:
        return None
    try:
        return Image.open(p).convert("RGBA")
    except Exception:
        return None

# -------------------------
# Profile layout detection (hard-coded after detecting profile_base)
# -------------------------
# These coordinates were derived from your uploaded profile_base.png (900×1280 expected)
# If your base image size differs, the code will scale coordinates proportionally.
_profile_base_path = _asset_path(PROFILE_BASE)
_profile_base_image = None
if _profile_base_path:
    try:
        _profile_base_image = Image.open(_profile_base_path).convert("RGBA")
        BASE_W, BASE_H = _profile_base_image.size
    except Exception:
        _profile_base_image = None
        BASE_W, BASE_H = 900, 1280
else:
    BASE_W, BASE_H = 900, 1280

# Hard-coded boxes found from analysis (these are relative to the base image size used above).
# If your profile_base is exactly the uploaded one, these will map precisely. Otherwise they are scaled.
# Coordinates from detection:
# header box (x1,y1,x2,y2)
_DET_HEADER = (46, 54, 977, 203)
# center image box (frame area)
_DET_CENTER = (76, 203, 947, 871)  # adjusted top to include the visible frame (approx)
# bottom left small box (level)
_DET_BLEFT = (76, 1047, 335, 1215)
# bottom middle box (wins)
_DET_BMID  = (361, 1047, 947, 1215)
# footer big box (footer for TG/CA)
_DET_FOOTER = (76, 1239, 947, 1402)

# Utility to scale coordinates if base image used at different size
def _scale_box(box, w, h):
    bx1,by1,bx2,by2 = box
    sx = w / BASE_W
    sy = h / BASE_H
    return (int(bx1*sx), int(by1*sy), int(bx2*sx), int(by2*sy))

# -------------------------
# PROFILE generator
# -------------------------
def generate_profile_image(user: Dict[str,Any]) -> str:
    """
    Generate profile PNG based on profile_base.png and overlay the username, sprite and stats.
    user keys used: user_id, username, form, level, xp_total, xp_current, xp_to_next_level,
                    wins, fights (or mobs_defeated), rituals, tg, ca
    Returns: path to saved PNG
    """
    uid = str(user.get("user_id","unknown"))
    username = str(user.get("username", f"User-{uid}"))
    form = str(user.get("form","Tadpole"))
    level = int(user.get("level",1))
    xp_total = int(user.get("xp_total",0))
    xp_current = int(user.get("xp_current",0))
    xp_to_next = int(user.get("xp_to_next_level", max(200,1)))
    wins = int(user.get("wins",0))
    fights = int(user.get("fights", user.get("mobs_defeated", 0)))
    rituals = int(user.get("rituals",0))
    tg = user.get("tg","")
    ca = user.get("ca","")

    # Load base card (or create fallback canvas)
    base_path = _asset_path(PROFILE_BASE)
    if base_path:
        card = Image.open(base_path).convert("RGBA")
    else:
        card = Image.new("RGBA", (BASE_W, BASE_H), (255,249,230,255))

    W,H = card.size
    draw = ImageDraw.Draw(card)

    # scale detection boxes to actual size
    header = _scale_box(_DET_HEADER, W, H)
    center = _scale_box(_DET_CENTER, W, H)
    bleft = _scale_box(_DET_BLEFT, W, H)
    bmid  = _scale_box(_DET_BMID, W, H)
    footer = _scale_box(_DET_FOOTER, W, H)

    # Header Title (centered inside header box)
    title_text = "MEGAGROK"
    tx = _centered_x(draw, title_text, TITLE_FONT, header[0]+10, header[2]-10)
    ty = header[1] + 6
    draw_outline_text(draw, (tx, ty), title_text, TITLE_FONT, fill=(20,20,20), outline=(255,220,120), stroke=6)

    # Username under the title (centered)
    uname_y = ty + 80
    ux = _centered_x(draw, username, USERNAME_FONT, header[0]+10, header[2]-10)
    draw_outline_text(draw, (ux, uname_y), username, USERNAME_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)

    # Sprite placement: center region. We'll place sprite centered horizontally, slightly right vertically matching style.
    sprite = load_form_image(form)
    if sprite:
        # target width is ~50% of the center width (matches earlier request)
        c_w = center[2] - center[0]
        target_w = int(c_w * 0.50)
        asp = sprite.height / sprite.width
        target_h = int(target_w * asp)
        sprite_resized = sprite.resize((target_w, target_h), resample=Image.LANCZOS)
        # place centered horizontally inside center box but shifted slightly right (visual preference)
        sx = center[0] + (c_w - sprite_resized.width)//2 + int(c_w*0.08)
        sy = center[1] + ( (center[3]-center[1]) - sprite_resized.height )//2 - 20
        card.paste(sprite_resized, (sx, sy), sprite_resized)

    # Stats on bottom boxes (text large and prominent)
    # LEVEL (left box) - label + big number
    left_label_pos = (bleft[0] + 18, bleft[1] + 10)
    left_num_pos   = (bleft[0] + 18, bleft[1] + 48)
    draw_outline_text(draw, left_label_pos, "LEVEL", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)
    draw_outline_text(draw, left_num_pos, str(level), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=4)

    # WINS (middle box left area)
    mid_label_pos = (bmid[0] + 18, bmid[1] + 10)
    mid_num_pos   = (bmid[0] + 18, bmid[1] + 48)
    draw_outline_text(draw, mid_label_pos, "WINS", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)
    draw_outline_text(draw, mid_num_pos, str(wins), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=4)

    # RITUALS (right-most small area inside the mid box: we'll position near right)
    # We try to place at rightmost region of the mid box (visual match)
    rit_label_x = bmid[0] + int((bmid[2]-bmid[0])*0.70)
    rit_label_pos = (rit_label_x, bmid[1] + 10)
    rit_num_pos = (rit_label_x, bmid[1] + 48)
    draw_outline_text(draw, rit_label_pos, "RITUALS", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)
    draw_outline_text(draw, rit_num_pos, str(rituals), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=4)

    # Small left stats inside center region (FIGHTS / WINS text block)
    stat_x = center[0] + 18
    stat_y = center[1] + 18
    draw_outline_text(draw, (stat_x, stat_y), "FIGHTS / WINS", SMALL_FONT, fill=(30,30,30), outline=(255,255,255), stroke=2)
    draw_outline_text(draw, (stat_x, stat_y + 30), f"{fights} / {wins}", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=2)

    # Footer TG and CA one under another (centered inside footer box)
    if tg:
        ft1 = f"TG: {tg}"
        fx = _centered_x(draw, ft1, FOOTER_FONT, footer[0]+8, footer[2]-8)
        fy = footer[1] + 8
        draw.text((fx, fy), ft1, font=FOOTER_FONT, fill=(18,18,18))
    if ca:
        ft2 = f"CA: {ca}"
        fx2 = _centered_x(draw, ft2, FOOTER_FONT, footer[0]+8, footer[2]-8)
        fy2 = footer[1] + 28
        draw.text((fx2, fy2), ft2, font=FOOTER_FONT, fill=(18,18,18))

    out = f"/tmp/profile_{uid}.png"
    card.save(out)
    return out

# -------------------------
# Leaderboard generator
# -------------------------
def generate_leaderboard_image() -> str:
    """
    Compose top-5 leaderboard image using leaderboard base template.
    Pulls data from bot.db.get_top_users() if available, else falls back to sample rows.
    """
    # lazy import to avoid circular imports in package startup
    try:
        from bot.db import get_top_users
        rows = get_top_users(limit=5)
    except Exception:
        # fallback placeholder data
        rows = [
            {"user_id": 1001, "username": "ExampleName1", "xp_total": 3450, "mobs_defeated": 70, "wins": 50, "form": "Hopper"},
            {"user_id": 1002, "username": "ExampleName2", "xp_total": 3020, "mobs_defeated": 65, "wins": 45, "form": "Hopper"},
            {"user_id": 1003, "username": "ExampleName3", "xp_total": 2800, "mobs_defeated": 60, "wins": 40, "form": "Tadpole"},
            {"user_id": 1004, "username": "ExampleName4", "xp_total": 2550, "mobs_defeated": 55, "wins": 35, "form": "Tadpole"},
            {"user_id": 1005, "username": "ExampleName5", "xp_total": 2400, "mobs_defeated": 50, "wins": 30, "form": "Tadpole"},
        ]

    base_path = _asset_path(LEADERBOARD_BASE)
    if base_path:
        img = Image.open(base_path).convert("RGBA")
    else:
        # create fallback
        img = Image.new("RGBA", (1000,1600), (22,18,40,255))

    W,H = img.size
    draw = ImageDraw.Draw(img)

    # Title (center-top)
    title = "TOP 5 LEADERBOARD"
    tx = _centered_x(draw, title, TITLE_FONT, 40, W-40)
    draw_outline_text(draw, (tx, 20), title, TITLE_FONT, fill=(255,200,60), outline=(10,10,40), stroke=6)

    # rows area (we assume 5 equal rows)
    rows_top = int(H * 0.20)
    rows_left = int(W * 0.06)
    rows_right = int(W * 0.94)
    row_h = int((H - rows_top - 60)/5)

    for i, r in enumerate(rows):
        y = rows_top + i*row_h
        rank = i+1

        # rank number region (we'll center number where base circle is expected)
        rank_circle_x = rows_left + 10
        rank_circle_w = int(row_h * 0.6)
        # compute number placement
        num_text = str(rank)
        try:
            bbox = draw.textbbox((0,0), num_text, font=BIG_NUM_FONT)
            tw = bbox[2]-bbox[0]; th = bbox[3]-bbox[1]
        except Exception:
            tw,th = draw.textsize(num_text, font=BIG_NUM_FONT)
        num_x = rank_circle_x + (rank_circle_w - tw)//2
        num_y = y + (row_h - th)//2
        draw.text((num_x, num_y), num_text, font=BIG_NUM_FONT, fill=(10,10,10))

        # sprite paste (to the right of rank circle)
        sprite = load_form_image(r.get("form","Tadpole"))
        if sprite:
            sp_w = int(rank_circle_w * 0.85)
            asp = sprite.height / sprite.width
            sp_h = int(sp_w * asp)
            sp = sprite.resize((sp_w, sp_h), resample=Image.LANCZOS)
            sp_x = rank_circle_x + rank_circle_w + 18
            sp_y = y + (row_h - sp_h)//2
            img.paste(sp, (sp_x, sp_y), sp)

        # text block to the right of sprite
        text_block_x = rank_circle_x + rank_circle_w + 18 + (rank_circle_w)
        name_y = y + int(row_h * 0.18)
        name = r.get("username", f"User{r.get('user_id', rank)}")
        draw_outline_text(draw, (text_block_x, name_y), name, USERNAME_FONT, fill=(10,10,10), outline=(255,255,255), stroke=3)

        # second line: XP + FIGHTS / WINS
        line2_y = name_y + 50
        xp = r.get("xp_total", r.get("xp", 0))
        fights = r.get("mobs_defeated", r.get("fights", 0))
        wins = r.get("wins", 0)
        line2 = f"XP: {xp}   FIGHTS / WINS: {fights} / {wins}"
        draw.text((text_block_x, line2_y), line2, font=LABEL_FONT, fill=(10,10,10))

    out = "/tmp/leaderboard.png"
    img.save(out)
    return out

# -------------------------
# If module run, create demo previews
# -------------------------
if __name__ == "__main__":
    demo = {
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
    print("Writing /tmp/profile_demo.png")
    print(generate_profile_image(demo))
    print("Writing /tmp/leaderboard_demo.png")
    print(generate_leaderboard_image())
