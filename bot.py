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

# Постоянные хранилища в памяти процесса
PLAYERS_POOL = set()
PLAYER_SKILLS = {}
EXCLUDED_PAIRS = set()

# Простейший флаг режима ожидания ввода игроков
WAITING_FOR_PLAYERS_FLAG = set()


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

    WAITING_FOR_PLAYERS_FLAG.discard(message.from_user.id)
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
async def process_callbacks(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ Недостаточно прав!", show_alert=True)
        return

    user_id = callback.from_user.id
    action = callback.data

    if action == "add_players":
        WAITING_FOR_PLAYERS_FLAG.add(user_id)
        await callback.message.answer(
            "✍️ **Режим добавления игроков активирован!**\n\n"
            "Отправьте одним сообщением список игроков (имена и юзернеймы через пробел или с новой строки):\n"
            "Пример: `Егор @Rmgild Vladimir @SereginS2`"
        )

    elif action == "set_skills":
        WAITING_FOR_PLAYERS_FLAG.discard(user_id)
        await callback.message.answer(
            "⭐ Отправьте оценку игрока в формате:\n`Имя число` (от 1 до 10)\n\n"
            "Пример: `Егор 8`"
        )

    elif action == "add_exclude":
        WAITING_FOR_PLAYERS_FLAG.discard(user_id)
        await callback.message.answer(
            "🚫 Отправьте двух игроков через пробел, которые не должны играть вместе:\n\n"
            "Пример: `Егор Vladimir`"
        )

    elif action == "remove_exclude":
        WAITING_FOR_PLAYERS_FLAG.discard(user_id)
        await callback.message.answer(
            "❌ Отправьте двух игроков через пробел для удаления пары исключения:\n\n"
            "Пример: `Егор Vladimir`"
        )

    elif action == "clear_list":
        WAITING_FOR_PLAYERS_FLAG.discard(user_id)
        PLAYERS_POOL.clear()
        await callback.message.answer(
            "🗑 Список игроков очищен! (Скиллы и пары исключений сохранены)."
        )
        await callback.message.answer("Главное меню:", reply_markup=get_admin_keyboard())

    elif action == "make_teams":
        WAITING_FOR_PLAYERS_FLAG.discard(user_id)
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


# Главный текстовый обработчик
@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text_input(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    user_id = message.from_user.id

    # Если администратор нажал кнопку "Добавить игрока" и прислал список
    if user_id in WAITING_FOR_PLAYERS_FLAG:
        tokens = [word.strip(",.;:!?") for word in message.text.split() if word.strip(",.;:!?")]
        if not tokens:
            await message.answer("⚠️ Список пустой. Отправьте имена игроков еще раз:")
            return

        for t in tokens:
            PLAYERS_POOL.add(t)

        WAITING_FOR_PLAYERS_FLAG.discard(user_id)  # Сбрасываем флаг

        added_str = ", ".join(tokens)
        await message.answer(
            f"✅ **Игроки успешно добавлены в базу!**\n\n"
            f"Добавлены: {added_str}\n"
            f"👥 **Всего игроков в базе: {len(PLAYERS_POOL)}**",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown",
        )
        return

    # Обработка ввода скиллов (если текст похож на "Имя число")
    parts = message.text.strip().split()
    if len(parts) >= 2 and parts[-1].isdigit() and 1 <= int(parts[-1]) <= 10:
        skill = int(parts[-1])
        player_name = " ".join(parts[:-1])
        PLAYER_SKILLS[player_name] = skill
        PLAYERS_POOL.add(player_name)
        await message.answer(
            f"⭐ Скилл игрока **{player_name}** установлен на **{skill}**!",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown",
        )
        return

    # Обработка пар исключений (если прислали двух игроков)
    if len(parts) == 2:
        pair = frozenset([parts[0], parts[1]])
        if pair in EXCLUDED_PAIRS:
            EXCLUDED_PAIRS.remove(pair)
            await message.answer(
                f"✅ Пара исключений **{parts[0]}** и **{parts[1]}** удалена.",
                reply_markup=get_admin_keyboard(),
                parse_mode="Markdown",
            )
        else:
            EXCLUDED_PAIRS.add(pair)
            await message.answer(
                f"🚫 Пара исключений добавлена: **{parts[0]}** и **{parts[1]}** не сыграют вместе.",
                reply_markup=get_admin_keyboard(),
                parse_mode="Markdown",
            )
        return


if __name__ == "__main__":
    import asyncio

    asyncio.run(dp.start_polling(bot))
