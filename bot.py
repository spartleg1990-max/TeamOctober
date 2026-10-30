import logging
import random
import re
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Токен бота и ID администраторов из настроек проекта
TOKEN = "9275964752:AAHhDAMBKHW8WxKrjUv1fKApP3Xa9Jg8GEU"
ADMIN_IDS = {107742498, 92769858}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Постоянные данные (хранятся в памяти бота)
players_pool = set()  # Список всех добавленных игроков (никуда не исчезает без "Очистить список")
player_skills = {}  # Словарь скиллов: {"@username": rating}
excluded_pairs = set()  # Множество пар исключений: замороженные пары в виде фрозен-сетов (frozenset)


# Состояния для FSM (ожидание ввода от админа)
class AdminStates(StatesGroup):
    waiting_for_players = State()
    waiting_for_skills = State()
    waiting_for_exclude_pair = State()
    waiting_for_remove_pair = State()


# Проверка на администратора
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# Главная клавиатура для администраторов
def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить игрока", callback_data="add_players")],
        [InlineKeyboardButton(text="⭐ Оценить скилл игроков", callback_data="set_skills")],
        [InlineKeyboardButton(text="🔀 Собрать состав", callback_data="make_teams")],
        [
            InlineKeyboardButton(
                text="🚫 Пары исключения", callback_data="add_exclude"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Удалить пары исключения", callback_data="remove_exclude"
            )
        ],
        [InlineKeyboardButton(text="🗑 Очистить список игроков", callback_data="clear_list")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Старт и вход в админ-панель
@dp.message(Command("start"))
@dp.message(Command("admin"))
async def cmd_start(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer(
            "⚠️ У вас нет прав администратора для управления ботом."
        )
        return

    text = (
        "⚽ **Панель управления футбольными составами**\n\n"
        f"Игроков в базе: {len(players_pool)}\n"
        f"Оценок скилла задано: {len(player_skills)}\n"
        f"Пар исключений: {len(excluded_pairs)}\n\n"
        "Выберите действие с помощью кнопок ниже:"
    )
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")


# Обработка нажатий на кнопки
@dp.callback_query(
    F.data.in_(
        [
            "add_players",
            "set_skills",
            "make_teams",
            "add_exclude",
            "remove_exclude",
            "clear_list",
        ]
    )
)
async def process_callbacks(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ Недостаточно прав!", show_alert=True)
        return

    action = callback.data

    if action == "add_players":
        await state.set_state(AdminStates.waiting_for_players)
        await callback.message.answer(
            "✍️ Отправьте одним сообщением список игроков через `@username`:\n\n"
            "Пример: `@user1 @user2 @user3`"
        )

    elif action == "set_skills":
        await state.set_state(AdminStates.waiting_for_skills)
        await callback.message.answer(
            "⭐ Отправьте оценку игрока в формате:\n`@username число` (от 1 до 10)\n\n"
            "Пример: `@user1 9`"
        )

    elif action == "add_exclude":
        await state.set_state(AdminStates.waiting_for_exclude_pair)
        await callback.message.answer(
            "🚫 Отправьте двух игроков через `@`, которые **не должны** играть в одной команде:\n\n"
            "Пример: `@user1 @user2`"
        )

    elif action == "remove_exclude":
        await state.set_state(AdminStates.waiting_for_remove_pair)
        await callback.message.answer(
            "❌ Отправьте пару исключения, которую нужно удалить:\n\n"
            "Пример: `@user1 @user2`"
        )

    elif action == "clear_list":
        players_pool.clear()
        await callback.message.answer(
            "🗑 Список игроков очищен! (Скиллы и пары исключений сохранены)."
        )
        await callback.message.answer(
            "Главное меню:", reply_markup=get_admin_keyboard()
        )

    elif action == "make_teams":
        if len(players_pool) < 2:
            await callback.answer(
                "⚠️ Недостаточно игроков для сборки (нужно минимум 2).",
                show_alert=True,
            )
            return

        # Превращаем в список для распределения
        players = list(players_pool)
        random.shuffle(players)

        # Сортируем игроков по скиллу (убывание), по умолчанию 5
        def get_skill(p):
            return player_skills.get(p, 5)

        players.sort(key=get_skill, reverse=True)

        team1 = []
        team2 = []
        sum1 = 0
        sum2 = 0

        # Жадный алгоритм балансировки по среднему арифметическому
        for player in players:
            p_skill = get_skill(player)
            # Проверяем пары исключений перед распределением
            can_go_to_1 = True
            can_go_to_2 = True

            for p in team1:
                if frozenset([player, p]) in excluded_pairs:
                    can_go_to_1 = False
            for p in team2:
                if frozenset([player, p]) in excluded_pairs:
                    can_go_to_2 = False

            # Распределяем на основе суммы скиллов и ограничений
            if len(team1) <= len(team2) and can_go_to_1 and (sum1 <= sum2 or not can_go_to_2):
                team1.append(player)
                sum1 += p_skill
            elif can_go_to_2:
                team2.append(player)
                sum2 += p_skill
            elif can_go_to_1:
                team1.append(player)
                sum1 += p_skill
            else:
                # Если сработали все исключения, принудительно кидаем туда, где меньше народу
                if len(team1) <= len(team2):
                    team1.append(player)
                    sum1 += p_skill
                else:
                    team2.append(player)
                    sum2 += p_skill

        # Формируем красивый отчет
        avg1 = round(sum1 / len(team1), 1) if team1 else 0
        avg2 = round(sum2 / len(team2), 1) if team2 else 0

        text = "🔀 **Сбалансированные составы команд:**\n\n"
        text += f"**Команда 1** (Средний скилл: {avg1}):\n"
        for p in team1:
            text += f"• {p} (скилл: {player_skills.get(p, 5)})\n"

        text += f"\n**Команда 2** (Средний скилл: {avg2}):\n"
        for p in team2:
            text += f"• {p} (скилл: {player_skills.get(p, 5)})\n"

        await callback.message.answer(text, parse_mode="Markdown")
        await callback.message.answer(
            "Главное меню:", reply_markup=get_admin_keyboard()
        )

    await callback.answer()


# Получение списка игроков сообщением
@dp.message(AdminStates.waiting_for_players)
async def save_players(message: types.Message, state: FSMContext):
    usernames = re.findall(r"@[\w_]+", message.text)
    if not usernames:
        await message.answer(
            "⚠️ Не найдено ни одного юзернейма с `@`. Попробуйте еще раз:"
        )
        return

    for u in usernames:
        players_pool.add(u)

    await state.clear()
    await message.answer(
        f"✅ Успешно добавлено/обновлено игроков в пуле: {len(usernames)}.\n"
        f"Всего игроков в базе: {len(players_pool)}",
        reply_markup=get_admin_keyboard(),
    )


# Сохранение скилла игрока
@dp.message(AdminStates.waiting_for_skills)
async def save_skill(message: types.Message, state: FSMContext):
    match = re.search(r"(@[\w_]+)\s+(\d+)", message.text)
    if not match:
        await message.answer(
            "⚠️ Неверный формат. Укажите через пробел, например: `@user1 8`"
        )
        return

    username = match.group(1)
    skill = int(match.group(2))

    if not (1 <= skill <= 10):
        await message.answer("⚠️ Оценка должна быть в диапазоне от 1 до 10!")
        return

    player_skills[username] = skill
    players_pool.add(username)  # Автоматически добавляем в пул, если его там не было

    await state.clear()
    await message.answer(
        f"⭐ Скилл игрока {username} установлен на значение **{skill}** закреплен навсегда!",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown",
    )


# Добавление пары исключения
@dp.message(AdminStates.waiting_for_exclude_pair)
async def save_exclude(message: types.Message, state: FSMContext):
    usernames = re.findall(r"@[\w_]+", message.text)
    if len(usernames) < 2:
        await message.answer(
            "⚠️ Нужно указать ровно двух игроков через `@`. Попробуйте снова:"
        )
        return

    pair = frozenset([usernames[0], usernames[1]])
    excluded_pairs.add(pair)

    await state.clear()
    await message.answer(
        f"🚫 Пара исключений добавлена: **{usernames[0]}** и **{usernames[1]}** не будут играть в одной команде.",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown",
    )


# Удаление пары исключения
@dp.message(AdminStates.waiting_for_remove_pair)
async def remove_exclude(message: types.Message, state: FSMContext):
    usernames = re.findall(r"@[\w_]+", message.text)
    if len(usernames) < 2:
        await message.answer(
            "⚠️ Нужно указать ровно двух игроков через `@` для удаления пары:"
        )
        return

    pair = frozenset([usernames[0], usernames[1]])
    if pair in excluded_pairs:
        excluded_pairs.remove(pair)
        text = f"✅ Пара исключений **{usernames[0]}** и **{usernames[1]}** успешно удалена."
    else:
        text = "⚠️ Такая пара исключений не найдена в списке."

    await state.clear()
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")


if __name__ == "__main__":
    import asyncio

    asyncio.run(dp.start_polling(bot))
