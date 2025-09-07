import os
import psycopg2
from telegram import Bot
import time
import schedule

# --- Настройки ---
# Вставь сюда Connection String из Neon
DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_Cp3nJgZU9ufr@ep-red-waterfall-addsdfyk-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
# Вставь сюда токен своего Telegram-бота
TELEGRAM_BOT_TOKEN = "8277096952:AAHypda1H8aIWa6EMZ_pbADzN5CvmU3f8mI"
# Вставь сюда свой ID чата в Telegram
TELEGRAM_CHAT_ID = "987765617"

def check_and_remind():
    """
    Проверяет открытые заявки и отправляет напоминание.
    """
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cursor = conn.cursor()

        # SQL-запрос для поиска невыполненных заявок
        select_query = "SELECT id, club_name, issue_description, status, created_at FROM requests WHERE status = 'не выполнено';"
        cursor.execute(select_query)
        open_requests = cursor.fetchall()

        cursor.close()
        conn.close()

        if open_requests:
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            message_text = "⏰ *Напоминание: Есть открытые заявки!* ⏰\n\n"
            
            for req in open_requests:
                req_id, club, description, status, created_at = req
                message_text += f"ID: `{req_id}`\n"
                message_text += f"Клуб: `{club}`\n"
                message_text += f"Описание: `{description}`\n"
                message_text += f"Статус: `{status}`\n"
                message_text += f"Создана: `{created_at.strftime('%Y-%m-%d %H:%M')}`\n\n"
            
            # Отправляем сообщение в Telegram
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message_text, parse_mode='Markdown')
            print("Напоминание отправлено.")
        else:
            print("Открытых заявок нет. Напоминание не требуется.")

    except Exception as e:
        print(f"Ошибка при отправке напоминания: {e}")

if __name__ == '__main__':
    # Настраиваем расписание
    schedule.every(4).hours.do(check_and_remind)

    print("Скрипт напоминаний запущен...")

    while True:
        schedule.run_pending()
        time.sleep(1)