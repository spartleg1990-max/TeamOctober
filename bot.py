import logging
import random
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = "9275964752:AAHhDAMBKHW8WxKrjUv1fKApP3Xa9Jg8GEU"
ADMIN_IDS = {107742498, 92769858}

# Создаем 50 заготовок игроков со скиллом 5 при запуске
PLAYER_SKILLS = {f"Игрок {i}": 5 for i in range(1, 51)}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Базы данных в памяти бота
PLAYERS_POOL = set()
EXCLUDED_PAIRS = set()
WAITING_FOR_PLAYERS = set()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить игроков", callback_data="add_players")],
        [InlineKeyboardButton(text="⭐ Оценить скилл игроков", callback_data="set_skills")],
        [InlineKeyboardButton(text="📋 Проверить скиллы", callback_data="check_skills")],  # <-- Кнопка на месте!
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
    WAITING_FOR_PLAYERS.discard(message.from_user.id)
    
    # Считаем реальных игроков (у которых имя НЕ начинается с "Игрок ")
    real_skills_count = sum(1 for name in PLAYER_SKILLS.keys() if not name.startswith("Игрок "))
    
    text = (
        "⚽ **Панель управления футбольными составами**\n\n"
        f"👥 Игроков в базе: **{len(PLAYERS_POOL)}**\n"
        f"⭐ Оценок скилла: {real_skills_count}\n"
        f"🚫 Пар исключений: {len(EXCLUDED_PAIRS)}\n\n"
        "Выберите действие с помощью кнопок ниже:"
    )
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")


@dp.callback_query(F.data == "add_players")
async def cb_add_players(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    WAITING_FOR_PLAYERS.add(callback.from_user.id)
    text = (
        "Добавьте списком имена игроков.\n"
        "Список — это имена через пробелы: Олег Макс и т.д."
    )
    await callback.message.answer(text)
    await callback.answer()


@dp.callback_query(F.data == "check_skills")
async def cb_check_skills(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    WAITING_FOR_PLAYERS.discard(callback.from_user.id)
    
    text = "⭐ **Оценки скиллов (реальные игроки):**\n\n"
    has_real = False
    for name, skill in PLAYER_SKILLS.items():
        if not name.startswith("Игрок "):
            text += f"• {name} — **{skill}**\n"
            has_real = True
            
    if not has_real:
        text = "⭐ Вы еще не оценили ни одного игрока. Нажмите «Оценить скилл игроков» и отправьте сообщение в формате: `Олег 8`"
            
    await callback.message.answer(text, parse_mode="Markdown", reply_markup=get_admin_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "make_teams")
async def cb_make_teams(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    WAITING_FOR_PLAYERS.discard(callback.from_user.id)

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
    WAITING_FOR_PLAYERS.discard(callback.from_user.id)
    PLAYERS_POOL.clear()
    await callback.message.answer("🗑 Список игроков очищен.", reply_markup=get_admin_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "set_skills")
async def cb_skills(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    WAITING_FOR_PLAYERS.discard(callback.from_user.id)
    await callback.message.answer("⭐ Отправьте оценку скилла в формате: `Имя число` (например: `Олег 8`)")
    await callback.answer()


@dp.callback_query(F.data == "add_exclude")
async def cb_exclude(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    WAITING_FOR_PLAYERS.discard(callback.from_user.id)
    await callback.message.answer("🚫 Отправьте двух игроков через пробел, которые не должны играть вместе.")
    await callback.answer()


@dp.callback_query(F.data == "remove_exclude")
async def cb_remove_exclude(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    WAITING_FOR_PLAYERS.discard(callback.from_user.id)
    await callback.message.answer("❌ Отправьте двух игроков через пробел для удаления пары исключения.")
    await callback.answer()


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    text = message.text.strip()

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
        n = len(PLAYERS_POOL)
        await message.answer(f"Заявленное количество игроков {n}", reply_markup=get_admin_keyboard())
        return

    # Обработка скилла (например: "Олег 5")
    parts = text.split()
    if len(parts) >= 2 and parts[-1].isdigit() and 1 <= int(parts[-1]) <= 10:
        skill = int(parts[-1])
        name = " ".join(parts[:-1])
        
        if name in PLAYER_SKILLS:
            PLAYER_SKILLS[name] = skill
        else:
            target_key = None
            for key in PLAYER_SKILLS.keys():
                if key.startswith("Игрок "):
                    target_key = key
                    break
            
            if target_key:
                del PLAYER_SKILLS[target_key]
            
            PLAYER_SKILLS[name] = skill
            
        await message.answer(f"⭐ Скилл игрока {name} установлен на {skill}", reply_markup=get_admin_keyboard())
        return

    if len(parts) == 2:
        pair = frozenset([parts[0], parts[1]])
        if pair in EXCLUDED_PAIRS:
            EXCLUDED_PAIRS.remove(pair)
            await message.answer(f"✅ Пара исключений {parts[0]} и {parts[1]} удалена.", reply_markup=get_admin_keyboard())
        else:
            EXCLUDED_PAIRS.add(pair)
            await message.answer(f"🚫 Пара исключений добавлена: {parts[0]} и {parts[1]}", reply_markup=get_admin_keyboard())
        return

    await message.answer("⚠️ Воспользуйтесь кнопками меню для управления.", reply_markup=get_admin_keyboard())


if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
