import os
import random
from bot.db import get_db, init_db
from bot.quests import get_quests
from bot.fights import choose_enemy, pick_fight_gif
from bot.images import generate_profile_card
from bot.evolutions import evolve

# Initialize DB on import
init_db()

def register_handlers(bot):

    @bot.message_handler(commands=['start'])
    def start(message):
        bot.reply_to(message, "🐸 Welcome to MegaGrok! Use /help to see commands.")

    @bot.message_handler(commands=['help'])
    def help_cmd(message):
        help_text = (
            "🐸 MegaGrok Commands\n"
            "/start - Start\n"
            "/help - This menu\n"
            "/growmygrok - Gain XP\n"
            "/hop - Daily hop (1/day)\n"
            "/fight - Battle a mob (1/day)\n"
            "/profile - View your profile card\n"
            "/leaderboard - Top players\"
        )
        bot.reply_to(message, help_text)

    def get_user_row(user_id, username=None):
        conn, cursor = get_db()
        cursor.execute("SELECT user_id, xp, level, form, username FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO users (user_id, xp, level, form, username) VALUES (?, 0, 1, 'Tadpole', ?)", (user_id, username))
            conn.commit()
            cursor.execute("SELECT user_id, xp, level, form, username FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
        conn.close()
        return row

    def update_user_row(user_id, xp, level, form, username=None):
        conn, cursor = get_db()
        cursor.execute("UPDATE users SET xp = ?, level = ?, form = ?, username = ? WHERE user_id = ?", (xp, level, form, username, user_id))
        conn.commit()
        conn.close()

    @bot.message_handler(commands=['growmygrok'])
    def grow(message):
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name or str(user_id)
        row = get_user_row(user_id, username)
        xp = row['xp']
        level = row['level']
        gain = random.randint(5,35)
        xp += gain
        while xp >= 200:
            xp -= 200
            level += 1
        form = evolve(level)
        update_user_row(user_id, xp, level, form, username)
        bot.reply_to(message, f"✨ +{gain} XP — Level {level} | {xp}/200 XP")

    @bot.message_handler(commands=['hop'])
    def hop(message):
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name or str(user_id)
        row = get_user_row(user_id, username)
        quests = get_quests(user_id)
        if quests['hop'] == 1:
            bot.reply_to(message, "You've already done /hop today!")
            return
        gain = random.randint(20,50)
        xp = row['xp'] + gain
        level = row['level']
        while xp >= 200:
            xp -= 200
            level += 1
        form = evolve(level)
        update_user_row(user_id, xp, level, form, username)
        conn, cursor = get_db()
        cursor.execute("UPDATE daily_quests SET quest_hop = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"🐸 Hop ritual +{gain} XP — Level {level} | {xp}/200 XP")

    @bot.message_handler(commands=['fight'])
    def fight(message):
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name or str(user_id)
        row = get_user_row(user_id, username)
        quests = get_quests(user_id)
        if quests['fight'] == 1:
            bot.reply_to(message, "⚔️ You've already fought today!")
            return
        enemy, min_xp, max_xp = choose_enemy()
        outcome = random.choices(['win','crit','dodge','lose','loot'], weights=[55,8,12,15,10], k=1)[0]
        if outcome == 'crit':
            gain = random.randint(max_xp, max_xp+150)
            text = f"💥 CRITICAL! You obliterated the {enemy}! +{gain} XP"
        elif outcome == 'dodge':
            gain = random.randint(20,40)
            text = f"🌀 You dodged the {enemy}! +{gain} XP"
        elif outcome == 'lose':
            gain = random.randint(-10,10)
            text = f"😵 You got hit by the {enemy}. {gain:+} XP"
        elif outcome == 'loot':
            gain = random.randint(30,70)
            loot = random.choice(['Hop Crystal','Cosmic Pebble','FUD Shield'])
            text = f"🎁 LOOT: {loot}! +{gain} XP"
        else:
            gain = random.randint(min_xp, max_xp)
            text = f"⚡ Victory vs {enemy}! +{gain} XP"
        xp = row['xp'] + gain
        level = row['level']
        while xp >= 200:
            xp -= 200
            level += 1
        form = evolve(level)
        update_user_row(user_id, xp, level, form, username)
        conn, cursor = get_db()
        cursor.execute("UPDATE daily_quests SET quest_fight = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        from bot.fights import pick_fight_gif
        gif_path = pick_fight_gif()
        if gif_path:
            try:
                with open(gif_path, 'rb') as g:
                    bot.send_animation(message.chat.id, g)
            except Exception:
                pass
        bot.reply_to(message, text)

    @bot.message_handler(commands=['profile'])
    def profile(message):
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name or str(user_id)
        row = get_user_row(user_id, username)
        xp = row['xp']; level = row['level']
        path = generate_profile_card(username, level, xp)
        try:
            with open(path, 'rb') as f:
                bot.send_photo(message.chat.id, f)
        except Exception as e:
            bot.reply_to(message, f"Could not generate profile: {e}")

    @bot.message_handler(commands=['leaderboard'])
    def leaderboard(message):
        conn, cursor = get_db()
        cursor.execute("SELECT username, xp, level, form FROM users ORDER BY level DESC, xp DESC LIMIT 10")
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            bot.reply_to(message, "No players yet.")
            return
        lines = ["🏆 MegaGrok Leaderboard 🐸\n"]
        rank = 1
        for r in rows:
            name = r['username'] or 'anonymous'
            lines.append(f"{rank}. {name} — Lv{r['level']} {r['form']} — {r['xp']} XP")
            rank += 1
        bot.reply_to(message, "\n".join(lines))
