from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, selectinload

from model import City, Order, User
from services.commission_service import get_master_pct
from handlers.utils import get_equip_type_name, get_status_name_ru

logger = logging.getLogger(__name__)


COMPLETED_STATUS = "completed"
CANCELLED_STATUS = "cancelled"
REFUSED_STATUSES = {"declined"}
ACTIVE_STATUSES = {
    "new",
    "assigned",
    "accepted",
    "on_place",
    "to_sd",
    "done_pending_sum",
    "done",
    "scheduled",
}

PERIOD_PRESETS = ("today", "week", "month", "quarter", "year", "last_30")


def get_period_bounds(preset: str = "month") -> Tuple[datetime, datetime]:
    """Вернёт границы периода для предустановленных значений."""
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    if preset == "today":
        return start, end
    if preset == "week":
        start = start - timedelta(days=6)
        return start, end
    if preset == "last_30":
        start = start - timedelta(days=29)
        return start, end
    if preset == "quarter":
        month = (now.month - 1) - (now.month - 1) % 3 + 1
        start = start.replace(month=month, day=1)
        return start, end
    if preset == "year":
        start = start.replace(month=1, day=1)
        return start, end

    # preset == "month" (по умолчанию)
    start = start.replace(day=1)
    return start, end


def _safe_net_amount(order: Order) -> float:
    order_sum = float(order.sum_amount or 0)
    sd_price = float(order.sd_price or 0)
    zpch_sum = float(order.zpch_sum or 0)
    return round(max(order_sum - sd_price - zpch_sum, 0.0), 2)


def _resolve_master_pct(order: Order, net_amount: float, masters_map: Dict[int, User]) -> float:
    # Гарантия: фиксированный процент 50% независимо от суммы/настроек
    if getattr(order, "is_warranty", False):
        return 50.0
    if order.assigned_to:
        master = masters_map.get(order.assigned_to)
        if master and master.master_percentage is not None:
            return float(master.master_percentage)
    try:
        return float(get_master_pct(order.equip_type, net_amount))
    except Exception:
        return 40.0


def _company_share(net_amount: float, pct: float) -> float:
    return round(max(net_amount - net_amount * (pct / 100.0), 0.0), 2)


def _city_name(session: Session, city_id: Optional[int]) -> str:
    if not city_id:
        return "Все города"
    city = session.query(City).filter_by(id=city_id).first()
    return city.name if city else f"Город #{city_id}"


def _format_money(value: float) -> str:
    try:
        return f"{value:,.0f}".replace(",", " ")
    except Exception:
        return f"{value:.0f}"


def summarize_dashboard(
    dashboard: Dict,
    role: str = "owner",
    *,
    max_equipment: int = 3,
    max_masters: int = 3,
) -> List[str]:
    """Генерирует человекочитаемое описание статистики (как в боте)."""
    cards = dashboard["cards"]
    meta = dashboard["meta"]
    date_from = meta["date_from"]
    date_to = meta["date_to"]
    period = f"{date_from.strftime('%d.%m')}–{date_to.strftime('%d.%m')}"

    lines = [f"📊 Статистика за {period}"]
    if role != "master":
        lines.append(f"🏙 {meta['city_name']}")

    lines.append(
        f"✅ Закрыто: {cards['completed']} / {cards['total']} ({cards['conversion']}%)"
    )
    lines.append(f"💰 Чистая касса: {_format_money(cards['net_sum'])} ₽")
    if role != "master":
        lines.append(f"🏦 Доля компании: {_format_money(cards['company_share'])} ₽")
    lines.append(f"📈 Средний чек: {_format_money(cards['avg_check'])} ₽")
    lines.append(f"🚀 В работе: {cards['in_progress']} · ❌ Отказов: {cards['refused']}")

    if cards["cash_pending_count"]:
        lines.append(
            f"💼 К сдаче: {cards['cash_pending_count']} / {_format_money(cards['cash_pending_sum'])} ₽"
        )

    if role == "master":
        equips = dashboard["equipment"][:max_equipment]
        if equips:
            lines.append("")
            lines.append("🛠 Техника:")
            for equip in equips:
                lines.append(
                    f"• {equip['name']}: {equip['count']} / {_format_money(equip['net_sum'])} ₽"
                )
    else:
        masters = dashboard["masters"][:max_masters]
        if masters:
            lines.append("")
            lines.append("👤 Топ мастеров:")
            for idx, master in enumerate(masters, 1):
                lines.append(
                    f"{idx}. {master['name']} — {master['count']} / {_format_money(master['net_sum'])} ₽"
                )

        daily = dashboard["daily"][-3:]
        if daily:
            lines.append("")
            lines.append("📆 Последние дни:")
            for day in daily:
                lines.append(
                    f"{day['date']}: {day['count']} / {_format_money(day['net_sum'])} ₽"
                )

    return lines


