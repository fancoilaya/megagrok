import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from bot.db import get_top_users

ASSET_DIR = "assets"

# ---------------------------------------------------
# FONT LOADING
# ---------------------------------------------------
def load_font(size):
    """Load font from assets or fallback."""
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "Roboto-Bold.ttf"), size)
    except:
        return ImageFont.load_default()

DEFAULT_FONT = load_font(28)


# ---------------------------------------------------
# OUTLINE TEXT
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
# GROK SPRITES
# ---------------------------------------------------
def load_form_image(form_name):
    form_map = {
        "Tadpole": "tadpole.png",
        "Hopper": "hopper.png",
        "Ascended": "ascended.png",
        "Ascended Hopper": "ascended.png",
    }

    filename = form_map.get(form_name, "tadpole.png")
    path = os.path.join(ASSET_DIR, filename)

    if not os.path.exists(path):
        return None

    return Image.open(path).convert("RGBA")


# ---------------------------------------------------
# PROFILE IMAGE (FIXED FOR NEW XP SYSTEM)
# ---------------------------------------------------
def generate_profile_image(user):
    """
    user = {
        user_id,
        xp_total,
        xp_current,
        xp_to_next_level,
        level,
        form
    }
    """

    user_id = user["user_id"]
    level = user["level"]
    xp_current = user["xp_current"]
    xp_next = user["xp_to_next_level"]
    xp_total = user["xp_total"]
    form = user["form"]

    width, height = 600, 350
    img = Image.new("RGBA", (width, height), (20, 20, 30, 255))

    # Nebula background
    nebula_path = os.path.join(ASSET_DIR, "nebula_bg.png")
    if os.path.exists(nebula_path):
        nebula = Image.open(nebula_path).convert("RGBA").resize((width, height))
        img = Image.alpha_composite(img, nebula)

    draw = ImageDraw.Draw(img)

    # XP bar percentage
    pct = min(max(xp_current / xp_next, 0), 1)
    bar_width = int(350 * pct)

    # Title
    outline_text(draw, (20, 20), "MEGAGROK PROFILE", load_font(40),
                 fill="white", outline="black", stroke=4)

    # Stats
    draw.text((20, 100), f"User: {user_id}", font=DEFAULT_FONT, fill="white")
    draw.text((20, 140), f"Level: {level}", font=DEFAULT_FONT, fill="white")
    draw.text((20, 180), f"Form: {form}", font=DEFAULT_FONT, fill="white")

    # XP Text
    draw.text(
        (20, 220),
        f"XP: {xp_current}/{xp_next}   (Total: {xp_total})",
        font=DEFAULT_FONT,
        fill="white"
    )

    # XP Bar background
    draw.rectangle([20, 260, 370, 290], fill="#333333")

    # XP Bar fill
    draw.rectangle([20, 260, 20 + bar_width, 290], fill="#00FF66")

    # Grok sprite
    sprite = load_form_image(form)
    if sprite:
        sprite = sprite.resize((180, 180))
        img.paste(sprite, (400, 140), sprite)

    out = f"/tmp/profile_{user_id}.png"
    img.save(out)
    return out


# ---------------------------------------------------
# LEADERBOARD IMAGE (FIXED)
# ---------------------------------------------------
def generate_leaderboard_image():
    rows = get_top_users()  # each user contains xp_total, xp_current, xp_to_next_level, level, form

    width = 1000
    height = 200 + len(rows) * 140
    img = Image.new("RGBA", (width, height), (10, 5, 20, 255))

    # Nebula background
    nebula_path = os.path.join(ASSET_DIR, "nebula_bg.png")
    if os.path.exists(nebula_path):
        neb = Image.open(nebula_path).convert("RGBA").resize((width, height))
        img = Image.alpha_composite(img, neb)

    draw = ImageDraw.Draw(img)

    # Title
    outline_text(
        draw, (width // 2, 80),
        "MEGAGROK HOP-FAME",
        load_font(70),
        fill=(255, 230, 120),
        outline="purple",
        stroke=6,
        anchor="mm"
    )

    icon_crown = os.path.join(ASSET_DIR, "icon_crown.png")
    icon_xp = os.path.join(ASSET_DIR, "icon_xp.png")
    icon_comic = os.path.join(ASSET_DIR, "icon_comic.png")

    y = 180

    for i, user in enumerate(rows):
        rank = i + 1

        # Glow for top 3
        if rank <= 3:
            glow = Image.new("RGBA", (width, 140), (255, 220, 50, 60))
            glow = glow.filter(ImageFilter.GaussianBlur(18))
            img.paste(glow, (0, y - 20), glow)

        # Row background box
        draw.rectangle(
            [(40, y), (width - 40, y + 120)],
            fill=(255, 255, 255, 22),
            outline=(255, 255, 255, 50),
            width=2
        )

        # Rank text
        outline_text(draw, (70, y + 35), f"#{rank}", load_font(48),
                     fill=(255, 255, 200), outline="black", stroke=4)

        # Crown for first place
        if rank == 1 and os.path.exists(icon_crown):
            crown = Image.open(icon_crown).convert("RGBA").resize((70, 70))
            img.paste(crown, (150, y - 5), crown)

        # Grok sprite
        sprite = load_form_image(user["form"])
        if sprite:
            sprite = sprite.resize((110, 110))
            img.paste(sprite, (240, y + 5), sprite)

        # Username
        outline_text(draw, (380, y + 15), f"User {user['user_id']}",
                     load_font(36), fill="white",
                     outline="black", stroke=4)

        # XP + Level
        xp_text = f"Lvl {user['level']}    {user['xp_total']} XP"

        if os.path.exists(icon_xp):
            xp_ic = Image.open(icon_xp).convert("RGBA").resize((36, 36))
            img.paste(xp_ic, (380, y + 65), xp_ic)

        outline_text(draw, (430, y + 65), xp_text,
                     load_font(30), fill="white",
                     outline="black", stroke=3)

        # Comic FX for top rankings
        if rank <= 3 and os.path.exists(icon_comic):
            fx = Image.open(icon_comic).convert("RGBA").resize((90, 90))
            img.paste(fx, (width - 160, y + 15), fx)

        y += 140

    out = "/tmp/leaderboard.png"
    img.save(out)
    return out
