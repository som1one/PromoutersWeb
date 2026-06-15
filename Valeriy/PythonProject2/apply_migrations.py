#!/usr/bin/env python3
"""
Скрипт для применения миграций БД.
Запустите: python apply_migrations.py
"""

import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения
if os.path.exists('local.env'):
    load_dotenv('local.env')
else:
    load_dotenv()

def apply_migrations():
    """Применить все неприменённые миграции"""
    try:
        from alembic.config import Config
        from alembic import command
        from alembic.script import ScriptDirectory
        
        alembic_cfg = Config("alembic.ini")
        
        # Проверяем состояние миграций
        script = ScriptDirectory.from_config(alembic_cfg)
        heads = script.get_revisions("heads")
        
        if len(heads) > 1:
            print(f"⚠️ Обнаружено несколько голов миграций: {[h.revision for h in heads]}")
            print("Попытка применить все головы...")
            command.upgrade(alembic_cfg, "heads")
        else:
            print("🔄 Применение миграций БД...")
            command.upgrade(alembic_cfg, "head")
        
        print("✅ Миграции успешно применены!")
        return True
    except Exception as e:
        print(f"❌ Ошибка при применении миграций: {e}")
        import traceback
        traceback.print_exc()
        print("\n💡 Попробуйте применить миграции вручную:")
        print("   alembic upgrade heads  # для всех голов")
        print("   или")
        print("   alembic upgrade add_zpch_sum_001  # для конкретной миграции")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("📦 Применение миграций базы данных")
    print("=" * 60)
    print()
    
    if apply_migrations():
        print("\n🎉 Готово! Все миграции применены.")
        sys.exit(0)
    else:
        print("\n❌ Произошла ошибка. Проверьте логи выше.")
        sys.exit(1)

