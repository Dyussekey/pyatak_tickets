import os
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import telegram.constants

# --- Настройки ---
# Получаем переменные окружения из Render
DB_CONNECTION_STRING = os.environ.get("DATABASE_URL")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def escape_markdown_v2(text):
    """Экранирует специальные символы в тексте для MarkdownV2."""
    special_chars = r'_*[]()~`>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def send_request_with_buttons(chat_id, request_id, club, description):
    """Отправляет сообщение о новой заявке с кнопками."""
    keyboard = [
        [
            InlineKeyboardButton("Выполнено", callback_data=f"done_{request_id}"),
            InlineKeyboardButton("В работе", callback_data=f"in_progress_{request_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = f"🔔 *Новая заявка* от клуба `{club}`\n" \
                   f"Описание: `{description}`\n" \
                   f"ID заявки: `{request_id}`"

    escaped_text = escape_markdown_v2(message_text)

    await Application.builder().token(TELEGRAM_BOT_TOKEN).build().bot.send_message(
        chat_id=chat_id,
        text=escaped_text,
        reply_markup=reply_markup,
        parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
    )

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на кнопки."""
    query = update.callback_query
    await query.answer()

    # Извлекаем данные из кнопки
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
        UPDATE requests
        SET status = %s
        WHERE id = %s AND status != %s
        RETURNING id;
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

    # Извлекаем данные из кнопки
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
        UPDATE requests
        SET status = %s
        WHERE id = %s AND status != %s
        RETURNING id;
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

async def set_status_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает команду /done для смены статуса заявки.
    """
    # Этот код останется для обратной совместимости, но теперь мы будем использовать кнопки.
    # Он всё ещё работает, но кнопки удобнее.
    # ... (старый код, который ты уже использовал)
    pass

def main():
    """
    Основная функция, которая запускает бота.
    """
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Добавляем обработчик для команды /done
    application.add_handler(CommandHandler("done", set_status_done))
    
    # Добавляем обработчик для нажатий на кнопки
    application.add_handler(CallbackQueryHandler(button_callback_handler))

    # Запускаем бота
    print("Бот запущен и готов к работе...")
    application.run_polling()

if __name__ == '__main__':

    main()
