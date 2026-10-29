import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
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

main_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Привет"), KeyboardButton(text="Помощь")]],
    resize_keyboard=True
)

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("Привет! Я работаю в облаке 24/7. Напиши что-нибудь, и я повторю.", reply_markup=main_kb)

@dp.message(F.text == "Привет")
async def hi(message: types.Message):
    await message.answer("И тебе привет! 👋")

@dp.message(F.text == "Помощь")
async def help_cmd(message: types.Message):
    await message.answer("Просто напиши любой текст, и я его повторю.")

@dp.message(F.text & ~F.text.startswith("/"))
async def echo(message: types.Message):
    await message.answer(f"Ты написал: {message.text}")

async def on_startup(bot: Bot):
    if WEBHOOK_URL:
        await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
        log.info(f"Webhook установлен: {WEBHOOK_URL}/webhook")

def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN не задан")
    
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