def calculate_dashboard_stats(
    session: Session,
    *,
    date_from: datetime,
    date_to: datetime,
    city_id: Optional[int] = None,
    city_name: Optional[str] = None,
    master_id: Optional[int] = None,
    equip_category: Optional[str] = None,  # "appliance", "digital", "other", None (все)
    include_warranty: bool = True,  # Включать гарантийные заявки
) -> Dict:
    """Собирает агрегированную статистику для веба и бота."""

    from model import Stat
    
    # Для статистики важно учитывать:
    # - Для закрытых заявок (completed) - дату закрытия из Stat.recorded_at
    # - Для остальных заявок - дату создания Order.created_at
    
    # Получаем записи Stat для определения дат закрытия заявок
    # Фильтруем по дате закрытия и городу/мастеру
    stat_query = session.query(Stat).filter(
        Stat.recorded_at >= date_from,
        Stat.recorded_at <= date_to,
    )
    if city_id:
        stat_query = stat_query.join(Order, Order.id == Stat.order_id).filter(Order.city_id == city_id)
    if master_id:
        stat_query = stat_query.filter(Stat.master_tg == master_id)
    
    # Получаем order_id из Stat для completed заявок, закрытых в периоде
    completed_order_ids = {s.order_id for s in stat_query.all()}
    
    # Получаем заявки, созданные в периоде
    query_created = (
        session.query(Order)
        .options(selectinload(Order.city_rel))
        .filter(Order.created_at >= date_from, Order.created_at <= date_to)
    )
    if city_id:
        query_created = query_created.filter(Order.city_id == city_id)
    if master_id:
        query_created = query_created.filter(Order.assigned_to == master_id)
    
    orders_created = query_created.all()
    
    # Получаем completed заявки, закрытые в периоде (через Stat)
    orders_completed = []
    if completed_order_ids:
        query_completed = (
            session.query(Order)
            .options(selectinload(Order.city_rel))
            .filter(Order.id.in_(completed_order_ids), Order.status == COMPLETED_STATUS)
        )
        if city_id:
            query_completed = query_completed.filter(Order.city_id == city_id)
        if master_id:
            query_completed = query_completed.filter(Order.assigned_to == master_id)
        orders_completed = query_completed.all()
    
    # Объединяем заявки, убирая дубликаты
    orders_dict = {o.id: o for o in orders_created}
    for o in orders_completed:
        orders_dict[o.id] = o
    
    orders = list(orders_dict.values())

    # Фильтры как на странице /stats (чтобы графики/карточки совпадали с таблицами)
    if equip_category:
        orders = [o for o in orders if get_equipment_category(getattr(o, "equip_type", None)) == equip_category]
    if not include_warranty:
        orders = [o for o in orders if not getattr(o, "is_warranty", False)]
    
    # Создаем словарь order_id -> Stat для быстрого доступа (для completed заявок)
    stats_by_order_id = {s.order_id: s for s in stat_query.all()}
    

    master_ids = {o.assigned_to for o in orders if o.assigned_to}
    masters_map: Dict[int, User] = {}
    if master_ids:
        masters_map = {
            m.tg_id: m for m in session.query(User).filter(User.tg_id.in_(master_ids)).all()
        }

    if city_name is None:
        city_name = _city_name(session, city_id)

    # "Отмена" не должна попадать в общую статистику
    orders = [o for o in orders if (o.status or "") != CANCELLED_STATUS]

    completed_orders = [o for o in orders if o.status == COMPLETED_STATUS]
    active_orders = [o for o in orders if o.status in ACTIVE_STATUSES]
    refused_orders = [o for o in orders if o.status in REFUSED_STATUSES]
    cash_pending_orders = [o for o in orders if o.status == "done_pending_sum"]

    gross_sum = sum(float(o.sum_amount or 0) for o in completed_orders)
    net_sum = 0.0
    master_share_total = 0.0

    masters_stats = defaultdict(
        lambda: {
            "count": 0,
            "total": 0.0,
            "gross": 0.0,
            "refused": 0,
            "active": 0,
        }
    )
    masters_conversions = defaultdict(lambda: {"total": 0, "closed": 0, "refused": 0})

    equipment_stats = defaultdict(lambda: {"count": 0, "net": 0.0, "refused": 0})
    source_counter = Counter()
    status_counter = Counter()
    city_breakdown = defaultdict(lambda: {"name": "Без города", "count": 0, "net": 0.0})
    daily_breakdown = defaultdict(lambda: {"completed": 0, "net": 0.0})

    for order in orders:
        status_counter[order.status or "unknown"] += 1
        source = (order.source or "Не указан").strip()
        source_counter[source] += 1

        city_label = order.city_rel.name if order.city_rel else "Без города"
        city_breakdown[order.city_id or 0]["name"] = city_label
        city_breakdown[order.city_id or 0]["count"] += 1

        master_key = order.assigned_to
        if master_key:
            masters_conversions[master_key]["total"] += 1
            if order.status == COMPLETED_STATUS:
                masters_conversions[master_key]["closed"] += 1
            if order.status in REFUSED_STATUSES:
                masters_conversions[master_key]["refused"] += 1
            if order.status in ACTIVE_STATUSES:
                masters_stats[master_key]["active"] += 1

        if order.status == COMPLETED_STATUS:
            net = _safe_net_amount(order)
            net_sum += net
            pct = _resolve_master_pct(order, net, masters_map)
            company_part = _company_share(net, pct)
            master_share_total += net - company_part

            city_breakdown[order.city_id or 0]["net"] += net

            equip_code = order.equip_type or "other"
            equipment_stats[equip_code]["count"] += 1
            equipment_stats[equip_code]["net"] += net

            if master_key:
                masters_stats[master_key]["count"] += 1
                masters_stats[master_key]["total"] += net
                masters_stats[master_key]["gross"] += float(order.sum_amount or 0)

            created_at = order.created_at or datetime.now()
            key_date = created_at.date()
            daily_breakdown[key_date]["completed"] += 1
            daily_breakdown[key_date]["net"] += net
        elif order.status in REFUSED_STATUSES:
            equip_code = order.equip_type or "other"
            equipment_stats[equip_code]["refused"] += 1
            if master_key:
                masters_stats[master_key]["refused"] += 1

    for order in cash_pending_orders:
        net = _safe_net_amount(order)
        pct = _resolve_master_pct(order, net, masters_map)
        order._company_share_value = _company_share(net, pct)

    cash_company_total = round(sum(getattr(o, "_company_share_value", 0.0) for o in cash_pending_orders), 2)

    period_days = max((date_to - date_from).days + 1, 1)
    conversion = round(
        (len(completed_orders) / len(orders) * 100) if orders else 0.0, 2
    )

    cards = {
        "completed": len(completed_orders),
        "total": len(orders),
        "in_progress": len(active_orders),
        "refused": len(refused_orders),
        "gross_sum": round(gross_sum, 2),
        "net_sum": round(net_sum, 2),
        "company_share": round(net_sum - master_share_total, 2),
        "avg_check": round(net_sum / len(completed_orders), 2) if completed_orders else 0.0,
        "conversion": conversion,
        "per_day": round(len(completed_orders) / period_days, 2),
        "cash_pending_sum": cash_company_total,
        "cash_pending_count": len(cash_pending_orders),
    }

    status_breakdown = [
        {
            "code": code,
            "name": get_status_name_ru(code),
            "count": status_counter.get(code, 0),
        }
        for code in [
            "new",
            "assigned",
            "accepted",
            "on_place",
            "to_sd",
            "done_pending_sum",
            "cancelled",
            "completed",
            "declined",
        ]
    ]

    sources = [
        {"name": name, "count": count}
        for name, count in source_counter.most_common()
    ]

    equipment = [
        {
            "code": code,
            "name": get_equip_type_name(code),
            "count": data["count"],
            "net_sum": round(data["net"], 2),
            "refused": data["refused"],
            "avg_check": round(data["net"] / data["count"], 2) if data["count"] else 0.0,
        }
        for code, data in sorted(
            equipment_stats.items(), key=lambda item: item[1]["net"], reverse=True
        )
    ]

    masters = []
    for master_tg, data in masters_stats.items():
        master_obj = masters_map.get(master_tg)
        name = (
            master_obj.full_name
            or master_obj.name
            or (f"ID {master_tg}" if master_tg else "Не назначен")
            if master_obj
            else (str(master_tg) if master_tg else "Не назначен")
        )
        totals = masters_conversions.get(master_tg, {"total": 0, "closed": 0, "refused": 0})
        conversion_rate = (
            round(totals["closed"] / totals["total"] * 100, 2)
            if totals["total"]
            else 0.0
        )
        masters.append(
            {
                "id": master_tg,
                "name": name,
                "count": data["count"],
                "net_sum": round(data["total"], 2),
                "avg_check": round(data["total"] / data["count"], 2) if data["count"] else 0.0,
                "conversion": conversion_rate,
                "refused": totals["refused"],
                "active": data["active"],
            }
        )

    masters.sort(key=lambda item: item["net_sum"], reverse=True)

    cities = [
        {
            "id": city_id_key,
            "name": info["name"],
            "count": info["count"],
            "net_sum": round(info["net"], 2),
        }
        for city_id_key, info in sorted(
            city_breakdown.items(), key=lambda item: item[1]["count"], reverse=True
        )
    ]

    daily_series = [
        {
            "date": day.strftime("%d.%m"),
            "count": data["completed"],
            "net_sum": round(data["net"], 2),
        }
        for day, data in sorted(daily_breakdown.items())
    ]

    return {
        "meta": {
            "date_from": date_from,
            "date_to": date_to,
            "period_days": period_days,
            "city_id": city_id,
            "city_name": city_name,
            "master_id": master_id,
        },
        "cards": cards,
        "status_breakdown": status_breakdown,
        "sources": sources,
        "equipment": equipment,
        "masters": masters,
        "cities": cities,
        "daily": daily_series,
        "cash_pending": {
            "count": cards["cash_pending_count"],
            "company_sum": cards["cash_pending_sum"],
        },
    }


