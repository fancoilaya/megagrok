import os
import time
import json
import random
from telebot import TeleBot
from PIL import Image

from bot.db import (
    get_user,
    update_user_xp,
    get_quests,
    record_quest,
    increment_win,
    increment_ritual,
    get_top_users
)
from bot.images import generate_profile_image, generate_leaderboard_image
from bot.mobs import MOBS
from bot.utils import safe_send_gif
from bot.grokdex import GROKDEX

# NEW: evolutions integration
import evolutions

# --------------------------
# HELP TEXT
# --------------------------
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

# ---------------------------------------
# GROW COOLDOWN STORAGE
# ---------------------------------------
COOLDOWN_FILE = "/tmp/grow_cooldowns.json"
GROW_COOLDOWN_SECONDS = 30 * 60  # 30 minutes


def _load_cooldowns():
    try:
        if os.path.exists(COOLDOWN_FILE):
            return json.load(open(COOLDOWN_FILE, "r"))
    except:
        pass
    return {}


def _save_cooldowns(data):
    try:
        json.dump(data, open(COOLDOWN_FILE, "w"))
    except:
        pass


def _format_seconds_left(secs):
    secs = max(int(secs), 0)
    m = secs // 60
    s = secs % 60
    return f"{m}m {s}s" if m else f"{s}s"


def _render_progress_bar(pct, length=20):
    pct = max(0, min(1, pct))
    fill = int(pct * length)
    bar = "█" * fill + "░" * (length - fill)
    return f"`{bar}` {int(pct*100)}%"


