import os
from PIL import Image, ImageDraw, ImageFont

ASSET_DIR = "assets"

# -----------------------------
# Load fonts
# -----------------------------
def load_font(size):
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "Roboto-Black.ttf"), size)
    except:
        return ImageFont.load_default()

FONT_HUGE = load_font(82)        # MEGAGROK
FONT_LARGE = load_font(56)       # Username
FONT_STAT = load_font(48)        # LEVEL, FIGHTS/WINS, RITUALS
FONT_STAT_NUM = load_font(72)    # Stat numbers
FONT_FOOTER = load_font(32)      # TG + CA

# -----------------------------
# Outline text helper
# -----------------------------
def draw_outline(draw, pos, text, font, fill, outline="black", stroke=5, anchor=None):
    draw.text(
        pos,
        text,
        font=font,
        fill=fill,
        stroke_width=stroke,
        stroke_fill=outline,
        anchor=anchor
    )

# -----------------------------
# Load evolution PNG
# -----------------------------
def load_grok_sprite(form):
    filename = {
        "Tadpole": "tadpole.png",
        "Hopper": "hopper.png",
        "Ascended": "ascended.png"
    }.get(form, "tadpole.png")

    path = os.path.join(ASSET_DIR, filename)
    if not os.path.exists(path):
        return None
    return Image.open(path).convert("RGBA")


# -----------------------------
# Generate Profile Image
# -----------------------------
def generate_profile_image(user):
    """
    user keys required:
      username, level, form, fights, wins, rituals
    """

    username = user.get("username", "Unknown")
    form = user.get("form", "Tadpole")
    level = user.get("level", 1)
    fights = user.get("fights", 0)
    wins = user.get("wins", 0)
    rituals = user.get("rituals", 0)

    TG_TEXT = "TG: t.me/megagrok"
    CA_TEXT = "CA: FZL2K9TBybDh32KFJWQbMttQ71PExyNXir9+652pump"

    # Load base card
    base_path = "/mnt/data/profile_base.png"   # ← your uploaded template
    card = Image.open(base_path).convert("RGBA")
    draw = ImageDraw.Draw(card)

    W, H = card.size

    # -----------------------------
    # HEADER TEXT
    # -----------------------------
    draw_outline(draw,
        (W // 2, 125),
        "MEGAGROK",
        FONT_HUGE,
        fill=(0, 0, 0),
        stroke=6,
        anchor="mm"
    )

    draw_outline(draw,
        (W // 2, 200),
        username.upper(),
        FONT_LARGE,
        fill=(0, 0, 0),
        stroke=5,
        anchor="mm"
    )

    # -----------------------------
    # Evolution Sprite
    # -----------------------------
    sprite = load_grok_sprite(form)
    if sprite:
        sprite = sprite.resize((520, 520), Image.LANCZOS)
        sx = W // 2 - sprite.width // 2
        sy = 260
        card.paste(sprite, (sx, sy), sprite)

    # -----------------------------
    # STAT BOXES
    # -----------------------------
    # Box positions from your template
    box_y = 820
    box_h = 200

    left_box = (60, box_y, 60 + 260, box_y + box_h)
    mid_box = (340, box_y, 340 + 520, box_y + box_h)
    right_box = (880, box_y, 880 + 260, box_y + box_h)

    # LEVEL box
    draw_outline(draw, (left_box[0] + 130, box_y + 50), "LEVEL", FONT_STAT,
                 fill=(0,0,0), stroke=4, anchor="mm")
    draw_outline(draw, (left_box[0] + 130, box_y + 135), str(level), FONT_STAT_NUM,
                 fill=(0,0,0), stroke=4, anchor="mm")

    # FIGHTS / WINS
    draw_outline(draw, (mid_box[0] + 260, box_y + 50), "FIGHTS / WINS", FONT_STAT,
                 fill=(0,0,0), stroke=4, anchor="mm")
    draw_outline(draw, (mid_box[0] + 260, box_y + 135), f"{fights} / {wins}", FONT_STAT_NUM,
                 fill=(0,0,0), stroke=4, anchor="mm")

    # RITUALS
    draw_outline(draw, (right_box[0] + 130, box_y + 50), "RITUALS", FONT_STAT,
                 fill=(0,0,0), stroke=4, anchor="mm")
    draw_outline(draw, (right_box[0] + 130, box_y + 135), str(rituals), FONT_STAT_NUM,
                 fill=(0,0,0), stroke=4, anchor="mm")

    # -----------------------------
    # FOOTER (TG + CA)
    # -----------------------------
    footer_box = (60, 1060, W - 60, 1220)

    draw_outline(draw, (W // 2, footer_box[1] + 45), TG_TEXT, FONT_FOOTER,
                 fill=(0, 0, 0), stroke=3, anchor="mm")

    draw_outline(draw, (W // 2, footer_box[1] + 110), CA_TEXT, FONT_FOOTER,
                 fill=(0, 0, 0), stroke=3, anchor="mm")

    # Save
    out = f"/tmp/profile_{username}.png"
    card.save(out)
    return out
