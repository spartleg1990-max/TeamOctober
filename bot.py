import base64, json, logging, os, random, urllib.request, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Мгновенно поднимаем веб-сервер для Render при старте файла
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active!")
    def log_message(self, format, *args):
        pass

def run_web_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

TOKEN = "9275964752:AAHhDAMBKHW8WxKrjUv1fKApP3Xa9Jg8GEU"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

DATA_FILE = "bot_database.json"
GH_TOKEN = os.getenv("GITHUB_TOKEN")
GH_REPO = os.getenv("GITHUB_REPO")
GH_BRANCH = os.getenv("GITHUB_BRANCH", "main")

PLAYERS_POOL, PLAYER_SKILLS, EXCLUDED_PAIRS, USER_STATES = set(), {}, set(), {}

def load_data():
    global PLAYERS_POOL, PLAYER_SKILLS, EXCLUDED_PAIRS
    if GH_TOKEN and GH_REPO:
        try:
            url = f"https://api.github.com/repos/{GH_REPO}/contents/{DATA_FILE}"
            req = urllib.request.Request(url, headers={"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json", "User-Agent": "Bot"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                res_data = json.loads(resp.read().decode())
                data = json.loads(base64.b64decode(res_data["content"]).decode())
                PLAYERS_POOL = set(data.get("players", []))
                PLAYER_SKILLS = data.get("skills", {})
                EXCLUDED_PAIRS = {frozenset(p) for p in data.get("excludes", [])}
                logging.info("✅ Данные успешно загружены с GitHub!")
                return
        except Exception as e:
            logging.warning(f"⚠️ Не удалось загрузить с GitHub: {e}")
            
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                PLAYERS_POOL = set(data.get("players", []))
                PLAYER_SKILLS = data.get("skills", {})
                EXCLUDED_PAIRS = {frozenset(p) for p in data.get("excludes", [])}
        except Exception:
            pass

def save_data():
    data = {"players": list(PLAYERS_POOL), "skills": PLAYER_SKILLS, "excludes": [list(p) for p in EXCLUDED_PAIRS]}
    json_str = json.dumps(data, ensure_ascii=False, indent=4)
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            f.write(json_str)
    except Exception as e:
        logging.error(f"❌ Ошибка локального сохранения: {e}")
        
    if GH_TOKEN and GH_REPO:
        url = f"https://api.github.com/repos/{GH_REPO}/contents/{DATA_FILE}"
        content_encoded = base64.b64encode(json_str.encode()).decode()
        
        for attempt in range(2):
            try:
                sha = None
                req_get = urllib.request.Request(url, headers={"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json", "User-Agent": "Bot"})
                try:
                    with urllib.request.urlopen(req_get, timeout=5) as resp:
                        sha = json.loads(resp.read().decode()).get("sha")
                except Exception:
                    pass
                    
                payload = {"message": "Update DB", "content": content_encoded, "branch": GH_BRANCH}
                if sha: payload["sha"] = sha
                
                req_put = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json", "Content-Type": "application/json", "User-Agent": "Bot"}, method="PUT")
                with urllib.request.urlopen(req_put, timeout=5) as resp:
                    logging.info("🚀 Данные успешно отправлены и сохранены на GitHub!")
                    break
            except Exception as e:
                logging.error(f"❌ Попытка {attempt+1} отправки на GitHub не удалась: {e}")

def get_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить игроков", callback_data="add_players")],
        [InlineKeyboardButton(text="⭐ Оценить скилл игроков", callback_data="set_skills")],
        [InlineKeyboardButton(text="📋 Проверить скиллы", callback_data="check_skills")],
        [InlineKeyboardButton(text="🗑 Очистить скиллы", callback_data="clear_skills_menu")],
        [InlineKeyboardButton(text="📋 Проверить пары исключения", callback_data="check_excludes")],
        [InlineKeyboardButton(text="🔀 Собрать команду", callback_data="make_teams")],
        [InlineKeyboardButton(text="🚫 Добавить пару исключения", callback_data="add_exclude")],
        [InlineKeyboardButton(text="❌ Удалить пару исключения", callback_data="remove_exclude")],
        [InlineKeyboardButton(text="🗑 Очистить список игроков", callback_data="clear_list")]
    ])

@dp.message(Command("start"), Command("admin"))
async def cmd_start(message: types.Message):
    USER_STATES.pop(message.from_user.id, None)
    text = f"⚽ **Панель управления**\n\n👥 Игроков: **{len(PLAYERS_POOL)}**\n⭐ Скиллов: **{len(PLAYER_SKILLS)}**\n🚫 Исключений: {len(EXCLUDED_PAIRS)}"
    await message.answer(text, reply_markup=get_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "add_players")
