
import os, tempfile
from xml.sax.saxutils import escape
from typing import List, Dict
from PIL import Image, ImageDraw, ImageFont

try:
    import cairosvg
    HAVE_CAIROSVG = True
except Exception:
    HAVE_CAIROSVG = False

# assets folder is at repo root: ../assets relative to this file
ASSET_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
PROFILE_TEMPLATE = os.path.join(ASSET_DIR, "templates", "profile_template.svg")
LEADERBOARD_TEMPLATE = os.path.join(ASSET_DIR, "templates", "leaderboard_template.svg")
SPRITE_DIR = os.path.join(ASSET_DIR, "sprites")
PROJECT_TG = "t.me/megagrok"
PROJECT_CA = "FZL2K9TBybDh32KfJWQBhMtQ71PExyNXiry8Y5e2pump"

def _esc(s): return escape(str(s))

def _write_temp_text(s, suffix=".svg"):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    return path

def _render_svg(svg_path, out_size):
    if HAVE_CAIROSVG:
        out_fd, out_png = tempfile.mkstemp(suffix=".png")
        os.close(out_fd)
        cairosvg.svg2png(url=svg_path, write_to=out_png, output_width=out_size[0], output_height=out_size[1])
        return out_png
    return None

def generate_profile_image(user: Dict, size=(900,1280)):
    if os.path.exists(PROFILE_TEMPLATE):
        with open(PROFILE_TEMPLATE, "r", encoding="utf-8") as f:
            svg = f.read()
    else:
        raise FileNotFoundError("profile_template.svg missing in assets/templates")

    replacements = {
        "{{USERNAME}}": _esc(user.get("username","UNKNOWN").upper()),
        "{{LEVEL}}": _esc(user.get("level",1)),
        "{{EVOLUTION}}": _esc(user.get("form","Tadpole")),
        "{{WINS}}": _esc(user.get("wins",0)),
        "{{FIGHTS}}": _esc(user.get("fights",0)),
        "{{RITUALS}}": _esc(user.get("rituals",0)),
        "{{TG}}": _esc(user.get("tg", PROJECT_TG)),
        "{{CA}}": _esc(user.get("ca", PROJECT_CA))
    }
    for k,v in replacements.items():
        svg = svg.replace(k, str(v))

    sprite_name = user.get("form","tadpole").lower() + ".svg"
    sprite_path = os.path.join(SPRITE_DIR, sprite_name)
    if os.path.exists(sprite_path):
        svg = svg.replace('id="SPRITE_HERE_PLACEHOLDER"', f'id="SPRITE_HERE" href="file://{sprite_path}"')
    else:
        svg = svg.replace('id="SPRITE_HERE_PLACEHOLDER"', '')

    svg_path = _write_temp_text(svg, suffix=".svg")
    png = _render_svg(svg_path, size)
    if png:
        return png

    # PIL fallback (simple)
    base = os.path.join(ASSET_DIR, "backgrounds", "profile_base.png")
    out = os.path.join("/tmp", f"profile_{user.get('username','user')}.png")
    if not os.path.exists(base):
        # create blank fallback
        im = Image.new("RGBA", size, (255,255,255,255))
        im.save(out)
        return out
    base_im = Image.open(base).convert("RGBA").resize(size)
    draw = ImageDraw.Draw(base_im)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    except Exception:
        font = ImageFont.load_default()
    draw.text((size[0]//2, 120), user.get("username","UNKNOWN"), font=font, anchor="mm", fill=(10,10,10))
    base_im.save(out)
    return out

def generate_leaderboard_image(rows: List[Dict]=None, size=(1000,1600)):
    if rows is None:
        rows = [
            {"rank":1,"username":"Example1","xp":3450,"fights":70,"wins":50},
            {"rank":2,"username":"Example2","xp":3020,"fights":65,"wins":45},
            {"rank":3,"username":"Example3","xp":2800,"fights":60,"wins":40},
            {"rank":4,"username":"Example4","xp":2550,"fights":55,"wins":35},
            {"rank":5,"username":"Example5","xp":2400,"fights":50,"wins":30},
        ]

    if os.path.exists(LEADERBOARD_TEMPLATE):
        with open(LEADERBOARD_TEMPLATE, 'r', encoding='utf-8') as f:
            svg = f.read()
    else:
        raise FileNotFoundError("leaderboard_template.svg missing in assets/templates")

    for i in range(5):
        r = rows[i] if i < len(rows) else {"username":f"Player{i+1}", "xp":0, "fights":0, "wins":0}
        svg = svg.replace(f"{{{{R{i+1}_NAME}}}}", _esc(r.get('username')))
        stats = f"XP: {r.get('xp',0)}   FIGHTS/WINS: {r.get('fights',0)} / {r.get('wins',0)}"
        svg = svg.replace(f"{{{{R{i+1}_STATS}}}}", _esc(stats))

    svg_path = _write_temp_text(svg, suffix='.svg')
    png = _render_svg(svg_path, size)
    if png:
        return png

    # PIL fallback: simple text overlay
    base = os.path.join(ASSET_DIR, "backgrounds", "leaderboard_base.png")
    out = os.path.join("/tmp", "leaderboard.png")
    if not os.path.exists(base):
        im = Image.new("RGBA", size, (240,200,120,255))
        im.save(out)
        return out
    im = Image.open(base).convert("RGBA").resize(size)
    draw = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except Exception:
        font = ImageFont.load_default()
    y = int(im.height*0.18)
    for r in rows:
        draw.text((int(im.width*0.28), y), f"{r['username']} - XP {r['xp']}  F/W: {r['fights']}/{r['wins']}", font=font, fill=(10,10,10))
        y += int(im.height*0.18)
    im.save(out)
    return out
