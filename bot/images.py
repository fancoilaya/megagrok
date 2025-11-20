from PIL import Image, ImageDraw, ImageFont
import os

ASSETS = {
    "Tadpole": "assets/tadpole.png",
    "Hopper": "assets/hopper.png",
    "Ascended Hopper": "assets/ascended.png",
}

def generate_profile_card(username, level, xp):
    # horizontal card 800x400
    width, height = 800, 400
    card = Image.new("RGBA", (width, height), (18, 18, 28, 255))
    draw = ImageDraw.Draw(card)
    try:
        font_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        font_m = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except:
        font_b = ImageFont.load_default()
        font_m = ImageFont.load_default()
    draw.text((240, 40), f"@{username}", font=font_b, fill=(255,255,255,255))
    draw.text((240, 90), f"Level {level}", font=font_m, fill=(200,200,200,255))
    draw.text((240, 130), f"XP: {xp}/200", font=font_m, fill=(180,240,180,255))
    bar_x, bar_y, bar_w, bar_h = 240, 170, 480, 28
    draw.rectangle([bar_x, bar_y, bar_x+bar_w, bar_y+bar_h], fill=(50,50,60,255))
    filled = int((xp/200)*bar_w) if xp>0 else 0
    draw.rectangle([bar_x, bar_y, bar_x+filled, bar_y+bar_h], fill=(100,220,140,255))
    form = "Tadpole"
    if level >= 10:
        form = "Ascended Hopper"
    elif level >=5:
        form = "Hopper"
    sprite_path = ASSETS.get(form)
    if sprite_path and os.path.exists(sprite_path):
        try:
            sprite = Image.open(sprite_path).convert("RGBA")
            sprite = sprite.resize((360,360))
            card.paste(sprite, (420,20), sprite)
        except:
            pass
    out_dir = "profiles"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"profile_{username}.png")
    card.save(out_path)
    return out_path
