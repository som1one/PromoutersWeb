#!/usr/bin/env python3
"""
Скрипт для применения миграции добавления поля order_date
"""

import os
import sys
from sqlalchemy import create_engine, text
from alembic import command
from alembic.config import Config

def apply_migration():
    """Применить миграцию для добавления поля order_date"""
    
    # Получаем URL базы данных из переменных окружения
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL не установлен в переменных окружения")
        return False
    
    try:
        # Создаем подключение к базе данных
        engine = create_engine(database_url)
        
        # Проверяем, существует ли уже поле order_date
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'orders' AND column_name = 'order_date'
            """))
            
            if result.fetchone():
                print("✅ Поле order_date уже существует")
                return True
        
        # Применяем миграцию напрямую через SQL
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE orders ADD COLUMN order_date TIMESTAMP WITH TIME ZONE"))
            conn.commit()
            print("✅ Поле order_date успешно добавлено")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка при применении миграции: {e}")
        return False

if __name__ == "__main__":
    success = apply_migration()
    sys.exit(0 if success else 1)