def get_equipment_category(equip_type: Optional[str]) -> str:
    """Определяет категорию техники для группировки"""
    if not equip_type:
        return "other"
    
    # Бытовая техника
    if equip_type in ("appliance", "washing_machine", "refrigerator", "oven", "dishwasher", "microwave"):
        return "appliance"
    
    # Цифровая техника (телевизоры, компьютеры)
    if equip_type in ("pc", "laptop", "monitor", "phones", "tv", "tablet"):
        return "digital"
    
    # По умолчанию - другое
    return "other"


def calculate_detailed_stats(
    session: Session,
    *,
    date_from: datetime,
    date_to: datetime,
    city_id: Optional[int] = None,
    city_name: Optional[str] = None,
    master_id: Optional[int] = None,
    equip_category: Optional[str] = None,  # "appliance", "digital", "other", None (все)
    include_warranty: bool = True,  # Включать гарантийные заявки
) -> Dict:
    """
    Детальная статистика с разбивкой по датам, типам техники, гарантиям.
    Возвращает детальную информацию для анализа.
    """
    from model import Stat
    
    # Получаем записи Stat для определения дат закрытия заявок
    stat_query = session.query(Stat).filter(
        Stat.recorded_at >= date_from,
        Stat.recorded_at <= date_to,
    )
    if city_id:
        stat_query = stat_query.join(Order, Order.id == Stat.order_id).filter(Order.city_id == city_id)
    if master_id:
        stat_query = stat_query.filter(Stat.master_tg == master_id)
    
    completed_order_ids = {s.order_id for s in stat_query.all()}
    
    # Получаем заявки, созданные в периоде
    query_created = (
        session.query(Order)
        .options(selectinload(Order.city_rel))
        .filter(Order.created_at >= date_from, Order.created_at <= date_to)
    )
    if city_id:
        query_created = query_created.filter(Order.city_id == city_id)
    if master_id:
        query_created = query_created.filter(Order.assigned_to == master_id)
    
    orders_created = query_created.all()
    
    # Получаем completed заявки, закрытые в периоде
    orders_completed = []
    if completed_order_ids:
        query_completed = (
            session.query(Order)
            .options(selectinload(Order.city_rel))
            .filter(Order.id.in_(completed_order_ids), Order.status == COMPLETED_STATUS)
        )
        if city_id:
            query_completed = query_completed.filter(Order.city_id == city_id)
        if master_id:
            query_completed = query_completed.filter(Order.assigned_to == master_id)
        orders_completed = query_completed.all()
    
    # Объединяем заявки
    orders_dict = {o.id: o for o in orders_created}
    for o in orders_completed:
        orders_dict[o.id] = o
    
    all_orders = list(orders_dict.values())
    
    # Фильтруем по категории техники
    if equip_category:
        all_orders = [o for o in all_orders if get_equipment_category(o.equip_type) == equip_category]
    
    # Фильтруем по гарантийным заявкам
    if not include_warranty:
        all_orders = [o for o in all_orders if not getattr(o, "is_warranty", False)]
    
    stats_by_order_id = {s.order_id: s for s in stat_query.all()}
    
    # Группировка по датам
    daily_stats = defaultdict(lambda: {
        "date": None,
        "orders": [],
        "completed_count": 0,
        "active_count": 0,
        "refused_count": 0,
        "total_gross": 0.0,
        "total_net": 0.0,
        "company_income": 0.0,
        "warranty_count": 0,
        "equipment_breakdown": defaultdict(lambda: {"count": 0, "net": 0.0}),
    })
    
    # Группировка по городам
    city_stats = defaultdict(lambda: {
        "name": "",
        "orders": [],
        "completed_count": 0,
        "total_gross": 0.0,
        "total_net": 0.0,
        "company_income": 0.0,
        "avg_check": 0.0,
    })
    
    # Группировка по категориям техники
    equipment_category_stats = defaultdict(lambda: {
        "name": "",
        "orders": [],
        "completed_count": 0,
        "total_gross": 0.0,
        "total_net": 0.0,
        "company_income": 0.0,
        "avg_check": 0.0,
    })
    
    master_ids = {o.assigned_to for o in all_orders if o.assigned_to}
    masters_map: Dict[int, User] = {}
    if master_ids:
        masters_map = {
            m.tg_id: m for m in session.query(User).filter(User.tg_id.in_(master_ids)).all()
        }
    
    for order in all_orders:
        # Определяем дату для группировки
        order_date = None
        try:
            if order.status == COMPLETED_STATUS and order.id in stats_by_order_id:
                stat = stats_by_order_id[order.id]
                if stat and stat.recorded_at:
                    # Если recorded_at - timezone-aware, преобразуем в naive
                    if hasattr(stat.recorded_at, 'tzinfo') and stat.recorded_at.tzinfo is not None:
                        order_date = stat.recorded_at.replace(tzinfo=None).date()
                    else:
                        order_date = stat.recorded_at.date()
            elif order.created_at:
                # Если created_at - timezone-aware, преобразуем в naive
                if hasattr(order.created_at, 'tzinfo') and order.created_at.tzinfo is not None:
                    order_date = order.created_at.replace(tzinfo=None).date()
                else:
                    order_date = order.created_at.date()
        except (AttributeError, TypeError) as e:
            logger.warning(f"Ошибка при определении даты для заявки {order.id}: {e}")
            continue
        
        if not order_date:
            continue
        
        # Категория техники
        equip_cat = get_equipment_category(order.equip_type)
        equip_cat_name = {
            "appliance": "Бытовая техника",
            "digital": "Цифровая техника",
            "other": "Другое"
        }.get(equip_cat, "Другое")
        
        # Статистика по дате
        daily = daily_stats[order_date]
        daily["date"] = order_date
        daily["orders"].append(order.id)
        
        if order.status == COMPLETED_STATUS:
            daily["completed_count"] += 1
            net_amount = _safe_net_amount(order)
            gross = float(order.sum_amount or 0)
            daily["total_gross"] += gross
            daily["total_net"] += net_amount
            
            master_pct = _resolve_master_pct(order, net_amount, masters_map)
            company_share = _company_share(net_amount, master_pct)
            daily["company_income"] += company_share
            
            # По категориям техники
            daily["equipment_breakdown"][equip_cat]["count"] += 1
            daily["equipment_breakdown"][equip_cat]["net"] += net_amount
        elif order.status in ACTIVE_STATUSES:
            daily["active_count"] += 1
        elif order.status in REFUSED_STATUSES:
            daily["refused_count"] += 1
        
        if getattr(order, "is_warranty", False):
            daily["warranty_count"] += 1
        
        # Статистика по городу
        city_key = order.city_id or 0
        city = city_stats[city_key]
        if not city["name"]:
            city["name"] = order.city_rel.name if order.city_rel else "Без города"
        city["orders"].append(order.id)
        
        if order.status == COMPLETED_STATUS:
            city["completed_count"] += 1
            net_amount = _safe_net_amount(order)
            gross = float(order.sum_amount or 0)
            city["total_gross"] += gross
            city["total_net"] += net_amount
            
            master_pct = _resolve_master_pct(order, net_amount, masters_map)
            company_share = _company_share(net_amount, master_pct)
            city["company_income"] += company_share
        
        # Статистика по категориям техники
        equip_stat = equipment_category_stats[equip_cat]
        equip_stat["name"] = equip_cat_name
        equip_stat["orders"].append(order.id)
        
        if order.status == COMPLETED_STATUS:
            equip_stat["completed_count"] += 1
            net_amount = _safe_net_amount(order)
            gross = float(order.sum_amount or 0)
            equip_stat["total_gross"] += gross
            equip_stat["total_net"] += net_amount
            
            master_pct = _resolve_master_pct(order, net_amount, masters_map)
            company_share = _company_share(net_amount, master_pct)
            equip_stat["company_income"] += company_share
    
    # Вычисляем средние чеки
    for city_key, city in city_stats.items():
        if city["completed_count"] > 0:
            city["avg_check"] = round(city["total_net"] / city["completed_count"], 2)
    
    for equip_cat, equip_stat in equipment_category_stats.items():
        if equip_stat["completed_count"] > 0:
            equip_stat["avg_check"] = round(equip_stat["total_net"] / equip_stat["completed_count"], 2)
    
    # Формируем итоговые данные
    daily_list = []
    for date_key in sorted(daily_stats.keys()):
        daily = daily_stats[date_key]
        completed = daily["completed_count"]
        daily["avg_check"] = round(daily["total_net"] / completed, 2) if completed > 0 else 0.0
        # Преобразуем defaultdict в обычный dict для сериализации
        daily["equipment_breakdown"] = {
            k: {"count": v["count"], "net": round(v["net"], 2)} 
            for k, v in daily["equipment_breakdown"].items()
        }
        daily_list.append(daily)
    
    return {
        "daily_breakdown": daily_list,
        "city_breakdown": dict(city_stats),
        "equipment_category_breakdown": dict(equipment_category_stats),
        "total_orders": len(all_orders),
        "completed_orders": len([o for o in all_orders if o.status == COMPLETED_STATUS]),
        "active_orders": len([o for o in all_orders if o.status in ACTIVE_STATUSES]),
        "refused_orders": len([o for o in all_orders if o.status in REFUSED_STATUSES]),
        "warranty_orders": len([o for o in all_orders if getattr(o, "is_warranty", False)]),
    }


