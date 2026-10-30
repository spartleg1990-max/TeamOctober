import logging
import random
import json
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = "9275964752:AAHhDAMBKHW8WxKrjUv1fKApP3Xa9Jg8GEU"
ADMIN_IDS = {107742498, 92769858}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

DATA_FILE = "bot_database.json"

PLAYERS_POOL = set()
PLAYER_SKILLS = {}
EXCLUDED_PAIRS = set()
USER_STATES = {}


def load_data():
    global PLAYERS_POOL, PLAYER_SKILLS, EXCLUDED_PAIRS
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                PLAYERS_POOL = set(data.get("players", []))
                PLAYER_SKILLS = data.get("skills", {})
                EXCLUDED_PAIRS = {frozenset(pair) for pair in data.get("excludes", [])}
        except Exception as e:
            logging.error(f"Ошибка загрузки данных: {e}")


def save_data():
    try:
        data = {
            "players": list(PLAYERS_POOL),
            "skills": PLAYER_SKILLS,
            "excludes": [list(pair) for pair in EXCLUDED_PAIRS]
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения данных: {e}")


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить игроков", callback_data="add_players")],
        [InlineKeyboardButton(text="⭐ Оценить скилл игроков", callback_data="set_skills")],
        [InlineKeyboardButton(text="📋 Проверить скиллы", callback_data="check_skills")],
        [InlineKeyboardButton(text="🔀 Собрать команду", callback_data="make_teams")],
        [InlineKeyboardButton(text="🚫 Пары исключения", callback_data="add_exclude")],
        [InlineKeyboardButton(text="❌ Удалить пары исключения", callback_data="remove_exclude")],
        [InlineKeyboardButton(text="🗑 Очистить список игроков", callback_data="clear_list")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@dp.message(Command("start"))
@dp.message(Command("admin"))
async def cmd_start(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    USER_STATES.pop(message.from_user.id, None)
    
    text = (
        "⚽ **Панель управления футбольными составами**\n\n"
        f"👥 Игроков в базе матча: **{len(PLAYERS_POOL)}**\n"
        f"⭐ Оценок скилла в базе: **{len(PLAYER_SKILLS)}**\n"
        f"🚫 Пар исключений: {len(EXCLUDED_PAIRS)}\n\n"
        "Выберите действие с помощью кнопок ниже:"
    )
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")


@dp.callback_query(F.data == "add_players")
async def cb_add_players(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    USER_STATES[callback.from_user.id] = "WAITING_PLAYERS"
    await callback.message.answer("✍️ Кого добавляем? Отправьте список игроков (через пробел или с новой строки):")
    await callback.answer()


@dp.callback_query(F.data == "set_skills")
async def cb_skills(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    USER_STATES[callback.from_user.id] = "WAITING_SKILL"
    await callback.message.answer("⭐ Введите имя и цифру скилла от 1 до 10 (например: Олег 5):")
    await callback.answer()


@dp.callback_query(F.data == "add_exclude")
async def cb_exclude(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    USER_STATES[callback.from_user.id] = "WAITING_EXCLUDE"
    await callback.message.answer("🚫 Отправьте двух игроков через пробел, которые не должны играть вместе (например: Олег Макс):")
    await callback.answer()


@dp.callback_query(F.data == "remove_exclude")
async def cb_remove_exclude(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    USER_STATES[callback.from_user.id] = "WAITING_REMOVE_EXCLUDE"
    await callback.message.answer("❌ Отправьте двух игроков через пробел для удаления из пар исключения:")
    await callback.answer()


@dp.callback_query(F.data == "check_skills")
async def cb_check_skills(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    USER_STATES.pop(callback.from_user.id, None)
    if not PLAYER_SKILLS:
        text = "⭐ Список скиллов пока пустой."
    else:
        text = "⭐ **Список всех оцененных игроков:**\n\n"
        for name, skill in sorted(PLAYER_SKILLS.items(), key=lambda x: x[1], reverse=True):
            text += f"• {name} — **{skill}**\n"
    await callback.message.answer(text, parse_mode="Markdown", reply_markup=get_admin_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "clear_list")
async def cb_clear(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    USER_STATES.pop(callback.from_user.id, None)
    PLAYERS_POOL.clear()
    save_data()
    await callback.message.answer("🗑 Список игроков на матч очищен.", reply_markup=get_admin_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "make_teams")
async def cb_make_teams(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    USER_STATES.pop(callback.from_user.id, None)

    if len(PLAYERS_POOL) < 2:
        await callback.answer(f"⚠️ Недостаточно игроков (сейчас: {len(PLAYERS_POOL)}, нужно мин. 2).", show_alert=True)
        return

    players = list(PLAYERS_POOL)
    
    def get_skill(p):
        return PLAYER_SKILLS.get(p, 5)

    def check_excludes(team):
        for i in range(len(team)):
            for j in range(i + 1, len(team)):
                if frozenset([team[i], team[j]]) in EXCLUDED_PAIRS:
                    return False
        return True

    best_team1, best_team2 = [], []
    best_diff = 999
    target_size = len(players) // 2

    for _ in range(1000):
        random.shuffle(players)
        t1 = players[:target_size]
        t2 = players[target_size:]
        
        if abs(len(t1) - len(t2)) > 1:
            continue
            
        if check_excludes(t1) and check_excludes(t2):
            s1 = sum(get_skill(p) for p in t1)
            s2 = sum(get_skill(p) for p in t2)
            diff = abs(s1 - s2)
            
            if diff < best_diff:
                best_diff = diff
                best_team1, best_team2 = t1, t2
                if diff == 0:
                    break

    if not best_team1:
        best_team1 = players[:target_size]
        best_team2 = players[target_size:]

    sum1 = sum(get_skill(p) for p in best_team1)
    sum2 = sum(get_skill(p) for p in best_team2)
    avg1 = round(sum1 / len(best_team1), 1) if best_team1 else 0
    avg2 = round(sum2 / len(best_team2), 1) if best_team2 else 0

    text = "🔀 **Сбалансированные составы команд:**\n\n"
    
    text += f"**Команда 1** (Средний скилл: {avg1}):\n"
    for idx, p in enumerate(best_team1, 1):
        text += f"{idx}) {p} (скилл: {get_skill(p)})\n"
        
    text += f"\n**Команда 2** (Средний скилл: {avg2}):\n"
    for idx, p in enumerate(best_team2, 1):
        text += f"{idx}) {p} (скилл: {get_skill(p)})\n"

    await callback.message.answer(text, parse_mode="Markdown", reply_markup=get_admin_keyboard())
    await callback.answer()


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    current_state = USER_STATES.get(user_id)

    if not current_state:
        return

    text = message.text.strip()
    parts = text.split()

    if current_state == "WAITING_PLAYERS":
        names = []
        for line in text.split("\n"):
            for word in line.split():
                cleaned = word.strip(",.;:!?")
                if cleaned:
                    names.append(cleaned)
        
        if names:
            for name in names:
                PLAYERS_POOL.add(name)
            save_data()
        
        USER_STATES.pop(user_id, None)
        await message.answer(f"✅ Добавлено! Всего игроков в базе: {len(PLAYERS_POOL)}", reply_markup=get_admin_keyboard())
        return

    if current_state == "WAITING_SKILL":
        if len(parts) >= 2 and parts[-1].isdigit() and 1 <= int(parts[-1]) <= 10:
            skill = int(parts[-1])
            name = " ".join(parts[:-1])
            PLAYER_SKILLS[name] = skill
            save_data()
            USER_STATES.pop(user_id, None)
            await message.answer(f"⭐ Сохранено: {name} — {skill}", reply_markup=get_admin_keyboard())
        else:
            await message.answer("⚠️ Неверный формат. Введите имя и цифру скилла от 1 до 10 (например: Олег 5):")
        return

    if current_state == "WAITING_EXCLUDE":
        if len(parts) == 2 and not parts[0].isdigit() and not parts[1].isdigit():
            pair = frozenset([parts[0], parts[1]])
            EXCLUDED_PAIRS.add(pair)
            save_data()
            USER_STATES.pop(user_id, None)
            await message.answer(f"🚫 Пара исключения добавлена: {parts[0]} и {parts[1]}", reply_markup=get_admin_keyboard())
        else:
            await message.answer("⚠️ Введите ровно два имени через пробел:")
        return

    if current_state == "WAITING_REMOVE_EXCLUDE":
        if len(parts) == 2 and not parts[0].isdigit() and not parts[1].isdigit():
            pair = frozenset([parts[0], parts[1]])
            if pair in EXCLUDED_PAIRS:
                EXCLUDED_PAIRS.remove(pair)
                save_data()
                await message.answer(f"✅ Пара исключения удалена: {parts[0]} и {parts[1]}", reply_markup=get_admin_keyboard())
            else:
                await message.answer("⚠️ Такая пара не найдена в списке.")
            USER_STATES.pop(user_id, None)
        else:
            await message.answer("⚠️ Введите ровно два имени через пробел:")
        return


if __name__ == "__main__":
    import asyncio
    load_data()
    asyncio.run(dp.start_polling(bot))
