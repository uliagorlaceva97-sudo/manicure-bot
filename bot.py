import asyncio
import sqlite3
import os
from datetime import datetime
from calendar import monthcalendar, month_name
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession

# --- Конфигурация (берем из переменных окружения) ---
API_TOKEN = os.getenv('API_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')

if not API_TOKEN:
    raise ValueError("API_TOKEN не установлен!")
if not ADMIN_ID:
    raise ValueError("ADMIN_ID не установлен!")

# Преобразуем ADMIN_ID в число
ADMIN_ID = int(ADMIN_ID)

TIME_SLOTS = ["8.00-10.00", "11.00-13.00", "14.00-16.00"]

PRICE_LIST = """
💅 *ПРАЙС-ЛИСТ НА МАНИКЮР*

✨ *КЛАССИЧЕСКИЙ МАНИКЮР*
• Обрезной маникюр — 1000 руб.
• Необрезной маникюр — 1200 руб.
• Комбинированный маникюр — 1300 руб.

💎 *АППАРАТНЫЙ МАНИКЮР*
• Аппаратный маникюр — 1500 руб.

🎨 *ПОКРЫТИЕ*
• Однотонное покрытие (гель-лак) — 800 руб.
• Френч — 1000 руб.
• Дизайн на 1 ноготь — 100 руб.
• Дизайн на все ногти — 800 руб.

💆 *УХОД*
• SPA-уход (парафинотерапия, маска) — 500 руб.
• Наращивание ногтей (1 ноготь) — 300 руб.
• Полное наращивание — 3000 руб.

📞 *Запись и вопросы:* +7 (XXX) XXX-XX-XX
📍 *Адрес:* ул. Примерная, д. 123

*Ждем вас!* 💅✨
"""

REVIEWS_LINK = "https://t.me/your_reviews_channel"

session = AiohttpSession()
bot = Bot(token=API_TOKEN, session=session)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- База данных ---
def init_db():
    conn = sqlite3.connect('bookings.db')
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            client_name TEXT,
            client_phone TEXT,
            booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def clear_expired_bookings():
    conn = sqlite3.connect('bookings.db')
    cur = conn.cursor()
    now = datetime.now()
    cur.execute("SELECT id, date, time_slot FROM bookings WHERE status = 'active'")
    rows = cur.fetchall()
    for booking_id, date_str, slot_str in rows:
        start_time_str = slot_str.split('-')[0]
        try:
            slot_datetime = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H.%M")
            if slot_datetime < now:
                cur.execute("UPDATE bookings SET status = 'expired' WHERE id = ?", (booking_id,))
        except:
            pass
    conn.commit()
    conn.close()

def user_has_active_booking(user_id):
    conn = sqlite3.connect('bookings.db')
    cur = conn.cursor()
    now = datetime.now()
    cur.execute("SELECT date, time_slot FROM bookings WHERE user_id = ? AND status = 'active'", (user_id,))
    rows = cur.fetchall()
    conn.close()
    for date_str, slot_str in rows:
        start_time_str = slot_str.split('-')[0]
        slot_datetime = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H.%M")
        if slot_datetime > now:
            return True
    return False

def get_user_active_booking(user_id):
    conn = sqlite3.connect('bookings.db')
    cur = conn.cursor()
    now = datetime.now()
    cur.execute("SELECT id, date, time_slot, client_name, client_phone FROM bookings WHERE user_id = ? AND status = 'active'", (user_id,))
    rows = cur.fetchall()
    conn.close()
    for booking_id, date_str, slot_str, client_name, client_phone in rows:
        start_time_str = slot_str.split('-')[0]
        slot_datetime = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H.%M")
        if slot_datetime > now:
            return {'id': booking_id, 'date': date_str, 'time': slot_str, 'name': client_name, 'phone': client_phone}
    return None

def cancel_booking(booking_id):
    conn = sqlite3.connect('bookings.db')
    cur = conn.cursor()
    cur.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()

