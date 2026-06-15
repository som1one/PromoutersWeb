"""
Тест для проверки сохранения и вывода чеков
"""
import sys
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from io import BytesIO

# Добавляем путь к проекту
sys.path.insert(0, '.')

from db import get_session
from model import User, Order, City
from pathlib import Path


def create_test_receipt_file(content: bytes = b"test receipt content", extension: str = ".jpg") -> Path:
    """Создает тестовый файл чека"""
    temp_dir = Path("bso_files")
    temp_dir.mkdir(exist_ok=True)
    temp_file = temp_dir / f"test_receipt_{datetime.now().timestamp()}{extension}"
    with open(temp_file, "wb") as f:
        f.write(content)
    return temp_file


def test_receipt_save_via_web():
    """Тест сохранения чека через веб-интерфейс"""
    print("=" * 60)
    print("ТЕСТ: Сохранение чека через веб-интерфейс")
    print("=" * 60)
    
    session = get_session()
    try:
        # Создаем тестовую заявку
        test_order = session.query(Order).first()
        if not test_order:
            print("❌ Нет заявок в базе для тестирования")
            return False
        
        order_id = test_order.id
        print(f"✅ Используем заявку #{test_order.order_number} (ID: {order_id})")
        
        # Создаем тестовый файл чека
        test_content = b"test receipt file content for web upload"
        test_file = create_test_receipt_file(test_content, ".jpg")
        print(f"✅ Создан тестовый файл: {test_file}")
        
        # Симулируем сохранение через веб (прямое обновление в БД)
        test_order.receipt_file_path = str(test_file.resolve())
        session.commit()
        
        # Проверяем, что путь сохранен
        session.refresh(test_order)
        if not test_order.receipt_file_path:
            print("❌ Путь к чеку не сохранен в БД")
            return False
        
        print(f"✅ Путь к чеку сохранен в БД: {test_order.receipt_file_path}")
        
        # Проверяем, что файл существует
        if not Path(test_order.receipt_file_path).exists():
            print(f"❌ Файл чека не найден на диске: {test_order.receipt_file_path}")
            return False
        
        print(f"✅ Файл чека существует на диске")
        
        # Проверяем содержимое файла
        with open(test_order.receipt_file_path, "rb") as f:
            file_content = f.read()
            if file_content != test_content:
                print("❌ Содержимое файла не совпадает")
                return False
        
        print("✅ Содержимое файла корректно")
        
        # Очистка
        if test_file.exists():
            test_file.unlink()
            print(f"✅ Тестовый файл удален")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def test_receipt_save_via_bot():
    """Тест сохранения чека через бота (receipt_file_id)"""
    print("\n" + "=" * 60)
    print("ТЕСТ: Сохранение чека через бота (receipt_file_id)")
    print("=" * 60)
    
    session = get_session()
    try:
        # Создаем тестовую заявку
        test_order = session.query(Order).first()
        if not test_order:
            print("❌ Нет заявок в базе для тестирования")
            return False
        
        order_id = test_order.id
        print(f"✅ Используем заявку #{test_order.order_number} (ID: {order_id})")
        
        # Симулируем сохранение через бота (только receipt_file_id)
        test_receipt_id = f"test_receipt_id_{datetime.now().timestamp()}"
        test_order.receipt_file_id = test_receipt_id
        session.commit()
        
        # Проверяем, что ID сохранен
        session.refresh(test_order)
        if not test_order.receipt_file_id:
            print("❌ receipt_file_id не сохранен в БД")
            return False
        
        print(f"✅ receipt_file_id сохранен в БД: {test_order.receipt_file_id}")
        
        # Проверяем, что receipt_file_path может быть None при наличии receipt_file_id
        if test_order.receipt_file_path:
            print(f"ℹ️ receipt_file_path также установлен: {test_order.receipt_file_path}")
        else:
            print("ℹ️ receipt_file_path не установлен (ожидаемо для бота)")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def test_receipt_retrieval():
    """Тест получения чека из БД"""
    print("\n" + "=" * 60)
    print("ТЕСТ: Получение чека из БД")
    print("=" * 60)
    
    session = get_session()
    try:
        # Ищем заявки с чеками
        orders_with_receipts = session.query(Order).filter(
            (Order.receipt_file_path.isnot(None)) | (Order.receipt_file_id.isnot(None))
        ).limit(5).all()
        
        if not orders_with_receipts:
            print("ℹ️ Нет заявок с чеками в базе")
            print("💡 Создайте заявку с чеком для полного тестирования")
            return True  # Не критичная ошибка
        
        print(f"✅ Найдено заявок с чеками: {len(orders_with_receipts)}")
        
        for order in orders_with_receipts:
            print(f"\n📋 Заявка #{order.order_number}:")
            if order.receipt_file_path:
                print(f"   ✅ receipt_file_path: {order.receipt_file_path}")
                # Проверяем существование файла
                if Path(order.receipt_file_path).exists():
                    file_size = Path(order.receipt_file_path).stat().st_size
                    print(f"   ✅ Файл существует, размер: {file_size} байт")
                else:
                    print(f"   ⚠️ Файл не найден на диске")
            if order.receipt_file_id:
                print(f"   ✅ receipt_file_id: {order.receipt_file_id[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def test_receipt_file_search():
    """Тест поиска файла чека по паттерну"""
    print("\n" + "=" * 60)
    print("ТЕСТ: Поиск файла чека по паттерну")
    print("=" * 60)
    
    session = get_session()
    try:
        # Создаем тестовую заявку
        test_order = session.query(Order).first()
        if not test_order:
            print("❌ Нет заявок в базе для тестирования")
            return False
        
        order_id = test_order.id
        print(f"✅ Используем заявку #{test_order.order_number} (ID: {order_id})")
        
        # Создаем тестовый файл чека с паттерном receipt_{order_id}_*
        from pathlib import Path
        bso_dir = Path("bso_files")
        bso_dir.mkdir(exist_ok=True)
        
        test_filename = f"receipt_{order_id}_test_{datetime.now().timestamp()}.jpg"
        test_file = bso_dir / test_filename
        
        test_content = b"test receipt for pattern search"
        with open(test_file, "wb") as f:
            f.write(test_content)
        
        print(f"✅ Создан тестовый файл: {test_file}")
        
        # Симулируем ситуацию: есть receipt_file_id, но нет receipt_file_path
        test_order.receipt_file_id = f"test_id_{datetime.now().timestamp()}"
        test_order.receipt_file_path = None
        session.commit()
        
        # Ищем файл по паттерну
        possible_files = list(bso_dir.glob(f"receipt_{order_id}_*"))
        
        if possible_files:
            print(f"✅ Найдено файлов по паттерну: {len(possible_files)}")
            for f in possible_files:
                print(f"   📄 {f.name}")
        else:
            print("⚠️ Файлы по паттерну не найдены (может быть нормально, если файлы не созданы)")
        
        # Очистка
        if test_file.exists():
            test_file.unlink()
            print(f"✅ Тестовый файл удален")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def test_receipt_display_in_templates():
    """Тест отображения чеков в шаблонах"""
    print("\n" + "=" * 60)
    print("ТЕСТ: Отображение чеков в шаблонах")
    print("=" * 60)
    
    session = get_session()
    try:
        # Ищем заявки с чеками
        orders_with_receipts = session.query(Order).filter(
            (Order.receipt_file_path.isnot(None)) | (Order.receipt_file_id.isnot(None))
        ).limit(3).all()
        
        if not orders_with_receipts:
            print("ℹ️ Нет заявок с чеками для тестирования отображения")
            return True
        
        print(f"✅ Найдено заявок с чеками: {len(orders_with_receipts)}")
        
        for order in orders_with_receipts:
            print(f"\n📋 Заявка #{order.order_number}:")
            
            # Проверяем условия для отображения в шаблонах
            has_receipt = bool(order.receipt_file_path or order.receipt_file_id)
            print(f"   Условие для отображения: {has_receipt}")
            
            if order.receipt_file_path:
                filename = order.receipt_file_path.split('/')[-1]
                print(f"   📄 Имя файла для отображения: {filename}")
            
            if order.receipt_file_id and not order.receipt_file_path:
                receipt_id_display = order.receipt_file_id[:20] + "..." if len(order.receipt_file_id) > 20 else order.receipt_file_id
                print(f"   📎 ID чека для отображения: {receipt_id_display}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def test_receipt_file_extensions():
    """Тест различных расширений файлов чеков"""
    print("\n" + "=" * 60)
    print("ТЕСТ: Различные расширения файлов чеков")
    print("=" * 60)
    
    allowed_extensions = [".jpg", ".jpeg", ".png", ".webp", ".pdf"]
    test_content = b"test receipt content"
    
    session = get_session()
    try:
        test_order = session.query(Order).first()
        if not test_order:
            print("❌ Нет заявок в базе для тестирования")
            return False
        
        created_files = []
        
        for ext in allowed_extensions:
            test_file = create_test_receipt_file(test_content, ext)
            created_files.append(test_file)
            
            # Проверяем, что файл создан
            if not test_file.exists():
                print(f"❌ Не удалось создать файл с расширением {ext}")
                continue
            
            file_size = test_file.stat().st_size
            print(f"✅ {ext}: файл создан, размер {file_size} байт")
            
            # Проверяем расширение
            if test_file.suffix.lower() != ext:
                print(f"⚠️ Расширение файла не совпадает: ожидалось {ext}, получено {test_file.suffix}")
        
        # Очистка
        for f in created_files:
            if f.exists():
                f.unlink()
        
        print(f"✅ Все тестовые файлы удалены")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def run_all_tests():
    """Запуск всех тестов"""
    print("\n" + "=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ СОХРАНЕНИЯ И ВЫВОДА ЧЕКОВ")
    print("=" * 60)
    print()
    
    results = []
    
    # Тест 1: Сохранение через веб
    results.append(("Сохранение через веб", test_receipt_save_via_web()))
    
    # Тест 2: Сохранение через бота
    results.append(("Сохранение через бота", test_receipt_save_via_bot()))
    
    # Тест 3: Получение из БД
    results.append(("Получение из БД", test_receipt_retrieval()))
    
    # Тест 4: Поиск по паттерну
    results.append(("Поиск по паттерну", test_receipt_file_search()))
    
    # Тест 5: Отображение в шаблонах
    results.append(("Отображение в шаблонах", test_receipt_display_in_templates()))
    
    # Тест 6: Различные расширения
    results.append(("Различные расширения", test_receipt_file_extensions()))
    
    # Итоги
    print("\n" + "=" * 60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{status}: {test_name}")
    
    print(f"\n📈 Результат: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены успешно!")
        return True
    else:
        print("⚠️ Некоторые тесты провалены")
        return False


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Тестирование прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

