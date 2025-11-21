import os
import time
import json
import random
from telebot import TeleBot
from datetime import datetime, timedelta

from bot.db import (
    get_user,
    update_user_xp,
    get_quests,
    record_quest,
    increment_win,
    increment_ritual
)
from bot.images import generate_profile_image, generate_leaderboard_image
from bot.mobs import MOBS
from bot.utils import safe_send_gif
from bot.grokdex import GROKDEX
from PIL import Image

# ------------------------
# HELP TEXT
# ------------------------
HELP_TEXT = (
    "🐸 **MegaGrok Bot Commands**\n\n"
    "/start – Begin your journey.\n"
    "/help – Show this help menu.\n"
    "/growmygrok – Gain XP and grow your Grok.\n"
    "/hop – Perform your daily hop ritual.\n"
    "/fight – Fight a random mob for XP.\n"
    "/profile – Show your Grok profile card.\n"
    "/leaderboard – View the Top 10 Grok tamers.\n"
    "/grokdex – View all known creatures.\n"
    "/mob <name> – Inspect a specific creature.\n\n"
    "Evolve your Grok, level up, complete quests and climb the ranks!"
)

start_text = (
    "🐸🌌 *THE COSMIC AMPHIBIAN HAS AWAKENED* 🌌🐸\n\n"
    "✨ A portal cracks open…\n"
    "✨ Your MegaGrok emerges from the liquidity void…\n"
    "✨ Your evolution begins *now*.\n\n"
    "⚡ *Core Commands*\n"
    "🐸 /growmygrok — Feed cosmic hop-energy\n"
    "🔮 /hop — Daily ritual boost\n"
    "⚔️ /fight — Battle Hop-Verse creatures\n"
    "🧬 /profile — View your Grok\n"
    "📜 /help — Full command list\n\n"
    "🚀 Train him. Evolve him. Conquer the Hop-Verse."
)

# -------------------------
# COOLDOWN STORAGE (file-based)
# -------------------------
COOLDOWN_FILE = "/tmp/grow_cooldowns.json"
GROW_COOLDOWN_SECONDS = 30 * 60  # 30 minutes


def _load_cooldowns():
    try:
        if os.path.exists(COOLDOWN_FILE):
            with open(COOLDOWN_FILE, "r") as fh:
                return json.load(fh)
    except Exception:
        pass
    return {}


def _save_cooldowns(d):
    try:
        with open(COOLDOWN_FILE, "w") as fh:
            json.dump(d, fh)
    except Exception:
        pass


