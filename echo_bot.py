import os
import asyncio
import logging
import json
import datetime
import math
import zoneinfo

import google.generativeai as genai
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", "8080"))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

dp = Dispatcher()

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# ИНСТРУМЕНТЫ (TOOLS)
# ==========================================
def get_weather(city: str) -> str:
    """Возвращает текущую погоду в указанном городе."""
    fake = {"москва": "-3 C, снег", "сочи": "+18 C, солнечно"}
    return f"Погода в {city}: {fake.get(city.lower(), '+15 C, ясно')}"

def get_time(timezone: str = "UTC") -> str:
    """Возвращает текущее время в указанном часовом поясе."""
    try:
        tz = zoneinfo.ZoneInfo(timezone)
        return datetime.datetime.now(tz).strftime(f"%H:%M (%Y-%m-%d, {timezone})")
    except Exception:
        return "Неизвестный часовой пояс."

def calculate(expression: str) -> str:
    """Вычисляет математическое выражение."""
    allowed = {"abs": abs, "round": round, "sqrt": math.sqrt, "pi": math.pi}
    try:
        return str(eval(expression, {"__builtins__": {}}, allowed))
    except Exception as e:
        return f"Ошибка: {e}"

# Список функций, которые может вызывать нейросеть
TOOL_FUNCTIONS = [get_weather, get_time, calculate]

# Инициализация модели с инструментами
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    tools=TOOL_FUNCTIONS,
    system_instruction="Ты умный ассистент. Отвечай на русском. Используй инструменты для погоды, времени или математики, если это нужно."
)

# ==========================================
# ЛОГИКА АГЕНТА
# ==========================================
async def run_agent(user_text: str) -> str:
    try:
        # Запускаем чат (для сохранения контекста можно хранить историю, но здесь простой запрос)
        chat = model.start_chat(enable_automatic_function_calling=True)
        
        # Отправляем запрос. Google сам вызовет нужные Python-функции и вернет ответ.
        response = await chat.send_message_async(user_text)
        
        # Логируем вызовы инструментов (для отчета)
        for message in chat.history:
            if message.parts and message.parts[0].function_call:
                fn = message.parts[0].function_call
                log.info(f"[tool] {fn.name} вызван!")
                
        return response.text
    except Exception as e:
        return f"Ошибка Gemini: {e}"

# ==========================================
# ОБРАБОТЧИКИ TELEGRAM
# ==========================================
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("Привет! Я умный бот на базе Google Gemini. Напиши вопрос (погода, время, счёт).")

@dp.message(F.text & ~F.text.startswith("/"))
async def handler(message: types.Message):
    await message.bot.send_chat_action(message.chat.id, "typing")
    ans = await run_agent(message.text)
    await message.answer(ans)

# ==========================================
# ЗАПУСК (Webhook / Polling)
# ==========================================
async def on_startup(bot: Bot):
    if WEBHOOK_URL:
        await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
        log.info(f"Webhook установлен: {WEBHOOK_URL}/webhook")

def main():
    if not BOT_TOKEN: raise SystemExit("BOT_TOKEN не задан")
    
    bot = Bot(token=BOT_TOKEN)
    if WEBHOOK_URL:
        dp.startup.register(on_startup)
        app = web.Application()
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
        setup_application(app, dp, bot=bot)
        log.info(f"Webhook запуск на порту {PORT}")
        web.run_app(app, host="0.0.0.0", port=PORT)
    else:
        log.info("Polling запуск (локально)")
        asyncio.run(dp.start_polling(bot))

if __name__ == "__main__":
    main()

