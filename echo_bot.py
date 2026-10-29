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
HF_TOKEN = os.getenv("HF_TOKEN")  # Наш ключ Hugging Face
PORT = int(os.getenv("PORT", "8080"))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

dp = Dispatcher()

async def get_ai_response(prompt: str) -> str:
    # Используем API Hugging Face
    API_URL = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-72B-Instruct"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    # Формируем запрос в формате чата
    payload = {
        "inputs": f"Ты умный ассистент. Отвечай на русском языке.\n\nПользователь: {prompt}\nАссистент:",
        "parameters": {"max_new_tokens": 500, "temperature": 0.7}
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, headers=headers, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Извлекаем ответ из JSON
                    if isinstance(data, list) and len(data) > 0:
                        text = data[0].get("generated_text", "")
                        # Отрезаем наш промпт от ответа
                        if "Ассистент:" in text:
                            return text.split("Ассистент:")[-1].strip()
                        return text
                    return "Нейросеть вернула пустой ответ."
                elif resp.status == 503:
                    return "Нейросеть просыпается (это бывает при первом запросе). Подождите 10 секунд и напишите снова."
                else:
                    err = await resp.text()
                    log.error(f"Ошибка HF: {err}")
                    return "Ошибка нейросети. Попробуйте позже."
    except Exception as e:
        log.error(f"Ошибка: {e}")
        return "Нейросеть временно недоступна."

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("Привет! Я умный бот. Спроси меня о чем угодно!")

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
