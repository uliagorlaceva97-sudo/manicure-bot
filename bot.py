# version 1.0
import asyncio
import sqlite3
from datetime import datetime, timedelta
from calendar import monthcalendar, month_name
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

# --- Конфигурация ---
API_TOKEN = '8670803051:AAEN4vMrXe1opp4HUXSa0-_2t0efg04E_eE'

# Временные слоты
TIME_SLOTS = ["8.00-10.00", "11.00-13.00", "14.00-16.00"]

# Прайс-лист
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

# Ссылка на канал с отзывами
REVIEWS_LINK = "https://t.me/mannnnikaaa" 

# --- Инициализация бота ---
bot = Bot(token=API_TOKEN)
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
    deleted = 0
    for row in rows:
        booking_id, date_str, slot_str = row
        start_time_str = slot_str.split('-')[0]
        try:
            slot_datetime = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H.%M")
            if slot_datetime < now:
                cur.execute("UPDATE bookings SET status = 'expired' WHERE id = ?", (booking_id,))
                deleted += 1
        except Exception as e:
            print(f"Error parsing date: {e}")
    if deleted > 0:
        conn.commit()
        print(f"Cleared {deleted} expired bookings")
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
            return {
                'id': booking_id,
                'date': date_str,
                'time': slot_str,
                'name': client_name,
                'phone': client_phone
            }
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
    free = []
    for slot in TIME_SLOTS:
        if is_slot_free(date_str, slot):
            free.append(slot)
    return free

def make_booking(user_id, username, date_str, time_slot, client_name, client_phone):
    conn = sqlite3.connect('bookings.db')
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO bookings (user_id, username, date, time_slot, client_name, client_phone, status) VALUES (?, ?, ?, ?, ?, ?, 'active')",
        (user_id, username, date_str, time_slot, client_name, client_phone)
    )
    booking_id = cur.lastrowid
    conn.commit()
    conn.close()
    return booking_id

def get_all_active_bookings():
    conn = sqlite3.connect('bookings.db')
    cur = conn.cursor()
    now = datetime.now()
    cur.execute("""
        SELECT id, user_id, username, date, time_slot, client_name, client_phone, booked_at 
        FROM bookings 
        WHERE status = 'active'
        ORDER BY date, time_slot
    """)
    rows = cur.fetchall()
    conn.close()
    
    future_bookings = []
    for row in rows:
        booking_id, user_id, username, date_str, slot_str, client_name, client_phone, booked_at = row
        start_time_str = slot_str.split('-')[0]
        slot_datetime = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H.%M")
        if slot_datetime > now:
            future_bookings.append({
                'id': booking_id,
                'user_id': user_id,
                'username': username,
                'date': date_str,
                'time': slot_str,
                'name': client_name,
                'phone': client_phone,
                'booked_at': booked_at
            })
    return future_bookings

async def notify_admin(booking_id, user_id, username, date_str, time_slot, client_name, client_phone):
    message = (
        f"🆕 НОВАЯ ЗАПИСЬ!\n\n"
        f"📅 Дата: {date_str}\n"
        f"⏰ Время: {time_slot}\n"
        f"👤 Имя клиента: {client_name}\n"
        f"📞 Телефон: {client_phone}\n"
        f"🆔 ID пользователя: {user_id}\n"
        f"📝 Username: @{username if username else 'не указан'}\n"
        f"🔖 Номер записи: #{booking_id}"
    )
    try:
        await bot.send_message(ADMIN_ID, message)
    except Exception as e:
        print(f"Error sending notification to admin: {e}")

# --- FSM Состояния ---
class BookingStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_confirmation = State()

# --- Главное меню ---
def get_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Запись и свободные окошки")],
            [KeyboardButton(text="💰 Прайс")],
            [KeyboardButton(text="⭐️ Отзывы")]
        ],
        resize_keyboard=True
    )
    return keyboard

