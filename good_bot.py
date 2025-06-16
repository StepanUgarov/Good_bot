import logging
import os
import asyncio
import datetime as dt
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Токен бота не найден в .env файле!")

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler()

# Программы голодания
FASTING_PROGRAMS = {
    "16/8": (16, 8),
    "18/6": (18, 6), 
    "20/4": (20, 4),
}

# Состояния FSM
class FastingStates(StatesGroup):
    WAITING_PROGRAM = State()
    WAITING_TIME = State()
    CONFIRMATION = State()

# ========================
# Обработчики сообщений
# ========================

# Команда /start
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=program)] for program in FASTING_PROGRAMS],
        resize_keyboard=True
    )

    await message.answer(
        "🏆 Выберите программу интервального голодания:",
        reply_markup=keyboard
    )
    await state.set_state(FastingStates.WAITING_PROGRAM)

# Обработка выбора программы
@dp.message(FastingStates.WAITING_PROGRAM)
async def program_handler(message: types.Message, state: FSMContext):
    if message.text not in FASTING_PROGRAMS:
        await message.answer("Пожалуйста, выберите программу из списка.")
        return

    await state.update_data(program=message.text)
    await message.answer(
        "⏳ Введите время последнего приема пищи в формате ЧЧ:ММ\n"
        "Или нажмите /now чтобы использовать текущее время",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await dp.fsm.set_state(user_id=message.from_user.id, state=FastingStates.WAITING_TIME)

# Обработка ввода времени
@dp.message(FastingStates.WAITING_TIME)
async def time_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()

    if message.text == "/now":
        last_meal = dt.datetime.now()
    else:
        try:
            hours, minutes = map(int, message.text.split(":"))
            last_meal = dt.datetime.now().replace(
                hour=hours,
                minute=minutes,
                second=0,
                microsecond=0
            )
        except ValueError:
            await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ")
            return

    fasting_hours, eating_hours = FASTING_PROGRAMS[data["program"]]
    fasting_end = last_meal + dt.timedelta(hours=fasting_hours)
    window_end = last_meal + dt.timedelta(hours=eating_hours)

    await state.update_data(
        last_meal=last_meal,
        fasting_end=fasting_end,
        window_end=window_end
    )

    # Запланировать напоминание через 5 минут после окна питания
    reminder_time = window_end + dt.timedelta(minutes=5)
    scheduler.add_job(
        send_reminder,
        "date",
        run_date=reminder_time,
        args=[message.chat.id],
    )

    # Клавиатура подтверждения
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="✅ Всё верно")],
            [types.KeyboardButton(text="✏️ Исправить время")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        f"🔍 Проверьте данные:\n"
        f"▪ Программа: {data['program']}\n"
        f"▪ Последний прием: {last_meal.strftime('%H:%M')}\n"
        f"▪ Окно питания до: {window_end.strftime('%H:%M')}\n"
        f"▪ Голодание до: {fasting_end.strftime('%H:%M')}\n\n"
        f"Если всё правильно, нажмите <b>✅ Всё верно</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await dp.fsm.set_state(user_id=message.from_user.id, state=FastingStates.CONFIRMATION)

# Напоминание о проверке времени
async def send_reminder(chat_id: int):
    await bot.send_message(
        chat_id,
        "🔄 Вы поели? Если нужно изменить время последнего приема пищи, "
        "нажмите /edit_time",
        reply_markup=types.ReplyKeyboardRemove()
    )

# Обработка подтверждения
@dp.message(FastingStates.CONFIRMATION)
async def confirmation_handler(message: types.Message, state: FSMContext):
    if message.text == "✅ Всё верно":
        data = await state.get_data()
        await message.answer(
            f"⏳ Голодание начато! Следующий прием пищи в {data['fasting_end'].strftime('%H:%M')}",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.clear()
    elif message.text == "✏️ Исправить время":
        await message.answer(
            "🔄 Введите новое время последнего приема пищи (ЧЧ:ММ) или /now",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await dp.fsm.set_state(user_id=message.from_user.id, state=FastingStates.WAITING_TIME)

# Команда /edit_time
@dp.message(Command("edit_time"))
async def edit_time_handler(message: types.Message):
    await message.answer(
        "🔄 Введите новое время последнего приема пищи (ЧЧ:ММ) или /now",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await dp.fsm.set_state(user_id=message.from_user.id, state=FastingStates.WAITING_TIME)

# ========================
# Запуск бота
# ========================

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