def is_slot_free(date_str, time_slot):
    conn = sqlite3.connect('bookings.db')
    cur = conn.cursor()
    cur.execute("SELECT id FROM bookings WHERE date = ? AND time_slot = ? AND status = 'active'", (date_str, time_slot))
    result = cur.fetchone()
    conn.close()
    return result is None

def get_free_slots(date_str):
    return [slot for slot in TIME_SLOTS if is_slot_free(date_str, slot)]

def make_booking(user_id, username, date_str, time_slot, client_name, client_phone):
    conn = sqlite3.connect('bookings.db')
    cur = conn.cursor()
    cur.execute("INSERT INTO bookings (user_id, username, date, time_slot, client_name, client_phone, status) VALUES (?, ?, ?, ?, ?, ?, 'active')",
                (user_id, username, date_str, time_slot, client_name, client_phone))
    booking_id = cur.lastrowid
    conn.commit()
    conn.close()
    return booking_id

def get_all_active_bookings():
    conn = sqlite3.connect('bookings.db')
    cur = conn.cursor()
    now = datetime.now()
    cur.execute("SELECT id, user_id, username, date, time_slot, client_name, client_phone, booked_at FROM bookings WHERE status = 'active' ORDER BY date, time_slot")
    rows = cur.fetchall()
    conn.close()
    future_bookings = []
    for row in rows:
        booking_id, user_id, username, date_str, slot_str, client_name, client_phone, booked_at = row
        start_time_str = slot_str.split('-')[0]
        slot_datetime = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H.%M")
        if slot_datetime > now:
            future_bookings.append({'id': booking_id, 'user_id': user_id, 'username': username, 'date': date_str, 'time': slot_str, 'name': client_name, 'phone': client_phone, 'booked_at': booked_at})
    return future_bookings

async def notify_admin(booking_id, user_id, username, date_str, time_slot, client_name, client_phone):
    message = f"🆕 НОВАЯ ЗАПИСЬ!\n\n📅 Дата: {date_str}\n⏰ Время: {time_slot}\n👤 Имя: {client_name}\n📞 Телефон: {client_phone}\n🆔 ID: {user_id}\n📝 Username: @{username or 'не указан'}\n🔖 #{booking_id}"
    try:
        await bot.send_message(ADMIN_ID, message)
    except:
        pass

class BookingStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_confirmation = State()

def get_main_menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📝 Запись"), KeyboardButton(text="💰 Прайс"), KeyboardButton(text="⭐️ Отзывы")]], resize_keyboard=True)

