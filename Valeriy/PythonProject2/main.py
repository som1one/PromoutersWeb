import os
import sys
import logging
from dotenv import load_dotenv
import telebot
from handlers import user_handlers, admin_handlers

# Настройка логирования перед загрузкой переменных
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Загрузка переменных окружения
# Сначала пробуем загрузить local.env, если не найден - загружаем .env
logger = logging.getLogger(__name__)
if os.path.exists('local.env'):
    load_dotenv('local.env')
    logger.info("Загружены переменные из local.env")
else:
    load_dotenv()  # Загружаем из .env по умолчанию
    logger.info("Загружены переменные из .env")

# Установка переменных вручную, если .env не работает
if not os.getenv("TELEGRAM_TOKEN"):
    os.environ["TELEGRAM_TOKEN"] = "YOUR_BOT_TOKEN_HERE"  # Замените на ваш токен
if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "postgresql://username:password@localhost:5432/database_name"  # Замените на вашу БД

def run_telegram_bot():
    """Запуск Telegram бота"""
    try:
        from telegram_bot import TelegramBot
        bot = TelegramBot()
        logger.info("Telegram Bot started")
        bot.run()
    except ImportError:
        # Fallback на старую версию с handlers
        TOKEN = os.getenv("TELEGRAM_TOKEN")
        
        if not TOKEN:
            raise RuntimeError("TELEGRAM_TOKEN required")
        
        bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
        
        # Регистрируем все хендлеры
        user_handlers.register(bot)
        admin_handlers.register(bot)
        
        logger.info("Telegram Bot started (legacy mode)")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)

def run_vk_bot():
    """Запуск ВК бота"""
    try:
        from vk_bot import VKBot
        bot = VKBot()
        logger.info("VK Bot started")
        bot.run()
    except ImportError as e:
        logger.error(f"VK bot dependencies not installed: {e}")
        logger.error("Install VK dependencies: pip install vk-api")
        sys.exit(1)
    except Exception as e:
        logger.error(f"VK bot error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    """Главная функция с выбором бота"""
    global logger
    if logger is None:
        logger = logging.getLogger(__name__)
    
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1:
        bot_type = sys.argv[1].lower()
        
        # Поддержка флагов --vk, --telegram и т.д.
        if bot_type.startswith('--'):
            bot_type = bot_type[2:]  # Убираем --
        
        if bot_type == "telegram" or bot_type == "tg":
            run_telegram_bot()
        elif bot_type == "vk" or bot_type == "vkontakte":
            run_vk_bot()
        elif bot_type == "both":
            # Запуск обоих ботов в разных процессах
            import multiprocessing
            
            telegram_process = multiprocessing.Process(target=run_telegram_bot)
            vk_process = multiprocessing.Process(target=run_vk_bot)
            
            telegram_process.start()
            vk_process.start()
            
            try:
                telegram_process.join()
                vk_process.join()
            except KeyboardInterrupt:
                logger.info("Stopping bots...")
                telegram_process.terminate()
                vk_process.terminate()
        else:
            print_usage()
    else:
        # По умолчанию запускаем Telegram бота
        run_telegram_bot()

def print_usage():
    """Показать справку по использованию"""
    print("""
Использование: python main.py [тип_бота]

Типы ботов:
  telegram, tg  - Запуск Telegram бота (по умолчанию)
  vk, vkontakte - Запуск ВК бота
  both          - Запуск обоих ботов одновременно

Примеры:
  python main.py              # Telegram бот
  python main.py telegram     # Telegram бот
  python main.py vk           # ВК бот
  python main.py both         # Оба бота

Настройка:
  1. Скопируйте config.env в .env и заполните токены
  2. Для ВК бота: pip install -r requirements_vk.txt
  3. Запустите нужный бот
""")

if __name__ == "__main__":
    main()
