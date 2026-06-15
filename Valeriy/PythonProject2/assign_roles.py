#!/usr/bin/env python3
"""
Скрипт для массового назначения ролей пользователям VK.
Использование: python assign_roles.py
"""

from db import get_session
from model import User
from dotenv import load_dotenv
import os

# Загружаем переменные окружения
load_dotenv('local.env')

def assign_roles_from_list():
    """
    Массовое назначение ролей по списку VK ID.
    
    Формат данных:
    users_to_assign = [
        {"vk_id": 123456789, "role": "director", "city_id": 1},  # city_id опционально
        {"vk_id": 987654321, "role": "dispatcher"},
        {"vk_id": 555555555, "role": "master"},
    ]
    """
    
    # ВАШ СПИСОК ПОЛЬЗОВАТЕЛЕЙ ДЛЯ НАЗНАЧЕНИЯ
    # Вставьте сюда VK ID из URL (например: https://vk.com/id123456789 -> vk_id: 123456789)
    users_to_assign = [
        # Примеры:
        # {"vk_id": 123456789, "role": "owner"},
        # {"vk_id": 987654321, "role": "director", "city_id": 1},  # Для директора можно указать city_id
        # {"vk_id": 555555555, "role": "dispatcher"},
        # {"vk_id": 444444444, "role": "master"},
    ]
    
    if not users_to_assign:
        print("⚠️ Список пользователей пуст!")
        print("\n💡 Как использовать:")
        print("1. Откройте профили пользователей в VK")
        print("2. Скопируйте VK ID из URL (цифры после 'id' в адресе)")
        print("3. Добавьте их в список users_to_assign выше")
        print("4. Укажите нужную роль для каждого")
        return
    
    session = get_session()
    try:
        print(f"🔄 Начинаю назначение ролей для {len(users_to_assign)} пользователей...\n")
        
        for user_data in users_to_assign:
            vk_id = user_data["vk_id"]
            role = user_data["role"]
            city_id = user_data.get("city_id")  # Опционально для директора
            
            # Проверяем существование пользователя
            user = session.query(User).filter_by(tg_id=vk_id).first()
            
            if user:
                old_role = user.role
                user.role = role
                if city_id is not None:
                    user.city_id = city_id
                print(f"✅ Обновлен: ID {vk_id} - роль изменена с '{old_role}' на '{role}'")
            else:
                user = User(
                    tg_id=vk_id,
                    name=str(vk_id),
                    role=role,
                    city_id=city_id
                )
                session.add(user)
                print(f"✅ Создан: ID {vk_id} - роль '{role}'")
        
        session.commit()
        print(f"\n🎉 Готово! Обработано {len(users_to_assign)} пользователей.")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


def assign_from_admin_ids():
    """
    Назначает роль 'owner' всем пользователям из ADMIN_IDS в local.env
    """
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    if not admin_ids_str:
        print("⚠️ ADMIN_IDS не указаны в local.env")
        return
    
    admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]
    print(f"🔑 Назначаю роль 'owner' для {len(admin_ids)} администраторов из ADMIN_IDS...\n")
    
    session = get_session()
    try:
        for vk_id in admin_ids:
            user = session.query(User).filter_by(tg_id=vk_id).first()
            if user:
                if user.role != "owner":
                    old_role = user.role
                    user.role = "owner"
                    print(f"✅ ID {vk_id}: роль изменена с '{old_role}' на 'owner'")
                else:
                    print(f"ℹ️ ID {vk_id}: уже имеет роль 'owner'")
            else:
                user = User(tg_id=vk_id, name=str(vk_id), role="owner")
                session.add(user)
                print(f"✅ ID {vk_id}: создан с ролью 'owner'")
        
        session.commit()
        print(f"\n🎉 Готово!")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    print("=" * 60)
    print("🔧 Скрипт назначения ролей")
    print("=" * 60)
    print()
    
    choice = input("Выберите действие:\n1 - Назначить из списка users_to_assign\n2 - Назначить owner из ADMIN_IDS\nВаш выбор: ")
    
    if choice == "1":
        assign_roles_from_list()
    elif choice == "2":
        assign_from_admin_ids()
    else:
        print("❌ Неверный выбор")