async def cb_add(c: types.CallbackQuery):
    await c.answer()
    USER_STATES[c.from_user.id] = "WAITING_PLAYERS"
    await c.message.answer("✍️ Отправьте список игроков (через пробел или с новой строки):")

@dp.callback_query(F.data == "set_skills")
async def cb_skills(c: types.CallbackQuery):
    await c.answer()
    USER_STATES[c.from_user.id] = "WAITING_SKILL"
    await c.message.answer("⭐ Введите имя и цифру скилла от 1 до 10 (можно отправлять списком):\n*(Пример: Олег 4)*")

@dp.callback_query(F.data == "clear_skills_menu")
async def cb_clear_skills_menu(c: types.CallbackQuery):
    await c.answer()
    USER_STATES[c.from_user.id] = "WAITING_CLEAR_SKILL"
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Да, удалить ВСЕ скиллы", callback_data="confirm_clear_all")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
    ])
    await c.message.answer("🗑 Напишите имя конкретного игрока, которого нужно удалить.\n\nИли нажмите кнопку ниже для полной очистки списка скиллов:", reply_markup=confirm_kb)

@dp.callback_query(F.data == "confirm_clear_all")
async def cb_confirm_clear_all(c: types.CallbackQuery):
    await c.answer("Список скиллов очищен!")
    PLAYER_SKILLS.clear()
    save_data()
    USER_STATES.clear()
    await c.message.answer("🗑 Список скиллов полностью очищен.", reply_markup=get_keyboard())

@dp.callback_query(F.data == "cancel_action")
async def cb_cancel_action(c: types.CallbackQuery):
    await c.answer("Отменено")
    USER_STATES.clear()
    await c.message.answer("❌ Действие отменено.", reply_markup=get_keyboard())

@dp.callback_query(F.data == "add_exclude")
async def cb_excl(c: types.CallbackQuery):
    await c.answer()
    USER_STATES[c.from_user.id] = "WAITING_EXCLUDE"
    await c.message.answer("🚫 Отправьте двух игроков через пробел (например: Олег Макс):")

@dp.callback_query(F.data == "remove_exclude")
async def cb_rem_excl(c: types.CallbackQuery):
    await c.answer()
    USER_STATES[c.from_user.id] = "WAITING_REMOVE_EXCLUDE"
    await c.message.answer("❌ Отправьте двух игроков через пробел для удаления из исключений:")

@dp.callback_query(F.data == "check_skills")
async def cb_check(c: types.CallbackQuery):
    await c.answer()
    USER_STATES.pop(c.from_user.id, None)
    if not PLAYER_SKILLS:
        text = "⭐ Список скиллов пуст."
    else:
        text = "⭐ **Список скиллов игроков:**\n\n"
        for i, (n, s) in enumerate(sorted(PLAYER_SKILLS.items(), key=lambda x: x[1], reverse=True), 1):
            text += f"{i}. {n} — **{s}**\n"
    await c.message.answer(text, parse_mode="Markdown", reply_markup=get_keyboard())

@dp.callback_query(F.data == "check_excludes")
async def cb_check_excludes(c: types.CallbackQuery):
    await c.answer()
    USER_STATES.pop(c.from_user.id, None)
    if not EXCLUDED_PAIRS:
        text = "🚫 Список пар исключений пуст."
    else:
        text = "🚫 **Пары исключений:**\n\n"
        for i, pair in enumerate(EXCLUDED_PAIRS, 1):
            p_list = list(pair)
            text += f"{i}. {p_list[0]} ❌ {p_list[1]}\n"
    await c.message.answer(text, parse_mode="Markdown", reply_markup=get_keyboard())

@dp.callback_query(F.data == "clear_list")
async def cb_clear(c: types.CallbackQuery):
    await c.answer()
    USER_STATES.pop(c.from_user.id, None)
    PLAYERS_POOL.clear()
    save_data()
    await c.message.answer("🗑 Список игроков очищен.", reply_markup=get_keyboard())