def calculate_category_table_stats(
    session: Session,
    *,
    date_from: datetime,
    date_to: datetime,
    city_id: Optional[int] = None,
    master_id: Optional[int] = None,
    equip_category: Optional[str] = None,
    include_warranty: bool = True,
) -> Dict:
    """
    Генерирует статистику в формате таблицы по категориям оборудования/мастерам.
    Возвращает структурированные данные для отображения в таблице как в Excel.
    """
    from model import Stat
    
    # Получаем записи Stat для определения дат закрытия заявок
    stat_query = session.query(Stat).filter(
        Stat.recorded_at >= date_from,
        Stat.recorded_at <= date_to,
    )
    if city_id:
        stat_query = stat_query.join(Order, Order.id == Stat.order_id).filter(Order.city_id == city_id)
    if master_id:
        stat_query = stat_query.filter(Stat.master_tg == master_id)
    
    completed_order_ids = {s.order_id for s in stat_query.all()}
    
    # Получаем заявки, созданные в периоде
    query_created = (
        session.query(Order)
        .options(selectinload(Order.city_rel))
        .filter(Order.created_at >= date_from, Order.created_at <= date_to)
    )
    if city_id:
        query_created = query_created.filter(Order.city_id == city_id)
    if master_id:
        query_created = query_created.filter(Order.assigned_to == master_id)
    
    orders_created = query_created.all()
    
    # Получаем completed заявки, закрытые в периоде
    orders_completed = []
    if completed_order_ids:
        query_completed = (
            session.query(Order)
            .options(selectinload(Order.city_rel))
            .filter(Order.id.in_(completed_order_ids), Order.status == COMPLETED_STATUS)
        )
        if city_id:
            query_completed = query_completed.filter(Order.city_id == city_id)
        if master_id:
            query_completed = query_completed.filter(Order.assigned_to == master_id)
        orders_completed = query_completed.all()
    
    # Объединяем заявки
    orders_dict = {o.id: o for o in orders_created}
    for o in orders_completed:
        orders_dict[o.id] = o
    
    all_orders = list(orders_dict.values())
    
    # Фильтры
    if equip_category:
        all_orders = [o for o in all_orders if get_equipment_category(o.equip_type) == equip_category]
    if not include_warranty:
        all_orders = [o for o in all_orders if not getattr(o, "is_warranty", False)]
    
    # Исключаем отменённые заявки
    all_orders = [o for o in all_orders if (o.status or "") != CANCELLED_STATUS]
    
    stats_by_order_id = {s.order_id: s for s in stat_query.all()}
    
    # Получаем маппинг мастеров
    master_ids = {o.assigned_to for o in all_orders if o.assigned_to}
    masters_map: Dict[int, User] = {}
    if master_ids:
        masters_map = {
            m.tg_id: m for m in session.query(User).filter(User.tg_id.in_(master_ids)).all()
        }
    
    # Группируем по мастерам и категориям оборудования
    # Структура: {master_id: {category: [orders]}}
    master_categories = defaultdict(lambda: defaultdict(list))
    
    for order in all_orders:
        master_key = order.assigned_to if order.assigned_to else None
        category = get_equipment_category(order.equip_type)
        master_categories[master_key][category].append(order)
    
    # Функция для получения имени категории с типом техники
    def get_category_display_name(equip_type: Optional[str], category: str) -> str:
        if category == "digital":
            # Для цифровой техники показываем конкретный тип
            type_names = {
                "tv": "ТВ",
                "pc": "ПК",
                "laptop": "ПК",
                "monitor": "ПК",
                "phones": "ПК",
                "tablet": "ПК",
            }
            return type_names.get(equip_type or "", "Цифровая техника")
        elif category == "appliance":
            return "Бытовая"
        else:
            return "Другое"
    
    # Формируем строки таблицы
    table_rows = []
    totals = {
        "total": 0,
        "refused": 0,
        "warranty": 0,
        "turnover": 0.0,
        "master_salary": 0.0,
        "company_share": 0.0,
    }
    
    # Сортируем мастеров (None в конец)
    sorted_masters = sorted(master_categories.keys(), key=lambda x: (x is None, x or 0))
    
    for master_id_key in sorted_masters:
        master = masters_map.get(master_id_key) if master_id_key else None
        master_name = (master.full_name or master.name or f"Мастер #{master_id_key}") if master else "Не назначен"
        
        categories_dict = master_categories[master_id_key]
        
        # Группируем категории с одинаковым отображаемым именем
        category_groups = defaultdict(list)
        for category, orders in categories_dict.items():
            if orders:
                # Группируем по отображаемому имени (ТВ/ПК отдельно)
                for order in orders:
                    display_name = get_category_display_name(order.equip_type, category)
                    category_groups[display_name].append(order)
        
        # Сортируем категории: Другое, ТВ, ПК, Бытовая
        category_order = {"Другое": 0, "ТВ": 1, "ПК": 2, "Бытовая": 3}
        sorted_categories = sorted(category_groups.keys(), key=lambda x: category_order.get(x, 99))
        
        for category_display in sorted_categories:
            orders_in_category = category_groups[category_display]
            
            # Считаем статистику по категории
            category_total = len(orders_in_category)
            category_refused = len([o for o in orders_in_category if o.status in REFUSED_STATUSES])
            category_warranty = len([o for o in orders_in_category if getattr(o, "is_warranty", False)])
            
            category_turnover = sum(float(o.sum_amount or 0) for o in orders_in_category)
            category_net = sum(_safe_net_amount(o) for o in orders_in_category)
            category_avg_check = category_turnover / category_total if category_total > 0 else 0.0
            
            # Считаем ЗП мастеров и долю компании
            category_master_salary = 0.0
            category_company_share = 0.0
            
            for order in orders_in_category:
                net_amount = _safe_net_amount(order)
                if order.status == COMPLETED_STATUS:
                    master_pct = _resolve_master_pct(order, net_amount, masters_map)
                    master_share = net_amount * (master_pct / 100.0)
                    company_share_val = _company_share(net_amount, master_pct)
                    category_master_salary += master_share
                    category_company_share += company_share_val
            
            # Строка с итогом категории
            category_row = {
                "type": "category_total",
                "label": category_display,
                "master_name": master_name,
                "total": category_total,
                "refused": category_refused,
                "warranty": category_warranty,
                "turnover": round(category_turnover, 2),
                "avg_check": round(category_avg_check, 2),
                "master_salary": round(category_master_salary, 2),
                "company_share": round(category_company_share, 2),
            }
            table_rows.append(category_row)
            
            # Подстроки с отдельными заявками (только для completed)
            completed_orders_in_category = [o for o in orders_in_category if o.status == COMPLETED_STATUS]
            for order in sorted(completed_orders_in_category, key=lambda x: x.order_number or 0):
                net_amount = _safe_net_amount(order)
                master_pct = _resolve_master_pct(order, net_amount, masters_map)
                master_share = net_amount * (master_pct / 100.0)
                company_share_val = _company_share(net_amount, master_pct)
                
                order_row = {
                    "type": "order",
                    "label": f"заявка номер {order.order_number or order.id}",
                    "master_name": "",
                    "total": 1,
                    "refused": 0,
                    "warranty": 1 if getattr(order, "is_warranty", False) else 0,
                    "turnover": round(float(order.sum_amount or 0), 2),
                    "avg_check": round(float(order.sum_amount or 0), 2),
                    "master_salary": round(master_share, 2),
                    "company_share": round(company_share_val, 2),
                    "order_id": order.id,
                }
                table_rows.append(order_row)
            
            # Обновляем общие итоги
            totals["total"] += category_total
            totals["refused"] += category_refused
            totals["warranty"] += category_warranty
            totals["turnover"] += category_turnover
            totals["master_salary"] += category_master_salary
            totals["company_share"] += category_company_share
    
    # Итоговая строка
    totals_avg_check = totals["turnover"] / totals["total"] if totals["total"] > 0 else 0.0
    
    return {
        "rows": table_rows,
        "totals": {
            "turnover": round(totals["turnover"], 2),
            "avg_check": round(totals_avg_check, 2),
            "master_salary": round(totals["master_salary"], 2),
            "company_share": round(totals["company_share"], 2),
        },
    }