def get_calendar_keyboard(year: int, month: int):
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    month_days = monthcalendar(year, month)
    keyboard = []
    nav_row = [InlineKeyboardButton(text="◀️", callback_data=f"cal_prev_{year}_{month}"), InlineKeyboardButton(text=f"{month_name[month]} {year}", callback_data="ignore"), InlineKeyboardButton(text="▶️", callback_data=f"cal_next_{year}_{month}")]
    keyboard.append(nav_row)
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard.append([InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])
    for week in month_days:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                is_past = datetime(year, month, day).date() < now.date()
                free_slots = get_free_slots(date_str)
                is_full = len(free_slots) == 0 and not is_past
                if is_past:
                    row.append(InlineKeyboardButton(text=f"◽️{day}", callback_data="ignore"))
                elif is_full:
                    row.append(InlineKeyboardButton(text=f"🔘{day}", callback_data="ignore"))
                else:
                    display_text = f"🔴{day}" if date_str == today_str else str(day)
                    row.append(InlineKeyboardButton(text=display_text, callback_data=f"date_{date_str}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="📋 Мои записи", callback_data="my_bookings")])
    keyboard.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking")])
    keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    clear_expired_bookings()
    await message.answer("🌸 Добро пожаловать!\n\nВыберите действие:", parse_mode="Markdown", reply_markup=get_main_menu())

@dp.message(lambda m: m.text == "📝 Запись")
async def booking_button(message: types.Message):
    if user_has_active_booking(message.from_user.id):
        b = get_user_active_booking(message.from_user.id)
        await message.answer(f"❌ У вас есть активная запись на {b['date']} {b['time']}\nОтмените её в календаре.")
        return
    now = datetime.now()
    await message.answer("📅 Выберите дату:", reply_markup=get_calendar_keyboard(now.year, now.month))

@dp.message(lambda m: m.text == "💰 Прайс")
async def price_button(message: types.Message):
    await message.answer(PRICE_LIST, parse_mode="Markdown")

@dp.message(lambda m: m.text == "⭐️ Отзывы")
async def reviews_button(message: types.Message):
    await message.answer(f"⭐️ Наши отзывы:\n\n[Читать]({REVIEWS_LINK})", parse_mode="Markdown", disable_web_page_preview=True)

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Нет прав.")
        return
    bookings = get_all_active_bookings()
    if not bookings:
        await message.answer("📭 Нет записей.")
        return
    text = "📋 ЗАПИСИ:\n\n"
    for b in bookings:
        text += f"#{b['id']} {b['date']} {b['time']}\n{b['name']} {b['phone']}\n\n"
    await message.answer(text[:4000])

@dp.callback_query(lambda c: c.data == "main_menu")
async def back_to_menu(callback_query: CallbackQuery):
    await callback_query.answer()
    await callback_query.message.delete()
    await cmd_start(callback_query.message)

@dp.callback_query(lambda c: c.data == "my_bookings")
async def show_my_bookings(callback_query: CallbackQuery):
    await callback_query.answer()
    b = get_user_active_booking(callback_query.from_user.id)
    if not b:
        await callback_query.message.answer("📭 Нет активных записей.")
        return
    await callback_query.message.answer(f"📋 Ваша запись:\n{b['date']} {b['time']}\n{b['name']}\n{b['phone']}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_{b['id']}")]]))

@dp.callback_query(lambda c: c.data.startswith("cancel_"))
async def cancel_booking_start(callback_query: CallbackQuery):
    await callback_query.answer()
    booking_id = int(callback_query.data.split("_")[1])
    b = get_user_active_booking(callback_query.from_user.id)
    if not b or b['id'] != booking_id:
        await callback_query.message.answer("❌ Запись не найдена.")
        return
    await callback_query.message.answer(f"❓ Отменить запись на {b['date']} {b['time']}?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_cancel_{booking_id}"), InlineKeyboardButton(text="❌ Нет", callback_data="back_to_calendar")]]))

@dp.callback_query(lambda c: c.data.startswith("confirm_cancel_"))
async def confirm_cancel(callback_query: CallbackQuery):
    await callback_query.answer()
    booking_id = int(callback_query.data.split("_")[2])
    b = get_user_active_booking(callback_query.from_user.id)
    if not b or b['id'] != booking_id:
        await callback_query.message.answer("❌ Запись уже отменена.")
        return
    cancel_booking(booking_id)
    await callback_query.message.answer(f"✅ Запись на {b['date']} {b['time']} отменена.")
    try:
        await bot.send_message(ADMIN_ID, f"❌ ОТМЕНА #{booking_id}\n{b['date']} {b['time']}\n{b['name']}\n{b['phone']}")
    except:
        pass
    now = datetime.now()
    await callback_query.message.answer("📅 Выберите новую дату:", reply_markup=get_calendar_keyboard(now.year, now.month))

@dp.callback_query(lambda c: c.data == "back_to_calendar")
async def back_to_calendar(callback_query: CallbackQuery):
    await callback_query.answer()
    now = datetime.now()
    await callback_query.message.answer("📅 Выберите дату:", reply_markup=get_calendar_keyboard(now.year, now.month))

