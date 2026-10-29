import os
import asyncio
import logging
import json
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", "8080"))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

dp = Dispatcher()

# Функция запроса к бесплатному DuckDuckGo AI
async def get_ai_response(prompt: str) -> str:
    url = "https://duckduckgo.com/duckchat/v1/chat"
    headers = {
        "x-vqd-accept": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            # 1. Получаем токен сессии
            async with session.get("https://duckduckgo.com/duckchat/v1/status", headers=headers) as resp:
                if resp.status != 200:
                    return "Ошибка: не удалось подключиться к нейросети."
                vqd = resp.headers.get("x-vqd-4")
                if not vqd:
                    return "Ошибка: сервер не выдал токен."
            
            # 2. Отправляем сообщение
            headers["x-vqd-4"] = vqd
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}]
            }
            
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    return f"Ошибка сервера: {resp.status}"
                
                # Читаем ответ построчно (сервер шлет поток данных)
                full_text = ""
                async for line in resp.content:
                    line_str = line.decode('utf-8').strip()
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if "message" in data:
                                full_text += data["message"]
                        except json.JSONDecodeError:
                            pass
                
                return full_text if full_text else "Нейросеть промолчала."
                
        except Exception as e:
            log.error(f"Ошибка DuckDuckGo: {e}")
            return "Извините, нейросеть временно недоступна."

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("Привет! Я умный бот (нейросеть GPT-4o mini). Спроси меня о чем угодно!")

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
