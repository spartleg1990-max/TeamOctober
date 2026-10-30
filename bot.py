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

PLAYERS_POOL = set()
PLAYER_SKILLS = {}
EXCLUDED_PAIRS = set()
USER_STATES = {}


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

    # Функция проверки: нарушает ли пара правила исключения в команде
    def check_excludes(team):
        for i in range(len(team)):
            for j in range(i + 1, len(team)):
                if frozenset([team[i], team[j]]) in EXCLUDED_PAIRS:
                    return False
        return True

    # Пытаемся найти честное распределение без перекосов (максимум 100 попыток с рандомом)
    best_team1, best_team2 = [], []
    best_diff = 999
    
    total_players = len(players)
    max_team_size = (total_players + 1) // 2

    for _ in range(200):
        random.shuffle(players)
        t1 = []
        t2 = []
        
        # Сортируем по скиллу для баланса
        sorted_pl = sorted(players, key=get_skill, reverse=True)
        
        s1, s2 = 0, 0
        for p in sorted_pl:
            # Строго следим за равным размером команд (разница не больше 1 игрока)
            if len(t1) < max_team_size and (len(t1) <= len(t2) and s1 <= s2 or len(t2) >= max_team_size):
                t1.append(p)
                s1 += get_skill(p)
            else:
                t2.append(p)
                s2 += get_skill(p)
                
        # Если в обеих командах нет запрещенных пар и размеры честные
        if check_excludes(t1) and check_excludes(t2) and abs(len(t1) - len(t2)) <= 1:
            diff = abs(s1 - s2)
            if diff < best_diff:
                best_diff = diff
                best_team1, best_team2 = t1, t2
                if diff == 0:
                    break

    # Если идеальный вариант не нашелся, берем хоть какой-то валидный по размерам
    if not best_team1:
        best_team1 = players[:max_team_size]
        best_team2 = players[max_team_size:]

    sum1 = sum(get_skill(p) for p in best_team1)
    sum2 = sum(get_skill(p) for p in best_team2)
    avg1 = round(sum1 / len(best_team1), 1) if best_team1 else 0
    avg2 = round(sum2 / len(best_team2), 1) if best_team2 else 0

    # Формируем текст с нумерацией напротив имен
    text = "🔀 **Сбалансированные составы команд:**\n\n"
    
    text += f"**Команда 1** (Средний скилл: {avg1}):\n"
    for idx, p in enumerate(best_team1, 1):
        text += f"{idx}. {p} (скилл: {get_skill(p)})\n"
        
    text += f"\n**Команда 2** (Средний скилл: {avg2}):\n"
    for idx, p in enumerate(best_team2, 1):
        text += f"{idx}. {p} (скилл: {get_skill(p)})\n"

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
        
        USER_STATES.pop(user_id, None)
        await message.answer(f"✅ Добавлено! Всего игроков в базе: {len(PLAYERS_POOL)}", reply_markup=get_admin_keyboard())
        return

    if current_state == "WAITING_SKILL":
        if len(parts) >= 2 and parts[-1].isdigit() and 1 <= int(parts[-1]) <= 10:
            skill = int(parts[-1])
            name = " ".join(parts[:-1])
            PLAYER_SKILLS[name] = skill
            USER_STATES.pop(user_id, None)
            await message.answer(f"⭐ Сохранено: {name} — {skill}", reply_markup=get_admin_keyboard())
        else:
            await message.answer("⚠️ Неверный формат. Введите имя и цифру от 1 до 10 (например: Олег 5):")
        return

    if current_state == "WAITING_EXCLUDE":
        if len(parts) == 2 and not parts[0].isdigit() and not parts[1].isdigit():
            pair = frozenset([parts[0], parts[1]])
            EXCLUDED_PAIRS.add(pair)
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
                await message.answer(f"✅ Пара исключения удалена: {parts[0]} и {parts[1]}", reply_markup=get_admin_keyboard())
            else:
                await message.answer("⚠️ Такая пара не найдена в списке.")
            USER_STATES.pop(user_id, None)
        else:
            await message.answer("⚠️ Введите ровно два имени через пробел:")
        return


if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
