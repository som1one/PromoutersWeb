#!/usr/bin/env python3
"""
Скрипт для управления пользователями: добавление и изменение ролей
Использование:
    python manage_user.py <tg_id> [role] [city_id]
    python manage_user.py <tg_id> --show          # Показать информацию о пользователе
    python manage_user.py <tg_id> --role <role>   # Изменить роль
    python manage_user.py <tg_id> --city <city_id>  # Установить город
    python manage_user.py --interactive           # Интерактивный режим
"""

import sys
import argparse
from db import get_session
from model import User, City
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv('local.env')

# Доступные роли
ALLOWED_ROLES = ["owner", "director", "dispatcher", "master", "user"]

# Названия ролей для отображения
ROLE_NAMES = {
    "owner": "👑 Собственник",
    "director": "👔 Директор",
    "dispatcher": "📞 Диспетчер",
    "master": "🔧 Мастер",
    "user": "👤 Пользователь"
}


def show_user_info(session, tg_id: int):
    """Показать информацию о пользователе"""
    user = session.query(User).filter_by(tg_id=tg_id).first()
    
    if not user:
        print(f"❌ Пользователь с ID {tg_id} не найден в базе данных")
        return False
    
    print(f"\n{'=' * 60}")
    print(f"👤 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ")
    print(f"{'=' * 60}")
    print(f"ID (tg_id): {user.tg_id}")
    print(f"Имя: {user.name or 'Не указано'}")
    print(f"Полное имя: {user.full_name or 'Не указано'}")
    print(f"Роль: {ROLE_NAMES.get(user.role, user.role)} ({user.role})")
    print(f"Телефон: {user.phone or 'Не указан'}")
    
    if user.city_id:
        city = session.query(City).filter_by(id=user.city_id).first()
        city_name = city.name if city else f"ID {user.city_id} (не найден)"
        print(f"Город: {city_name} (ID: {user.city_id})")
    else:
        print(f"Город: Не назначен")
    
    if user.master_percentage:
        print(f"Индивидуальный процент мастера: {user.master_percentage}%")
    
    print(f"{'=' * 60}\n")
    return True


def list_cities(session):
    """Показать список всех городов"""
    cities = session.query(City).order_by(City.name).all()
    
    if not cities:
        print("❌ В базе данных нет городов")
        return []
    
    print("\n📍 Доступные города:")
    print("-" * 60)
    for city in cities:
        print(f"  ID: {city.id:3d} | {city.name}")
    print("-" * 60)
    
    return cities


