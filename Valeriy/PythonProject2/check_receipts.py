"""
Скрипт для проверки файлов чеков и их соответствия записям в БД
"""
import sys
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Добавляем путь к проекту
sys.path.insert(0, '.')

from db import get_session
from model import Order, User


def check_receipt_files_on_disk():
    """Проверяет файлы чеков на диске"""
    print("=" * 80)
    print("ПРОВЕРКА ФАЙЛОВ ЧЕКОВ НА ДИСКЕ")
    print("=" * 80)
    
    bso_dir = Path("bso_files")
    if not bso_dir.exists():
        print(f"❌ Директория {bso_dir.absolute()} не существует")
        return []
    
    print(f"📁 Директория: {bso_dir.absolute()}")
    
    # Ищем все файлы чеков
    receipt_files = list(bso_dir.glob("receipt_*"))
    
    print(f"\n📊 Найдено файлов чеков: {len(receipt_files)}")
    
    if not receipt_files:
        print("⚠️ Файлы чеков не найдены")
        return []
    
    # Группируем по order_id
    files_by_order = defaultdict(list)
    for file in receipt_files:
        # Парсим имя файла: receipt_{order_id}_...
        parts = file.stem.split('_')
        if len(parts) >= 2 and parts[0] == "receipt":
            try:
                order_id = int(parts[1])
                files_by_order[order_id].append(file)
            except ValueError:
                print(f"⚠️ Не удалось распарсить order_id из имени файла: {file.name}")
    
    print(f"\n📋 Файлы сгруппированы по заявкам: {len(files_by_order)} заявок")
    
    for order_id, files in sorted(files_by_order.items()):
        print(f"\n  Заявка #{order_id}:")
        for file in files:
            size = file.stat().st_size
            modified = datetime.fromtimestamp(file.stat().st_mtime)
            print(f"    📄 {file.name}")
            print(f"       Размер: {size} байт")
            print(f"       Изменен: {modified.strftime('%d.%m.%Y %H:%M:%S')}")
            print(f"       Путь: {file.absolute()}")
    
    return receipt_files


def check_receipts_in_db():
    """Проверяет записи о чеках в БД"""
    print("\n" + "=" * 80)
    print("ПРОВЕРКА ЗАПИСЕЙ О ЧЕКАХ В БД")
    print("=" * 80)
    
    session = get_session()
    try:
        # Заявки с receipt_file_path
        orders_with_path = session.query(Order).filter(
            Order.receipt_file_path.isnot(None)
        ).all()
        
        # Заявки с receipt_file_id
        orders_with_id = session.query(Order).filter(
            Order.receipt_file_id.isnot(None)
        ).all()
        
        # Заявки с обоими полями
        orders_with_both = session.query(Order).filter(
            Order.receipt_file_path.isnot(None),
            Order.receipt_file_id.isnot(None)
        ).all()
        
        # Заявки только с receipt_file_id (без receipt_file_path)
        orders_only_id = session.query(Order).filter(
            Order.receipt_file_id.isnot(None),
            Order.receipt_file_path.is_(None)
        ).all()
        
        # Заявки только с receipt_file_path (без receipt_file_id)
        orders_only_path = session.query(Order).filter(
            Order.receipt_file_path.isnot(None),
            Order.receipt_file_id.is_(None)
        ).all()
        
        print(f"\n📊 Статистика:")
        print(f"   Заявок с receipt_file_path: {len(orders_with_path)}")
        print(f"   Заявок с receipt_file_id: {len(orders_with_id)}")
        print(f"   Заявок с обоими полями: {len(orders_with_both)}")
        print(f"   Заявок только с receipt_file_id: {len(orders_only_id)}")
        print(f"   Заявок только с receipt_file_path: {len(orders_only_path)}")
        
        # Проверяем существование файлов для заявок с receipt_file_path
        print(f"\n📋 Заявки с receipt_file_path:")
        missing_files = []
        existing_files = []
        
        for order in orders_with_path:
            file_path = Path(order.receipt_file_path)
            exists = file_path.exists()
            
            if exists:
                existing_files.append(order)
                size = file_path.stat().st_size
                print(f"   ✅ #{order.order_number} (ID: {order.id}): {order.receipt_file_path}")
                print(f"      Размер: {size} байт")
            else:
                missing_files.append(order)
                print(f"   ❌ #{order.order_number} (ID: {order.id}): {order.receipt_file_path}")
                print(f"      Файл не найден!")
        
        # Заявки только с receipt_file_id
        if orders_only_id:
            print(f"\n📋 Заявки только с receipt_file_id (без receipt_file_path):")
            for order in orders_only_id:
                print(f"   📎 #{order.order_number} (ID: {order.id})")
                print(f"      receipt_file_id: {order.receipt_file_id[:50]}...")
                
                # Пробуем найти файл по паттерну
                bso_dir = Path("bso_files")
                if bso_dir.exists():
                    possible_files = list(bso_dir.glob(f"receipt_{order.id}_*"))
                    if possible_files:
                        print(f"      ✅ Найден файл по паттерну: {possible_files[0].name}")
                    else:
                        print(f"      ⚠️ Файл по паттерну не найден")
        
        return {
            'orders_with_path': orders_with_path,
            'orders_with_id': orders_with_id,
            'orders_only_id': orders_only_id,
            'missing_files': missing_files,
            'existing_files': existing_files
        }
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        session.close()