def _format_seconds_left(secs):
    mins = int(secs // 60)
    sec = int(secs % 60)
    return f"{mins}m {sec}s" if mins else f"{sec}s"


def _render_progress_bar(pct, length=20):
    """Return a textual progress bar using block characters."""
    pct = max(0.0, min(1.0, pct))
    filled = int(round(pct * length))
    empty = length - filled
    bar = "█" * filled + "░" * empty
    percent_text = f"{int(pct * 100)}%"
    return f"`{bar}` {percent_text}"


# ---------------------------------------------------------
# REGISTER ALL COMMAND HANDLERS
# ---------------------------------------------------------
def register_handlers(bot: TeleBot):

    # ---------------- START ----------------
    @bot.message_handler(commands=['start'])
    def start(message):
        bot.reply_to(message, start_text, parse_mode="Markdown")

    # ---------------- HELP ----------------
    @bot.message_handler(commands=['help'])
    def help_cmd(message):
        bot.reply_to(message, HELP_TEXT)

    # ---------------- GROW ----------------
    @bot.message_handler(commands=['growmygrok'])
    def grow(message):
        user_id = str(message.from_user.id)

        # load cooldowns and check
        cds = _load_cooldowns()
        now_ts = time.time()
        last_ts = cds.get(user_id, 0)
        elapsed = now_ts - last_ts
        if last_ts and elapsed < GROW_COOLDOWN_SECONDS:
            left = GROW_COOLDOWN_SECONDS - elapsed
            bot.reply_to(message, f"⏳ You must wait { _format_seconds_left(left) } before using /growmygrok again.")
            return

        # compute xp change: allow small negative outcomes as requested
        xp_change = random.randint(-10, 25)  # may be negative

        # fetch current user record from DB
        user = get_user(int(user_id))

        # We expect DB user to have at least these keys:
        # xp_total, xp_current, xp_to_next_level, level
        # For level curve, fall back to a sensible default if missing.
        xp_total = int(user.get("xp_total", user.get("xp", 0)))
        xp_current = int(user.get("xp_current", user.get("xp", 0)))
        xp_to_next = int(user.get("xp_to_next_level", max(200, user.get("level", 1) * 200)))
        level = int(user.get("level", 1))

        # level growth factor (slightly increasing requirement per level)
        level_curve_factor = float(user.get("level_curve_factor", 1.12))

        # Apply XP change
        new_xp_total = max(0, xp_total + xp_change)
        new_xp_current = xp_current + xp_change

        leveled_up = False
        leveled_down = False
        level_events = []

        # Handle level ups (support multiple level-ups in one gain)
        while new_xp_current >= xp_to_next:
            new_xp_current -= xp_to_next
            level += 1
            # increase xp_to_next by the curve factor
            xp_to_next = int(max(50, xp_to_next * level_curve_factor))
            leveled_up = True
            level_events.append(f"⬆️ Leveled up to {level}")

        # Handle level down (if xp went negative and level > 1)
        while new_xp_current < 0 and level > 1:
            # step one level down
            level -= 1
            # approximate previous level requirement by reversing the factor
            xp_to_next = max(200, int(xp_to_next / level_curve_factor))
            # add the reduced level threshold to current xp (don't go below 0)
            new_xp_current += xp_to_next
            leveled_down = True
            level_events.append(f"⬇️ Leveled down to {level}")
            if new_xp_current < 0:
                new_xp_current = 0
                break

        # ensure non-negative
        new_xp_current = max(0, new_xp_current)
        new_xp_total = max(0, new_xp_total)

        # Persist to DB using update_user_xp (same pattern as other commands)
        update_user_xp(int(user_id), {
            "xp_total": new_xp_total,
            "xp_current": new_xp_current,
            "xp_to_next_level": xp_to_next,
            "level": level
        })

        # record cooldown
        cds[user_id] = now_ts
        _save_cooldowns(cds)

        # Build user-facing message including a nicer progress bar
        progress_bar = _render_progress_bar(new_xp_current / xp_to_next, length=20)

        # friendly XP sign
        sign = "+" if xp_change >= 0 else ""
        lines = []
        lines.append(f"✨ Your MegaGrok {'grew' if xp_change>=0 else 'changed'}! {sign}{xp_change} XP")
        lines.append(f"**Level {level}**")
        lines.append(f"XP: {new_xp_current}/{xp_to_next}")
        lines.append(progress_bar)

        if leveled_up:
            lines.append("🎉 **Level up!** Your Grok has evolved.")
        if leveled_down:
            lines.append("💀 Ouch — your Grok regressed. Keep training!")

        # Combine and send as Markdown (progress bar uses backticks)
        bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")

    # ---------------- HOP (RITUAL) ----------------
    @bot.message_handler(commands=['hop'])
    def hop(message):
        user_id = message.from_user.id
        quests = get_quests(user_id)

        if quests["hop"] == 1:
            bot.reply_to(message, "🐸 You've already performed your Hop Ritual today!")
            return

        xp_gain = random.randint(20, 50)
        user = get_user(user_id)

        xp_total = user["xp_total"] + xp_gain
        xp_current = user["xp_current"] + xp_gain
        xp_to_next = user["xp_to_next_level"]
        level = user["level"]

        if xp_current >= xp_to_next:
            xp_current -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * user["level_curve_factor"])

        update_user_xp(user_id, {
            "xp_total": xp_total,
            "xp_current": xp_current,
            "xp_to_next_level": xp_to_next,
            "level": level
        })

        record_quest(user_id, "hop")
        increment_ritual(user_id, 1)

        bot.reply_to(
            message,
            f"🐸✨ Hop Ritual complete! +{xp_gain} XP\n"
            f"The cosmic hop-energy flows through your MegaGrok!"
        )

    # ---------------- FIGHT ----------------
    @bot.message_handler(commands=['fight'])
    def fight(message):
        user_id = message.from_user.id
        quests = get_quests(user_id)

        if quests["fight"] == 1:
            bot.reply_to(message, "⚔️ You've already fought today! Come back tomorrow.")
            return

        mob = random.choice(MOBS)

        bot.reply_to(message, f"⚔️ **{mob['name']} Encounter!**\n\n{mob['intro']}", parse_mode="Markdown")

        try:
            with open(mob["portrait"], "rb") as img:
                bot.send_photo(message.chat.id, img)
        except:
            bot.reply_to(message, "⚠️ Failed to load mob portrait.")

        win = random.choice([True, False])

        if win:
            xp = random.randint(mob["min_xp"], mob["max_xp"])
            outcome_text = mob["win_text"]
            increment_win(user_id, 1)
        else:
            xp = random.randint(10, 25)
            outcome_text = mob["lose_text"]

        safe_send_gif(bot, message.chat.id, mob["gif"])

        user = get_user(user_id)
        xp_total = user["xp_total"] + xp
        xp_current = user["xp_current"] + xp
        xp_to_next = user["xp_to_next_level"]
        level = user["level"]

        if xp_current >= xp_to_next:
            xp_current -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * user["level_curve_factor"])

        update_user_xp(user_id, {
            "xp_total": xp_total,
            "xp_current": xp_current,
            "xp_to_next_level": xp_to_next,
            "level": level
        })

        record_quest(user_id, "fight")

        bot.send_message(
            message.chat.id,
            f"{outcome_text}\n\n✨ **XP Gained:** {xp}"
        )

    # ---------------- PROFILE ----------------
    @bot.message_handler(commands=['profile'])
    def profile(message):
        """
        Fog-proof version: converts PNG → flattened JPEG before sending.
        Prevents Telegram client preview tinting.
        """
        user_id = message.from_user.id
        user = get_user(user_id)

        try:
            png_path = generate_profile_image(user)

            # Unique safe jpeg path
            jpeg_path = f"/tmp/profile_{user_id}_{int(time.time())}.jpg"

            img = Image.open(png_path).convert("RGBA")
            paper = (255, 249, 230)
            bg = Image.new("RGB", img.size, paper)

            if img.mode == "RGBA":
                bg.paste(img, mask=img.split()[3])
            else:
                bg.paste(img)

            bg.save(jpeg_path, format="JPEG", quality=95)

            with open(jpeg_path, "rb") as f:
                bot.send_photo(message.chat.id, f)

            # clean temp jpeg
            try:
                os.remove(jpeg_path)
            except:
                pass

        except Exception as e:
            bot.reply_to(message, f"Error generating profile: {e}")
            print("PROFILE ERROR:", e)

    # ---------------- LEADERBOARD ----------------
    @bot.message_handler(commands=['leaderboard'])
    def leaderboard(message):
        try:
            img_path = generate_leaderboard_image()
            with open(img_path, "rb") as f:
                bot.send_photo(message.chat.id, f)
        except Exception as e:
            bot.reply_to(message, f"Error generating leaderboard: {e}")

    # ---------------- GROKDEX ----------------
    @bot.message_handler(commands=['grokdex'])
    def grokdex(message):
        text = "📘 *MEGAGROK DEX — Known Creatures*\n\n"

        for key, mob in GROKDEX.items():
            text += f"• *{mob['name']}* — {mob['rarity']}\n"

        text += "\nUse `/mob <name>` for details."
        bot.reply_to(message, text, parse_mode="Markdown")

    # ---------------- MOB INFO ----------------
    @bot.message_handler(commands=['mob'])
    def mob_info(message):
        try:
            name = message.text.split(" ", 1)[1].strip()
        except:
            bot.reply_to(message, "Usage: `/mob FUDling`", parse_mode="Markdown")
            return

        if name not in GROKDEX:
            bot.reply_to(message, "❌ Creature not found in the GrokDex.")
            return

        mob = GROKDEX[name]

        text = (
            f"📘 *{mob['name']}*\n"
            f"⭐ Rarity: *{mob['rarity']}*\n"
            f"🎭 Type: {mob['type']}\n"
            f"💥 Power: {mob['combat_power']}\n\n"
            f"📜 *Lore*\n{mob['description']}\n\n"
            f"⚔️ Strength: {mob['strength']}\n"
            f"🛡 Weakness: {mob['weakness']}\n"
            f"🎁 Drops: {', '.join(mob['drops'])}\n"
        )

        try:
            with open(mob["portrait"], "rb") as img:
                bot.send_photo(message.chat.id, img, caption=text, parse_mode="Markdown")
        except:
            bot.reply_to(message, text, parse_mode="Markdown")
