import os
from flask import Flask, request, jsonify, send_from_directory
import psycopg2
import requests 
import json
import telebot # <-- ПЕРЕМЕСТИ ЭТУ СТРОКУ СЮДА

app = Flask(__name__)

# --- Настройки ---
# Получаем переменные окружения из Render
DB_CONNECTION_STRING = os.environ.get("DATABASE_URL")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- Маршруты сервера ---

# Маршрут для главной страницы
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# Маршрут для страницы создания заявки
@app.route('/create_request.html')
def create_request_page():
    return send_from_directory('.', 'create_request.html')

# Маршрут для отправки заявки
@app.route('/create_request', methods=['POST'])
def create_request():
    """
    Принимает данные из формы, сохраняет их в базу данных
    и отправляет уведомление в Telegram.
    """
    try:
        data = request.json
        club = data.get('club')
        description = data.get('description')

        if not club or not description:
            return jsonify({"error": "Отсутствуют обязательные поля"}), 400

        # Подключение к базе данных Neon
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cursor = conn.cursor()

        # SQL-запрос для вставки данных
        insert_query = """
        INSERT INTO requests (club_name, issue_description)
        VALUES (%s, %s) RETURNING id;
        """
        cursor.execute(insert_query, (club, description))
        request_id = cursor.fetchone()[0]
        conn.commit()
        
        # Отправляем сообщение в Telegram с кнопками
        tb = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
        keyboard = telebot.types.InlineKeyboardMarkup()
        button_done = telebot.types.InlineKeyboardButton(text="Выполнено", callback_data=f"done_{request_id}")
        button_in_progress = telebot.types.InlineKeyboardButton(text="в работе", callback_data=f"in_progress_{request_id}")
        keyboard.add(button_done, button_in_progress)

        message_text = f"🔔 *Новая заявка* от клуба `{club}`\n" \
                    f"Описание: `{description}`\n" \
                    f"ID заявки: `{request_id}`"
        
        tb.send_message(chat_id=TELEGRAM_CHAT_ID, text=message_text, reply_markup=keyboard)


        cursor.close()
        conn.close()

        return jsonify({"message": "Заявка успешно создана!", "request_id": request_id}), 201

    except Exception as e:
        print(f"Ошибка: {e}")
        return jsonify({"error": "Произошла внутренняя ошибка сервера"}), 500

@app.route('/requests_history', methods=['GET'])
def get_requests_history():
    """
    Возвращает историю всех заявок из базы данных.
    """
    try:
        # Подключение к базе данных Neon
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cursor = conn.cursor()

        select_query = "SELECT id, club_name, issue_description, status, created_at FROM requests ORDER BY created_at DESC;"
        cursor.execute(select_query)
        requests_from_db = cursor.fetchall()

        cursor.close()
        conn.close()

        # Форматирование данных для отправки
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

# Маршрут для страницы истории заявок
@app.route('/request_history.html')
def request_history_page():
    return send_from_directory('.', 'request_history.html')

# Маршрут для страницы калькулятора
@app.route('/calculator.html')
def calculator_page():
    return send_from_directory('.', 'calculator.html')

# Маршрут для страницы советов
@app.route('/tips.html')
def tips_page():
    return send_from_directory('.', 'tips.html')

if __name__ == '__main__':

    app.run(debug=True)
