import os
from PIL import Image, ImageDraw, ImageFont

ASSET_DIR = "assets"
PROFILE_BASE = "profile_base.png"
LEADERBOARD_BASE = "leaderboard_base.png"

# Load fonts
def load_font(name, size):
    path1 = os.path.join(ASSET_DIR, name)
    path2 = os.path.join("/mnt/data", name)

    if os.path.exists(path1):
        return ImageFont.truetype(path1, size)
    if os.path.exists(path2):
        return ImageFont.truetype(path2, size)
    return ImageFont.load_default()

TITLE_FONT     = load_font("Roboto-Bold.ttf", 76)
USERNAME_FONT  = load_font("Roboto-Bold.ttf", 52)
LABEL_FONT     = load_font("Roboto-Regular.ttf", 36)
NUMBER_FONT    = load_font("Roboto-Bold.ttf", 64)
SMALL_FONT     = load_font("Roboto-Regular.ttf", 32)
FOOTER_FONT    = load_font("Roboto-Light.ttf", 26)

# ---------------------------------------
# LOAD SPRITE BY FORM
# ---------------------------------------
def load_sprite(form):
    fname_map = {
        "Tadpole": "tadpole.png",
        "Hopper": "hopper.png",
        "Ascended": "ascended.png"
    }
    fname = fname_map.get(form, "tadpole.png")
    path = os.path.join(ASSET_DIR, fname)
    if not os.path.exists(path):
        return None
    return Image.open(path).convert("RGBA")

