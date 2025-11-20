import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from bot.db import get_top_users

ASSET_DIR = "assets"

# ----------------------------
# GLOBAL FONTS
# ----------------------------
def load_font(size):
    """Load TTF from assets or fall back to default."""
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "Roboto-Bold.ttf"), size)
    except:
        return ImageFont.load_default()

DEFAULT_FONT = load_font(28)
SMALL_FONT = load_font(22)


# ----------------------------
# Comic-style outline text
# ----------------------------
def outline_text(draw, pos, text, font, fill, outline="black", stroke=3, anchor=None):
    draw.text(
        pos,
        text,
        font=font,
        fill=fill,
        stroke_width=stroke,
        stroke_fill=outline,
        anchor=anchor,
    )


# ----------------------------
# Load Grok form image
# ----------------------------
def load_form_image(form_name):
    form_map = {
        "Tadpole": "tadpole.png",
        "Hopper": "hopper.png",
        "Ascended Hopper": "ascended.png",
        "Ascended": "ascended.png",
    }

    filename = form_map.get(form_name, "tadpole.png")
    path = os.path.join(ASSET_DIR, filename)

    if not os.path.exists(path):
        return None

    return Image.open(path).convert("RGBA")


# ----------------------------
# Profile Image Generator
# ----------------------------
def generate_profile_image(user):
    """
    user = {
      "user_id": ...,
      "level": ...,
      "xp": ...,
      "form": ...
    }
    """

    user_id = user["user_id"]
    level = user["level"]
    xp = user["xp"]
    form = user["form"]

    width, height = 600, 350
    img = Image.new("RGBA", (width, height), (20, 20, 25))
    draw = ImageDraw.Draw(img)

    # Background nebula (optional)
    nebula_path = os.path.join(ASSET_DIR, "nebula_bg.png")
    if os.path.exists(nebula_path):
        nebula = Image.open(nebula_path).convert("RGBA").resize((width, height))
        img = Image.alpha_composite(img, nebula)

    # XP math
    xp_current = xp
    xp_next = level * 200
    pct = min(max(xp_current / xp_next, 0), 1)
    progress_bar_width = int(350 * pct)