def create_or_update_user(tg_id: int, role: str = None, city_id: int = None, name: str = None):
    """Создать или обновить пользователя"""
    session = get_session()
    
    try:
        user = session.query(User).filter_by(tg_id=tg_id).first()
        
        if user:
            # Обновляем существующего пользователя
            changes = []
            
            if role:
                if role not in ALLOWED_ROLES:
                    print(f"❌ Неверная роль: {role}")
                    print(f"💡 Доступные роли: {', '.join(ALLOWED_ROLES)}")
                    return False
                
                old_role = user.role
                user.role = role
                changes.append(f"роль: '{old_role}' → '{role}'")
            
            if city_id is not None:
                # Проверяем существование города
                city = session.query(City).filter_by(id=city_id).first()
                if not city:
                    print(f"❌ Город с ID {city_id} не найден")
                    list_cities(session)
                    return False
                
                old_city = user.city_id
                user.city_id = city_id
                if old_city != city_id:
                    city_name = city.name
                    changes.append(f"город: {old_city or 'не назначен'} → {city_name} (ID: {city_id})")
            
            if name:
                old_name = user.name
                user.name = name
                if old_name != name:
                    changes.append(f"имя: '{old_name or 'не указано'}' → '{name}'")
            
            session.commit()
            
            if changes:
                print(f"✅ Пользователь ID {tg_id} обновлен:")
                for change in changes:
                    print(f"   • {change}")
            else:
                print(f"ℹ️ Пользователь ID {tg_id} уже имеет указанные параметры")
            
            show_user_info(session, tg_id)
            return True
        else:
            # Создаем нового пользователя
            if not role:
                print(f"❌ Для создания нового пользователя необходимо указать роль")
                print(f"💡 Доступные роли: {', '.join(ALLOWED_ROLES)}")
                return False
            
            if role not in ALLOWED_ROLES:
                print(f"❌ Неверная роль: {role}")
                print(f"💡 Доступные роли: {', '.join(ALLOWED_ROLES)}")
                return False
            
            # Проверяем город, если указан
            if city_id is not None:
                city = session.query(City).filter_by(id=city_id).first()
                if not city:
                    print(f"❌ Город с ID {city_id} не найден")
                    list_cities(session)
                    return False
            
            user = User(
                tg_id=tg_id,
                name=name or str(tg_id),
                role=role,
                city_id=city_id
            )
            session.add(user)
            session.commit()
            
            print(f"✅ Создан новый пользователь:")
            print(f"   • ID: {tg_id}")
            print(f"   • Роль: {ROLE_NAMES.get(role, role)} ({role})")
            if city_id:
                city = session.query(City).filter_by(id=city_id).first()
                print(f"   • Город: {city.name if city else city_id} (ID: {city_id})")
            
            show_user_info(session, tg_id)
            return True
            
    except Exception as e:
        session.rollback()
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def interactive_mode():
    """Интерактивный режим управления пользователями"""
    print("\n" + "=" * 60)
    print("🔧 ИНТЕРАКТИВНОЕ УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ")
    print("=" * 60)
    
    session = get_session()
    
    try:
        while True:
            print("\nВыберите действие:")
            print("1 - Показать информацию о пользователе")
            print("2 - Создать нового пользователя")
            print("3 - Изменить роль пользователя")
            print("4 - Установить город для пользователя")
            print("5 - Показать список городов")
            print("0 - Выход")
            
            choice = input("\nВаш выбор: ").strip()
            
            if choice == "0":
                print("👋 До свидания!")
                break
            elif choice == "1":
                try:
                    tg_id = int(input("Введите ID пользователя: ").strip())
                    show_user_info(session, tg_id)
                except ValueError:
                    print("❌ Неверный формат ID (должно быть число)")
            elif choice == "2":
                try:
                    tg_id = int(input("Введите ID нового пользователя: ").strip())
                    
                    # Проверяем, не существует ли уже
                    existing = session.query(User).filter_by(tg_id=tg_id).first()
                    if existing:
                        print(f"⚠️ Пользователь с ID {tg_id} уже существует")
                        show_user_info(session, tg_id)
                        continue
                    
                    print(f"\nДоступные роли: {', '.join(ALLOWED_ROLES)}")
                    role = input("Введите роль: ").strip().lower()
                    
                    if role not in ALLOWED_ROLES:
                        print(f"❌ Неверная роль")
                        continue
                    
                    name = input("Введите имя (опционально, Enter для пропуска): ").strip() or None
                    
                    city_id = None
                    if role == "director":
                        list_cities(session)
                        city_input = input("Введите ID города (опционально, Enter для пропуска): ").strip()
                        if city_input:
                            try:
                                city_id = int(city_input)
                            except ValueError:
                                print("❌ Неверный формат ID города")
                                continue
                    
                    create_or_update_user(tg_id, role, city_id, name)
                except ValueError:
                    print("❌ Неверный формат ID (должно быть число)")
            elif choice == "3":
                try:
                    tg_id = int(input("Введите ID пользователя: ").strip())
                    
                    user = session.query(User).filter_by(tg_id=tg_id).first()
                    if not user:
                        print(f"❌ Пользователь с ID {tg_id} не найден")
                        continue
                    
                    print(f"\nТекущая роль: {ROLE_NAMES.get(user.role, user.role)} ({user.role})")
                    print(f"Доступные роли: {', '.join(ALLOWED_ROLES)}")
                    new_role = input("Введите новую роль: ").strip().lower()
                    
                    if new_role not in ALLOWED_ROLES:
                        print(f"❌ Неверная роль")
                        continue
                    
                    create_or_update_user(tg_id, role=new_role)
                except ValueError:
                    print("❌ Неверный формат ID (должно быть число)")
            elif choice == "4":
                try:
                    tg_id = int(input("Введите ID пользователя: ").strip())
                    
                    user = session.query(User).filter_by(tg_id=tg_id).first()
                    if not user:
                        print(f"❌ Пользователь с ID {tg_id} не найден")
                        continue
                    
                    list_cities(session)
                    city_input = input("Введите ID города (Enter для сброса): ").strip()
                    
                    city_id = None
                    if city_input:
                        try:
                            city_id = int(city_input)
                        except ValueError:
                            print("❌ Неверный формат ID города")
                            continue
                    
                    create_or_update_user(tg_id, city_id=city_id)
                except ValueError:
                    print("❌ Неверный формат ID (должно быть число)")
            elif choice == "5":
                list_cities(session)
            else:
                print("❌ Неверный выбор")
    finally:
        session.close()


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description="Управление пользователями: добавление и изменение ролей",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python manage_user.py 123456789 --show
  python manage_user.py 123456789 --role owner
  python manage_user.py 123456789 --role director --city 1
  python manage_user.py 123456789 master 1
  python manage_user.py --interactive
        """
    )
    
    parser.add_argument("tg_id", nargs="?", type=int, help="ID пользователя (VK ID)")
    parser.add_argument("role", nargs="?", help=f"Роль пользователя ({', '.join(ALLOWED_ROLES)})")
    parser.add_argument("city_id", nargs="?", type=int, help="ID города (опционально)")
    parser.add_argument("--show", action="store_true", help="Показать информацию о пользователе")
    parser.add_argument("--role", dest="set_role", help="Изменить роль пользователя")
    parser.add_argument("--city", type=int, help="Установить город для пользователя")
    parser.add_argument("--name", help="Установить имя пользователя")
    parser.add_argument("--interactive", "-i", action="store_true", help="Интерактивный режим")
    
    args = parser.parse_args()
    
    # Интерактивный режим
    if args.interactive:
        interactive_mode()
        return
    
    # Проверяем наличие tg_id
    if not args.tg_id:
        parser.print_help()
        return
    
    tg_id = args.tg_id
    
    # Показать информацию
    if args.show:
        session = get_session()
        try:
            show_user_info(session, tg_id)
        finally:
            session.close()
        return
    
    # Определяем роль
    role = args.set_role or args.role
    
    # Определяем city_id
    city_id = args.city or args.city_id
    
    # Создаем или обновляем пользователя
    create_or_update_user(tg_id, role, city_id, args.name)


if __name__ == "__main__":
    main()