# ---------------------------------------
# DRAW CENTERED TEXT
# ---------------------------------------
def centered(draw, box, text, font, fill=(0,0,0)):
    x1, y1, x2, y2 = box
    w = x2 - x1
    try:
        tw, th = draw.textbbox((0,0), text, font=font)[2:]
    except:
        tw, th = draw.textsize(text, font=font)
    return (x1 + (w - tw)//2, y1, text, font, fill)

# ---------------------------------------
# PROFILE GENERATOR
# ---------------------------------------
def generate_profile_image(user):

    uid = user.get("user_id")
    username = user.get("username", f"User{uid}")
    form = user.get("form", "Tadpole")
    level = user.get("level", 1)
    wins = user.get("wins", 0)
    rituals = user.get("rituals", 0)
    fights = user.get("fights", user.get("mobs_defeated", 0))

    tg = user.get("tg", "")
    ca = user.get("ca", "")

    # Load template
    base_path = os.path.join(ASSET_DIR, PROFILE_BASE)
    card = Image.open(base_path).convert("RGBA")
    draw = ImageDraw.Draw(card)

    W, H = card.size

    # ---------------------------------------
    # A) MEGAGROK centered in yellow bar
    # ---------------------------------------
    title_box = (0, 40, W, 140)
    tx, ty, text, font, fill = centered(draw, title_box, "MEGAGROK", TITLE_FONT)
    draw.text((tx, ty), text, font=font, fill=(0,0,0))

    # ---------------------------------------
    # B) Username centered under MEGAGROK
    # ---------------------------------------
    username_box = (0, 150, W, 220)
    ux, uy, text, font, fill = centered(draw, username_box, username, USERNAME_FONT)
    draw.text((ux, uy), text, font=font, fill=(20,20,20))

    # ---------------------------------------
    # C) Sprite placed in the center frame
    # (Auto-detect box from template coordinates)
    # ---------------------------------------
    center_box = (140, 240, 760, 820)  # ← fixed from your template
    sprite = load_sprite(form)

    if sprite:
        max_w = center_box[2] - center_box[0]
        max_h = center_box[3] - center_box[1]

        # Scale sprite to 75% of center box
        scale_w = int(max_w * 0.75)
        aspect = sprite.height / sprite.width
        scale_h = int(scale_w * aspect)
        sprite = sprite.resize((scale_w, scale_h), Image.LANCZOS)

        sx = center_box[0] + (max_w - scale_w)//2
        sy = center_box[1] + (max_h - scale_h)//2

        card.paste(sprite, (sx, sy), sprite)

    # ---------------------------------------
    # D) Fights/Wins block inside left big center box
    # ---------------------------------------
    stats_x = center_box[0] + 10
    stats_y = center_box[1] + 20

    draw.text((stats_x, stats_y), "FIGHTS / WINS", font=SMALL_FONT, fill=(20,20,20))
    draw.text((stats_x, stats_y + 40), f"{fights} / {wins}", font=LABEL_FONT, fill=(20,20,20))

    # ---------------------------------------
    # E) Bottom boxes — level / wins / rituals
    # bottom boxes taken from template coordinates
    # ---------------------------------------
    # Level box
    lvl_box = (140, 860, 300, 990)
    draw.text((lvl_box[0]+20, lvl_box[1]+10), "LEVEL", font=LABEL_FONT, fill=(0,0,0))
    draw.text((lvl_box[0]+20, lvl_box[1]+60), str(level), font=NUMBER_FONT, fill=(0,0,0))

    # Wins box
    wins_box = (320, 860, 580, 990)
    draw.text((wins_box[0]+20, wins_box[1]+10), "WINS", font=LABEL_FONT, fill=(0,0,0))
    draw.text((wins_box[0]+20, wins_box[1]+60), str(wins), font=NUMBER_FONT, fill=(0,0,0))

    # Rituals box
    rit_box = (600, 860, 760, 990)
    draw.text((rit_box[0]+20, rit_box[1]+10), "RITUALS", font=LABEL_FONT, fill=(0,0,0))
    draw.text((rit_box[0]+20, rit_box[1]+60), str(rituals), font=NUMBER_FONT, fill=(0,0,0))

    # ---------------------------------------
    # F) Footer TG + CA centered
    # ---------------------------------------
    footer_box = (0, 1020, W, 1150)

    if tg:
        fx, fy, text, font, fill = centered(draw, footer_box, f"TG: {tg}", FOOTER_FONT)
        draw.text((fx, fy), text, font=font, fill=(10,10,10))

    if ca:
        fx2, fy2, text2, font2, fill2 = centered(draw, footer_box, f"CA: {ca}", FOOTER_FONT)
        draw.text((fx2, fy2+34), text2, font=font2, fill=(10,10,10))

    out = f"/tmp/profile_{uid}.png"
    card.save(out)
    return out



# ================================================================
#                    LEADERBOARD GENERATOR
# ================================================================
def generate_leaderboard_image():
    try:
        from bot.db import get_top_users
        rows = get_top_users(5)
    except:
        rows = []

    base = _load_img(LEADERBOARD_BASE)
    if base is None:
        return None

    W, H = base.size
    draw = ImageDraw.Draw(base)

    # --------------------
    # HEADER
    # --------------------
    title = "TOP 5 LEADERBOARD"
    tw = draw.textlength(title, font=FONT_TITLE)
    draw.text(((W - tw) / 2, 45), title, font=FONT_TITLE, fill=(0, 0, 0))

    # --------------------
    # ROW COORDINATES
    # --------------------
    ROW_TOP_START = 230
    ROW_HEIGHT = 210

    for i, r in enumerate(rows):
        y = ROW_TOP_START + i * ROW_HEIGHT

        # Rank number (large number inside circle)
        rank = str(i + 1)
        draw.text((100, y + 50), rank, font=FONT_VALUE, fill=(0, 0, 0))

        # Sprite
        sprite = _load_img(FORM_SPRITES.get(r.get("form", "Tadpole"), TADPOLE))
        if sprite:
            sp = sprite.resize((160, 160), Image.LANCZOS)
            base.paste(sp, (200, y + 10), sp)

        # Username
        name = r.get("username", f"User{r['user_id']}")
        draw.text((390, y + 35), name, font=FONT_ROW_NAME, fill=(0, 0, 0))

        # Stats line:
        xp = r.get("xp_total", 0)
        fights = r.get("mobs_defeated", r.get("fights", 0))
        wins = r.get("wins", 0)

        stat = f"XP: {xp}     FIGHTS / WINS: {fights} / {wins}"
        draw.text((390, y + 95), stat, font=FONT_ROW_STATS, fill=(0, 0, 0))

    # Output
    out = "/tmp/leaderboard.png"
    base.save(out)
    return out