# --- Календарь ---
def get_calendar_keyboard(year: int, month: int):
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    month_days = monthcalendar(year, month)
    
    keyboard = []
    
    nav_row = []
    nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"cal_prev_{year}_{month}"))
    nav_row.append(InlineKeyboardButton(text=f"{month_name[month]} {year}", callback_data="ignore"))
    nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"cal_next_{year}_{month}"))
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
    keyboard.append([InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel_booking")])
    keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- Хендлеры ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    clear_expired_bookings()
    
    welcome_text = (
        "🌸 *Добро пожаловать в студию маникюра!* 🌸\n\n"
        "Здесь вы можете:\n"
        "📝 *Записаться* на удобное время\n"
        "💰 *Ознакомиться с прайсом*\n"
        "⭐️ *Посмотреть отзывы*\n\n"
        "Выберите, что хотите сделать:"
    )
    
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

@dp.message(lambda message: message.text == "📝 Запись и свободные окошки")
async def booking_button(message: types.Message):
    # Проверяем, нет ли у пользователя активной записи
    if user_has_active_booking(message.from_user.id):
        booking = get_user_active_booking(message.from_user.id)
        await message.answer(
            f"❌ *У вас уже есть активная запись!*\n\n"
            f"📅 Дата: {booking['date']}\n"
            f"⏰ Время: {booking['time']}\n\n"
            f"Вы можете отменить текущую запись через меню 'Мои записи' в календаре.",
            parse_mode="Markdown"
        )
        return
    
    now = datetime.now()
    keyboard = get_calendar_keyboard(now.year, now.month)
    await message.answer(
        "📅 *Выберите дату для записи:*\n\n"
        "🔴 - сегодня\n"
        "◽️ - прошедшие дни\n"
        "🔘 - полностью занятые дни",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.message(lambda message: message.text == "💰 Прайс")
async def price_button(message: types.Message):
    await message.answer(PRICE_LIST, parse_mode="Markdown")

@dp.message(lambda message: message.text == "⭐️ Отзывы")
async def reviews_button(message: types.Message):
    await message.answer(
        f"⭐️ *Наши отзывы:* ⭐️\n\n"
        f"Посмотрите, что говорят наши довольные клиенты!\n\n"
        f"[📱 Читать отзывы в Telegram]({REVIEWS_LINK})",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    
    bookings = get_all_active_bookings()
    
    if not bookings:
        await message.answer("📭 Нет активных записей.")
        return
    
    message_text = "📋 **СПИСОК ВСЕХ ЗАПИСЕЙ:**\n\n"
    for booking in bookings:
        message_text += (
            f"🔹 **Запись #{booking['id']}**\n"
            f"   📅 Дата: {booking['date']}\n"
            f"   ⏰ Время: {booking['time']}\n"
            f"   👤 Имя: {booking['name']}\n"
            f"   📞 Телефон: {booking['phone']}\n"
            f"   🆔 User ID: {booking['user_id']}\n"
            f"   📝 Username: @{booking['username'] if booking['username'] else 'не указан'}\n"
            f"   🕐 Записано: {booking['booked_at']}\n\n"
        )
    
    if len(message_text) > 4096:
        parts = [message_text[i:i+4096] for i in range(0, len(message_text), 4096)]
        for part in parts:
            await message.answer(part, parse_mode="Markdown")
    else:
        await message.answer(message_text, parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "main_menu")
async def back_to_main_menu(callback_query: CallbackQuery):
    await callback_query.answer()
    await callback_query.message.delete()
    await cmd_start(callback_query.message)

@dp.callback_query(lambda c: c.data == "my_bookings")
async def show_my_bookings(callback_query: CallbackQuery):
    await callback_query.answer()
    
    booking = get_user_active_booking(callback_query.from_user.id)
    
    if not booking:
        await callback_query.message.answer(
            "📭 У вас нет активных записей.\n\n"
            "Вы можете записаться, выбрав дату в календаре."
        )
        return
    
    message_text = (
        f"📋 **ВАША АКТИВНАЯ ЗАПИСЬ:**\n\n"
        f"📅 Дата: {booking['date']}\n"
        f"⏰ Время: {booking['time']}\n"
        f"👤 Имя: {booking['name']}\n"
        f"📞 Телефон: {booking['phone']}\n\n"
        f"Если вы хотите отменить запись, нажмите кнопку ниже."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить эту запись", callback_data=f"cancel_booking_{booking['id']}")]
    ])
    
    await callback_query.message.answer(message_text, parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "cancel_booking")
async def cancel_booking_start(callback_query: CallbackQuery):
    await callback_query.answer()
    
    booking = get_user_active_booking(callback_query.from_user.id)
    
    if not booking:
        await callback_query.message.answer("📭 У вас нет активных записей для отмены.")
        return
    
    message_text = (
        f"❓ **Вы уверены, что хотите отменить запись?**\n\n"
        f"📅 Дата: {booking['date']}\n"
        f"⏰ Время: {booking['time']}\n\n"
        f"Это действие нельзя будет отменить."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"confirm_cancel_{booking['id']}")],
        [InlineKeyboardButton(text="❌ Нет, вернуться", callback_data="back_to_calendar")]
    ])
    
    await callback_query.message.answer(message_text, parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("confirm_cancel_"))
