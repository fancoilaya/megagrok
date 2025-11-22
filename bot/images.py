import os
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

ASSET_DIR = "assets"

PROFILE_BASE = "profile_base.png"
TADPOLE = "tadpole.png"
HOPPER = "hopper.png"
ASCENDED = "ascended.png"

FONT_BOLD = "Roboto-Bold.ttf"
FONT_REG = "Roboto-Regular.ttf"
FONT_LIGHT = "Roboto-Light.ttf"


def asset(path):
    a = os.path.join(ASSET_DIR, path)
    b = os.path.join("/mnt/data", path)
    if os.path.exists(a):
        return a
    if os.path.exists(b):
        return b
    return None


def load_font(name, size):
    for p in [
        os.path.join(ASSET_DIR, name),
        os.path.join("/mnt/data", name),
        name
    ]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


TITLE_FONT = load_font(FONT_BOLD, 90)
USERNAME_FONT = load_font(FONT_REG, 60)
LABEL_FONT = load_font(FONT_BOLD, 40)
VALUE_FONT = load_font(FONT_BOLD, 72)
FOOTER_FONT = load_font(FONT_LIGHT, 34)


FORM_TO_SPRITE = {
    "Tadpole": TADPOLE,
    "Hopper": HOPPER,
    "Ascended": ASCENDED
}


def load_sprite(form: str):
    f = FORM_TO_SPRITE.get(form, TADPOLE)
    path = asset(f)
    if not path:
        return None
    return Image.open(path).convert("RGBA")


def generate_profile_image(user: Dict[str, Any]) -> str:

    username = user.get("username", "Player")
    form = user.get("form", "Tadpole")
    level = int(user.get("level", 1))
    wins = int(user.get("wins", 0))
    fights = int(user.get("fights", user.get("mobs_defeated", 0)))
    rituals = int(user.get("rituals", 0))
    tg = user.get("tg", "")
    ca = user.get("ca", "")
    uid = user.get("user_id", 0)

    base_path = asset(PROFILE_BASE)
    card = Image.open(base_path).convert("RGBA")
    W, H = card.size

    draw = ImageDraw.Draw(card)

    # ------------------------------
    # AUTO-DETECTED REGIONS (from your template)
    # ------------------------------

    # Header yellow bar
    header_y1 = int(H * 0.03)
    header_y2 = int(H * 0.17)

    # Art region
    art_y1 = int(H * 0.17)
    art_y2 = int(H * 0.68)
    art_x1 = int(W * 0.05)
    art_x2 = int(W * 0.95)

    # Bottom 3 stat boxes
    stats_y1 = int(H * 0.68)
    stats_y2 = int(H * 0.80)

    box_width = (art_x2 - art_x1) // 3

    box1 = (art_x1, stats_y1, art_x1 + box_width, stats_y2)
    box2 = (art_x1 + box_width, stats_y1, art_x1 + 2 * box_width, stats_y2)
    box3 = (art_x1 + 2 * box_width, stats_y1, art_x2, stats_y2)

    # Footer bar
    footer_y1 = int(H * 0.81)
    footer_y2 = int(H * 0.94)
    footer_box = (art_x1, footer_y1, art_x2, footer_y2)

    # ------------------------------
    # HEADER TEXT
    # ------------------------------
    title = "MEGAGROK"
    tw = draw.textlength(title, TITLE_FONT)
    draw.text(((W - tw) / 2, header_y1 + 10), title, font=TITLE_FONT, fill=(0, 0, 0))

    un_w = draw.textlength(username, USERNAME_FONT)
    draw.text(((W - un_w) / 2, header_y1 + 110), username, font=USERNAME_FONT, fill=(0, 0, 0))

    # ------------------------------
    # SPRITE IN ART BOX
    # ------------------------------
    sprite = load_sprite(form)
    if sprite:
        target_w = int((art_x2 - art_x1) * 0.55)
        aspect = sprite.height / sprite.width
        target_h = int(target_w * aspect)
        sprite = sprite.resize((target_w, target_h), Image.LANCZOS)

        sx = art_x1 + ((art_x2 - art_x1) - target_w) // 2
        sy = art_y1 + ((art_y2 - art_y1) - target_h) // 2
        card.paste(sprite, (sx, sy), sprite)

    # ------------------------------
    # BOTTOM STATS — CENTERED
    # ------------------------------

    def center_text_in_box(text, box, font, y_offset=0):
        x1, y1, x2, y2 = box
        w = draw.textlength(text, font)
        x = x1 + ((x2 - x1) - w) // 2
        y = y1 + ((y2 - y1) - font.size) // 2 + y_offset
        draw.text((x, y), text, font=font, fill=(0, 0, 0))

    # LEVEL box
    center_text_in_box("LEVEL", box1, LABEL_FONT, -28)
    center_text_in_box(str(level), box1, VALUE_FONT, 18)

    # FIGHTS / WINS box
    center_text_in_box("FIGHTS / WINS", box2, LABEL_FONT, -28)
    center_text_in_box(f"{fights} / {wins}", box2, VALUE_FONT, 18)

    # RITUALS box
    center_text_in_box("RITUALS", box3, LABEL_FONT, -28)
    center_text_in_box(str(rituals), box3, VALUE_FONT, 18)

    # ------------------------------
    # FOOTER — TG & CA (two centered lines)
    # ------------------------------
    if tg or ca:
        footer_text = ""
        if tg:
            footer_text += f"TG: {tg}\n"
        if ca:
            footer_text += f"CA: {ca}"

        # center inside footer box
        lines = footer_text.split("\n")
        y = footer_box[1] + 10

        for line in lines:
            lw = draw.textlength(line, FOOTER_FONT)
            lx = footer_box[0] + ((footer_box[2] - footer_box[0]) - lw) // 2
            draw.text((lx, y), line, font=FOOTER_FONT, fill=(0, 0, 0))
            y += FOOTER_FONT.size + 4

    # Save
    out = f"/tmp/profile_{uid}.png"
    card.save(out)
    return out
