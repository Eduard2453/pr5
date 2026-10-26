import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
import ollama

# Укажите токен вашего Telegram-бота
BOT_TOKEN = "8804982952:AAEfsi9vLUyicFDK1CDf7Az2dDTl1p_b_AA"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Словарь для хранения истории сообщений {user_id: [список сообщений]}
# Каждое сообщение хранится в формате словаря: {"role": "user"/"assistant", "content": "текст"}
user_history = {}

# Максимальное количество хранимых сообщений (последние 5 запросов + 5 ответов)
MAX_HISTORY = 10
# Название модели, которую вы скачали в Ollama
MODEL_NAME = "qwen2.5:3b"

# Команда /start
@dp.message(Command("start"))
async def start_cmd(message: Message):
    user_history[message.from_user.id] = []  # Очищаем историю при старте
    await message.answer(
        f"Привет! Я умный чат-бот, работающий на локальной модели {MODEL_NAME}.\n"
        "Задай мне любой вопрос! Для очистки контекста используй /clear."
    )

# Команда /clear для очистки истории диалога
@dp.message(Command("clear"))
async def clear_cmd(message: Message):
    user_id = message.from_user.id
    user_history[user_id] = []
    await message.answer("🧹 История нашего диалога успешно очищена!")

# Обработка всех текстовых сообщений от пользователя
@dp.message(F.text)
async def chat_with_llm(message: Message):
    user_id = message.from_user.id
    user_text = message.text

    # Если пользователя еще нет в словаре истории, создаем для него пустой список
    if user_id not in user_history:
        user_history[user_id] = []

    # Добавляем новое сообщение пользователя в историю
    user_history[user_id].append({"role": "user", "content": user_text})

    # Обрезаем историю, если она превышает лимит (помним последние 5 диалогов)
    if len(user_history[user_id]) > MAX_HISTORY:
        user_history[user_id] = user_history[user_id][-MAX_HISTORY:]

    # Отправляем временный статус, чтобы пользователь видел, что бот «думает»
    waiting_message = await message.answer("🔄 Думаю над ответом...")

    try:
        # Запрос к локальной Ollama с передачей всей истории
        response = ollama.chat(
            model=MODEL_NAME,
            messages=user_history[user_id]
        )
        
        # Получаем текст ответа
        bot_response = response['message']['content']

        # Добавляем ответ бота в историю, чтобы поддерживать контекст
        user_history[user_id].append({"role": "assistant", "content": bot_response})

        # Удаляем сообщение "Думаю..." и присылаем настоящий ответ
        await waiting_message.delete()
        await message.answer(bot_response)

    except Exception as e:
        await waiting_message.delete()
        await message.answer(f"❌ Произошла ошибка при обращении к Ollama: {e}\nУбедитесь, что приложение Ollama запущено.")

# Запуск бота в режиме Long Polling
async def main():
    print("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

