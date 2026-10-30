import logging
import random
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = "9275964752:AAHhDAMBKHW8WxKrjUv1fKApP3Xa9Jg8GEU"
ADMIN_IDS = {107742498, 92769858}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Базы данных в памяти бота
PLAYERS_POOL = set()
PLAYER_SKILLS = {}
EXCLUDED_PAIRS = set()

# Состояния ожидания ввода от пользователя
WAITING_FOR_PLAYERS = set()
WAITING_FOR_SKILL = set()
WAITING_FOR_EXCLUDE = set()
WAITING_FOR_REMOVE_EXCLUDE = set()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def clear_user_states(user_id: int):
    """Сбрасывает все флаги ожидания для пользователя"""
    WAITING_FOR_PLAYERS.discard(user_id)
    WAITING_FOR_SKILL.discard(user_id)
    WAITING_FOR_EXCLUDE.discard(user_id)
    WAITING_FOR_REMOVE_EXCLUDE.discard(user_id)


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
    clear_user_states(message.from_user.id)
    
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
    clear_user_states(callback.from_user.id)
    WAITING_FOR_PLAYERS.add(callback.from_user.id)
    await callback.message.answer("✍️ Отправьте список игроков на матч через пробел или с новой строки:")
    await callback.answer()


@dp.callback_query(F.data == "set_skills")
async def cb_skills(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    clear_user_states(callback.from_user.id)
    WAITING_FOR_SKILL.add(callback.from_user.id)
    await callback.message.answer("⭐ Введите имя и цифру скилла от 1 до 10 (например: Олег 5)")
    await callback.answer()


@dp.callback_query(F.data == "check_skills")
async def cb_check_skills(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    clear_user_states(callback.from_user.id)
    
    if not PLAYER_SKILLS:
        text = "⭐ Список скиллов пока пустой."
    else:
        text = "⭐ **Список всех оцененных игроков:**\n\n"
        for name, skill in sorted(PLAYER_SKILLS.items(), key=lambda x: x[1], reverse=True):
            text += f"• {name} — **{skill}**\n"
            
    await callback.message.answer(text, parse_mode="Markdown", reply_markup=get_admin_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "make_teams")
async def cb_make_teams(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    clear_user_states(callback.from_user.id)

    if len(PLAYERS_POOL) < 2:
        await callback.answer(
            f"⚠️ Недостаточно игроков (сейчас: {len(PLAYERS_POOL)}, нужно мин. 2).",
            show_alert=True,
        )
        return

    players = list(PLAYERS_POOL)
    random.shuffle(players)

    def get_skill(p):
        return PLAYER_SKILLS.get(p, 5)

    players.sort(key=get_skill, reverse=True)

    team1, team2 = [], []
    sum1, sum2 = 0, 0

    for player in players:
        p_skill = get_skill(player)
        can_go_1 = all(frozenset([player, p]) not in EXCLUDED_PAIRS for p in team1)
        can_go_2 = all(frozenset([player, p]) not in EXCLUDED_PAIRS for p in team2)

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
        text += f"• {p} (скилл: {get_skill(p)})\n"
    text += f"\n**Команда 2** (Средний скилл: {avg2}):\n"
    for p in team2:
        text += f"• {p} (скилл: {get_skill(p)})\n"

    await callback.message.answer(text, parse_mode="Markdown", reply_markup=get_admin_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "clear_list")
async def cb_clear(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    clear_user_states(callback.from_user.id)
    PLAYERS_POOL.clear()
    await callback.message.answer("🗑 Список игроков на матч очищен.", reply_markup=get_admin_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "add_exclude")
async def cb_exclude(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    clear_user_states(callback.from_user.id)
    WAITING_FOR_EXCLUDE.add(callback.from_user.id)
    await callback.message.answer("🚫 Отправьте двух игроков через пробел, которые не должны играть вместе.")
    await callback.answer()


@dp.callback_query(F.data == "remove_exclude")
async def cb_remove_exclude(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    clear_user_states(callback.from_user.id)
    WAITING_FOR_REMOVE_EXCLUDE.add(callback.from_user.id)
    await callback.message.answer("❌ Отправьте двух игроков через пробел для удаления пары исключения.")
    await callback.answer()


# Строгий обработчик текста: реагирует ТОЛЬКО если пользователь нажал соответствующую кнопку
@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    text = message.text.strip()
    parts = text.split()

    # Если пользователь не находится ни в одном режиме ввода — молчим (пропускаем обычный чат)
    if (user_id not in WAITING_FOR_PLAYERS and 
        user_id not in WAITING_FOR_SKILL and 
        user_id not in WAITING_FOR_EXCLUDE and 
        user_id not in WAITING_FOR_REMOVE_EXCLUDE):
        return

    # 1. Обработка ввода списка игроков
    if user_id in WAITING_FOR_PLAYERS:
        names = []
        for line in text.split("\n"):
            for word in line.split():
                cleaned = word.strip(",.;:!?")
                if cleaned:
                    names.append(cleaned)
        
        if names:
            PLAYERS_POOL.clear()
            for name in names:
                PLAYERS_POOL.add(name)
        
        WAITING_FOR_PLAYERS.discard(user_id)
        await message.answer(f"✅ Список обновлен! Игроков: {len(PLAYERS_POOL)}", reply_markup=get_admin_keyboard())
        return

    # 2. Обработка оценки скилла (например: "Олег 5")
    if user_id in WAITING_FOR_SKILL:
        if len(parts) >= 2 and parts[-1].isdigit() and 1 <= int(parts[-1]) <= 10:
            skill = int(parts[-1])
            name = " ".join(parts[:-1])
            PLAYER_SKILLS[name] = skill
            WAITING_FOR_SKILL.discard(user_id)
            await message.answer(f"⭐ Сохранено: {name} — {skill}", reply_markup=get_admin_keyboard())
        else:
            await message.answer("⚠️ Неверный формат. Введите имя и цифру от 1 до 10 (например: Олег 5):")
        return

    # 3. Добавление пары исключения
    if user_id in WAITING_FOR_EXCLUDE:
        if len(parts) == 2 and not parts[0].isdigit() and not parts[1].isdigit():
            pair = frozenset([parts[0], parts[1]])
            EXCLUDED_PAIRS.add(pair)
            WAITING_FOR_EXCLUDE.discard(user_id)
            await message.answer(f"🚫 Пара исключения добавлена: {parts[0]} и {parts[1]}", reply_markup=get_admin_keyboard())
        else:
            await message.answer("⚠️ Введите ровно два имени через пробел:")
        return

    # 4. Удаление пары исключения
    if user_id in WAITING_FOR_REMOVE_EXCLUDE:
        if len(parts) == 2 and not parts[0].isdigit() and not parts[1].isdigit():
            pair = frozenset([parts[0], parts[1]])
            if pair in EXCLUDED_PAIRS:
                EXCLUDED_PAIRS.remove(pair)
                await message.answer(f"✅ Пара исключения удалена: {parts[0]} и {parts[1]}", reply_markup=get_admin_keyboard())
            else:
                await message.answer("⚠️ Такая пара исключений не найдена в списке.")
            WAITING_FOR_REMOVE_EXCLUDE.discard(user_id)
        else:
            await message.answer("⚠️ Введите ровно два имени через пробел:")
        return


if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
