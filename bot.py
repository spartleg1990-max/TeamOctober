import json
import logging
import random
import re
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

def load_data():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return (
                set(data.get("players", [])),
                data.get("skills", {}),
                {frozenset(pair) for pair in data.get("exclude_pairs", [])},
            )
    except (FileNotFoundError, json.JSONDecodeError):
        return set(), {}, set()

def save_data():
    data = {
        "players": list(players_pool),
        "skills": player_skills,
        "exclude_pairs": [list(pair) for pair in excluded_pairs],
    }
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

players_pool, player_skills, excluded_pairs = load_data()


class AdminStates(StatesGroup):
    waiting_for_players = State()
    waiting_for_skills = State()
    waiting_for_exclude_pair = State()
    waiting_for_remove_pair = State()


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
async def cmd_start(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⚠️ У вас нет прав администратора.")
        return

    text = (
        "⚽ **Панель управления футбольными составами**\n\n"
        f"👥 Игроков в базе: **{len(players_pool)}**\n"
        f"⭐ Оценок скилла: {len(player_skills)}\n"
        f"🚫 Пар исключений: {len(excluded_pairs)}\n\n"
        "Выберите действие с помощью кнопок ниже:"
    )
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")


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
            "✍️ Отправьте список игроков (имена или юзернеймы через пробел/строку):\n\n"
            "Пример: `Егор @Rmgild Vladimir @SereginS2`"
        )

    elif action == "set_skills":
        await state.set_state(AdminStates.waiting_for_skills)
        await callback.message.answer(
            "⭐ Отправьте оценку игрока в формате:\n`Имя_или_юзернейм число` (от 1 до 10)\n\n"
            "Пример: `Егор 9` или `@Rmgild 10`"
        )

    elif action == "add_exclude":
        await state.set_state(AdminStates.waiting_for_exclude_pair)
        await callback.message.answer(
            "🚫 Отправьте двух игроков через пробел, которые **не должны** играть в одной команде:\n\n"
            "Пример: `Егор Vladimir`"
        )

    elif action == "remove_exclude":
        await state.set_state(AdminStates.waiting_for_remove_pair)
        await callback.message.answer(
            "❌ Отправьте пару исключения, которую нужно удалить:\n\n"
            "Пример: `Егор Vladimir`"
        )

    elif action == "clear_list":
        players_pool.clear()
        save_data()
        await callback.message.answer(
            "🗑 Список игроков очищен! (Скиллы и пары исключений сохранены)."
        )
        await callback.message.answer("Главное меню:", reply_markup=get_admin_keyboard())

    elif action == "make_teams":
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

        players.sort(key=get_skill, reverse=True)

        team1 = []
        team2 = []
        sum1 = 0
        sum2 = 0

        for player in players:
            p_skill = get_skill(player)
            can_go_to_1 = True
            can_go_to_2 = True

            for p in team1:
                if frozenset([player, p]) in excluded_pairs:
                    can_go_to_1 = False
            for p in team2:
                if frozenset([player, p]) in excluded_pairs:
                    can_go_to_2 = False

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
            text += f"• {p} (скилл: {player_skills.get(p, 5)})\n"

        text += f"\n**Команда 2** (Средний скилл: {avg2}):\n"
        for p in team2:
            text += f"• {p} (скилл: {player_skills.get(p, 5)})\n"

        await callback.message.answer(text, parse_mode="Markdown")
        await callback.message.answer("Главное меню:", reply_markup=get_admin_keyboard())

    await callback.answer()


# Универсальная функция извлечения всех слов/токенов из текста
def extract_players_list(text: str) -> set:
    if not text:
        return set()
    tokens = text.split()
    found = set()
    for token in tokens:
        cleaned = token.strip(",.;:!?")
        if cleaned:
            found.add(cleaned)
    return found


@dp.message(AdminStates.waiting_for_players)
async def save_players(message: types.Message, state: FSMContext):
    players = extract_players_list(message.text)
    
    if not players:
        await message.answer("⚠️ Список пустой. Отправьте имена или юзернеймы игроков:")
        return

    for p in players:
        players_pool.add(p)
    
    save_data()

    await state.clear()
    await message.answer(
        f"✅ Успешно добавлено игроков: {len(players)}.\n"
        f"👥 Всего игроков в базе: **{len(players_pool)}**",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown",
    )


@dp.message(AdminStates.waiting_for_skills)
async def save_skill(message: types.Message, state: FSMContext):
    if not message.text:
        return
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("⚠️ Неверный формат. Укажите игрока и оценку от 1 до 10 через пробел, например: `Егор 8`")
        return

    skill_str = parts[-1]
    if not skill_str.isdigit() or not (1 <= int(skill_str) <= 10):
        await message.answer("⚠️ Последним элементом должна быть оценка от 1 до 10!")
        return

    skill = int(skill_str)
    player_name = " ".join(parts[:-1])

    player_skills[player_name] = skill
    players_pool.add(player_name)
    save_data()

    await state.clear()
    await message.answer(
        f"⭐ Скилл игрока {player_name} установлен на **{skill}** и сохранен навсегда!",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown",
    )


@dp.message(AdminStates.waiting_for_exclude_pair)
async def save_exclude(message: types.Message, state: FSMContext):
    players = list(extract_players_list(message.text))
    if len(players) < 2:
        await message.answer("⚠️ Нужно указать ровно двух игроков через пробел. Попробуйте снова:")
        return

    pair = frozenset([players[0], players[1]])
    excluded_pairs.add(pair)
    save_data()

    await state.clear()
    await message.answer(
        f"🚫 Пара исключений добавлена: **{players[0]}** и **{players[1]}** не сыграют вместе.",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown",
    )


@dp.message(AdminStates.waiting_for_remove_pair)
async def remove_exclude(message: types.Message, state: FSMContext):
    players = list(extract_players_list(message.text))
    if len(players) < 2:
        await message.answer("⚠️ Нужно указать ровно двух игроков для удаления пары:")
        return

    pair = frozenset([players[0], players[1]])
    if pair in excluded_pairs:
        excluded_pairs.remove(pair)
        save_data()
        text = f"✅ Пара исключений **{players[0]}** и **{players[1]}** успешно удалена."
    else:
        text = "⚠️ Такая пара исключений не найдена в списке."

    await state.clear()
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")


if __name__ == "__main__":
    import asyncio

    asyncio.run(dp.start_polling(bot))
