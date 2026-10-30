import base64
import json
import logging
import os
import random
import urllib.request
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = "9275964752:AAHhDAMBKHW8WxKrjUv1fKApP3Xa9Jg8GEU"
ADMIN_IDS = {107742498, 92769858}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

DATA_FILE = "bot_database.json"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

PLAYERS_POOL = set()
PLAYER_SKILLS = {}
EXCLUDED_PAIRS = set()
USER_STATES = {}


def load_data():
    global PLAYERS_POOL, PLAYER_SKILLS, EXCLUDED_PAIRS
    if GITHUB_TOKEN and GITHUB_REPO:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "TelegramBot",
            },
        )
        try:
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                file_content = base64.b64decode(res_data["content"]).decode(
                    "utf-8"
                )
                data = json.loads(file_content)
                PLAYERS_POOL = set(data.get("players", []))
                PLAYER_SKILLS = data.get("skills", {})
                EXCLUDED_PAIRS = {
                    frozenset(pair) for pair in data.get("excludes", [])
                }
                logging.info("Данные успешно загружены с GitHub!")
                return
        except Exception as e:
            logging.warning(
                f"Не удалось загрузить с GitHub, проверяем локальный файл: {e}"
            )

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                PLAYERS_POOL = set(data.get("players", []))
                PLAYER_SKILLS = data.get("skills", {})
                EXCLUDED_PAIRS = {
                    frozenset(pair) for pair in data.get("excludes", [])
                }
        except Exception as e:
            logging.error(f"Ошибка загрузки локального файла: {e}")


def save_data():
    data = {
        "players": list(PLAYERS_POOL),
        "skills": PLAYER_SKILLS,
        "excludes": [list(pair) for pair in EXCLUDED_PAIRS],
    }
    json_str = json.dumps(data, ensure_ascii=False, indent=4)

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            f.write(json_str)
    except Exception as e:
        logging.error(f"Ошибка сохранения локального файла: {e}")

    if GITHUB_TOKEN and GITHUB_REPO:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
        content_encoded = base64.b64encode(json_str.encode("utf-8")).decode(
            "utf-8"
        )

        sha = None
        req_get = urllib.request.Request(
            url,
            headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "TelegramBot",
            },
        )
        try:
            with urllib.request.urlopen(req_get) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                sha = res_data.get("sha")
        except Exception:
            pass

        payload = {
            "message": "Auto-update bot database [skip ci]",
            "content": content_encoded,
            "branch": GITHUB_BRANCH,
        }
        if sha:
            payload["sha"] = sha

        req_put = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