# ---------------------------------------
# REGISTER HANDLERS
# ---------------------------------------
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

        cooldowns = _load_cooldowns()
        now = time.time()
        last = cooldowns.get(user_id, 0)
        if last and now - last < GROW_COOLDOWN_SECONDS:
            left = GROW_COOLDOWN_SECONDS - (now - last)
            bot.reply_to(message, f"⏳ Wait {_format_seconds_left(left)} before using /growmygrok again.")
            return

        # --- preserved: random XP change (can be negative) ---
        xp_change = random.randint(-10, 25)

        # Read user before applying change
        user = get_user(int(user_id))

        xp_total = user["xp_total"]
        xp_current = user["xp_current"]
        xp_to_next = user["xp_to_next_level"]
        level = user["level"]
        curve = user["level_curve_factor"]

        # --- NEW: apply evolution multiplier from DB (if present) ---
        # If evolution_multiplier is not yet in DB, fallback to 1.0
        try:
            evo_mult = float(user.get("evolution_multiplier", 1.0))
        except Exception:
            evo_mult = 1.0

        # Multiply the raw xp_change by the evolution multiplier
        # (keeps sign for negative changes)
        effective_change = int(xp_change * evo_mult)

        new_total = max(0, xp_total + effective_change)
        cur = xp_current + effective_change

        leveled_up = False
        leveled_down = False

        # level-up loop
        while cur >= xp_to_next:
            cur -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * curve)
            leveled_up = True

        # level-down
        while cur < 0 and level > 1:
            level -= 1
            xp_to_next = int(xp_to_next / curve)
            cur += xp_to_next
            leveled_down = True

        cur = max(0, cur)
        new_total = max(0, new_total)

        # Save previous evolution stage (for detecting evolution event later)
        try:
            old_stage = int(user.get("evolution_stage", 0))
        except Exception:
            old_stage = 0

        update_user_xp(
            int(user_id),
            {
                "xp_total": new_total,
                "xp_current": cur,
                "xp_to_next_level": xp_to_next,
                "level": level
            }
        )

        cooldowns[user_id] = now
        _save_cooldowns(cooldowns)

        bar = _render_progress_bar(cur / xp_to_next if xp_to_next > 0 else 0)

        msg = [
            f"✨ MegaGrok {'grew' if xp_change>=0 else 'changed'} {effective_change:+d} XP (base {xp_change:+d} × evo {evo_mult}x)",
            f"**Level {level}**",
            f"XP: {cur}/{xp_to_next}",
            bar
        ]
        if leveled_up:
            msg.append("🎉 **Level up!**")
        if leveled_down:
            msg.append("💀 **Lost a level!**")

        bot.reply_to(message, "\n".join(msg), parse_mode="Markdown")

        # --- NEW: check for evolution event and announce ---
        updated = get_user(int(user_id))
        new_stage = int(updated.get("evolution_stage", 0))
        new_level = int(updated.get("level", level))

        # Use evolutions helper if available; fallback to comparing form
        try:
            evolved, new_stage_data = evolutions.determine_evolution_event(old_stage, new_level)
        except Exception:
            # fallback: evolved if form changed
            old_form = user.get("form")
            new_form = updated.get("form")
            evolved = old_form != new_form
            new_stage_data = {"name": new_form, "xp_multiplier": updated.get("evolution_multiplier", 1.0), "fight_bonus": None}

        if evolved:
            # Build asset paths (adjust to your repo if different)
            name_slug = new_stage_data.get("name", "tadpole").lower().replace(" ", "_")
            gif_path = f"assets/evolutions/{name_slug}/levelup.gif"
            fallback_gif = f"assets/evolutions/{name_slug}/idle.gif"

            # 1) Private DM to user (Telegram chat = user id)
            try:
                # prefer levelup.gif, fallback to idle.gif, else text-only
                if os.path.exists(gif_path):
                    safe_send_gif(bot, int(user_id), gif_path)
                    bot.send_message(int(user_id), f"🎉 You evolved into *{new_stage_data.get('name')}*! New perks: XP ×{new_stage_data.get('xp_multiplier')}", parse_mode="Markdown")
                elif os.path.exists(fallback_gif):
                    safe_send_gif(bot, int(user_id), fallback_gif)
                    bot.send_message(int(user_id), f"🎉 You evolved into *{new_stage_data.get('name')}*! New perks: XP ×{new_stage_data.get('xp_multiplier')}", parse_mode="Markdown")
                else:
                    bot.send_message(int(user_id), f"🎉 You evolved into *{new_stage_data.get('name')}*! New perks: XP ×{new_stage_data.get('xp_multiplier')}", parse_mode="Markdown")
            except Exception:
                # user may have blocked DMs or other issue — continue
                pass

            # 2) Public hype message in the same chat where command was invoked
            hype_text = f"🔥 **{message.from_user.first_name or message.from_user.username}** has evolved into **{new_stage_data.get('name')}**! Congrats!"
            try:
                if os.path.exists(gif_path):
                    safe_send_gif(bot, message.chat.id, gif_path)
                    bot.send_message(message.chat.id, hype_text, parse_mode="Markdown")
                else:
                    bot.send_message(message.chat.id, hype_text, parse_mode="Markdown")
            except Exception:
                # best-effort — continue if send fails
                pass

    # ---------------- HOP ----------------
    @bot.message_handler(commands=['hop'])
    def hop(message):

        user_id = message.from_user.id
        q = get_quests(user_id)

        if q["hop"] == 1:
            bot.reply_to(message, "🐸 You already performed today’s Hop Ritual!")
            return

        xp_gain = random.randint(20, 50)
        user = get_user(user_id)

        xp_total = user["xp_total"] + xp_gain
        cur = user["xp_current"] + xp_gain
        xp_to_next = user["xp_to_next_level"]
        level = user["level"]
        curve = user["level_curve_factor"]

        if cur >= xp_to_next:
            cur -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * curve)

        update_user_xp(
            user_id,
            {
                "xp_total": xp_total,
                "xp_current": cur,
                "xp_to_next_level": xp_to_next,
                "level": level
            }
        )

        record_quest(user_id, "hop")
        increment_ritual(user_id)

        bot.reply_to(message, f"🐸✨ Hop Ritual complete! +{xp_gain} XP")

    # ---------------- FIGHT ----------------
    @bot.message_handler(commands=['fight'])
    def fight(message):
        user_id = message.from_user.id
        q = get_quests(user_id)

        if q["fight"] == 1:
            bot.reply_to(message, "⚔️ You already fought today!")
            return

        mob = random.choice(MOBS)

        bot.reply_to(
            message,
            f"⚔️ **{mob['name']} Encounter!**\n\n{mob['intro']}",
            parse_mode="Markdown"
        )

        try:
            with open(mob["portrait"], "rb") as f:
                bot.send_photo(message.chat.id, f)
        except:
            pass

        win = random.choice([True, False])
        if win:
            xp = random.randint(mob["min_xp"], mob["max_xp"])
            outcome = mob["win_text"]
            increment_win(user_id)
        else:
            xp = random.randint(10, 25)
            outcome = mob["lose_text"]

        safe_send_gif(bot, message.chat.id, mob.get("gif"))

        user = get_user(user_id)
        xp_total = user["xp_total"] + xp
        cur = user["xp_current"] + xp
        xp_to_next = user["xp_to_next_level"]
