import os
import asyncio
import logging
import json
import datetime
import math
import zoneinfo

from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", "8080"))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

dp = Dispatcher()
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ==========================================
# ИНСТРУМЕНТЫ
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
    {"type": "function", "function": {"name": "get_weather", "description": "Погода в городе", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}},
    {"type": "function", "function": {"name": "get_time", "description": "Текущее время", "parameters": {"type": "object", "properties": {"timezone": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "calculate", "description": "Калькулятор", "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}}
]

async def run_agent(user_text: str) -> str:
    messages = [
        {"role": "system", "content": "Ты умный ассистент. Отвечай на русском. Используй инструменты для погоды, времени или математики."},
        {"role": "user", "content": user_text}
    ]
    
    for _ in range(5):
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto"
        )
        msg = response.choices[0].message
        
        if not msg.tool_calls:
            return msg.content or "Пусто"
        
        messages.append(msg)
        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            
            res = TOOL_FUNCTIONS[name](**args) if name in TOOL_FUNCTIONS else "Ошибка инструмента"
            log.info(f"[tool] {name}({args}) -> {res}")
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(res)
            })
    return "Не удалось завершить."

# ==========================================
# ОБРАБОТЧИКИ
# ==========================================
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("Привет! Я умный бот в облаке. Напиши вопрос (погода, время, счёт).")

@dp.message(F.text & ~F.text.startswith("/"))
async def handler(message: types.Message):
    await message.bot.send_chat_action(message.chat.id, "typing")
    try:
        ans = await run_agent(message.text)
    except Exception as e:
        ans = f"Ошибка OpenAI: {e}"
    await message.answer(ans)

# ==========================================
# ЗАПУСК
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
