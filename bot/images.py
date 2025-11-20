import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from bot.db import get_top_users

ASSET_DIR = "assets"

# ----------------------------
# Safe font loader
# ----------------------------
def load_font(size):
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "Roboto-Bold.ttf"), size)
    except:
        return ImageFont.load_default()


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
        "Ascended": "ascended.png",   # compatibility
    }

    filename = form_map.get(form_name, "tadpole.png")
    path = os.path.join(ASSET_DIR, filename)

    if not os.path.exists(path):
        return None

    return Image.open(path).convert("RGBA")


# ----------------------------
# Profile Image Generator
# ----------------------------
def generate_profile_image(user, xp_current, xp_next):
    width, height = 600, 350
    img = Image.new("RGBA", (width, height), (15, 15, 15, 255))
    draw = ImageDraw.Draw(img)

    title_font = load_font(40)
    stat_font = load_font(28)

    # Title
    draw.text((20, 20), "MegaGrok Profile", font=title_font, fill="white")

    # Stats
    draw.text((20, 80), f"User ID: {user['user_id']}", font=stat_font, fill="white")
    draw.text((20, 120), f"Level: {user['level']}", font=stat_font, fill="white")
    draw.text((20, 160), f"Form: {user['form']}", font=stat_font, fill="white")
    draw.text((20, 200), f"XP: {xp_current}/{xp_next}", font=stat_font, fill="white")

    # XP bar
    bar_x = 20
    bar_y = 250
    bar_width = 400
    bar_height = 25

    pct = min(max(xp_current / xp_next, 0), 1)
    progress_width = int(bar_width * pct)

    draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], fill="#444444")
    draw.rectangle([bar_x, bar_y, bar_x + progress_width, bar_y + bar_height], fill="#00FF00")

    # Grok sprite
    sprite = load_form_image(user["form"])
    if sprite:
        sprite = sprite.resize((160, 160))
        img.paste(sprite, (420, 160), sprite)

    output_path = f"/tmp/profile_{user['user_id']}.png"
    img.save(output_path)

    return output_path


# ============================================================
#             UPGRADED COMIC-BOOK LEADERBOARD
# ============================================================
def generate_leaderboard_image():
    # Auto-fetch Top 10
    rows = get_top_users()

    width = 1000
    height = 180 + len(rows) * 140
    bg = Image.new("RGBA", (width, height), (10, 5, 20))

    draw = ImageDraw.Draw(bg)

    # Optional nebula background
    nebula_path = os.path.join(ASSET_DIR, "nebula_bg.png")
    if os.path.exists(nebula_path):
        nebula = Image.open(nebula_path).convert("RGBA").resize((width, height))
        bg = Image.alpha_composite(bg, nebula)

    # Title (comic style)
    title_font = load_font(70)
    outline_text(
        draw,
        (width // 2, 80),
        "MEGAGROK HOP-FAME",
        title_font,
        fill=(255, 230, 120),
        outline="purple",
        stroke=6,
        anchor="mm",
    )

    # Icon paths
    icon_crown = os.path.join(ASSET_DIR, "icon_crown.png")
    icon_xp = os.path.join(ASSET_DIR, "icon_xp.png")
    icon_comic = os.path.join(ASSET_DIR, "icon_comic.png")

    y = 180
    rank_font = load_font(50)
    name_font = load_font(36)
    stat_font = load_font(30)

    for idx, user in enumerate(rows):
        rank = idx + 1

        # Glow for top 3
        if rank <= 3:
            glow_color = (255, 200, 70, 80)
            glow = Image.new("RGBA", (width, 140), (0, 0, 0, 0))
            g = ImageDraw.Draw(glow)
            g.rectangle([(20, 10), (width - 20, 130)], fill=glow_color)
            glow = glow.filter(ImageFilter.GaussianBlur(16))
            bg.paste(glow, (0, y - 20), glow)

        # Row box
        draw.rectangle(
            [(40, y), (width - 40, y + 120)],
            fill=(255, 255, 255, 18),
            outline=(255, 255, 255, 40),
            width=2,
        )

        # Rank number
        outline_text(
            draw,
            (70, y + 35),
            f"#{rank}",
            rank_font,
            fill=(255, 255, 180),
            outline="black",
            stroke=4,
        )

        # Crown for #1
        if rank == 1 and os.path.exists(icon_crown):
            crown = Image.open(icon_crown).convert("RGBA").resize((70, 70))
            bg.paste(crown, (140, y - 10), crown)

        # Grok portrait
        sprite = load_form_image(user["form"])
        if sprite:
            sprite = sprite.resize((110, 110))
            bg.paste(sprite, (220, y + 5), sprite)

        # Username
        outline_text(
            draw,
            (360, y + 20),
            f"User {user['user_id']}",
            name_font,
            fill=(180, 220, 255),
            outline="black",
            stroke=3,
        )

        # XP line + icon
        xp_text = f"Lvl {user['level']}  |  {user['xp']} XP"

        if os.path.exists(icon_xp):
            xp_ic = Image.open(icon_xp).convert("RGBA").resize((35, 35))
            bg.paste(xp_ic, (360, y + 65), xp_ic)

        outline_text(
            draw,
            (410, y + 65),
            xp_text,
            stat_font,
            fill=(230, 230, 255),
            outline="black",
            stroke=3,
        )

        # Comic bubble FX for top 3
        if rank <= 3 and os.path.exists(icon_comic):
            bubble = Image.open(icon_comic).convert("RGBA").resize((90, 90))
            bg.paste(bubble, (width - 160, y + 15), bubble)

        y += 140

    output_path = "leaderboard.png"
    bg.save(output_path)
    return output_path