@dp.callback_query(lambda c: c.data.startswith(('cal_prev', 'cal_next')))
async def calendar_nav(callback_query: CallbackQuery):
    await callback_query.answer()
    _, direction, year_str, month_str = callback_query.data.split('_')
    y, m = int(year_str), int(month_str)
    if direction == 'prev':
        m -= 1
        if m == 0: m, y = 12, y-1
    else:
        m += 1
        if m == 13: m, y = 1, y+1
    await callback_query.message.edit_reply_markup(reply_markup=get_calendar_keyboard(y, m))

@dp.callback_query(lambda c: c.data.startswith('date_'))
async def select_date(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    if user_has_active_booking(callback_query.from_user.id):
        await callback_query.message.answer("❌ У вас уже есть запись.")
        return
    date_str = callback_query.data.split('_')[1]
    clear_expired_bookings()
    free = get_free_slots(date_str)
    if not free:
        await callback_query.message.answer("😔 Нет свободных слотов.")
        return
    await state.update_data(selected_date=date_str)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=s, callback_data=f"time_{s}")] for s in free])
    await callback_query.message.answer(f"📅 {date_str}\nВыберите время:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith('time_'))
async def select_time(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    if user_has_active_booking(callback_query.from_user.id):
        await callback_query.message.answer("❌ У вас уже есть запись.")
        return
    time_slot = callback_query.data.split('_')[1]
    data = await state.get_data()
    date_str = data.get('selected_date')
    if not is_slot_free(date_str, time_slot):
        await callback_query.message.answer("⚠️ Время занято, выберите другое.")
        return
    await state.update_data(selected_time=time_slot)
    await callback_query.message.answer("✍️ Введите ваше имя:")
    await state.set_state(BookingStates.waiting_for_name)

@dp.message(StateFilter(BookingStates.waiting_for_name))
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(client_name=message.text.strip())
    await message.answer("📞 Введите номер телефона:")
    await state.set_state(BookingStates.waiting_for_phone)

@dp.message(StateFilter(BookingStates.waiting_for_phone))
async def get_phone(message: types.Message, state: FSMContext):
    await state.update_data(client_phone=message.text.strip())
    data = await state.get_data()
    await message.answer(f"✅ Подтверждение:\n{data['selected_date']} {data['selected_time']}\n{data['client_name']}\n{data['client_phone']}\n\nЗаписаться?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Да", callback_data="confirm_yes"), InlineKeyboardButton(text="❌ Нет", callback_data="confirm_no")]]))
    await state.set_state(BookingStates.waiting_confirmation)

@dp.callback_query(lambda c: c.data in ["confirm_yes", "confirm_no"])
async def confirm(callback_query: CallbackQuery, state: FSMContext):
    current = await state.get_state()
    if current != BookingStates.waiting_confirmation:
        await callback_query.answer("Неактуально.")
        return
    await callback_query.answer()
    if callback_query.data == "confirm_no":
        await state.clear()
        now = datetime.now()
        await callback_query.message.answer("Отменено.", reply_markup=get_calendar_keyboard(now.year, now.month))
        return
    data = await state.get_data()
    user_id = callback_query.from_user.id
    if user_has_active_booking(user_id):
        await callback_query.message.answer("❌ Вы уже записаны.")
        await state.clear()
        return
    if not is_slot_free(data['selected_date'], data['selected_time']):
        await callback_query.message.answer("❌ Время занято.")
        await state.clear()
        return
    booking_id = make_booking(user_id, callback_query.from_user.username or "", data['selected_date'], data['selected_time'], data['client_name'], data['client_phone'])
    await callback_query.message.answer(f"✅ Вы записаны на {data['selected_date']} {data['selected_time']}!\nЖдем вас ❤️")
    await notify_admin(booking_id, user_id, callback_query.from_user.username or "", data['selected_date'], data['selected_time'], data['client_name'], data['client_phone'])
    await state.clear()

@dp.callback_query(lambda c: c.data == "ignore")
async def ignore(callback_query: CallbackQuery):
    await callback_query.answer()

async def main():
    clear_expired_bookings()
    print("🤖 Бот запущен!")
    print(f"👑 ID администратора: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
    
    
