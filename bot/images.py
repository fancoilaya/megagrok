import os
from PIL import Image, ImageDraw, ImageFont

ASSET_DIR = "assets"

# Non-TTF default font (always available)
DEFAULT_FONT = ImageFont.load_default()


# ----------------------------
# Load Grok form image
# ----------------------------
def load_form_image(form_name):
    form_map = {
        "Tadpole": "tadpole.png",
        "Hopper": "hopper.png",
        "Ascended": "ascended.png"
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

    # Title
    draw.text((20, 20), f"MegaGrok Profile", font=DEFAULT_FONT, fill="white")

    # Stats text
    draw.text((20, 70), f"User ID: {user['user_id']}", font=DEFAULT_FONT, fill="white")
    draw.text((20, 100), f"Level: {user['level']}", font=DEFAULT_FONT, fill="white")
    draw.text((20, 130), f"Form: {user['form']}", font=DEFAULT_FONT, fill="white")
    draw.text((20, 160), f"XP: {xp_current}/{xp_next}", font=DEFAULT_FONT, fill="white")

    # XP bar
    bar_x = 20
    bar_y = 200
    bar_width = 400
    bar_height = 25

    pct = min(max(xp_current / xp_next, 0), 1)
    progress_width = int(bar_width * pct)

    draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], fill="#444444")
    draw.rectangle([bar_x, bar_y, bar_x + progress_width, bar_y + bar_height], fill="#00FF00")

    # Load Froggy sprite
    sprite = load_form_image(user["form"])
    if sprite:
        sprite = sprite.resize((160, 160))
        img.paste(sprite, (420, 160), sprite)

    output_path = f"/tmp/profile_{user['user_id']}.png"
    img.save(output_path)

    return output_path


# ----------------------------
# Leaderboard Image Generator
# ----------------------------
def generate_leaderboard_image(rows):
    width, height = 800, 1100
    img = Image.new("RGBA", (width, height), (10, 10, 10, 255))
    draw = ImageDraw.Draw(img)

    draw.text((20, 20), "🏆 MegaGrok Leaderboard — Top 10", font=DEFAULT_FONT, fill="white")

    y = 80

    for rank, row in enumerate(rows, start=1):
        user_id, xp, level, form = row

        # Text line
        draw.text(
            (20, y),
            f"{rank}. User {user_id} — Lv {level} — {form} — {xp} XP",
            font=DEFAULT_FONT,
            fill="white"
        )

        # Icon
        sprite = load_form_image(form)
        if sprite:
            sprite_small = sprite.resize((80, 80))
            img.paste(sprite_small, (700, y - 10), sprite_small)

        y += 100

    output_path = "/tmp/leaderboard.png"
    img.save(output_path)
    return output_path
