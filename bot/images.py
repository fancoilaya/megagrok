import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from bot.db import get_top_users

ASSET_DIR = "assets"

# ---------------------------------------------------
# FONT LOADING
# ---------------------------------------------------
def load_font(size):
    """Load Roboto font or fallback."""
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "Roboto-Bold.ttf"), size)
    except:
        return ImageFont.load_default()

DEFAULT_FONT = load_font(28)


# ---------------------------------------------------
# OUTLINE TEXT UTILITY
# ---------------------------------------------------
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


# ---------------------------------------------------
# GROK FORM IMAGE LOADER
# ---------------------------------------------------
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


# ---------------------------------------------------
# PROFILE IMAGE GENERATOR
# ---------------------------------------------------
def generate_profile_image(user):
    """
    user = {
        'user_id': ...,
        'level': ...,
        'xp': ...,
        'form': ...
    }
    """
    user_id = user["user_id"]
    level = user["level"]
    xp = user["xp"]
    form = user["form"]

    width, height = 600, 350
    img = Image.new("RGBA", (width, height), (20, 20, 25))
    draw = ImageDraw.Draw(img)

    # Optional background
    nebula = os.path.join(ASSET_DIR, "nebula_bg.png")
    if os.path.exists(nebula):
        nebula_img = Image.open(nebula).convert("RGBA").resize((width, height))
        img = Image.alpha_composite(img, nebula_img)

    # XP math
    xp_next = level * 200
    pct = min(max(xp / xp_next, 0), 1)
    progress_width = int(350 * pct)

    # Title
    outline_text(draw, (20, 20), "MEGAGROK PROFILE", load_font(40),
                 fill="white", outline="black", stroke=4)

    # Stats text
    draw.text((20, 100), f"User: {user_id}", font=DEFAULT_FONT, fill="white")
    draw.text((20, 140), f"Level: {level}", font=DEFAULT_FONT, fill="white")
    draw.text((20, 180), f"Form: {form}", font=DEFAULT_FONT, fill="white")
    draw.text((20, 220), f"XP: {xp}/{xp_next}", font=DEFAULT_FONT, fill="white")

    # XP bar
    draw.rectangle([20, 260, 370, 290], fill="#444444")
    draw.rectangle([20, 260, 20 + progress_width, 290], fill="#00FF66")

    # Grok sprite
    sprite = load_form_image(form)
    if sprite:
        sprite = sprite.resize((180, 180))
        img.paste(sprite, (400, 140), sprite)

    # Save
    out_path = f"/tmp/profile_{user_id}.png"
    img.save(out_path)
    return out_path


# ---------------------------------------------------
# LEADERBOARD IMAGE GENERATOR
# ---------------------------------------------------
def generate_leaderboard_image():
    """Generate top 10 leaderboard comic-style panel."""
    rows = get_top_users()

    width = 1000
    height = 180 + len(rows) * 140
    bg = Image.new("RGBA", (width, height), (10, 5, 20))

    draw = ImageDraw.Draw(bg)

    # Background
    nebula_path = os.path.join(ASSET_DIR, "nebula_bg.png")
    if os.path.exists(nebula_path):
        nebula = Image.open(nebula_path).convert("RGBA").resize((width, height))
        bg = Image.alpha_composite(bg, nebula)

    # Title
    outline_text(
        draw,
        (width // 2, 80),
        "MEGAGROK HOP-FAME",
        load_font(70),
        fill=(255, 230, 120),
        outline="purple",
        stroke=6,
        anchor="mm"
    )

    # Icons
    icon_crown = os.path.join(ASSET_DIR, "icon_crown.png")
    icon_xp = os.path.join(ASSET_DIR, "icon_xp.png")
    icon_comic = os.path.join(ASSET_DIR, "icon_comic.png")

    y = 180

    for i, user in enumerate(rows):
        rank = i + 1

        # Top 3 glow
        if rank <= 3:
            glow = Image.new("RGBA", (width, 140), (255, 220, 50, 60))
            glow = glow.filter(ImageFilter.GaussianBlur(16))
            bg.paste(glow, (0, y - 20), glow)

        # Box
        draw.rectangle([(40, y), (width - 40, y + 120)],
                       fill=(255, 255, 255, 20),
                       outline=(255, 255, 255, 40), width=2)

        # Rank
        outline_text(draw, (70, y + 35), f"#{rank}", load_font(48),
                     fill=(255, 255, 180), outline="black", stroke=4)

        # Crown
        if rank == 1 and os.path.exists(icon_crown):
            crown = Image.open(icon_crown).convert("RGBA").resize((70, 70))
            bg.paste(crown, (140, y - 10), crown)

        # Grok portrait
        sprite = load_form_image(user["form"])
        if sprite:
            sprite = sprite.resize((110, 110))
            bg.paste(sprite, (220, y + 5), sprite)

        # Username
        outline_text(draw, (360, y + 20), f"User {user['user_id']}",
                     load_font(34), fill=(180, 220, 255),
                     outline="black", stroke=3)

        # XP bar
        xp_text = f"Lvl {user['level']} | {user['xp']} XP"
        if os.path.exists(icon_xp):
            xp_ic = Image.open(icon_xp).convert("RGBA").resize((35, 35))
            bg.paste(xp_ic, (360, y + 65), xp_ic)

        outline_text(draw, (410, y + 65), xp_text,
                     load_font(28), fill="white",
                     outline="black", stroke=3)

        # Comic FX
        if rank <= 3 and os.path.exists(icon_comic):
            bubble = Image.open(icon_comic).convert("RGBA").resize((90, 90))
            bg.paste(bubble, (width - 160, y + 15), bubble)

        y += 140

    out_path = "/tmp/leaderboard.png"
    bg.save(out_path)
    return out_path
