"""
Скрипт для пересчета всех старых заявок мастера по новой ставке 50%
"""
import sys
from db import get_session
from model import Order, Stat, User
from services.commission_service import get_master_pct
from services.dashboard_stats import _resolve_master_pct

def recalculate_master_orders(master_tg_id: int, new_percentage: float = 50.0):
    """
    Пересчитать все заявки мастера по новой ставке
    
    Args:
        master_tg_id: VK ID мастера
        new_percentage: Новый процент мастера (по умолчанию 50%)
    """
    session = get_session()
    
    try:
        # Проверяем, что мастер существует
        master = session.query(User).filter_by(tg_id=master_tg_id).first()
        if not master:
            print(f"❌ Мастер с VK ID {master_tg_id} не найден")
            return
        
        print(f"👤 Мастер: {master.full_name or master.name or master_tg_id}")
        print(f"📊 Текущий индивидуальный процент: {master.master_percentage if master.master_percentage else 'по сетке'}%")
        print(f"🔄 Устанавливаем новый процент: {new_percentage}%")
        print("-" * 60)
        
        # Устанавливаем новый индивидуальный процент мастера
        master.master_percentage = new_percentage
        session.commit()
        print(f"✅ Индивидуальный процент мастера установлен: {new_percentage}%")
        print()
        
        # Находим все заявки мастера со статусами, где нужен пересчет
        # Статусы: done_pending_sum (готовы к сдаче кассы), completed (закрытые)
        orders_to_recalculate = session.query(Order).filter(
            Order.assigned_to == master_tg_id,
            Order.status.in_(["done_pending_sum", "completed"])
        ).all()
        
        print(f"📋 Найдено заявок для пересчета: {len(orders_to_recalculate)}")
        print()
        
        if not orders_to_recalculate:
            print("✅ Нет заявок для пересчета")
            return
        
        recalculated_count = 0
        stats_updated_count = 0
        
        for order in orders_to_recalculate:
            # Пропускаем заявки без суммы
            if not order.sum_amount or order.sum_amount <= 0:
                continue
            
            # Рассчитываем чистую сумму
            order_sum = float(order.sum_amount or 0)
            sd_price = float(order.sd_price or 0)
            zpch_sum = float(order.zpch_sum or 0)
            net_amount = max(order_sum - sd_price - zpch_sum, 0)
            
            if net_amount <= 0:
                continue
            
            # Используем новую ставку 50% для расчета
            old_master_pct = get_master_pct(order.equip_type or "other", net_amount)
            new_master_pct = new_percentage  # Используем индивидуальный процент мастера
            
            old_master_share = net_amount * (old_master_pct / 100.0)
            new_master_share = net_amount * (new_master_pct / 100.0)
            
            old_company_share = net_amount - old_master_share
            new_company_share = net_amount - new_master_share
            
            # Выводим информацию о пересчете
            print(f"📋 Заявка #{order.order_number}")
            print(f"   Чистая сумма: {net_amount:.2f} ₽")
            print(f"   Старый процент: {old_master_pct}% → Мастер: {old_master_share:.2f} ₽, Компания: {old_company_share:.2f} ₽")
            print(f"   Новый процент: {new_master_pct}% → Мастер: {new_master_share:.2f} ₽, Компания: {new_company_share:.2f} ₽")
            print(f"   Изменение компании: {new_company_share - old_company_share:+.2f} ₽")
            
            # Обновляем записи в Stat, если они есть
            stat = session.query(Stat).filter_by(order_id=order.id, master_tg=master_tg_id).first()
            if stat:
                # Обновляем сумму в Stat (там хранится общая сумма заявки, не чистая)
                # Но для статистики обычно важна чистая сумма
                stat.sum = net_amount
                stats_updated_count += 1
                print(f"   ✅ Запись в Stat обновлена")
            
            recalculated_count += 1
            print()
        
        session.commit()
        
        print("=" * 60)
        print(f"✅ Пересчет завершен!")
        print(f"📊 Пересчитано заявок: {recalculated_count}")
        print(f"📝 Обновлено записей в Stat: {stats_updated_count}")
        print()
        print("⚠️  ВАЖНО: Заявки со статусом 'done_pending_sum' будут пересчитаны")
        print("   при следующем просмотре кассы. Заявки со статусом 'completed'")
        print("   уже закрыты, но их записи в Stat обновлены.")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Ошибка при пересчете: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python recalculate_master_orders.py <VK_ID> [процент]")
        print("Пример: python recalculate_master_orders.py 377414771 50")
        sys.exit(1)
    
    master_tg_id = int(sys.argv[1])
    new_percentage = float(sys.argv[2]) if len(sys.argv) > 2 else 50.0
    
    print("=" * 60)
    print("🔄 ПЕРЕСЧЕТ ЗАЯВОК МАСТЕРА ПО НОВОЙ СТАВКЕ")
    print("=" * 60)
    print()
    
    recalculate_master_orders(master_tg_id, new_percentage)

