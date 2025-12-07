import os
import time
import random
import json

from telebot import TeleBot
from bot.db import get_user, update_user_xp
from bot.utils import safe_send_gif
import bot.evolutions as evolutions   # ensure package import
from bot.leaderboard_tracker import announce_leaderboard_if_changed

GROW_COOLDOWN_SECONDS = 30 * 60  # 30 minutes
COOLDOWN_FILE = "/tmp/grow_cooldowns.json"


def _load_cooldowns():
    if os.path.exists(COOLDOWN_FILE):
        try:
            return json.load(open(COOLDOWN_FILE))
        except Exception:
            return {}
    return {}


def _save_cooldowns(data):
    try:
        json.dump(data, open(COOLDOWN_FILE, "w"))
    except Exception:
        pass


def _format_seconds_left(secs):
    secs = max(int(secs), 0)
    m = secs // 60
    s = secs % 60
    return f"{m}m {s}s" if m else f"{s}s"


def _render_progress_bar(pct, length=20):
    pct = max(0, min(1, pct))
    fill = int(pct * length)
    bar = "▓" * fill + "░" * (length - fill)
    return bar, int(pct * 100)


def setup(bot: TeleBot):

    @bot.message_handler(commands=['growmygrok'])
    def grow(message):
        user_id = str(message.from_user.id)
        cooldowns = _load_cooldowns()
        now = time.time()
        last = cooldowns.get(user_id, 0)

        if last and now - last < GROW_COOLDOWN_SECONDS:
            left = GROW_COOLDOWN_SECONDS - (now - last)
            bot.reply_to(message, f"⏳ Wait {_format_seconds_left(left)} before growing again.")
            return

        # Base random XP change
        base_xp = random.randint(-10, 25)

        user = get_user(int(user_id))
        if not user:
            bot.reply_to(message, "❌ You do not have a Grok yet.")
            return

        level = int(user.get("level", 1))
        xp_total = user.get("xp_total", 0)
        xp_current = user.get("xp_current", 0)
        xp_to_next = user.get("xp_to_next_level", 100)
        curve = float(user.get("level_curve_factor", 1.15))

        # Evolution multiplier
        tier_mult = evolutions.get_xp_multiplier_for_level(level)
        user_mult = float(user.get("evolution_multiplier", 1.0))
        evo_mult = tier_mult * user_mult

        # Final XP
        effective = int(round(base_xp * evo_mult))

        new_total = max(0, xp_total + effective)
        cur = xp_current + effective

        leveled_up = False
        leveled_down = False

        # Level up
        while cur >= xp_to_next:
            cur -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * curve)
            leveled_up = True

        # Level down
        while cur < 0 and level > 1:
            level -= 1
            xp_to_next = int(xp_to_next / curve)
            cur += xp_to_next
            leveled_down = True

        cur = max(0, cur)
        new_total = max(0, new_total)

        old_stage = int(user.get("evolution_stage", 0))

        # Persist XP change
        update_user_xp(
            int(user_id),
            {
                "xp_total": new_total,
                "xp_current": cur,
                "xp_to_next_level": xp_to_next,
                "level": level,
            }
        )

        # Announce leaderboard changes if any (best-effort)
        try:
            announce_leaderboard_if_changed(bot)
        except Exception as e:
            # Resist crashing the command; log for devs
            print("Leaderboard update failed in growmygrok:", e)

        # Save cooldown
        cooldowns[user_id] = now
        _save_cooldowns(cooldowns)

        pct = cur / xp_to_next if xp_to_next else 0
        bar, pct_int = _render_progress_bar(pct)

        # Output message
        msg = (
            f"✨ **MegaGrok Growth Surge!**\n\n"
            f"📈 **Base XP:** {base_xp:+d}\n"
            f"🔮 **Evo Boost:** ×{evo_mult:.2f}\n"
            f"⚡ **Effective XP:** {effective:+d}\n\n"
            f"🧬 **Level:** {level}\n"
            f"🔸 **XP:** {cur} / {xp_to_next}\n"
            f"🟩 **Progress:** `{bar}` {pct_int}%\n"
        )

        if leveled_up:
            msg += "\n🎉 **LEVEL UP!** Your MegaGrok ascended!"
        if leveled_down:
            msg += "\n💀 **LEVEL DOWN!** Your MegaGrok weakened."

        bot.reply_to(message, msg, parse_mode="Markdown")

        # Evolution event check
        updated = get_user(int(user_id))
        new_stage = int(updated.get("evolution_stage", 0))
        new_level = int(updated.get("level", level))

        evolved, new_stage_data = evolutions.determine_evolution_event(old_stage, new_level)

        if evolved:
            name_slug = new_stage_data["name"].lower().replace(" ", "_")
            gif_path = f"assets/evolutions/{name_slug}/levelup.gif"
            fallback = f"assets/evolutions/{name_slug}/idle.gif"

            try:
                if os.path.exists(gif_path):
                    safe_send_gif(bot, int(user_id), gif_path)
                elif os.path.exists(fallback):
                    safe_send_gif(bot, int(user_id), fallback)

                bot.send_message(
                    int(user_id),
                    f"🎉 **Evolution!** You became *{new_stage_data['name']}*!",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

            hype = f"🔥 **{message.from_user.first_name}** evolved into **{new_stage_data['name']}**!"
            try:
                if os.path.exists(gif_path):
                    safe_send_gif(bot, message.chat.id, gif_path)
            except Exception:
                pass

            bot.send_message(message.chat.id, hype, parse_mode="Markdown")
