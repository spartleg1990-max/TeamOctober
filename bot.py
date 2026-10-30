import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# === ТВОИ ДАННЫЕ И АДМИНЫ ===
BOT_TOKEN = "9275964752:AAHhDAMBKHW8WxKrjUv1fKApP3Xa9Jg8GEU"
ADMIN_IDS = [107742498, 92769858]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# === БАЗА ДАННЫХ В ПАМЯТИ ===
players_queue = []  # Список записавшихся: [{"id": int, "username": str, "num": int}]
ratings = {}  # Уровень игроков: {"@username": skill_1_to_10}
forbidden_pairs = []  # Несовместимые пары: [("@user1", "@user2")]


class AdminState(StatesGroup):
    waiting_for_manual_add = State()
    waiting_for_pair = State()
    waiting_for_skill = State()


# === ВСПОМОГАТЕЛЬНЫЕ КЛАВИАТУРЫ ===
def get_admin_keyboard():
    kb = [
        [
            InlineKeyboardButton(
                text="⚽ Собрать Состав", callback_data="generate_teams"
            )
        ],
        [
            InlineKeyboardButton(
                text="➕ Добавить игрока", callback_data="add_manual_player"
            )
        ],
        [
            InlineKeyboardButton(
                text="⛔ Пары-исключения", callback_data="manage_pairs"
            )
        ],
        [
            InlineKeyboardButton(
                text="⭐ Оценить скилл игроков", callback_data="manage_skills"
            )
        ],
        [
            InlineKeyboardButton(
                text="🗑 Очистить список", callback_data="clear_queue"
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# === ОБРАБОТКА ЗАПИСИ (ЦИФРА 1-16) ===
@dp.message(F.text.cast(int) <= 16, F.text.cast(int) >= 1)
async def register_player(message: types.Message):
    num = int(message.text)
    user = message.from_user
    username = f"@{user.username}" if user.username else user.full_name

    # Проверка на повторную запись
    for p in players_queue:
        if p["id"] == user.id:
            p["num"] = num
            await message.reply(f"🔄 {username}, твой номер обновлен на {num}!")
            return

    players_queue.append({"id": user.id, "username": username, "num": num})
    await message.reply(
        f"✅ {username} записался под №{num}! Всего игроков: {len(players_queue)}"
    )


# === КОМАНДА /admin ИЛИ ВЫЗОВ ПАНЕЛИ ===
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав администратора.")
        return
    await message.reply("⚙ **Панель Администратора:**", reply_markup=get_admin_keyboard())


# === РУЧНОЕ ДОБАВЛЕНИЕ ИГРОКА ===
@dp.callback_query(F.data == "add_manual_player")
async def process_manual_add(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Введи username игрока (например, `@username`):"
    )
    await state.set_state(AdminState.waiting_for_manual_add)
    await callback.answer()


@dp.message(AdminState.waiting_for_manual_add)
async def save_manual_player(message: types.Message, state: FSMContext):
    username = message.text.strip()
    if not username.startswith("@"):
        username = "@" + username

    players_queue.append(
        {"id": random.randint(1000, 9999), "username": username, "num": 0}
    )
    await message.reply(
        f"✅ Игрок {username} добавлен вручную! Всего: {len(players_queue)}"
    )
    await state.clear()


# === НАСТРОЙКА ИСКЛЮЧЕНИЙ ПАР ===
@dp.callback_query(F.data == "manage_pairs")
async def process_pairs_menu(callback: types.CallbackQuery, state: FSMContext):
    pairs_text = "\n".join([f"• {p[0]} и {p[1]}" for p in forbidden_pairs]) or "Нет"
    await callback.message.answer(
        f"Текущие запрещенные пары:\n{pairs_text}\n\n"
        "Введи 2 юзернейма через пробел, чтобы развести их по командам:\n*(Пример: `@alex @ivan`)*"
    )
    await state.set_state(AdminState.waiting_for_pair)
    await callback.answer()


@dp.message(AdminState.waiting_for_pair)
async def save_pair(message: types.Message, state: FSMContext):
    parts = message.text.split()
    if len(parts) == 2:
        u1, u2 = (
            parts[0] if parts[0].startswith("@") else "@" + parts[0],
            parts[1] if parts[1].startswith("@") else "@" + parts[1],
        )
        forbidden_pairs.append((u1, u2))
        await message.reply(f"⛔ Пара {u1} и {u2} не будет попадать в одну команду!")
    else:
        await message.reply("❌ Ошибка. Введи ровно два ника через пробел.")
    await state.clear()


# === ОЦЕНКА СКИЛЛА (1-10) ===
@dp.callback_query(F.data == "manage_skills")
async def process_skills_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Введи ник и оценку от 1 до 10 через пробел:\n*(Пример: `@pavel 8`)*"
    )
    await state.set_state(AdminState.waiting_for_skill)
    await callback.answer()


@dp.message(AdminState.waiting_for_skill)
async def save_skill(message: types.Message, state: FSNContext if 'FSNContext' in globals() else FSMContext):
    try:
        username, score = message.text.split()
        score = int(score)
        if 1 <= score <= 10:
            if not username.startswith("@"):
                username = "@" + username
            ratings[username] = score
            await message.reply(f"⭐ Для {username} установлен скилл: {score}/10")
        else:
            await message.reply("Скилл должен быть от 1 до 10.")
    except Exception:
        await message.reply("Ошибка формата. Пример ввода: `@pavel 8`")
    await state.clear()


# === РАСЧЕТ И СБОР КОМАНД ===
@dp.callback_query(F.data == "generate_teams")
async def generate_teams(callback: types.CallbackQuery):
    if len(players_queue) < 2:
        await callback.message.answer("Слишком мало игроков для сборки составов!")
        await callback.answer()
        return

    active_players = [p["username"] for p in players_queue]

    best_t1, best_t2 = [], []
    best_diff = float("inf")

    for _ in range(200):
        shuffled = active_players.copy()
        random.shuffle(shuffled)

        half = len(shuffled) // 2
        t1, t2 = shuffled[:half], shuffled[half:]

        conflict = False
        for u1, u2 in forbidden_pairs:
            if (u1 in t1 and u2 in t1) or (u1 in t2 and u2 in t2):
                conflict = True
                break
        if conflict:
            continue

        s1 = sum(ratings.get(u, 5) for u in t1)
        s2 = sum(ratings.get(u, 5) for u in t2)
        diff = abs(s1 - s2)

        if diff < best_diff:
            best_diff = diff
            best_t1, best_t2 = t1, t2

    if not best_t1:
        half = len(active_players) // 2
        best_t1, best_t2 = active_players[:half], active_players[half:]

    text = "⚽ **Составы сформированы!**\n\n"
    text += "🔴 **Команда 1:**\n" + "\n".join(best_t1) + "\n\n"
    text += "🔵 **Команда 2:**\n" + "\n".join(best_t2)

    await callback.message.answer(text)
    await callback.answer()


@dp.callback_query(F.data == "clear_queue")
async def clear_queue(callback: types.CallbackQuery):
    players_queue.clear()
    await callback.message.answer("🧹 Список игроков полностью очищен!")
    await callback.answer()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
