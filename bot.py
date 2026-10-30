import json
import logging
import os
import random
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = "9275964752:AAHhDAMBKHW8WxKrjUv1fKApP3Xa9Jg8GEU"
ADMIN_IDS = {107742498, 92769858}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

DB_FILE = "database.json"

players_pool = set()
player_skills = {}
excluded_pairs = set()


# Загрузка базы из файла
def load_data():
    global players_pool, player_skills, excluded_pairs
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                players_pool = set(data.get("players", []))
                player_skills = data.get("skills", {})
                excluded_pairs = {
                    frozenset(pair) for pair in data.get("exclude_pairs", [])
                }
                logging.info(f"📂 Загружено игроков: {len(players_pool)}")
        except Exception as e:
            logging.error(f"Ошибка загрузки JSON: {e}")


# Сохранение базы в файл
def save_data():
    data = {
        "players": list(players_pool),
        "skills": player_skills,
        "exclude_pairs": [list(pair) for pair in excluded_pairs],
    }
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logging.info(f"💾 База сохранена. Игроков в пуле: {len(players_pool)}")
    except Exception as e:
        logging.error(f"Ошибка сохранения JSON: {e}")


load_data()


# Определение состояний FSM
class AdminStates(StatesGroup):
    waiting_for_players = State()
    waiting_for_skills = State()
    waiting_for_exclude = State()
    waiting_for_remove_exclude = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить игрока", callback_data="add_players")],
        [InlineKeyboardButton(text="⭐ Оценить скилл игроков", callback_data="set_skills")],
        [InlineKeyboardButton(text="🔀 Собрать состав", callback_data="make_teams")],
        [InlineKeyboardButton(text="🚫 Пары исключения", callback_data="add_exclude")],
        [InlineKeyboardButton(text="❌ Удалить пары исключения", callback_data="remove_exclude")],
        [InlineKeyboardButton(text="🗑 Очистить список игроков", callback_data="clear_list")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@dp.message(Command("start"))
@dp.message(Command("admin"))
async def cmd_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    text = (
        "⚽ **Панель управления футбольными составами**\n\n"
        f"👥 Игроков в базе: **{len(players_pool)}**\n"
        f"⭐ Оценок скилла: {len(player_skills)}\n"
        f"🚫 Пар исключений: {len(excluded_pairs)}\n\n"
        "Выберите действие с помощью кнопок ниже:"
    )
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")


# Кнопка: Добавить игрока
@dp.callback_query(F.data == "add_players")
async def cb_add_players(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_for_players)
    await callback.message.answer(
        "✍️ **Режим добавления игроков активирован.**\n\n"
        "Отправьте списком имена или юзернеймы через пробел или с новой строки:\n"
        "Пример: `Егор @Rmgild Vladimir @SereginS2`"
    )
    await callback.answer()


# Кнопка: Оценить скилл
@dp.callback_query(F.data == "set_skills")
async def cb_set_skills(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.waiting_for_skills)
    await callback.message.answer(
        "⭐ Отправьте оценку игрока в формате: `Имя число` (от 1 до 10)\nПример: `Егор 9`"
    )
    await callback.answer()


# Кнопка: Пары исключения
@dp.callback_query(F.data == "add_exclude")
async def cb_add_exclude(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.waiting_for_exclude)
    await callback.message.answer(
        "🚫 Отправьте двух игроков через пробел, которые не должны играть вместе:\nПример: `Егор Vladimir`"
    )
    await callback.answer()


# Кнопка: Удалить пары исключения
@dp.callback_query(F.data == "remove_exclude")
async def cb_remove_exclude(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.waiting_for_remove_exclude)
    await callback.message.answer(
        "❌ Отправьте двух игроков через пробел для удаления пары исключения:"
    )
    await callback.answer()


# Кнопка: Очистить список игроков
@dp.callback_query(F.data == "clear_list")
async def cb_clear(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    players_pool.clear()
    save_data()
    await callback.message.answer(
        "🗑 Список игроков очищен! (Скиллы и пары сохранены).",
        reply_markup=get_admin_keyboard(),
    )
    await callback.answer()


# Кнопка: Собрать состав
@dp.callback_query(F.data == "make_teams")
async def cb_make_teams(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    
    if len(players_pool) < 2:
        await callback.answer(
            f"⚠️ Недостаточно игроков для сборки (сейчас в базе: {len(players_pool)}, нужно минимум 2).",
            show_alert=True,
        )
        return

    players = list(players_pool)
    random.shuffle(players)

    def get_skill(p):
        return player_skills.get(p, 5)

    # Сортируем по убыванию скилла для балансировки
    players.sort(key=get_skill, reverse=True)

    team1, team2 = [], []
    sum1, sum2 = 0, 0

    for player in players:
        p_skill = get_skill(player)
        can_go_1 = all(frozenset([player, p]) not in excluded_pairs for p in team1)
        can_go_2 = all(frozenset([player, p]) not in excluded_pairs for p in team2)

        if len(team1) <= len(team2) and can_go_1 and (sum1 <= sum2 or not can_go_2):
            team1.append(player)
            sum1 += p_skill
        elif can_go_2:
            team2.append(player)
            sum2 += p_skill
        elif can_go_1:
            team1.append(player)
            sum1 += p_skill
        else:
            if len(team1) <= len(team2):
                team1.append(player)
                sum1 += p_skill
            else:
                team2.append(player)
                sum2 += p_skill

    avg1 = round(sum1 / len(team1), 1) if team1 else 0
    avg2 = round(sum2 / len(team2), 1) if team2 else 0

    text = "🔀 **Сбалансированные составы команд:**\n\n"
    text += f"**Команда 1** (Средний скилл: {avg1}):\n"
    for p in team1:
        text += f"{p}\n"
    text += f"\n**Команда 2** (Средний скилл: {avg2}):\n"
    for p in team2:
        text += f"{p}\n"

    await callback.message.answer(text, parse_mode="Markdown", reply_markup=get_admin_keyboard())
    await callback.answer()


# ОБРАБОТЧИК СОСТОЯНИЯ: Сохранение игроков
@dp.message(AdminStates.waiting_for_players)
async def process_players(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    tokens = []
    for line in message.text.split("\n"):
        for word in line.split():
            cleaned = word.strip(",.;:!?")
            if cleaned:
                tokens.append(cleaned)
    
    if not tokens:
        await message.answer("⚠️ Список пустой. Отправьте имена игроков еще раз:")
        return

    for t in tokens:
        players_pool.add(t)
    
    save_data()
    await state.clear()
    
    added_str = ", ".join(tokens)
    await message.answer(
        f"✅ **Игроки успешно добавлены в базу!**\n\n"
        f"Добавлены: {added_str}\n"
        f"👥 **Всего игроков в базе: {len(players_pool)}**",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown",
    )


# ОБРАБОТЧИК СОСТОЯНИЯ: Сохранение скиллов
@dp.message(AdminStates.waiting_for_skills)
async def process_skills(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[-1].isdigit() or not (1 <= int(parts[-1]) <= 10):
        await message.answer("⚠️ Неверный формат. Пример: `Егор 8`")
        return
    skill = int(parts[-1])
    name = " ".join(parts[:-1])
    player_skills[name] = skill
    players_pool.add(name)
    save_data()
    await state.clear()
    await message.answer(
        f"⭐ Скилл игрока **{name}** установлен на **{skill}**!",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown",
    )


# ОБРАБОТЧИК СОСТОЯНИЯ: Добавление пары исключения
@dp.message(AdminStates.waiting_for_exclude)
async def process_exclude(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    tokens = [w.strip(",.;:!?") for w in message.text.split() if w.strip(",.;:!?")]
    if len(tokens) < 2:
        await message.answer("⚠️ Укажите ровно двух игроков через пробел:")
        return
    pair = frozenset([tokens[0], tokens[1]])
    excluded_pairs.add(pair)
    save_data()
    await state.clear()
    await message.answer(
        f"🚫 Пара исключений добавлена: **{tokens[0]}** и **{tokens[1]}**",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown",
    )


# ОБРАБОТЧИК СОСТОЯНИЯ: Удаление пары исключения
@dp.message(AdminStates.waiting_for_remove_exclude)
async def process_remove_exclude(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    tokens = [w.strip(",.;:!?") for w in message.text.split() if w.strip(",.;:!?")]
    if len(tokens) < 2:
        await message.answer("⚠️ Укажите двух игроков:")
        return
    pair = frozenset([tokens[0], tokens[1]])
    if pair in excluded_pairs:
        excluded_pairs.remove(pair)
        save_data()
        resp = f"✅ Пара исключений успешно удалена."
    else:
        resp = "⚠️ Такая пара исключений не найдена."
    await state.clear()
    await message.answer(resp, reply_markup=get_admin_keyboard(), parse_mode="Markdown")


if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
