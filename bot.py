import logging
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

# Абсолютно постоянные хранилища в памяти процесса
PLAYERS_POOL = set()
PLAYER_SKILLS = {}
EXCLUDED_PAIRS = set()


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
        f"👥 Игроков в базе: **{len(PLAYERS_POOL)}**\n"
        f"⭐ Оценок скилла: {len(PLAYER_SKILLS)}\n"
        f"🚫 Пар исключений: {len(EXCLUDED_PAIRS)}\n\n"
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
            "✍️ Отправьте список игроков (имена или юзернеймы через пробел или строчку):\n\n"
            "Пример: `Егор @Rmgild Vladimir @SereginS2`"
        )

    elif action == "set_skills":
        await state.set_state(AdminStates.waiting_for_skills)
        await callback.message.answer(
            "⭐ Отправьте оценку игрока в формате:\n`Имя число` (от 1 до 10)\n\n"
            "Пример: `Егор 9`"
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
        PLAYERS_POOL.clear()
        await callback.message.answer(
            "🗑 Список игроков очищен! (Скиллы и пары исключений сохранены)."
        )
        await callback.message.answer("Главное меню:", reply_markup=get_admin_keyboard())

    elif action == "make_teams":
        if len(PLAYERS_POOL) < 2:
            await callback.answer(
                f"⚠️ Недостаточно игроков для сборки (сейчас в базе: {len(PLAYERS_POOL)}, нужно минимум 2).",
                show_alert=True,
            )
            return

        players = list(PLAYERS_POOL)
        random.shuffle(players)

        def get_skill(p):
            return PLAYER_SKILLS.get(p, 5)

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
                if frozenset([player, p]) in EXCLUDED_PAIRS:
                    can_go_to_1 = False
            for p in team2:
                if frozenset([player, p]) in EXCLUDED_PAIRS:
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
            text += f"• {p} (скилл: {PLAYER_SKILLS.get(p, 5)})\n"

        text += f"\n**Команда 2** (Средний скилл: {avg2}):\n"
        for p in team2:
            text += f"• {p} (скилл: {PLAYER_SKILLS.get(p, 5)})\n"

        await callback.message.answer(text, parse_mode="Markdown")
        await callback.message.answer("Главное меню:", reply_markup=get_admin_keyboard())

    await callback.answer()


def parse_tokens(text: str) -> set:
    if not text:
        return set()
    return {word.strip(",.;:!?") for word in text.split() if word.strip(",.;:!?")}


@dp.message(AdminStates.waiting_for_players)
async def save_players(message: types.Message, state: FSMContext):
    tokens = parse_tokens(message.text)
    if not tokens:
        await message.answer("⚠️ Список пустой. Отправьте имена игроков:")
        return

    for t in tokens:
        PLAYERS_POOL.add(t)

    await state.clear()
    await message.answer(
        f"✅ Успешно добавлено игроков: {len(tokens)}.\n"
        f"👥 Всего игроков в базе: **{len(PLAYERS_POOL)}**",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown",
    )


@dp.message(AdminStates.waiting_for_skills)
async def save_skill(message: types.Message, state: FSMContext):
    if not message.text:
        return
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("⚠️ Неверный формат. Пример: `Егор 8`")
        return

    skill_str = parts[-1]
    if not skill_str.isdigit() or not (1 <= int(skill_str) <= 10):
        await message.answer("⚠️ Последним словом должна быть цифра от 1 до 10!")
        return

    skill = int(skill_str)
    player_name = " ".join(parts[:-1])

    PLAYER_SKILLS[player_name] = skill
    PLAYERS_POOL.add(player_name)

    await state.clear()
    await message.answer(
        f"⭐ Скилл игрока {player_name} установлен на **{skill}**!",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown",
    )


@dp.message(AdminStates.waiting_for_exclude_pair)
async def save_exclude(message: types.Message, state: FSMContext):
    tokens = list(parse_tokens(message.text))
    if len(tokens) < 2:
        await message.answer("⚠️ Укажите ровно двух игроков через пробел:")
        return

    pair = frozenset([tokens[0], tokens[1]])
    EXCLUDED_PAIRS.add(pair)

    await state.clear()
    await message.answer(
        f"🚫 Пара исключений добавлена: **{tokens[0]}** и **{tokens[1]}** не сыграют вместе.",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown",
    )


@dp.message(AdminStates.waiting_for_remove_pair)
async def remove_exclude(message: types.Message, state: FSMContext):
    tokens = list(parse_tokens(message.text))
    if len(tokens) < 2:
        await message.answer("⚠️ Укажите ровно двух игроков для удаления пары:")
        return

    pair = frozenset([tokens[0], tokens[1]])
    if pair in EXCLUDED_PAIRS:
        EXCLUDED_PAIRS.remove(pair)
        text = f"✅ Пара исключений **{tokens[0]}** и **{tokens[1]}** успешно удалена."
    else:
        text = "⚠️ Такая пара исключений не найдена."

    await state.clear()
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")


if __name__ == "__main__":
    import asyncio

    asyncio.run(dp.start_polling(bot))
