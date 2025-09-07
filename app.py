import os
import psycopg2
import requests
from flask import Flask, request, jsonify, send_from_directory
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import telegram.constants
import threading
import schedule
import time


# --- Настройки ---
# Получаем переменные окружения из Render
DB_CONNECTION_STRING = os.environ.get("DATABASE_URL")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

app = Flask(__name__)

# --- Вспомогательные функции ---

def escape_markdown_v2(text):
    """Экранирует специальные символы в тексте для MarkdownV2."""
    special_chars = r'_*[]()~`>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

# --- Обработчики Telegram ---

async def check_and_remind(context: ContextTypes.DEFAULT_TYPE):
    """
    Проверяет открытые заявки и отправляет напоминание.
    """
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cursor = conn.cursor()
        select_query = "SELECT id, club_name, issue_description, status, created_at FROM requests WHERE status = 'не выполнено';"
        cursor.execute(select_query)
        open_requests = cursor.fetchall()
        cursor.close()
        conn.close()

        if open_requests:
            message_text = "⏰ *Напоминание: Есть открытые заявки!* ⏰\n\n"
            for req in open_requests:
                req_id, club, description, status, created_at = req
                message_text += f"ID: `{req_id}`\n"
                message_text += f"Клуб: `{club}`\n"
                message_text += f"Описание: `{description}`\n"
                message_text += f"Статус: `{status}`\n"
                message_text += f"Создана: `{created_at.strftime('%Y-%m-%d %H:%M')}`\n\n"
            
            escaped_text = escape_markdown_v2(message_text)
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=escaped_text, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2)
            print("Напоминание отправлено.")
        else:
            print("Открытых заявок нет. Напоминание не требуется.")
    except Exception as e:
        print(f"Ошибка при отправке напоминания: {e}")

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на кнопки."""
    query = update.callback_query
    await query.answer()

    data_parts = query.data.split('_')
    action = data_parts[0]
    request_id = int(data_parts[1])
    
    status_map = {
        "done": "выполнено",
        "in_progress": "в работе"
    }
    new_status = status_map.get(action)

    if not new_status:
        await query.edit_message_text("Неизвестное действие.")
        return

    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cursor = conn.cursor()
        update_query = """
        UPDATE requests SET status = %s WHERE id = %s AND status != %s RETURNING id;
        """
        cursor.execute(update_query, (new_status, request_id, new_status))
        updated_id = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        if updated_id:
            await query.edit_message_text(f"✅ Статус заявки `{request_id}` обновлён на '{new_status}'.")
        else:
            await query.edit_message_text(f"Заявка `{request_id}` уже имеет статус '{new_status}' или не найдена.")

    except Exception as e:
        print(f"Ошибка при обработке кнопки: {e}")
        await query.edit_message_text("Произошла ошибка при обновлении статуса.")

# --- Маршруты Flask ---

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/create_request.html')
def create_request_page():
    return send_from_directory('.', 'create_request.html')

@app.route('/create_request', methods=['POST'])
def create_request():
    try:
        data = request.json
        club = data.get('club')
        description = data.get('description')

        if not club or not description:
            return jsonify({"error": "Отсутствуют обязательные поля"}), 400

        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cursor = conn.cursor()
        insert_query = """
        INSERT INTO requests (club_name, issue_description) VALUES (%s, %s) RETURNING id;
        """
        cursor.execute(insert_query, (club, description))
        request_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        keyboard = [[
            InlineKeyboardButton("Выполнено", callback_data=f"done_{request_id}"),
            InlineKeyboardButton("В работе", callback_data=f"in_progress_{request_id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = f"🔔 *Новая заявка* от клуба `{club}`\n" \
                    f"Описание: `{description}`\n" \
                    f"ID заявки: `{request_id}`"
        
        # Отправляем сообщение через стандартный API Telegram с помощью requests
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message_text,
                "reply_markup": reply_markup.to_json(),
                "parse_mode": "Markdown"
            }
        ).raise_for_status()

        return jsonify({"message": "Заявка успешно создана!", "request_id": request_id}), 201

    except Exception as e:
        print(f"Ошибка: {e}")
        return jsonify({"error": "Произошла внутренняя ошибка сервера"}), 500

@app.route('/requests_history', methods=['GET'])
def get_requests_history():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cursor = conn.cursor()
        select_query = "SELECT id, club_name, issue_description, status, created_at FROM requests ORDER BY created_at DESC;"
        cursor.execute(select_query)
        requests_from_db = cursor.fetchall()
        cursor.close()
        conn.close()

        history = []
        for req in requests_from_db:
            history.append({
                "id": req[0],
                "club_name": req[1],
                "description": req[2],
                "status": req[3],
                "created_at": req[4].isoformat()
            })
        return jsonify(history), 200
    except Exception as e:
        print(f"Ошибка: {e}")
        return jsonify({"error": "Произошла внутренняя ошибка сервера"}), 500

@app.route('/request_history.html')
def request_history_page():
    return send_from_directory('.', 'request_history.html')

@app.route('/calculator.html')
def calculator_page():
    return send_from_directory('.', 'calculator.html')

@app.route('/tips.html')
def tips_page():
    return send_from_directory('.', 'tips.html')

# --- Точка входа ---

def run_flask():
    app.run(host='0.0.0.0', port=os.environ.get("PORT", 5000))

def run_bot():
    # ИСПРАВЛЕНИЕ: Добавляем job_queue=True
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build(job_queue=True)
    application.add_handler(CommandHandler("start", lambda update, context: update.message.reply_text("Привет! Я готов к работе.")))
    application.add_handler(CallbackQueryHandler(button_callback_handler))
    
    # Настраиваем регулярное напоминание каждые 4 часа (14400 секунд)
    application.job_queue.run_repeating(check_and_remind, interval=14400, first=10)
    
    print("Бот запущен и готов к работе...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    # Запускаем Flask и бота в разных потоках
    flask_thread = threading.Thread(target=run_flask)
    bot_thread = threading.Thread(target=run_bot)
    flask_thread.start()
    bot_thread.start()