def match_files_with_orders(receipt_files, db_data):
    """Сопоставляет файлы на диске с записями в БД"""
    print("\n" + "=" * 80)
    print("СОПОСТАВЛЕНИЕ ФАЙЛОВ С ЗАПИСЯМИ В БД")
    print("=" * 80)
    
    if not receipt_files or not db_data:
        print("⚠️ Нет данных для сопоставления")
        return
    
    session = get_session()
    try:
        # Создаем словарь файлов по order_id
        files_by_order = defaultdict(list)
        for file in receipt_files:
            parts = file.stem.split('_')
            if len(parts) >= 2 and parts[0] == "receipt":
                try:
                    order_id = int(parts[1])
                    files_by_order[order_id].append(file)
                except ValueError:
                    pass
        
        # Проверяем, какие файлы не привязаны к заявкам
        all_order_ids = set()
        for order in db_data.get('orders_with_path', []):
            all_order_ids.add(order.id)
        for order in db_data.get('orders_with_id', []):
            all_order_ids.add(order.id)
        
        orphan_files = []
        for order_id, files in files_by_order.items():
            if order_id not in all_order_ids:
                orphan_files.extend(files)
        
        if orphan_files:
            print(f"\n⚠️ Найдено {len(orphan_files)} файлов без привязки к заявкам:")
            for file in orphan_files:
                print(f"   📄 {file.name}")
        
        # Проверяем, какие заявки имеют файлы, но путь не указан
        orders_without_path_but_with_file = []
        for order_id, files in files_by_order.items():
            if order_id in all_order_ids:
                order = session.query(Order).filter_by(id=order_id).first()
                if order and not order.receipt_file_path:
                    orders_without_path_but_with_file.append((order, files))
        
        if orders_without_path_but_with_file:
            print(f"\n⚠️ Найдено {len(orders_without_path_but_with_file)} заявок с файлами, но без receipt_file_path:")
            for order, files in orders_without_path_but_with_file:
                print(f"   📋 Заявка #{order.order_number} (ID: {order.id})")
                for file in files:
                    print(f"      📄 {file.name}")
                    print(f"      💡 Рекомендуется обновить receipt_file_path: {file.absolute()}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


def check_receipt_endpoints():
    """Проверяет доступность endpoint'ов для получения чеков"""
    print("\n" + "=" * 80)
    print("ПРОВЕРКА ENDPOINT'ОВ")
    print("=" * 80)
    
    session = get_session()
    try:
        # Берем несколько заявок с чеками для тестирования
        test_orders = session.query(Order).filter(
            (Order.receipt_file_path.isnot(None)) | (Order.receipt_file_id.isnot(None))
        ).limit(5).all()
        
        if not test_orders:
            print("⚠️ Нет заявок с чеками для тестирования endpoint'ов")
            return
        
        print(f"\n📋 Тестовые заявки для проверки endpoint'ов:")
        for order in test_orders:
            print(f"\n   Заявка #{order.order_number} (ID: {order.id}):")
            print(f"      URL: /order/{order.id}/receipt-file")
            
            if order.receipt_file_path:
                file_path = Path(order.receipt_file_path)
                if file_path.exists():
                    print(f"      ✅ receipt_file_path: {order.receipt_file_path}")
                    print(f"      ✅ Файл существует")
                else:
                    print(f"      ⚠️ receipt_file_path: {order.receipt_file_path}")
                    print(f"      ❌ Файл не найден")
            else:
                print(f"      ⚠️ receipt_file_path: не указан")
            
            if order.receipt_file_id:
                print(f"      ✅ receipt_file_id: {order.receipt_file_id[:50]}...")
            else:
                print(f"      ⚠️ receipt_file_id: не указан")
            
            # Проверяем, можно ли найти файл по паттерну
            bso_dir = Path("bso_files")
            if bso_dir.exists():
                possible_files = list(bso_dir.glob(f"receipt_{order.id}_*"))
                if possible_files:
                    print(f"      ✅ Найден файл по паттерну: {possible_files[0].name}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


def generate_report():
    """Генерирует полный отчет"""
    print("\n" + "=" * 80)
    print("ОТЧЕТ О ПРОВЕРКЕ ЧЕКОВ")
    print("=" * 80)
    print(f"Дата проверки: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print()
    
    # 1. Проверка файлов на диске
    receipt_files = check_receipt_files_on_disk()
    
    # 2. Проверка записей в БД
    db_data = check_receipts_in_db()
    
    # 3. Сопоставление
    if receipt_files and db_data:
        match_files_with_orders(receipt_files, db_data)
    
    # 4. Проверка endpoint'ов
    check_receipt_endpoints()
    
    # Итоги
    print("\n" + "=" * 80)
    print("ИТОГИ")
    print("=" * 80)
    
    if db_data:
        missing_count = len(db_data.get('missing_files', []))
        existing_count = len(db_data.get('existing_files', []))
        only_id_count = len(db_data.get('orders_only_id', []))
        
        print(f"\n✅ Заявок с существующими файлами: {existing_count}")
        print(f"❌ Заявок с отсутствующими файлами: {missing_count}")
        print(f"⚠️ Заявок только с receipt_file_id: {only_id_count}")
        
        if missing_count > 0:
            print(f"\n💡 Рекомендации:")
            print(f"   - Проверьте пути к файлам в БД")
            print(f"   - Убедитесь, что файлы не были перемещены или удалены")
        
        if only_id_count > 0:
            print(f"\n💡 Рекомендации:")
            print(f"   - Для заявок только с receipt_file_id система попытается найти файл по паттерну")
            print(f"   - Проверьте, что файлы сохранены в директории bso_files с именем receipt_{{order_id}}_*")


if __name__ == "__main__":
    try:
        generate_report()
    except KeyboardInterrupt:
        print("\n\n⚠️ Проверка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

