"""
images.py — Overlay renderer for MegaGrok profile card and leaderboard.

This script **does not** attempt to redraw the artistic templates.
Instead it:
 - Loads your clean templates from assets/ (profile_base.png & leaderboard_base.png)
 - Pastes the appropriate evolution sprite (tadpole/hopper/ascended)
 - Draws crisp outlined text into the exact areas (username, level, evolution name,
   wins, rituals, TG, CA, XP, fights/wins)
 - Writes output images to /tmp for use by your bot.

USAGE:
 - Put these files in your repo's assets/ folder:
     assets/profile_base.png         # blank profile template (no text, no sprite)
     assets/leaderboard_base.png     # blank leaderboard template (no text, no sprites)
     assets/tadpole.png
     assets/hopper.png
     assets/ascended.png
     assets/Roboto-Bold.ttf          # optional (recommended)
 - Call generate_profile_image(user_dict)
 - Call generate_leaderboard_image(rows_list)

Return values: local filesystem path to generated PNGs.
"""

import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ASSET_DIR = "assets"

# Template filenames (expected)
PROFILE_TEMPLATE = os.path.join(ASSET_DIR, "profile_base.png")
LEADERBOARD_TEMPLATE = os.path.join(ASSET_DIR, "leaderboard_base.png")

FORM_SPRITES = {
    "Tadpole": os.path.join(ASSET_DIR, "tadpole.png"),
    "Hopper": os.path.join(ASSET_DIR, "hopper.png"),
    "Ascended": os.path.join(ASSET_DIR, "ascended.png"),
}
# Fallback sprite
DEFAULT_SPRITE = os.path.join(ASSET_DIR, "tadpole.png")

# Default project text (can be overridden by code when calling functions)
PROJECT_TG = "t.me/megagrok"
PROJECT_CA = "FZL2K9TBybDh32KfJWQBhMtQ71PExyNXiry8Y5e2pump"

# -------------------------
# Font helpers
# -------------------------
def _load_font(name_or_size, size=None):
    """
    Robust font loader.
    - _load_font(28) -> load default size
    - _load_font("Roboto-Bold.ttf", 32) -> load specific file from ASSET_DIR
    Falls back to ImageFont.load_default() if truetype fails.
    """
    try:
        if size is None and isinstance(name_or_size, int):
            size = name_or_size
            font_path = os.path.join(ASSET_DIR, "Roboto-Bold.ttf")
        elif size is None and isinstance(name_or_size, str):
            # only name provided (use default size)
            font_path = os.path.join(ASSET_DIR, name_or_size)
            size = 24
        else:
            font_path = os.path.join(ASSET_DIR, name_or_size)

        # try provided path first
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
        # fallback to Roboto if available
        roboto = os.path.join(ASSET_DIR, "Roboto-Bold.ttf")
        if os.path.exists(roboto):
            return ImageFont.truetype(roboto, size)
    except Exception:
        pass
    return ImageFont.load_default()

TITLE_FONT = _load_font(56)
SUBTITLE_FONT = _load_font(36)
LABEL_FONT = _load_font(22)
BIG_NUM_FONT = _load_font(64)
BODY_FONT = _load_font(26)
SMALL_FONT = _load_font(18)

# -------------------------
# Text outline helper (works across pillow versions)
# -------------------------
def outline_text(draw: ImageDraw.ImageDraw, pos, text, font, fill=(255,255,255), outline=(0,0,0), stroke=3, anchor=None):
    """
    Draw text with outline. Uses stroke parameters if available,
    otherwise draws a manual 8-direction outline.
    """
    try:
        draw.text(pos, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=outline, anchor=anchor)
    except TypeError:
        # fallback manual outline
        x, y = pos
        offsets = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
        for ox, oy in offsets:
            draw.text((x+ox, y+oy), text, font=font, fill=outline, anchor=anchor)
        draw.text(pos, text, font=font, fill=fill, anchor=anchor)

# -------------------------
# Sprite loader
# -------------------------
def load_sprite_for_form(form_name: str):
    path = FORM_SPRITES.get(form_name, DEFAULT_SPRITE)
    if os.path.exists(path):
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            return None
    # fallback
    if os.path.exists(DEFAULT_SPRITE):
        try:
            return Image.open(DEFAULT_SPRITE).convert("RGBA")
        except Exception:
            return None
    return None

