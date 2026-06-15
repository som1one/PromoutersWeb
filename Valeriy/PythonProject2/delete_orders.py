#!/usr/bin/env python3
"""
Скрипт для удаления заявок по номерам
"""
import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

from db import get_session
from model import Order, Stat

def delete_orders_by_numbers(order_numbers):
    """Удалить заявки по номерам"""
    session = get_session()
    try:
        # Находим заявки по номерам
        orders = session.query(Order).filter(Order.order_number.in_(order_numbers)).all()
        
        if not orders:
            print(f"❌ Заявки с номерами {order_numbers} не найдены")
            return
        
        print(f"📋 Найдено заявок: {len(orders)}")
        
        deleted_count = 0
        for order in orders:
            order_id = order.id
            order_number = order.order_number
            
            # Удаляем связанные записи в Stat
            stats = session.query(Stat).filter(Stat.order_id == order_id).all()
            if stats:
                print(f"  ⚠️  Заявка #{order_number}: найдено {len(stats)} записей в статистике")
                for stat in stats:
                    session.delete(stat)
            
            # Удаляем заявку
            session.delete(order)
            deleted_count += 1
            print(f"  ✅ Заявка #{order_number} удалена")
        
        # Коммитим изменения
        session.commit()
        print(f"\n✅ Успешно удалено заявок: {deleted_count}")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Ошибка при удалении: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    # Номера заявок для удаления
    order_numbers = [60016, 60017, 60018, 60019]
    
    print(f"🗑️  Удаление заявок: {order_numbers}\n")
    confirm = input("⚠️  Вы уверены? Это действие нельзя отменить! (yes/no): ")
    
    if confirm.lower() == "yes":
        delete_orders_by_numbers(order_numbers)
    else:
        print("❌ Удаление отменено")

