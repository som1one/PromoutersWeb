"""Тест генерации Excel-таблицы статистики в формате «город + категории».

Скрипт может использовать данные из БД (если запущен с аргументом ``--db``)
или сгенерировать демонстрационный набор заявок. Результат совпадает с тем,
что отправляет бот по кнопке «Статистика».
"""
from __future__ import annotations

import os
import random
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import List

from services.statistics_service import (
    CATEGORY_ORDER,
    collect_city_stats,
    generate_city_stats_excel_from_stats,
)

try:
    from db import get_session
    from model import Order
except Exception:  # pragma: no cover
    get_session = None  # type: ignore
    Order = None  # type: ignore


class FakeOrder:
    """Упрощённый объект заявки для тестовой генерации."""

    def __init__(
        self,
        order_number: int,
        city: str,
        equip_type: str,
        sum_amount: float,
        sd_price: float,
        zpch_sum: float,
        is_warranty: bool = False,
        status: str = "completed",
        created_at: datetime | None = None,
    ) -> None:
        self.order_number = order_number
        self.city_rel = SimpleNamespace(name=city)
        self.equip_type = equip_type
        self.sum_amount = sum_amount
        self.sd_price = sd_price
        self.zpch_sum = zpch_sum
        self.is_warranty = is_warranty
        self.status = status
        self.created_at = created_at or datetime.now()


def generate_sample_orders(seed: int = 42) -> List[FakeOrder]:
    random.seed(seed)
    now = datetime.now()
    cities = ["Краснодар", "Москва"]

    orders: List[FakeOrder] = []
    order_number = 10_000

    for city in cities:
        for _ in range(50):
            equip_type = random.choice(CATEGORY_ORDER)
            sum_amount = random.uniform(5_000, 80_000)
            sd_price = random.uniform(0, 3_000)
            zpch_sum = random.uniform(0, sum_amount * 0.4)

            is_refused = random.random() < 0.08
            is_warranty = random.random() < 0.05

            if is_refused:
                sum_amount = 0.0
                sd_price = 0.0
                zpch_sum = 0.0

            orders.append(
                FakeOrder(
                    order_number=order_number,
                    city=city,
                    equip_type=equip_type,
                    sum_amount=round(sum_amount, 2),
                    sd_price=round(sd_price, 2),
                    zpch_sum=round(zpch_sum, 2),
                    is_warranty=is_warranty,
                    status="completed",
                    created_at=now - timedelta(days=random.randint(0, 60)),
                )
            )
            order_number += 1

    return orders


def load_orders_from_db() -> List:
    if not get_session or not Order:
        return []

    session = get_session()
    try:
        orders = (
            session.query(Order)  # type: ignore[attr-defined]
            .filter(Order.status == "completed")  # type: ignore[attr-defined]
            .all()
        )
        for order in orders:
            _ = getattr(order, "city_rel", None)
        return orders
    except Exception as exc:  # pragma: no cover
        print(f"⚠️  Не удалось загрузить заявки из БД: {exc}")
        return []
    finally:
        session.close()


def main(argv: List[str]) -> None:
    use_db = "--db" in argv

    if use_db:
        print("📥 Пробуем загрузить данные из БД...")
        orders = load_orders_from_db()
        if orders:
            print(f"✅ Получено {len(orders)} заявок из базы данных.")
        else:
            print("⚠️  Заявок не найдено, используем демо-набор.")
            orders = generate_sample_orders()
    else:
        orders = generate_sample_orders()

    stats = collect_city_stats(orders)
    if not stats:
        print("❌ Нет данных для отчёта (нужны заявки со статусом completed).")
        return

    output_path = generate_city_stats_excel_from_stats(stats)
    print(f"✅ Excel-файл создан: {output_path}")
    print("📝 Таблица соответствует формату продакшена.")

    for city, city_stat in stats.items():
        print(
            f"\n🏙 {city}: всего={city_stat['total']}, отказов={city_stat['refused']}, "
            f"гарантия={city_stat['warranty']}, оборот={city_stat['turnover']:.2f}, "
            f"средний чек={city_stat['avg_check']:.2f}, KPI={city_stat['kpi']:.2f}"
        )


if __name__ == "__main__":
    main(sys.argv[1:])