@dp.callback_query(F.data == "make_teams")
async def cb_teams(c: types.CallbackQuery):
    await c.answer()
    USER_STATES.pop(c.from_user.id, None)
    if len(PLAYERS_POOL) < 2:
        await c.message.answer(f"⚠️ Мало игроков ({len(PLAYERS_POOL)}). Нужно мин. 2")
        return
    
    players = list(PLAYERS_POOL)
    get_s = lambda p: PLAYER_SKILLS.get(p, 5)
    check = lambda t: all(frozenset([t[i], t[j]]) not in EXCLUDED_PAIRS for i in range(len(t)) for j in range(i + 1, len(t)))
    
    t1, t2, best_diff = [], [], 999
    target = len(players) // 2
    
    for _ in range(1000):
        random.shuffle(players)
        p1, p2 = players[:target], players[target:]
        if abs(len(p1) - len(p2)) <= 1 and check(p1) and check(p2):
            diff = abs(sum(get_s(p) for p in p1) - sum(get_s(p) for p in p2))
            if diff < best_diff:
                best_diff, t1, t2 = diff, p1, p2
                if diff == 0: break
                
    if not t1: t1, t2 = players[:target], players[target:]
    
    avg1 = round(sum(get_s(p) for p in t1) / len(t1), 1) if t1 else 0
    avg2 = round(sum(get_s(p) for p in t2) / len(t2), 1) if t2 else 0
    
    text = f"🔀 **Составы команд:**\n\n**Команда 1** (Ср. скилл: {avg1}):\n" + "".join(f"{i}) {p} (скилл: {get_s(p)})\n" for i, p in enumerate(t1, 1))
    text += f"\n**Команда 2** (Ср. скилл: {avg2}):\n" + "".join(f"{i}) {p} (скилл: {get_s(p)})\n" for i, p in enumerate(t2, 1))
    
    await c.message.answer(text, parse_mode="Markdown", reply_markup=get_keyboard())

@dp.message(F.text & ~F.text.startswith("/"))
async def text_handler(m: types.Message):
    state = USER_STATES.get(m.from_user.id)
    if not state: return
    text = m.text.strip()
    
    if state == "WAITING_PLAYERS":
        USER_STATES.pop(m.from_user.id, None)
        names = [w.strip(",.;:!?") for line in text.split("\n") for w in line.split() if w.strip(",.;:!?")]
        if names:
            PLAYERS_POOL.update(names)
            save_data()
            await m.answer(f"✅ Добавлено! Всего игроков: {len(PLAYERS_POOL)}", reply_markup=get_keyboard())
            
    elif state == "WAITING_SKILL":
        USER_STATES.pop(m.from_user.id, None)
        lines = text.split("\n")
        results = []
        changes_made = False
        
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[-1].isdigit() and 1 <= int(parts[-1]) <= 10:
                name = " ".join(parts[:-1])
                skill = int(parts[-1])
                PLAYERS_POOL.add(name)
                
                if name in PLAYER_SKILLS:
                    old_skill = PLAYER_SKILLS[name]
                    if old_skill == skill:
                        results.append(f"• **{name}** уже внесен ранее с таким же скиллом (**{skill}**)")
                    else:
                        PLAYER_SKILLS[name] = skill
                        results.append(f"• **{name}**: скилл заменен с {old_skill} на **{skill}** 🔄")
                        changes_made = True
                else:
                    PLAYER_SKILLS[name] = skill
                    results.append(f"• **{name}** — **{skill}** ✅")
                    changes_made = True
                    
        if results:
            if changes_made or any("заменен" in r or "✅" in r for r in results):
                save_data()
            response_text = "⭐ **Результат обработки скиллов:**\n\n" + "\n".join(results) + "\n\n*(Можете ввести следующие данные или выбрать пункт в меню)*"
            await m.answer(response_text, parse_mode="Markdown", reply_markup=get_keyboard())

    elif state == "WAITING_CLEAR_SKILL":
        USER_STATES.pop(m.from_user.id, None)
        found_key = None
        for name in PLAYER_SKILLS:
            if name.lower() == text.lower():
                found_key = name
                break
        if found_key:
            del PLAYER_SKILLS[found_key]
            save_data()
            await m.answer(f"✅ Игрок **{found_key}** удален из списка скиллов.", parse_mode="Markdown", reply_markup=get_keyboard())
        else:
            await m.answer(f"⚠️ Игрок **{text}** не найден в списке скиллов.", parse_mode="Markdown", reply_markup=get_keyboard())
            
    elif state == "WAITING_EXCLUDE":
        USER_STATES.pop(m.from_user.id, None)
        parts = text.split()
        if len(parts) == 2:
            EXCLUDED_PAIRS.add(frozenset([parts[0], parts[1]]))
            save_data()
            await m.answer("🚫 Пара исключения добавлена!", reply_markup=get_keyboard())
        else:
            await m.answer("⚠️ Введите ровно два имени через пробел:")
            
    elif state == "WAITING_REMOVE_EXCLUDE":
        USER_STATES.pop(m.from_user.id, None)
        parts = text.split()
        if len(parts) == 2:
            pair = frozenset([parts[0], parts[1]])
            if pair in EXCLUDED_PAIRS:
                EXCLUDED_PAIRS.remove(pair)
                save_data()
                await m.answer("✅ Пара удалена!", reply_markup=get_keyboard())
            else:
                await m.answer("⚠️ Такая пара не найдена.")
        else:
            await m.answer("⚠️ Введите ровно два имени через пробел:")

if __name__ == "__main__":
    import asyncio
    load_data()
    asyncio.run(dp.start_polling(bot))
