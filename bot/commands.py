import os
import random
from datetime import datetime, timedelta
from telebot import TeleBot

from bot.db import get_user, update_user_xp, get_quests, record_quest
from bot.images import generate_profile_image, generate_leaderboard_image
from bot.mobs import MOBS
from bot.utils import safe_send_gif
from bot.grokdex import GROKDEX


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


# ---------------------------------------------------------
# XP SYSTEM HELPERS
# ---------------------------------------------------------

def xp_needed_for_level(level: int, factor: float = 1.15):
    base = 200
    return int(base * (factor ** (level - 1)))


def xp_bar(current, needed, length=12):
    pct = current / needed
    filled = int(length * pct)
    empty = length - filled
    return f"⚡【{'█' * filled}{'▒' * empty}】⚡"


GROW_COOLDOWN_MINUTES = 30
last_grow_use = {}


def process_xp(user, xp_change: int):
    """
    Applies XP change and returns (new_user_data, leveled_up, levels_gained)
    Uses:
      - xp_current
      - xp_total
      - xp_to_next_level
    """

    # Extract current values
    xp_total = user["xp_total"]
    xp_current = user["xp_current"]
    xp_needed = user["xp_to_next_level"]
    level = user["level"]
    factor = user.get("level_curve_factor", 1.15)

    # Apply XP gain/loss
    xp_total += max(0, xp_change)  # total XP never decreases
    xp_current += xp_change

    # Clamp XP floor
    if xp_current < 0:
        xp_current = 0

    # Handle multi-level leveling
    levels_gained = 0
    leveled_up = False

    while xp_current >= xp_needed:
        xp_current -= xp_needed
        level += 1
        levels_gained += 1
        xp_needed = xp_needed_for_level(level, factor)
        leveled_up = True

    # Prepare updated dict for DB
    updated_user = {
        "xp_total": xp_total,
        "xp_current": xp_current,
        "xp_to_next_level": xp_needed,
        "level": level
    }

    return updated_user, leveled_up, levels_gained


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

    # ---------------- GROW (NEW SYSTEM) ----------------
    @bot.message_handler(commands=['growmygrok'])
    def growmygrok(message):
        user_id = message.from_user.id
        now = datetime.now()

        # Cooldown check
        if user_id in last_grow_use:
            next_ok = last_grow_use[user_id] + timedelta(minutes=GROW_COOLDOWN_MINUTES)
            if now < next_ok:
                remain = int((next_ok - now).total_seconds() // 60)
                bot.reply_to(message, f"⏳ Your Grok is still digesting cosmic energy… ({remain} min left)")
                return

        last_grow_use[user_id] = now

        # XP gain/loss roll
        outcome = random.choice(["gain", "gain", "gain", "loss"])
        xp_change = random.randint(15, 35) if outcome == "gain" else -random.randint(5, 20)

        # Get user
        user = get_user(user_id)

        # Process XP through new system
        updated_user, leveled_up, levels_gained = process_xp(user, xp_change)

        # Update DB
        update_user_xp(user_id, updated_user)

        # Prepare response visuals
        xp_current = updated_user["xp_current"]
        xp_needed = updated_user["xp_to_next_level"]
        level = updated_user["level"]

        bar = xp_bar(xp_current, xp_needed)

        # Text
        if xp_change >= 0:
            change_text = f"✨ Your MegaGrok grew! +{xp_change} XP"
        else:
            change_text = f"💀 Your Grok stumbled in the Hop-Verse… {xp_change} XP"

        msg = (
            f"{change_text}\n\n"
            f"**Level {level}**\n"
            f"{bar}\n"
            f"XP: {xp_current}/{xp_needed}"
        )

        if leveled_up:
            msg = (
                f"🎉 *LEVEL UP!* Your MegaGrok ascended **{levels_gained} levels!**\n\n" +
                msg
            )

        bot.reply_to(message, msg, parse_mode="Markdown")

    # ---------------- HOP ----------------
    @bot.message_handler(commands=['hop'])
    def hop(message):
        user_id = message.from_user.id
        quests = get_quests(user_id)

        if quests["hop"] == 1:
            bot.reply_to(message, "🐸 You've already performed your Hop Ritual today!")
            return

        xp_gain = random.randint(20, 50)
        user = get_user(user_id)

        updated_user, _, _ = process_xp(user, xp_gain)
        update_user_xp(user_id, updated_user)

        record_quest(user_id, "hop")

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

        mob_name = mob["name"]
        mob_intro = mob["intro"]
        mob_portrait = mob["portrait"]
        mob_gif = mob["gif"]

        bot.reply_to(message, f"⚔️ **{mob_name} Encounter!**\n\n{mob_intro}")

        try:
            with open(mob_portrait, "rb") as img:
                bot.send_photo(message.chat.id, img)
        except:
            bot.reply_to(message, "⚠️ Failed to load mob portrait.")

        win = random.choice([True, False])

        if win:
            xp = random.randint(mob["min_xp"], mob["max_xp"])
            outcome_text = mob["win_text"]
        else:
            xp = random.randint(10, 25)
            outcome_text = mob["lose_text"]

        safe_send_gif(bot, message.chat.id, mob_gif)

        # Apply XP
        user = get_user(user_id)
        updated_user, _, _ = process_xp(user, xp)
        update_user_xp(user_id, updated_user)

        record_quest(user_id, "fight")

        bot.send_message(
            message.chat.id,
            f"{outcome_text}\n\n✨ **XP Gained:** {xp}"
        )

    # ---------------- PROFILE ----------------
    @bot.message_handler(commands=['profile'])
    def profile(message):
        user_id = message.from_user.id
        user = get_user(user_id)

        try:
            img_path = generate_profile_image(user)
            with open(img_path, "rb") as f:
                bot.send_photo(message.chat.id, f)
        except Exception as e:
            bot.reply_to(message, f"Error generating profile: {e}")

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

    # ---------------- SPECIFIC MOB INFO ----------------
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