# -------------------------
# Profile card renderer
# -------------------------
def generate_profile_image(user: dict) -> str:
    """
    Render a profile card image by overlaying data on top of profile_base.png.

    Expected user dict keys:
      - user_id (int/str) (used for filename)
      - username (str) => displayed at top center (without '@' is fine)
      - level (int)
      - form (str) => Tadpole / Hopper / Ascended (decides sprite)
      - xp_total (int) optional
      - wins (int)
      - rituals (int)
      - tg (str) optional override for TG line (defaults to PROJECT_TG)
      - ca (str) optional override for CA line (defaults to PROJECT_CA)

    Returns: path to generated file (e.g. /tmp/profile_<user>.png)
    """
    if not os.path.exists(PROFILE_TEMPLATE):
        raise FileNotFoundError(f"profile template not found: {PROFILE_TEMPLATE}")

    # safe reads
    username = user.get("username") or user.get("display_name") or f"user{user.get('user_id','')}"
    level = int(user.get("level", 1))
    form = user.get("form", "Tadpole")
    xp_total = int(user.get("xp_total", 0))
    wins = int(user.get("wins", 0))
    rituals = int(user.get("rituals", 0))
    tg_line = user.get("tg", PROJECT_TG)
    ca_line = user.get("ca", PROJECT_CA)

    # load template
    base = Image.open(PROFILE_TEMPLATE).convert("RGBA")
    W, H = base.size
    canvas = base.copy()
    draw = ImageDraw.Draw(canvas)

    # --- compute relative positions using template proportions ---
    # Title area: center username in top yellow bar (we assume left/right padding)
    title_bar_y = int(H * 0.065)  # approximate y center for the username band
    # We'll measure text width and center horizontally
    outline_text(draw, (W//2, int(H * 0.08)), username, SUBTITLE_FONT,
                 fill=(20,20,20), outline=(255,255,255), stroke=3, anchor="ma")

    # Portrait area (center): place sprite centered in the big portrait box.
    # We estimate portrait box as a centered square occupying about 60% of height between 15% and 72% of H.
    portrait_top = int(H * 0.12)
    portrait_bottom = int(H * 0.72)
    portrait_h = portrait_bottom - portrait_top
    portrait_w = int(W * 0.86)  # leave small horizontal margins
    portrait_left = int((W - portrait_w) / 2)

    sprite = load_sprite_for_form(form)
    if sprite:
        # Resize sprite to fit portrait area (keep aspect, target ~65% of portrait height)
        target_h = int(portrait_h * 0.65)
        sw, sh = sprite.size
        ar = sw / float(sh)
        new_h = target_h
        new_w = int(ar * new_h)
        # if new_w > portrait_w, clamp by width
        if new_w > portrait_w:
            new_w = portrait_w
            new_h = int(new_w / ar)
        sprite_resized = sprite.resize((new_w, new_h), Image.LANCZOS)
        sx = portrait_left + (portrait_w - new_w)//2
        sy = portrait_top + (portrait_h - new_h)//2
        # optional small halo
        halo = sprite_resized.copy().filter(ImageFilter.GaussianBlur(radius=18))
        halo_tint = Image.new("RGBA", halo.size, (40,200,160,60))
        halo = Image.alpha_composite(halo, halo_tint)
        canvas.paste(halo, (sx-6, sy-6), halo)
        canvas.paste(sprite_resized, (sx, sy), sprite_resized)

    # --- Stat boxes area at the bottom ---
    # We'll divide the reserved bottom area (from portrait_bottom to footer_top) in 3 boxes.
    bottom_top = int(H * 0.73)
    bottom_margin_lr = int(W * 0.06)
    total_w = W - 2*bottom_margin_lr
    spacing = int(W * 0.02)
    box_w = int((total_w - spacing*2) / 3)
    box_h = int(H * 0.13)
    bx0 = bottom_margin_lr
    by0 = bottom_top

    # LEVEL box (left)
    lvl_box = (bx0, by0, bx0 + box_w, by0 + box_h)
    # Wins box (center)
    wins_box = (bx0 + box_w + spacing, by0, bx0 + 2*box_w + spacing, by0 + box_h)
    # Rituals box (right)
    rituals_box = (bx0 + 2*(box_w + spacing), by0, bx0 + 3*box_w + 2*spacing, by0 + box_h)

    # Draw content (we assume base template contains frames; we only place text)
    # LEVEL label + big number + evolution name below
    outline_text(draw, (lvl_box[0] + 16, lvl_box[1] + 10), "LEVEL", LABEL_FONT,
                 fill=(20,20,20), outline=(255,255,255), stroke=2, anchor="lm")
    # big number centered in box
    try:
        tb = draw.textbbox((0,0), str(level), font=BIG_NUM_FONT)
        wnum = tb[2]-tb[0]
        hnum = tb[3]-tb[1]
    except Exception:
        wnum, hnum = BIG_NUM_FONT.getsize(str(level))
    nx = lvl_box[0] + (box_w - wnum)/2
    ny = lvl_box[1] + (box_h - hnum)/2 - 8
    outline_text(draw, (nx, ny), str(level), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)

    # evolution name under number
    ev_txt = str(form)
    outline_text(draw, (lvl_box[0] + box_w/2, lvl_box[1] + box_h - 28), ev_txt, LABEL_FONT,
                 fill=(20,20,20), outline=(255,255,255), stroke=2, anchor="ma")

    # WINS box
    outline_text(draw, (wins_box[0] + 16, wins_box[1] + 10), "WINS", LABEL_FONT,
                 fill=(20,20,20), outline=(255,255,255), stroke=2, anchor="lm")
    try:
        tb = draw.textbbox((0,0), str(wins), font=BIG_NUM_FONT)
        wnum = tb[2]-tb[0]
        hnum = tb[3]-tb[1]
    except Exception:
        wnum, hnum = BIG_NUM_FONT.getsize(str(wins))
    nx = wins_box[0] + (box_w - wnum)/2
    ny = wins_box[1] + (box_h - hnum)/2 - 8
    outline_text(draw, (nx, ny), str(wins), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)

    # RITUALS box
    outline_text(draw, (rituals_box[0] + 16, rituals_box[1] + 10), "RITUALS", LABEL_FONT,
                 fill=(20,20,20), outline=(255,255,255), stroke=2, anchor="lm")
    try:
        tb = draw.textbbox((0,0), str(rituals), font=BIG_NUM_FONT)
        wnum = tb[2]-tb[0]
        hnum = tb[3]-tb[1]
    except Exception:
        wnum, hnum = BIG_NUM_FONT.getsize(str(rituals))
    nx = rituals_box[0] + (box_w - wnum)/2
    ny = rituals_box[1] + (box_h - hnum)/2 - 8
    outline_text(draw, (nx, ny), str(rituals), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)

    # Footer strip: TG left, CA right (we keep them optional/empty if not provided)
    footer_h = int(H * 0.08)
    footer_y = int(H - footer_h - 16)
    # left padding
    padding = int(W * 0.06)
    outline_text(draw, (padding, footer_y + 12), f"TG: {tg_line}", SMALL_FONT,
                 fill=(20,20,20), outline=(255,255,255), stroke=1, anchor="lm")
    # CA right-aligned
    ca_txt = f"CA: {ca_line}"
    try:
        cb = draw.textbbox((0,0), ca_txt, font=SMALL_FONT)
        cw = cb[2] - cb[0]
    except Exception:
        cw, _ = SMALL_FONT.getsize(ca_txt)
    outline_text(draw, (W - padding - cw, footer_y + 12), ca_txt, SMALL_FONT,
                 fill=(20,20,20), outline=(255,255,255), stroke=1, anchor="lm")

    # Save result
    safe_name = str(username).replace("@", "").replace(" ", "_")
    out_path = f"/tmp/profile_{safe_name}.png"
    canvas.convert("RGBA").save(out_path)
    return out_path

# -------------------------
# Leaderboard renderer (top 5)
# -------------------------
def generate_leaderboard_image(rows: list = None, tg: str = None, ca: str = None) -> str:
    """
    Render leaderboard by overlaying rows onto leaderboard_base.png.

    rows: list of dicts (length >= 5 recommended). Each dict:
      - rank (1..5)
      - username (str)
      - xp (int)
      - fights (int)
      - wins (int)
      - form (optional)
    If rows is None, a sample placeholder list will be used.

    Returns path to generated leaderboard (/tmp/leaderboard.png)
    """
    if not os.path.exists(LEADERBOARD_TEMPLATE):
        raise FileNotFoundError(f"leaderboard template not found: {LEADERBOARD_TEMPLATE}")

    if rows is None:
        rows = [
            {"rank":1, "username":"FrogKing",   "xp":3450, "fights":70, "wins":50, "form":"Ascended"},
            {"rank":2, "username":"HopMaster",  "xp":3020, "fights":65, "wins":45, "form":"Hopper"},
            {"rank":3, "username":"TadpolePro", "xp":2800, "fights":60, "wins":40, "form":"Hopper"},
            {"rank":4, "username":"MemeRibbit", "xp":2550, "fights":55, "wins":35, "form":"Hopper"},
            {"rank":5, "username":"SwampLord",  "xp":2100, "fights":50, "wins":30, "form":"Tadpole"},
        ]

    tg_line = tg or PROJECT_TG
    ca_line = ca or PROJECT_CA

    base = Image.open(LEADERBOARD_TEMPLATE).convert("RGBA")
    W, H = base.size
    canvas = base.copy()
    draw = ImageDraw.Draw(canvas)

    # Title area: replace header text if needed.
    # We'll center the header "TOP 5 LEADERBOARD" in the top bar.
    # Calculate an approximate title Y based on template height
    try:
        outline_text(draw, (W//2, int(H * 0.06)), "TOP 5 LEADERBOARD", TITLE_FONT,
                     fill=(236,170,53), outline=(5,5,5), stroke=5, anchor="ma")
    except Exception:
        pass

    # Row area: find a starting Y by scanning for the top-most rows area.
    # We'll assume rows are vertically stacked with uniform row height.
    # Choose conservative layout positions (proportional)
    title_bar_h = int(H * 0.16)
    row_top = title_bar_h + int(H * 0.04)
    row_h = int((H - row_top - int(H * 0.18)) / 5)  # reserve footer area bottom
    left_margin = int(W * 0.05)

    avatar_size = int(row_h * 0.6)
    for i, r in enumerate(rows[:5]):
        rank = int(r.get("rank", i+1))
        username = r.get("username", f"Player{rank}")
        xp = int(r.get("xp", 0))
        fights = int(r.get("fights", 0))
        wins = int(r.get("wins", 0))

        y0 = row_top + i * (row_h + int(H * 0.01))
        y1 = y0 + row_h
        # name position (approx)
        name_x = left_margin + int(W * 0.20) + avatar_size + 20
        name_y = y0 + int(row_h * 0.12)
        outline_text(draw, (name_x, name_y), username, SUBTITLE_FONT,
                     fill=(20,20,20), outline=(255,255,255), stroke=3, anchor="lm")

        # Stats line directly below (use the exact format: "XP: ####  ·  FIGHTS / WINS: FF / WW")
        stats_text = f"XP: {xp}  ·  FIGHTS / WINS: {fights} / {wins}"
        outline_text(draw, (name_x, name_y + 56), stats_text, BODY_FONT,
                     fill=(20,20,20), outline=(255,255,255), stroke=2, anchor="lm")

        # Rank number area: we assume the template kept the circular rank at left; keep it, do not overwrite rank.
        # If you want to draw the rank number (in case the template left area empty), uncomment below:
        # rank_x = left_margin + int(W * 0.05)
        # rank_y = y0 + row_h//2
        # outline_text(draw, (rank_x, rank_y), str(rank), BIG_NUM_FONT, fill=(236,170,53), outline=(5,5,5), stroke=3, anchor="mm")

        # Optionally paste a sprite if desired (we removed frogs from template; uncomment to add)
        # sprite = load_sprite_for_form(r.get("form","Tadpole"))
        # if sprite:
        #     av = sprite.resize((avatar_size, avatar_size), Image.LANCZOS).convert("RGBA")
        #     ax = left_margin + int(W * 0.20)
        #     ay = y0 + (row_h - avatar_size)//2
        #     canvas.paste(av, (ax, ay), av)

    # Footer: TG + CA (left + right)
    footer_y = int(H * 0.92)
    padding = int(W * 0.05)
    outline_text(draw, (padding, footer_y), f"TG: {tg_line}", SMALL_FONT,
                 fill=(20,20,20), outline=(255,255,255), stroke=1, anchor="lm")
    ca_txt = f"CA: {ca_line}"
    try:
        tb = draw.textbbox((0,0), ca_txt, font=SMALL_FONT)
        cw = tb[2] - tb[0]
    except Exception:
        cw, _ = SMALL_FONT.getsize(ca_txt)
    outline_text(draw, (W - padding - cw, footer_y), ca_txt, SMALL_FONT,
                 fill=(20,20,20), outline=(255,255,255), stroke=1, anchor="lm")

    # Save
    out = "/tmp/leaderboard.png"
    canvas.convert("RGBA").save(out)
    return out
