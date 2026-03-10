import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- Настройки ---
BOT_TOKEN = "8571754047:AAGvH6HvsSq94VQTbl1CdSNhR0a9uhlTBBc"  # ТВОЙ ТОКЕН
REMINDER_TIME = "10.00"  # Время ежедневного напоминания

# --- Инициализация ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- База данных ---
conn = sqlite3.connect('reminders.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        postpone_count INTEGER DEFAULT 0,
        last_reminded DATE
    )
''')
conn.commit()

# --- Функция определения руки по дню недели ---
def get_hand_by_weekday():
    weekday = datetime.now().weekday()
    
    if weekday in [0, 2, 4]:      # ПН, СР, ПТ
        return "правую"
    elif weekday in [1, 3, 5]:     # ВТ, ЧТ, СБ
        return "левую"
    else:                          # ВС
        return "левую"

def get_tomorrow_hand():
    tomorrow = datetime.now() + timedelta(days=1)
    weekday = tomorrow.weekday()
    
    if weekday in [0, 2, 4]:
        return "правую"
    elif weekday in [1, 3, 5]:
        return "левую"
    else:
        return "левую"

def get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def create_user(user_id):
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()

def reset_postpone_count(user_id):
    cursor.execute('UPDATE users SET postpone_count = 0 WHERE user_id = ?', (user_id,))
    conn.commit()

def increment_postpone_count(user_id):
    cursor.execute('UPDATE users SET postpone_count = postpone_count + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    cursor.execute('SELECT postpone_count FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone()[0]

def get_reminder_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Сделал", callback_data="done")
    builder.button(text="⏰ Перенести", callback_data="postpone")
    builder.adjust(2)
    return builder.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    create_user(user_id)
    
    today_hand = get_hand_by_weekday()
    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    today_name = weekday_names[datetime.now().weekday()]
    
    await message.answer(
        f"Привет! Я буду напоминать тебе делать упражнение в {REMINDER_TIME}.\n"
        f"📅 Сегодня {today_name} пишем **{today_hand}** рукой!\n\n"
        f"*ПН, СР, ПТ — правая*\n"
        f"*ВТ, ЧТ, СБ — левая*",
        parse_mode="Markdown"
    )

@dp.message(Command("hand"))
async def cmd_hand(message: Message):
    hand = get_hand_by_weekday()
    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    today_name = weekday_names[datetime.now().weekday()]
    
    await message.answer(
        f"📅 Сегодня {today_name}\n"
        f"✍️ Пишем **{hand}** рукой!",
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == 'done')
async def process_done(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    reset_postpone_count(user_id)
    tomorrow_hand = get_tomorrow_hand()
    
    await callback.message.edit_text(
        f"🔥 Молодец! Упражнение сделано.\n"
        f"Завтра напомню в {REMINDER_TIME}.\n"
        f"Завтра пишем **{tomorrow_hand}** рукой!",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == 'postpone')
async def process_postpone(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    count = increment_postpone_count(user_id)
    
    if count >= 5:
        reset_postpone_count(user_id)
        tomorrow_hand = get_tomorrow_hand()
        
        await callback.message.edit_text(
            f"⚠️ Лимит переносов (5 раз) исчерпан!\n"
            f"Давай начнем заново с завтрашнего дня.\n"
            f"Завтра пишем **{tomorrow_hand}** рукой.",
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            f"⏳ Перенес напоминание. Осталось переносов: {5 - count}/5.\n"
            f"Напомню снова в {REMINDER_TIME}."
        )
    await callback.answer()

async def daily_reminder():
    while True:
        now = datetime.now()
        target_time = datetime.strptime(REMINDER_TIME, "%H:%M").time()
        target_datetime = datetime.combine(now.date(), target_time)
        
        if now > target_datetime:
            target_datetime += timedelta(days=1)
        
        wait_seconds = (target_datetime - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        
        today_hand = get_hand_by_weekday()
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        today_name = weekday_names[datetime.now().weekday()]
        
        cursor.execute('SELECT user_id FROM users')
        users = cursor.fetchall()
        
        for user_id, in users:
            try:
                text = (f"⏰ Время делать упражнение!\n"
                       f"Сегодня {today_name} пишем **{today_hand}** рукой.\n"
                       f"Сделал или перенесем?")
                
                await bot.send_message(user_id, text, 
                                     reply_markup=get_reminder_keyboard(),
                                     parse_mode="Markdown")
                
                cursor.execute('UPDATE users SET last_reminded = ? WHERE user_id = ?', 
                             (now.date().isoformat(), user_id))
                conn.commit()
                
            except Exception as e:
                logging.error(f"Ошибка при отправке пользователю {user_id}: {e}")
        
        await asyncio.sleep(24 * 60 * 60)

async def main():
    asyncio.create_task(daily_reminder())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())