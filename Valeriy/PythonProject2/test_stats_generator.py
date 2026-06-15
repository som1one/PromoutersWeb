"""
Тестовый скрипт для создания записей статистики с рандомными датами
"""
import random
from datetime import datetime, timedelta
from db import get_session
from model import Stat, User
from sqlalchemy import func
from dotenv import load_dotenv
import os

# Загружаем переменные окружения
load_dotenv('local.env')

# Типы оборудования
EQUIP_TYPES = ["appliance", "pc", "phones", "other"]

def generate_random_stats(count: int = 50):
    """
    Создает указанное количество записей статистики с рандомными датами
    
    Args:
        count: Количество записей для создания
    """
    session = get_session()
    
    try:
        # Получаем список мастеров из базы (если есть)
        from model import User
        masters = session.query(User).filter_by(role="master").all()
        master_ids = [m.tg_id for m in masters] if masters else [1001, 1002, 1003, 1004, 1005]  # Fallback IDs
        
        # Генерируем случайные даты за последние 6 месяцев
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        
        stats_created = 0
        
        print(f"🔄 Создание {count} записей статистики...")
        
        for i in range(count):
            # Случайная дата в диапазоне
            random_seconds = random.randint(0, int((end_date - start_date).total_seconds()))
            random_date = start_date + timedelta(seconds=random_seconds)
            
            # Случайные значения
            order_id = random.randint(1, 9999)  # Случайный ID заявки
            equip_type = random.choice(EQUIP_TYPES)
            sum_value = round(random.uniform(1000, 50000), 2)  # Сумма от 1000 до 50000
            refused = random.choice([True, False])  # Случайно отказ или нет
            master_tg = random.choice(master_ids) if master_ids else None
            
            # Создаем запись
            stat = Stat(
                order_id=order_id,
                equip_type=equip_type,
                sum=sum_value if not refused else 0.0,  # Если отказ - сумма 0
                refused=refused,
                master_tg=master_tg,
                recorded_at=random_date
            )
            
            session.add(stat)
            
            # Коммитим каждые 10 записей для производительности
            if (i + 1) % 10 == 0:
                session.commit()
                stats_created += 10
                print(f"✅ Создано {stats_created} записей...")
        
        # Коммитим оставшиеся записи
        if stats_created < count:
            session.commit()
        
        print(f"✅ Успешно создано {count} записей статистики!")
        print(f"📅 Диапазон дат: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")
        
        # Показываем статистику
        total_sum = session.query(Stat).count()
        print(f"📊 Всего записей в таблице: {total_sum}")
        
        # Статистика по типам оборудования
        print("\n📈 Статистика по типам оборудования:")
        for eq_type in EQUIP_TYPES:
            count_by_type = session.query(Stat).filter_by(equip_type=eq_type).count()
            print(f"  - {eq_type}: {count_by_type} записей")
        
        # Статистика по отказам (из всех записей в таблице, а не только созданных)
        total_in_db = session.query(Stat).count()
        refused_count = session.query(Stat).filter_by(refused=True).count()
        successful_count = total_in_db - refused_count
        print(f"\n❌ Отказов: {refused_count} ({refused_count * 100 / total_in_db:.1f}%)")
        print(f"✅ Успешных: {successful_count} ({successful_count * 100 / total_in_db:.1f}%)")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Ошибка при создании записей: {e}")
        raise
    finally:
        session.close()


def view_stats(limit: int = 20):
    """Просмотр записей статистики"""
    session = get_session()
    try:
        stats = session.query(Stat).order_by(Stat.recorded_at.desc()).limit(limit).all()
        
        if not stats:
            print("📭 Записей статистики нет")
            return
        
        print(f"📊 Показано последних {len(stats)} записей из {session.query(Stat).count()}:\n")
        print("=" * 80)
        
        for i, stat in enumerate(stats, 1):
            master_name = f"ID {stat.master_tg}" if stat.master_tg else "Не указан"
            # Получаем имя мастера если есть
            if stat.master_tg:
                master = session.query(User).filter_by(tg_id=stat.master_tg).first()
                if master:
                    master_name = master.full_name or master.name or f"ID {stat.master_tg}"
            
            date_str = stat.recorded_at.strftime('%d.%m.%Y %H:%M') if stat.recorded_at else "Не указана"
            refused_str = "❌ ОТКАЗ" if stat.refused else "✅"
            
            print(f"{i}. ID: {stat.id} | Order ID: {stat.order_id}")
            print(f"   Тип: {stat.equip_type or '-'} | Сумма: {stat.sum:.2f} руб. | {refused_str}")
            print(f"   Мастер: {master_name} | Дата: {date_str}")
            print("-" * 80)
        
        # Общая статистика
        total = session.query(Stat).count()
        total_sum = session.query(Stat).with_entities(func.sum(Stat.sum)).scalar() or 0
        refused_count = session.query(Stat).filter_by(refused=True).count()
        
        print(f"\n📈 Общая статистика:")
        print(f"   Всего записей: {total}")
        print(f"   Общая сумма: {total_sum:.2f} руб.")
        print(f"   Отказов: {refused_count} ({refused_count * 100 / total:.1f}%)")
        print(f"   Успешных: {total - refused_count} ({(total - refused_count) * 100 / total:.1f}%)")
        
    except Exception as e:
        print(f"❌ Ошибка при просмотре: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


def clear_all_stats():
    """Очищает все записи статистики (для тестирования)"""
    session = get_session()
    try:
        count = session.query(Stat).count()
        session.query(Stat).delete()
        session.commit()
        print(f"🗑️ Удалено {count} записей статистики")
    except Exception as e:
        session.rollback()
        print(f"❌ Ошибка при удалении: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "clear":
            # Очистка всех записей
            confirm = input("⚠️ Вы уверены, что хотите удалить все записи статистики? (yes/no): ")
            if confirm.lower() == "yes":
                clear_all_stats()
            else:
                print("❌ Отменено")
        elif sys.argv[1] == "view":
            # Просмотр записей
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            view_stats(limit)
        else:
            # Создание указанного количества записей
            try:
                count = int(sys.argv[1])
                generate_random_stats(count)
            except ValueError:
                print("❌ Неверный аргумент.")
                print("💡 Используйте:")
                print("   python test_stats_generator.py <число> - создать записи")
                print("   python test_stats_generator.py view [лимит] - просмотреть записи")
                print("   python test_stats_generator.py clear - очистить все записи")
    else:
        # По умолчанию создаем 50 записей
        generate_random_stats(50)

