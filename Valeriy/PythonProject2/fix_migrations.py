#!/usr/bin/env python3
"""
Скрипт для исправления состояния миграций после удаления файла
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Загрузка переменных окружения
if os.path.exists('local.env'):
    load_dotenv('local.env')
else:
    load_dotenv()

def fix_migrations():
    """Исправить состояние миграций в БД"""
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL не установлен в переменных окружения")
        return False
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Проверяем текущую версию
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            current_version = result.fetchone()
            
            if current_version:
                current = current_version[0]
                print(f"📋 Текущая версия в БД: {current}")
                
                # Если версия - удалённая d7211f3d17c3, обновляем до f7a99a334367
                if current == 'd7211f3d17c3':
                    print("🔧 Обновляю версию с d7211f3d17c3 на f7a99a334367...")
                    conn.execute(text("UPDATE alembic_version SET version_num = 'f7a99a334367'"))
                    conn.commit()
                    print("✅ Версия обновлена!")
                else:
                    print(f"ℹ️ Версия {current} не требует исправления")
            else:
                print("⚠️ Таблица alembic_version пуста или не найдена")
            
            # Проверяем наличие колонок
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'orders' AND column_name IN ('sd_price', 'zpch_sum')
            """))
            existing_columns = {row[0] for row in result.fetchall()}
            
            print("\n📊 Статус колонок:")
            print(f"   sd_price: {'✅ есть' if 'sd_price' in existing_columns else '❌ отсутствует'}")
            print(f"   zpch_sum: {'✅ есть' if 'zpch_sum' in existing_columns else '❌ отсутствует'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 Исправление состояния миграций")
    print("=" * 60)
    
    if fix_migrations():
        print("\n✅ Готово! Теперь можно применить миграции:")
        print("   alembic upgrade head")
    else:
        print("\n❌ Не удалось исправить состояние миграций")
        sys.exit(1)

