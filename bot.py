import json
import logging
import os
import random
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = "9275964752:AAHhDAMBKHW8WxKrjUv1fKApP3Xa9Jg8GEU"
ADMIN_IDS = {107742498, 92769858}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

DB_FILE = "database.json"


# Загрузка базы данных с диска
def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return (
                    set(data.get("players", [])),
                    data.get("skills", {}),
                    {frozenset(pair) for pair in data.get("exclude_pairs", [])},
                )
        except Exception as e:
            logging.error(f"Error loading database: {e}")
    return set(), {}, set()


# Сохранение базы данных на диск
def save_data():
    data = {
        "players": list(players_pool),
        "skills": player_skills,
        "exclude_pairs": [list(pair) for pair in excluded_pairs],
    }
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error saving database: {e}")


players_pool, player_skills, excluded_pairs = load_data()

# Активные режимы администраторов: {admin_id: "add_players" | "set_skills" | "add_exclude" | "remove_exclude"}
admin_modes = {}


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

    admin_modes.pop(message.from_user.id, None)
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
async def process_callbacks(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ Недостаточно прав!", show_alert=True)
        return

    user_id = callback.from_user.id
    action = callback.data

    if action == "add_players":
        admin_modes[user_id] = "add_players"
        await callback.message.answer(
            "✍️ **Режим добавления игроков активирован.**\n\n"
            "Отправьте списком имена или юзернеймы через пробел или с новой строки:\n"
            "Пример: `Егор @Rmgild Vladimir @SereginS2`"
        )

    elif action == "set_skills":
        admin_modes[user_id] = "set_skills"
        await callback.message.answer(
            "⭐ **Режим оценки скилла активирован.**\n\n"
            "Отправьте оценку игрока в формате: `Имя_или_юзернейм число` (от 1 до 10)\n"
            "Пример: `Егор 9` или `@Rmgild 8`"
        )

    elif action == "add_exclude":
        admin_modes[user_id] = "add_exclude"
        await callback.message.answer(
            "🚫 **Режим добавления пар исключения активирован.**\n\n"
            "Отправьте двух игроков через пробел, которые не должны играть вместе:\n"
            "Пример: `Егор Vladimir`"
        )

    elif action == "remove_exclude":
        admin_modes[user_id] = "remove_exclude"
        await callback.message.answer(
            "❌ **Режим удаления пар исключения активирован.**\n\n"
            "Отправьте двух игроков через пробел для удаления пары исключения:\n"
            "Пример: `Егор Vladimir`"
        )

    elif action == "clear_list":
        admin_modes.pop(user_id, None)
        players_pool.clear()
        save_data()
        await callback.message.answer(
            "🗑 Список игроков очищен! (Скиллы и пары исключений сохранены)."
        )
        await callback.message.answer("Главное меню:", reply_markup=get_admin_keyboard())

    elif action == "make_teams":
        admin_modes.pop(user_id, None)
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

        # Жадный алгоритм балансировки по среднему арифметическому
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
            text += f"• {p}\n"

        text += f"\n**Команда 2** (Средний скилл: {avg2}):\n"
        for p in team2:
            text += f"• {p}\n"

        await callback.message.answer(text, parse_mode="Markdown")
        await callback.message.answer("Главное меню:", reply_markup=get_admin_keyboard())

    await callback.answer()


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text_input(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    user_id = message.from_user.id
    mode = admin_modes.get(user_id)

    if not mode:
        await message.answer(
            "⚠️ Пожалуйста, выберите нужное действие с помощью кнопок меню.",
            reply_markup=get_admin_keyboard(),
        )
        return

    text = message.text.strip()

    if mode == "add_players":
        tokens = []
        for line in text.split("\n"):
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
        admin_modes.pop(user_id, None)

        added_str = ", ".join(tokens)
        await message.answer(
            f"✅ **Игроки успешно добавлены!**\n\n"
            f"Добавлены: {added_str}\n"
            f"👥 **Всего игроков в базе: {len(players_pool)}**",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown",
        )

    elif mode == "set_skills":
        parts = text.split()
        if len(parts) < 2:
            await message.answer(
                "⚠️ Неверный формат. Укажите игрока и оценку от 1 до 10 через пробел, например: `Егор 8`"
            )
            return

        skill_str = parts[-1]
        if not skill_str.isdigit() or not (1 <= int(skill_str) <= 10):
            await message.answer("⚠️ Последним элементом должна быть цифра от 1 до 10!")
            return

        skill = int(skill_str)
        player_name = " ".join(parts[:-1])

        player_skills[player_name] = skill
        players_pool.add(player_name)
        save_data()
        admin_modes.pop(user_id, None)

        await message.answer(
            f"⭐ Скилл игрока **{player_name}** установлен на **{skill}** и сохранен навсегда!",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown",
        )

    elif mode == "add_exclude":
        tokens = [w.strip(",.;:!?") for w in text.split() if w.strip(",.;:!?")]
        if len(tokens) < 2:
            await message.answer("⚠️ Укажите ровно двух игроков через пробел:")
            return

        pair = frozenset([tokens[0], tokens[1]])
        excluded_pairs.add(pair)
        save_data()
        admin_modes.pop(user_id, None)

        await message.answer(
            f"🚫 Пара исключений добавлена: **{tokens[0]}** и **{tokens[1]}** не сыграют вместе.",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown",
        )

    elif mode == "remove_exclude":
        tokens = [w.strip(",.;:!?") for w in text.split() if w.strip(",.;:!?")]
        if len(tokens) < 2:
            await message.answer("⚠️ Укажите ровно двух игроков для удаления пары:")
            return

        pair = frozenset([tokens[0], tokens[1]])
        if pair in excluded_pairs:
            excluded_pairs.remove(pair)
            save_data()
            text_resp = f"✅ Пара исключений **{tokens[0]}** и **{tokens[1]}** успешно удалена."
        else:
            text_resp = "⚠️ Такая пара исключений не найдена."

        admin_modes.pop(user_id, None)
        await message.answer(
            text_resp, reply_markup=get_admin_keyboard(), parse_mode="Markdown"
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(dp.start_polling(bot))
