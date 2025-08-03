import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from dotenv import load_dotenv
import random
from datetime import datetime

# Загрузка токена из .env
load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Список скороговорок
tongue_twisters = [
    "Шла Саша по шоссе и сосала сушку",
    "Карл у Клары украл кораллы, а Клара у Карла украла кларнет",
    "От топота копыт пыль по полю летит",
    "На дворе трава, на траве дрова",
    "Ехал Грека через реку, видит Грека — в реке рак"
]

# Клавиатура
keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(KeyboardButton("🎯 Начать день"))
keyboard.add(KeyboardButton("🗣 Скороговорка"))
keyboard.add(KeyboardButton("✅ Отметить как сделано"))

# Хранилище дней streak
user_streak = {}
user_last_day = {}

@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    await message.reply(
        "👋 Привет! Я бот для тренировки дикции и речи.\nНажми 🎯 «Начать день» — и начнём!",
        reply_markup=keyboard
    )

@dp.message_handler(lambda message: message.text == "🎯 Начать день")
async def start_day(message: types.Message):
    user_id = message.from_user.id
    today = datetime.now().date()

    last_day = user_last_day.get(user_id)
    if last_day == today:
        await message.answer("Ты уже начал сегодня. Не забывай отметить выполнение ✅")
    else:
        user_last_day[user_id] = today
        streak = user_streak.get(user_id, 0) + 1
        user_streak[user_id] = streak
        await message.answer(
            f"📝 Чек-лист на сегодня:\n\n"
            f"1. Артикуляционная разминка\n"
            f"2. Скороговорки (3 подхода)\n"
            f"3. Пробка/карандаш во рту — тренировка\n"
            f"4. Мимика перед зеркалом\n"
            f"5. Видео/аудио запись речи\n\n"
            f"🔁 Стрик: {streak} дней подряд\n"
            f"Не забудь нажать ✅ когда всё сделаешь!"
        )

@dp.message_handler(lambda message: message.text == "🗣 Скороговорка")
async def send_tongue_twister(message: types.Message):
    twister = random.choice(tongue_twisters)
    await message.answer(f"🔈 Вот скороговорка:\n\n\"{twister}\"")

@dp.message_handler(lambda message: message.text == "✅ Отметить как сделано")
async def mark_done(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_streak:
        await message.answer("Сначала начни день с кнопки 🎯")
    else:
        await message.answer("🔥 Молодец! День выполнен. До завтра 🙌")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)