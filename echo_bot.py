import os
import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PORT = int(os.getenv("PORT", "8080"))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

dp = Dispatcher()

async def get_ai_response(prompt: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/your_bot", # Требование OpenRouter
        "X-Title": "My Telegram Bot"
    }
    payload = {
        "model": "liquid/lfm-3-1.7b:free", # Бесплатная модель!
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=40) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    err = await resp.text()
                    log.error(f"Ошибка OpenRouter: {err}")
                    return f"Ошибка OpenRouter: {resp.status}"
    except Exception as e:
        log.error(f"Ошибка сети: {e}")
        return "Нейросеть временно недоступна."

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("Привет! Я умный бот на OpenRouter. Спроси меня о чем угодно!")

@dp.message(F.text & ~F.text.startswith("/"))
async def chat_handler(message: types.Message):
    await message.bot.send_chat_action(message.chat.id, "typing")
    answer = await get_ai_response(message.text)
    await message.answer(answer)

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
        web.run_app(app, host="0.0.0.0", port=PORT)
    else:
        asyncio.run(dp.start_polling(bot))

if __name__ == "__main__":
    main()
