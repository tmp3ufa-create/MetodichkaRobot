import os
import asyncio
import logging
from pathlib import Path
from telethon import TelegramClient, events
import requests
import base64

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== КЛЮЧ NVIDIA API (ВАШ) ====================
# ВНИМАНИЕ: Ваш API-ключ уже встроен в код ниже.
# Вставьте его в строку 'Bearer nvapi-...' в функции recognize_text_with_nvidia.
NVIDIA_API_KEY = "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"

# ==================== ФУНКЦИЯ ДЛЯ NVIDIA API ====================
def recognize_text_with_nvidia(image_path: Path):
    """Отправляет изображение в NVIDIA NIM API и возвращает распознанный текст."""
    invoke_url = "https://ai.api.nvidia.com/v1/cv/nvidia/nemoretriever-ocr-v1"
    
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Accept": "application/json"
    }

    try:
        # Читаем и кодируем изображение в base64
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()

        # Проверяем размер (API NVIDIA имеет ограничения)
        if len(image_b64) > 180000:
            return "Ошибка: файл слишком большой для обработки."

        # Формируем запрос к API NVIDIA
        payload = {
            "input": [
                {
                    "type": "image_url",
                    "url": f"data:image/png;base64,{image_b64}"
                }
            ]
        }

        # Отправляем запрос
        logger.info(f"Отправляем запрос к NVIDIA API...")
        response = requests.post(invoke_url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            result_data = response.json()
            logger.info(f"Успешный ответ от NVIDIA API.")
            
            # ВАЖНО: Структура ответа может отличаться!
            # Извлекаем текст. Если ответ выглядит иначе, нужно будет скорректировать эту часть.
            # Сначала попробуем получить текст по ключу 'text'
            extracted_text = result_data.get('text', '')
            
            # Если нет ключа 'text', попробуем другие варианты или вернем весь ответ для отладки
            if not extracted_text:
                logger.warning(f"Ключ 'text' не найден в ответе. Полный ответ: {result_data}")
                # Попробуем найти текст в других возможных ключах
                if 'result' in result_data and 'text' in result_data['result']:
                    extracted_text = result_data['result']['text']
                else:
                    # Если не нашли текст, возвращаем информацию для отладки
                    extracted_text = f"Текст не найден в ответе API. Ответ для анализа: {str(result_data)[:500]}..."
            
            return extracted_text
        else:
            error_msg = f"Ошибка API NVIDIA: {response.status_code}. {response.text[:200]}"
            logger.error(error_msg)
            return error_msg
            
    except requests.exceptions.Timeout:
        logger.error("Таймаут запроса к NVIDIA API.")
        return "Ошибка: таймаут при обращении к сервису распознавания."
    except Exception as e:
        logger.error(f"Ошибка при вызове NVIDIA API: {str(e)}")
        return f"Ошибка при обработке файла: {str(e)}"

# ==================== ЗАГРУЗКА КЛЮЧЕЙ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ====================
# Эти значения вы установите в панели Render.com
BOT_TOKEN = os.getenv('BOT_TOKEN')  # Ваш: 8505417644:AAFgPWOy2ZqC5Sk7VDNqFyGOWkua7RCjPKI
APP_API_ID = os.getenv('APP_API_ID')  # Получите на my.telegram.org
APP_API_HASH = os.getenv('APP_API_HASH')  # Получите на my.telegram.org

# ==================== ПРОВЕРКА КЛЮЧЕЙ ПРИ ЗАПУСКЕ ====================
if not BOT_TOKEN or not APP_API_ID or not APP_API_HASH:
    logger.error("ОШИБКА: Не заданы одна или несколько переменных окружения!")
    logger.error("Пожалуйста, установите BOT_TOKEN, APP_API_ID и APP_API_HASH в настройках Render.com")
    exit(1)

# ==================== СОЗДАНИЕ КЛИЕНТА TELEGRAM ====================
bot = TelegramClient('bot', APP_API_ID, APP_API_HASH).start(bot_token=BOT_TOKEN)
logger.info("Бот запущен и ожидает сообщений...")

# ==================== ОБРАБОТЧИК КОМАНДЫ /start ====================
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    """Отправляет приветственное сообщение при команде /start"""
    welcome_text = (
        "👋 Привет! Я бот для распознавания текста с изображений.\n\n"
        "Просто отправьте мне изображение или документ (PNG, JPG, PDF), "
        "и я извлеку из него текст с помощью NVIDIA AI.\n\n"
        "Для справки используйте /help"
    )
    await event.respond(welcome_text)

@bot.on(events.NewMessage(pattern='/help'))
async def help_handler(event):
    """Отправляет справку"""
    help_text = (
        "📖 **Справка по боту:**\n\n"
        "• Просто отправьте мне изображение (PNG, JPG) или PDF-файл\n"
        "• Я обработаю его с помощью NVIDIA Nemoretriever-OCR-v1\n"
        "• Верну распознанный текстовый результат\n\n"
        "⚠️ **Ограничения:**\n"
        "• Размер файла должен быть разумным (до 1-2 МБ для быстрой обработки)\n"
        "• Сервис работает на бесплатном хостинге, поэтому первое сообщение после простоя может обрабатываться до 30-50 секунд\n\n"
        "Если возникли проблемы — проверьте логи бота на Render.com"
    )
    await event.respond(help_text)

# ==================== ОБРАБОТЧИК ИЗОБРАЖЕНИЙ И ДОКУМЕНТОВ ====================
@bot.on(events.NewMessage)
async def handle_file(event):
    """Обрабатывает изображения и документы"""
    # Пропускаем команды (они обрабатываются отдельно)
    if event.message.text and event.message.text.startswith('/'):
        return
    
    # Проверяем, есть ли в сообщении файл или изображение
    if not (event.message.document or event.message.photo):
        await event.reply("Пожалуйста, отправьте изображение или документ для распознавания текста.")
        return
    
    await event.reply("🔄 Получил файл, начинаю обработку...")
    
    try:
        # Создаем временную папку, если её нет
        temp_dir = Path("tmp")
        temp_dir.mkdir(exist_ok=True)
        
        # Определяем имя файла
        if event.message.document:
            file_name = event.message.document.attributes[0].file_name
        else:
            file_name = f"photo_{event.message.id}.jpg"
        
        file_path = temp_dir / file_name
        
        # Скачиваем файл
        logger.info(f"Скачиваю файл: {file_name}")
        await event.message.download_media(file=file_path)
        logger.info(f"Файл сохранен: {file_path}")
        
        # Обрабатываем файл через NVIDIA API
        await event.reply("🔍 Отправляю файл в NVIDIA AI для распознавания текста...")
        result_text = recognize_text_with_nvidia(file_path)
        
        # Удаляем временный файл
        try:
            os.remove(file_path)
            logger.info(f"Временный файл удален: {file_path}")
        except:
            pass
        
        # Отправляем результат (если текст слишком длинный, разбиваем на части)
        if len(result_text) > 4000:
            await event.reply("📄 Результат слишком длинный, отправляю частями...")
            for i in range(0, len(result_text), 4000):
                await event.reply(f"Часть {i//4000 + 1}:\n\n{result_text[i:i+4000]}")
                await asyncio.sleep(0.5)  # Небольшая задержка между сообщениями
        else:
            await event.reply(f"📝 **Распознанный текст:**\n\n{result_text}")
            
    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {str(e)}")
        await event.reply(f"❌ Произошла ошибка при обработке файла: {str(e)}")

# ==================== ЗАПУСК БОТА ====================
def main():
    """Запускает бота"""
    logger.info("Запускаю бота...")
    bot.run_until_disconnected()

if __name__ == '__main__':
    main()