def calculate_cash_income(
    session: Session,
    *,
    date_from: datetime,
    date_to: datetime,
    city_id: Optional[int] = None,
) -> Dict:
    """
    Рассчитывает приход денег в компанию (доход компании) по городам и периодам.
    Это деньги, которые остаются компании после выплаты доли мастерам.
    """
    from model import Stat
    
    # Получаем только закрытые заявки (completed) через Stat
    stat_query = session.query(Stat).filter(
        Stat.recorded_at >= date_from,
        Stat.recorded_at <= date_to,
    )
    
    if city_id:
        stat_query = stat_query.join(Order, Order.id == Stat.order_id).filter(Order.city_id == city_id)
    
    stats = stat_query.all()
    order_ids = {s.order_id for s in stats}
    
    if not order_ids:
        return {
            "total_income": 0.0,
            "by_city": {},
            "by_date": [],
            "total_orders": 0,
        }
    
    # Получаем заявки
    orders_query = (
        session.query(Order)
        .options(selectinload(Order.city_rel))
        .filter(Order.id.in_(order_ids), Order.status == COMPLETED_STATUS)
    )
    
    if city_id:
        orders_query = orders_query.filter(Order.city_id == city_id)
    
    orders = orders_query.all()
    
    master_ids = {o.assigned_to for o in orders if o.assigned_to}
    masters_map: Dict[int, User] = {}
    if master_ids:
        masters_map = {
            m.tg_id: m for m in session.query(User).filter(User.tg_id.in_(master_ids)).all()
        }
    
    stats_by_order_id = {s.order_id: s for s in stats}
    
    # Группировка по городам
    city_income = defaultdict(lambda: {
        "name": "",
        "income": 0.0,
        "orders_count": 0,
        "total_net": 0.0,
    })
    
    # Группировка по датам
    daily_income = defaultdict(lambda: {
        "date": None,
        "income": 0.0,
        "orders_count": 0,
    })
    
    total_income = 0.0
    
    for order in orders:
        net_amount = _safe_net_amount(order)
        master_pct = _resolve_master_pct(order, net_amount, masters_map)
        company_share = _company_share(net_amount, master_pct)
        
        total_income += company_share
        
        # По городу
        city_key = order.city_id or 0
        city = city_income[city_key]
        if not city["name"]:
            city["name"] = order.city_rel.name if order.city_rel else "Без города"
        city["income"] += company_share
        city["orders_count"] += 1
        city["total_net"] += net_amount
        
        # По дате
        if order.id in stats_by_order_id:
            stat = stats_by_order_id[order.id]
            if stat and stat.recorded_at:
                try:
                    # Если recorded_at - timezone-aware, преобразуем в naive
                    if hasattr(stat.recorded_at, 'tzinfo') and stat.recorded_at.tzinfo is not None:
                        date_key = stat.recorded_at.replace(tzinfo=None).date()
                    else:
                        date_key = stat.recorded_at.date()
                    daily = daily_income[date_key]
                    daily["date"] = date_key
                    daily["income"] += company_share
                    daily["orders_count"] += 1
                except (AttributeError, TypeError) as e:
                    logger.warning(f"Ошибка при определении даты для заявки {order.id} в cash_income: {e}")
    
    # Формируем итоговые данные
    city_list = []
    for city_key in sorted(city_income.keys()):
        city = city_income[city_key]
        city["avg_check"] = round(city["total_net"] / city["orders_count"], 2) if city["orders_count"] > 0 else 0.0
        city_list.append(city)
    
    daily_list = []
    for date_key in sorted(daily_income.keys()):
        daily = daily_income[date_key]
        daily_list.append(daily)
    
    return {
        "total_income": round(total_income, 2),
        "by_city": city_list,
        "by_date": daily_list,
        "total_orders": len(orders),
    }


