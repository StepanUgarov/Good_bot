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

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler()

# Программы голодания
FASTING_PROGRAMS = {
    "16/8": (16, 8),  # 16 часов голодания, 8 часов окно питания
    "18/6": (18, 6),
    "20/4": (20, 4),
}

# Состояния FSM
class FastingStates(StatesGroup):
    WAITING_PROGRAM = State()
    WAITING_TIME = State()
    CONFIRMATION = State()
    FASTING_PERIOD = State()  # Новое состояние для периода голодания

# Обработчики
@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    buttons = [
        [types.KeyboardButton(text=program)]
        for program in FASTING_PROGRAMS
    ]
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )
    
    await message.answer(
        "🏆 Выберите программу интервального голодания:",
        reply_markup=keyboard
    )
    await state.set_state(FastingStates.WAITING_PROGRAM)

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
    await state.set_state(FastingStates.WAITING_TIME)

@dp.message(FastingStates.WAITING_TIME)
async def time_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()

    # Определяем время последнего приёма пищи
    if message.text == "/now":
        last_meal = dt.datetime.now()
    else:
        try:
            hours, minutes = map(int, message.text.split(":"))
            now = dt.datetime.now()
            last_meal = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)

            # Если указанное время позже текущего — предположим, это вчерашний приём
            if last_meal > now:
                last_meal -= dt.timedelta(days=1)

        except ValueError:
            await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ")
            return

    fasting_hours, eating_hours = FASTING_PROGRAMS[data["program"]]

    # Расчёт времени
    fasting_start = last_meal  # последний приём — начало голодания
    fasting_end = fasting_start + dt.timedelta(hours=fasting_hours)
    eating_window_start = last_meal - dt.timedelta(hours=eating_hours)

    await state.update_data(
        last_meal=last_meal,
        fasting_start=fasting_start,
        fasting_end=fasting_end,
        eating_window_start=eating_window_start,
    )

    # Планируем уведомления
    scheduler.add_job(
        notify_fasting_start,
        "date",
        run_date=fasting_start,
        args=[message.chat.id],
    )

    scheduler.add_job(
        notify_fasting_end,
        "date",
        run_date=fasting_end - dt.timedelta(minutes=30),
        args=[message.chat.id],
    )

    scheduler.add_job(
        notify_fasting_complete,
        "date",
        run_date=fasting_end,
        args=[message.chat.id],
    )

    # Клавиатура подтверждения
    confirm_buttons = [
        [types.KeyboardButton(text="✅ Подтвердить")],
        [types.KeyboardButton(text="✏️ Изменить время")],
        [types.KeyboardButton(text="❌ Отмена")]
    ]
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=confirm_buttons,
        resize_keyboard=True
    )

    await message.answer(
        f"🔍 Проверьте данные:\n"
        f"▪ Программа: {data['program']}\n"
        f"▪ Последний приём: {last_meal.strftime('%H:%M')}\n"
        f"▪ Окно питания: с {eating_window_start.strftime('%H:%M')} до {last_meal.strftime('%H:%M')}\n"
        f"▪ Голодание до: {fasting_end.strftime('%H:%M')}\n\n"
        f"Если всё верно, нажмите <b>✅ Подтвердить</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await state.set_state(FastingStates.CONFIRMATION)


async def notify_eating_window_end(chat_id: int):
    await bot.send_message(
        chat_id,
        "🕒 Окно питания заканчивается через 30 минут!",
        reply_markup=types.ReplyKeyboardRemove()
    )

async def notify_fasting_start(chat_id: int):
    await bot.send_message(
        chat_id,
        "⏳ Период голодания начался!",
        reply_markup=types.ReplyKeyboardRemove()
    )

async def notify_fasting_end(chat_id: int):
    await bot.send_message(
        chat_id,
        "🕒 Голодание заканчивается через 30 минут!",
        reply_markup=types.ReplyKeyboardRemove()
    )

@dp.message(FastingStates.CONFIRMATION)
async def confirmation_handler(message: types.Message, state: FSMContext):
    if message.text == "✅ Подтвердить":
        data = await state.get_data()
        await message.answer(
            f"⏳ Голодание начато! Следующий прием пищи в {data['fasting_end'].strftime('%H:%M')}",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.set_state(FastingStates.FASTING_PERIOD)
    elif message.text == "✏️ Изменить время":
        await message.answer(
            "🔄 Введите новое время последнего приема пищи (ЧЧ:ММ) или /now",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.set_state(FastingStates.WAITING_TIME)

@dp.message(Command("edit_time"))
async def edit_time_handler(message: types.Message, state: FSMContext):
    await message.answer(
        "🔄 Введите новое время последнего приема пищи (ЧЧ:ММ) или /now",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(FastingStates.WAITING_TIME)

@dp.message(FastingStates.FASTING_PERIOD)
async def fasting_period_handler(message: types.Message, state: FSMContext):
    if message.text == "✏️ Изменить время":
        await message.answer(
            "🔄 Введите новое время последнего приема пищи (ЧЧ:ММ) или /now",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.set_state(FastingStates.WAITING_TIME)

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
