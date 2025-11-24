# bot/handlers/growmygrok.py
import os
import time
import random

from telebot import TeleBot
from bot.db import get_user, update_user_xp
from bot.utils import safe_send_gif

import bot.evolutions as evolutions  # <-- FIXED IMPORT


GROW_COOLDOWN_SECONDS = 30 * 60  # 30 minutes
COOLDOWN_FILE = "/tmp/grow_cooldowns.json"


def _load_cooldowns():
    try:
        if os.path.exists(COOLDOWN_FILE):
            import json
            return json.load(open(COOLDOWN_FILE, "r"))
    except:
        pass
    return {}


def _save_cooldowns(data):
    try:
        import json
        return json.dump(data, open(COOLDOWN_FILE, "w"))
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
    bar = "█" * fill + "░" * (length - length)
    return f"`{bar}` {int(pct*100)}%"


def setup(bot: TeleBot):

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

        xp_change = random.randint(-10, 25)

        user = get_user(int(user_id))
        xp_total = user["xp_total"]
        xp_current = user["xp_current"]
        xp_to_next = user["xp_to_next_level"]
        level = user["level"]
        curve = user["level_curve_factor"]

        evo_mult = float(user.get("evolution_multiplier", 1.0))
        effective_change = int(xp_change * evo_mult)

        new_total = max(0, xp_total + effective_change)
        cur = xp_current + effective_change

        leveled_up = False
        leveled_down = False

        while cur >= xp_to_next:
            cur -= xp_to_next
            level += 1
            xp_to_next = int(xp_to_next * curve)
            leveled_up = True

        while cur < 0 and level > 1:
            level -= 1
            xp_to_next = int(xp_to_next / curve)
            cur += xp_to_next
            leveled_down = True

        cur = max(0, cur)
        new_total = max(0, new_total)

        old_stage = int(user.get("evolution_stage", 0))

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

        bar = _render_progress_bar(cur / xp_to_next if xp_to_next else 0)

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

        updated = get_user(int(user_id))
        new_stage = int(updated.get("evolution_stage", 0))
        new_level = int(updated.get("level", level))

        evolved, new_stage_data = evolutions.determine_evolution_event(old_stage, new_level)

        if evolved:
            name_slug = new_stage_data.get("name", "").lower().replace(" ", "_")
            gif_path = f"assets/evolutions/{name_slug}/levelup.gif"
            fallback = f"assets/evolutions/{name_slug}/idle.gif"

            try:
                if os.path.exists(gif_path):
                    safe_send_gif(bot, int(user_id), gif_path)
                elif os.path.exists(fallback):
                    safe_send_gif(bot, int(user_id), fallback)

                bot.send_message(
                    int(user_id),
                    f"🎉 You evolved into *{new_stage_data['name']}*! XP × {new_stage_data['xp_multiplier']}",
                    parse_mode="Markdown"
                )
            except:
                pass

            hype = f"🔥 **{message.from_user.first_name}** evolved into **{new_stage_data['name']}**!"
            if os.path.exists(gif_path):
                safe_send_gif(bot, message.chat.id, gif_path)
            bot.send_message(message.chat.id, hype, parse_mode="Markdown")