async def confirm_cancel(callback_query: CallbackQuery):
    await callback_query.answer()
    
    booking_id = int(callback_query.data.split("_")[2])
    booking = get_user_active_booking(callback_query.from_user.id)
    
    if not booking or booking['id'] != booking_id:
        await callback_query.message.answer("❌ Эта запись уже была отменена или не существует.")
        return
    
    cancel_booking(booking_id)
    
    await callback_query.message.answer(
        f"✅ Запись на {booking['date']} {booking['time']} успешно отменена.\n\n"
        f"Вы можете записаться на другое время."
    )
    
    try:
        await bot.send_message(
            ADMIN_ID,
            f"❌ ОТМЕНА ЗАПИСИ #{booking_id}\n\n"
            f"📅 Дата: {booking['date']}\n"
            f"⏰ Время: {booking['time']}\n"
            f"👤 Имя: {booking['name']}\n"
            f"📞 Телефон: {booking['phone']}\n"
            f"🆔 User ID: {callback_query.from_user.id}"
        )
    except Exception as e:
        print(f"Error sending cancellation notification: {e}")
    
    now = datetime.now()
    keyboard = get_calendar_keyboard(now.year, now.month)
    await callback_query.message.answer("📅 Выберите новую дату для записи:", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "back_to_calendar")
async def back_to_calendar(callback_query: CallbackQuery):
    await callback_query.answer()
    now = datetime.now()
    keyboard = get_calendar_keyboard(now.year, now.month)
    await callback_query.message.answer("📅 Выберите дату для записи:", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith(('cal_prev', 'cal_next')))
async def process_calendar_navigation(callback_query: CallbackQuery):
    await callback_query.answer()
    _, direction, year_str, month_str = callback_query.data.split('_')
    year = int(year_str)
    month = int(month_str)
    
    if direction == 'prev':
        if month == 1:
            month = 12
            year -= 1
        else:
            month -= 1
    else:
        if month == 12:
            month = 1
            year += 1
        else:
            month += 1
    
    keyboard = get_calendar_keyboard(year, month)
    await callback_query.message.edit_reply_markup(reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith('date_'))
async def process_date_selection(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    
    if user_has_active_booking(callback_query.from_user.id):
        await callback_query.message.answer(
            "❌ У вас уже есть активная запись.\n\n"
            "Вы можете отменить текущую запись через меню 'Мои записи' или кнопку 'Отменить запись' в календаре."
        )
        return
    
    date_str = callback_query.data.split('_')[1]
    
    clear_expired_bookings()
    
    free_slots = get_free_slots(date_str)
    
    if not free_slots:
        await callback_query.message.answer("😔 На эту дату больше нет свободных слотов. Выберите другой день.")
        return
    
    await state.update_data(selected_date=date_str)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=slot, callback_data=f"time_{slot}")] for slot in free_slots
    ])
    
    await callback_query.message.answer(f"📅 Вы выбрали: {date_str}\n\nВыберите удобное время:", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith('time_'))
async def process_time_selection(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    
    if user_has_active_booking(callback_query.from_user.id):
        await callback_query.message.answer(
            "❌ У вас уже есть активная запись.\n\n"
            "Пожалуйста, отмените текущую запись перед созданием новой."
        )
        return
    
    time_slot = callback_query.data.split('_')[1]
    data = await state.get_data()
    selected_date = data.get('selected_date')
    
    if not is_slot_free(selected_date, time_slot):
        await callback_query.message.answer("⚠️ К сожалению, это время уже занято. Пожалуйста, выберите другое.")
        free_slots = get_free_slots(selected_date)
        if free_slots:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=slot, callback_data=f"time_{slot}")] for slot in free_slots
            ])
            await callback_query.message.answer(f"Доступное время на {selected_date}:", reply_markup=keyboard)
        else:
            await callback_query.message.answer("На эту дату больше нет свободных слотов.")
        return
    
    await state.update_data(selected_time=time_slot)
    
    await callback_query.message.answer("✍️ *Введите ваше имя:*", parse_mode="Markdown")
    await state.set_state(BookingStates.waiting_for_name)

