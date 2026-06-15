#!/usr/bin/env python3
"""
Скрипт для добавления полей username и password_hash в таблицу users
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Загружаем переменные окружения
if os.path.exists('local.env'):
    load_dotenv('local.env')
else:
    load_dotenv()

def add_web_auth_fields():
    """Добавить поля username и password_hash в таблицу users"""
    
    # Получаем URL базы данных из переменных окружения
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL не установлен в переменных окружения")
        return False
    
    try:
        # Создаем подключение к базе данных
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Проверяем, существуют ли уже поля
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name IN ('username', 'password_hash')
            """))
            
            existing_columns = {row[0] for row in result}
            
            # Добавляем username, если его нет
            if 'username' not in existing_columns:
                print("➕ Добавление поля username...")
                conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN username VARCHAR(100) UNIQUE
                """))
                print("✅ Поле username добавлено")
            else:
                print("ℹ️ Поле username уже существует")
            
            # Добавляем password_hash, если его нет
            if 'password_hash' not in existing_columns:
                print("➕ Добавление поля password_hash...")
                conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN password_hash VARCHAR(255)
                """))
                print("✅ Поле password_hash добавлено")
            else:
                print("ℹ️ Поле password_hash уже существует")
            
            # Создаем уникальный индекс для username, если его нет
            result = conn.execute(text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'users' AND indexname = 'ix_users_username'
            """))
            
            if not result.fetchone():
                print("➕ Создание уникального индекса для username...")
                conn.execute(text("""
                    CREATE UNIQUE INDEX ix_users_username ON users(username)
                    WHERE username IS NOT NULL
                """))
                print("✅ Индекс создан")
            else:
                print("ℹ️ Индекс ix_users_username уже существует")
            
            conn.commit()
            print("\n✅ Все поля успешно добавлены!")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка при добавлении полей: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("📦 Добавление полей для веб-аутентификации")
    print("=" * 60)
    print()
    
    if add_web_auth_fields():
        print("\n🎉 Готово! Поля username и password_hash добавлены в таблицу users.")
        sys.exit(0)
    else:
        print("\n❌ Произошла ошибка. Проверьте логи выше.")
        sys.exit(1)

