"""
Тест для проверки статистики в боте и веб-интерфейсе
"""
import sys
from datetime import datetime, date

# Добавляем путь к проекту
sys.path.insert(0, '.')

from db import get_session
from model import User, Order, Stat, City
from services.statistics_service import collect_city_stats, generate_city_stats_excel
from services.dashboard_stats import calculate_dashboard_stats, get_period_bounds, summarize_dashboard
from handlers.utils import get_equip_type_name


def test_statistics_service():
    """Тест сервиса статистики"""
    print("=" * 60)
    print("ТЕСТ: Сервис статистики")
    print("=" * 60)
    
    session = get_session()
    try:
        # Получаем все завершенные заявки
        completed_orders = session.query(Order).filter(
            Order.status == "completed"
        ).all()
        
        if not completed_orders:
            print("❌ Нет завершенных заявок для тестирования")
            return False
        
        print(f"✅ Найдено завершенных заявок: {len(completed_orders)}")
        
        # Тестируем сбор статистики
        stats = collect_city_stats(completed_orders)
        
        if not stats:
            print("❌ Статистика не собрана")
            return False
        
        print(f"✅ Статистика собрана для {len(stats)} городов")
        
        # Проверяем структуру статистики
        for city_name, city_stat in stats.items():
            print(f"\n🏙 Город: {city_name}")
            print(f"   Всего заявок: {city_stat['total']}")
            print(f"   Отказов: {city_stat['refused']}")
            print(f"   Гарантийных: {city_stat['warranty']}")
            print(f"   Оборот: {city_stat['turnover']:.2f} ₽")
            print(f"   Средний чек: {city_stat['avg_check']:.2f} ₽")
            print(f"   KPI директора: {city_stat['kpi']:.2f} ₽")
            
            # Проверяем категории
            for code, cat_stat in city_stat['categories'].items():
                if cat_stat['total'] > 0:
                    print(f"   📦 {cat_stat['title']}: {cat_stat['total']} заявок, {cat_stat['turnover']:.2f} ₽")
        
        # Тестируем генерацию Excel
        try:
            excel_path = generate_city_stats_excel(completed_orders)
            print(f"\n✅ Excel файл создан: {excel_path}")
            return True
        except Exception as e:
            print(f"❌ Ошибка при создании Excel: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def test_dashboard_statistics():
    """Тест агрегированной статистики (бот + веб)"""
    print("\n" + "=" * 60)
    print("ТЕСТ: Дашборд статистики")
    print("=" * 60)
    
    session = get_session()
    try:
        start, end = get_period_bounds("month")
        
        # Статистика для мастера
        master = session.query(User).filter_by(role="master").first()
        if master:
            master_stats = calculate_dashboard_stats(
                session,
                date_from=start,
                date_to=end,
                master_id=master.tg_id,
            )
            print(f"👤 Мастер: {master.full_name or master.name or master.tg_id}")
            print(f"   Закрыто: {master_stats['cards']['completed']} из {master_stats['cards']['total']}")
            print(f"   Чистая сумма: {master_stats['cards']['net_sum']:.2f} ₽")
            print(f"   Конверсия: {master_stats['cards']['conversion']}%")
            if master_stats["equipment"]:
                top = master_stats["equipment"][0]
                print(f"   Топ техника: {top['name']} ({top['count']} заявок)")
            summary_lines = summarize_dashboard(master_stats, "master")
            if summary_lines:
                print("   Текстовая сводка:")
                for line in summary_lines:
                    if line:
                        print("   ", line)
        else:
            print("⚠️ Нет мастеров для проверки")
        
        # Статистика для директора / owner
        director = session.query(User).filter(User.role.in_(["director", "owner"])).first()
        if director:
            city_id = director.city_id
            director_stats = calculate_dashboard_stats(
                session,
                date_from=start,
                date_to=end,
                city_id=city_id,
                city_name=director.city_rel.name if director.city_rel else None,
            )
            print(f"\n👔 {director.role.title()}: {director.full_name or director.name or director.tg_id}")
            print(f"   Город: {director_stats['meta']['city_name']}")
            print(f"   Закрыто: {director_stats['cards']['completed']} из {director_stats['cards']['total']}")
            print(f"   Чистая сумма: {director_stats['cards']['net_sum']:.2f} ₽")
            print(f"   Доля компании: {director_stats['cards']['company_share']:.2f} ₽")
            if director_stats["masters"]:
                best = director_stats["masters"][0]
                print(f"   Топ мастер: {best['name']} ({best['count']} заявок / {best['conversion']}%)")
            else:
                print("   ⚠️ Нет закрытых заявок по мастерам")
            summary_lines = summarize_dashboard(director_stats, director.role)
            if summary_lines:
                print("\n   Текстовая сводка (бот):")
                for line in summary_lines:
                    if line:
                        print("   ", line)
        else:
            print("⚠️ Нет директора/owner для проверки")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def test_statistics_calculations():
    """Тест расчетов статистики"""
    print("\n" + "=" * 60)
    print("ТЕСТ: Расчеты статистики")
    print("=" * 60)
    
    session = get_session()
    try:
        # Получаем завершенные заявки
        completed_orders = session.query(Order).filter(
            Order.status == "completed"
        ).all()
        
        if not completed_orders:
            print("❌ Нет завершенных заявок для тестирования")
            return False
        
        print(f"✅ Найдено завершенных заявок: {len(completed_orders)}")
        
        # Проверяем расчеты
        total_sum = 0.0
        total_net_sum = 0.0
        completed_count = 0
        
        for order in completed_orders:
            order_sum = float(order.sum_amount or 0)
            sd_price = float(order.sd_price or 0)
            zpch_sum = float(order.zpch_sum or 0)
            net_amount = max(order_sum - sd_price - zpch_sum, 0)
            
            total_sum += order_sum
            total_net_sum += net_amount
            completed_count += 1
        
        avg_check = total_net_sum / completed_count if completed_count > 0 else 0.0
        
        print(f"\n📊 Результаты расчетов:")
        print(f"   Всего завершенных заявок: {completed_count}")
        print(f"   Общая сумма: {total_sum:.2f} ₽")
        print(f"   Чистая сумма: {total_net_sum:.2f} ₽")
        print(f"   Средний чек: {avg_check:.2f} ₽")
        
        # Проверяем записи в Stat
        stats = session.query(Stat).all()
        print(f"\n📈 Записей в таблице Stat: {len(stats)}")
        
        if stats:
            stat_total = sum(x.sum for x in stats)
            print(f"   Сумма в Stat: {stat_total:.2f} ₽")
            
            # Проверяем соответствие
            if abs(stat_total - total_net_sum) < 0.01:
                print("✅ Суммы совпадают")
            else:
                print(f"⚠️ Несоответствие: Stat={stat_total:.2f}, Orders={total_net_sum:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def test_statistics_by_date():
    """Тест статистики по датам"""
    print("\n" + "=" * 60)
    print("ТЕСТ: Статистика по датам")
    print("=" * 60)
    
    session = get_session()
    try:
        # Текущий месяц
        today = date.today()
        month_start = datetime.combine(today.replace(day=1), datetime.min.time())
        
        orders_this_month = session.query(Order).filter(
            Order.status == "completed",
            Order.created_at >= month_start
        ).all()
        
        print(f"📅 Текущий месяц ({today.strftime('%B %Y')}):")
        print(f"   Завершенных заявок: {len(orders_this_month)}")
        
        if orders_this_month:
            total_net = 0.0
            for order in orders_this_month:
                order_sum = float(order.sum_amount or 0)
                sd_price = float(order.sd_price or 0)
                zpch_sum = float(order.zpch_sum or 0)
                net_amount = max(order_sum - sd_price - zpch_sum, 0)
                total_net += net_amount
            
            avg = total_net / len(orders_this_month) if orders_this_month else 0
            print(f"   Чистая сумма: {total_net:.2f} ₽")
            print(f"   Средний чек: {avg:.2f} ₽")
        
        # Статистика по Stat
        stats_this_month = session.query(Stat).filter(
            Stat.recorded_at >= month_start
        ).all()
        
        print(f"\n📈 Записей в Stat за месяц: {len(stats_this_month)}")
        if stats_this_month:
            stat_total = sum(x.sum for x in stats_this_month)
            print(f"   Сумма: {stat_total:.2f} ₽")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def main():
    """Запуск всех тестов"""
    print("\n" + "=" * 60)
    print("ЗАПУСК ТЕСТОВ СТАТИСТИКИ")
    print("=" * 60 + "\n")
    
    results = []
    
    # Тест 1: Сервис статистики
    results.append(("Сервис статистики", test_statistics_service()))
    
    # Тест 2: Дашборд статистики (бот/веб)
    results.append(("Дашборд статистики", test_dashboard_statistics()))
    
    # Тест 3: Расчеты статистики
    results.append(("Расчеты статистики", test_statistics_calculations()))
    
    # Тест 4: Статистика по датам
    results.append(("Статистика по датам", test_statistics_by_date()))
    
    # Итоги
    print("\n" + "=" * 60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{name}: {status}")
    
    print(f"\nВсего тестов: {total}")
    print(f"Пройдено: {passed}")
    print(f"Провалено: {total - passed}")
    
    if passed == total:
        print("\n🎉 Все тесты пройдены успешно!")
    else:
        print(f"\n⚠️ {total - passed} тест(ов) провалено")


if __name__ == "__main__":
    main()