@dp.message(StateFilter(BookingStates.waiting_for_name))
async def process_name(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, введите имя текстом.")
        return
    
    await state.update_data(client_name=message.text.strip())
    await message.answer("📞 *Введите ваш контактный номер телефона:*", parse_mode="Markdown")
    await state.set_state(BookingStates.waiting_for_phone)

@dp.message(StateFilter(BookingStates.waiting_for_phone))
async def process_phone(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, введите номер телефона.")
        return
    
    await state.update_data(client_phone=message.text.strip())
    data = await state.get_data()
    
    selected_date = data.get('selected_date')
    selected_time = data.get('selected_time')
    client_name = data.get('client_name')
    client_phone = data.get('client_phone')
    
    confirm_text = (
        f"✅ *ПОДТВЕРЖДЕНИЕ ЗАПИСИ*\n\n"
        f"📅 Дата: {selected_date}\n"
        f"⏰ Время: {selected_time}\n"
        f"👤 Имя: {client_name}\n"
        f"📞 Телефон: {client_phone}\n\n"
        f"Вы уверены, что хотите записаться?"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, записаться", callback_data="confirm_yes")],
        [InlineKeyboardButton(text="❌ Нет, отменить", callback_data="confirm_no")]
    ])
    
    await message.answer(confirm_text, parse_mode="Markdown", reply_markup=keyboard)
    await state.set_state(BookingStates.waiting_confirmation)

@dp.callback_query(lambda c: c.data in ["confirm_yes", "confirm_no"])
async def process_confirmation(callback_query: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state != BookingStates.waiting_confirmation:
        await callback_query.answer("Это действие уже неактивно.")
        return
    
    await callback_query.answer()
    
    if callback_query.data == "confirm_no":
        await state.clear()
        now = datetime.now()
        keyboard = get_calendar_keyboard(now.year, now.month)
        await callback_query.message.answer("Запись отменена. Выберите другую дату:", reply_markup=keyboard)
        return
    
    data = await state.get_data()
    selected_date = data.get('selected_date')
    selected_time = data.get('selected_time')
    client_name = data.get('client_name')
    client_phone = data.get('client_phone')
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or f"user_{user_id}"
    
    if user_has_active_booking(user_id):
        await callback_query.message.answer("❌ Ошибка: вы уже записаны на другой сеанс.")
        await state.clear()
        return
    
    if not is_slot_free(selected_date, selected_time):
        await callback_query.message.answer("❌ Ошибка: это время уже занято. Пожалуйста, выберите другое.")
        await state.clear()
        now = datetime.now()
        keyboard = get_calendar_keyboard(now.year, now.month)
        await callback_query.message.answer("Выберите другую дату:", reply_markup=keyboard)
        return
    
    booking_id = make_booking(user_id, username, selected_date, selected_time, client_name, client_phone)
    
    await callback_query.message.answer(
        f"✅ *ВЫ УСПЕШНО ЗАПИСАНЫ!*\n\n"
        f"📅 Дата: {selected_date}\n"
        f"⏰ Время: {selected_time}\n"
        f"👤 Имя: {client_name}\n"
        f"📞 Телефон: {client_phone}\n\n"
        f"Спасибо за доверие! Ждем вас ❤️\n\n"
        f"Чтобы отменить запись, используйте кнопку 'Мои записи' в календаре.",
        parse_mode="Markdown"
    )
    
    await notify_admin(booking_id, user_id, username, selected_date, selected_time, client_name, client_phone)
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "ignore")
async def ignore_callback(callback_query: CallbackQuery):
    await callback_query.answer()

async def main():
    clear_expired_bookings()
    print("🤖 Бот запущен и готов к работе!")
    print(f"👑 ID администратора: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
