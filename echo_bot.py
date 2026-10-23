import os
import asyncio
import logging
import json
import datetime
import math
import zoneinfo

import ollama
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv

# Загружаем .env (если файл есть)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Если есть — работаем в облаке
PORT = int(os.getenv("PORT", "8080"))
MODEL = "llama3.2"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

dp = Dispatcher()

# ==========================================
# ИНСТРУМЕНТЫ (из Задания 9)
# ==========================================
def get_weather(city: str) -> str:
    fake = {"москва": "-3 C, снег", "сочи": "+18 C, солнечно"}
    return f"Погода в {city}: {fake.get(city.lower(), '+15 C, ясно')}"

def get_time(timezone: str = "UTC") -> str:
    try:
        tz = zoneinfo.ZoneInfo(timezone)
        return datetime.datetime.now(tz).strftime(f"%H:%M (%Y-%m-%d, {timezone})")
    except Exception:
        return "Неизвестный часовой пояс."

def calculate(expression: str) -> str:
    allowed = {"abs": abs, "round": round, "sqrt": math.sqrt, "pi": math.pi}
    try:
        return str(eval(expression, {"__builtins__": {}}, allowed))
    except Exception as e:
        return f"Ошибка: {e}"

TOOL_FUNCTIONS = {"get_weather": get_weather, "get_time": get_time, "calculate": calculate}

TOOLS_SCHEMA = [
    {"type": "function", "function": {"name": "get_weather", "description": "Погода", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}},
    {"type": "function", "function": {"name": "get_time", "description": "Время", "parameters": {"type": "object", "properties": {"timezone": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "calculate", "description": "Калькулятор", "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}},
]

async def run_agent(user_text: str) -> str:
    messages = [{"role": "system", "content": "Ты ассистент. Используй инструменты."}, {"role": "user", "content": user_text}]
    for _ in range(5):
        resp = await asyncio.to_thread(ollama.chat, model=MODEL, messages=messages, tools=TOOLS_SCHEMA)
        msg = resp["message"]
        if not msg.get("tool_calls"):
            return msg.get("content") or "Пусто"
        messages.append(msg)
        for call in msg["tool_calls"]:
            name = call["function"]["name"]
            args = call["function"].get("arguments") or {}
            if isinstance(args, str):
                try: args = json.loads(args)
                except: args = {}
            res = TOOL_FUNCTIONS[name](**args) if name in TOOL_FUNCTIONS else "Нет инструмента"
            messages.append({"role": "tool", "content": str(res), "name": name})
    return "Слишком долго."

# ==========================================
# ОБРАБОТЧИКИ TELEGRAM
# ==========================================
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("Привет! Напиши вопрос (погода/время/счёт) или просто текст.")

@dp.message(F.text & ~F.text.startswith("/"))
async def handler(message: types.Message):
    await message.bot.send_chat_action(message.chat.id, "typing")
    try:
        ans = await run_agent(message.text)
    except Exception as e:
        ans = f"Ошибка: {e}"
    await message.answer(ans)

# ==========================================
# ЗАПУСК (Webhook для Railway / Polling для ПК)
# ==========================================
async def on_startup(bot: Bot):
    if WEBHOOK_URL:
        await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
        log.info(f"Webhook установлен: {WEBHOOK_URL}/webhook")

def main():
    if not BOT_TOKEN:
        print("ОШИБКА: не задан BOT_TOKEN в файле .env")
        return

    bot = Bot(token=BOT_TOKEN)
    
    # Если есть WEBHOOK_URL — значит мы в облаке
    if WEBHOOK_URL:
        dp.startup.register(on_startup)
        app = web.Application()
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
        setup_application(app, dp, bot=bot)
        log.info(f"Запуск в режиме Webhook на порту {PORT}")
        web.run_app(app, host="0.0.0.0", port=PORT)
    else:
        # Иначе запускаем обычный локальный бот
        log.info("Запуск в режиме Long Polling (локально)")
        asyncio.run(dp.start_polling(bot))

if __name__ == "__main__":
    main()