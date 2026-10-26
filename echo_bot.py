import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Загружаем переменные из .env (нужно только для локальных тестов)
load_dotenv()

# Достаем переменные окружения (на Railway они задаются в панели управления)
BOT_TOKEN = os.getenv("TOKEN")
MODEL_NAME = os.getenv("LLM_MODEL", "qwen2.5:3b")

# Инициализируем асинхронный клиент. 
# По умолчанию он смотрит на официальный API OpenAI, но на Railway вы сможете 
# переопределить BASE_URL на любой бесплатный провайдер (Groq, OpenRouter, Gemini)
openai_client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://openai.com")
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Словарь для хранения истории сообщений {user_id: [список сообщений]}
user_history = {}
MAX_HISTORY = 10


@dp.message(Command("start"))
async def start_cmd(message: Message):
    user_history[message.from_user.id] = []
    await message.answer(
        f"Привет! Я умный чат-бот, работающий на модели {MODEL_NAME}.\n"
        "Задай мне любой вопрос! Для очистки контекста используй /clear."
    )


@dp.message(Command("clear"))
async def clear_cmd(message: Message):
    user_id = message.from_user.id
    user_history[user_id] = []
    await message.answer("🧹 История нашего диалога успешно очищена!")


@dp.message(F.text)
async def chat_with_llm(message: Message):
    user_id = message.from_user.id
    user_text = message.text

    if user_id not in user_history:
        user_history[user_id] = []

    user_history[user_id].append({"role": "user", "content": user_text})

    if len(user_history[user_id]) > MAX_HISTORY:
        user_history[user_id] = user_history[user_id][-MAX_HISTORY:]

    waiting_message = await message.answer("🔄 Думаю над ответом...")

    try:
        # Асинхронный запрос к языковой модели через универсальный клиент
        response = await openai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=user_history[user_id]
        )
        
        bot_response = response.choices[0].message.content

        user_history[user_id].append({"role": "assistant", "content": bot_response})

        await waiting_message.delete()
        await message.answer(bot_response)

    except Exception as e:
        await waiting_message.delete()
        await message.answer(f"❌ Произошла ошибка при обращении к ИИ: {e}")


async def main():
    print(f"Бот успешно запущен на базе модели {MODEL_NAME}!")
    # Сбрасываем старые сообщения, которые пришли пока бот спал
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

