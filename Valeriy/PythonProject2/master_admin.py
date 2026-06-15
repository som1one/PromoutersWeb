"""
Веб-админка для мастеров.
Лаконичный интерфейс для просмотра заявок, СД и кассы.
"""
import os
from datetime import datetime, date
from typing import Optional
from fastapi import FastAPI, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from db import get_session
from model import User, City, Order
from handlers.utils import get_equip_type_name, get_status_name_ru
from services.commission_service import get_master_pct
from sqlalchemy import func

app = FastAPI(title="Master Admin", version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("MASTER_SECRET_KEY", "master-secret-key"))

# Шаблоны
templates = Jinja2Templates(directory="templates")

# Создаём папку для шаблонов если её нет
os.makedirs("templates", exist_ok=True)


# Функция проверки прав доступа (master или director)
def check_master_or_director_access(session, user_tg_id: int) -> bool:
    """Проверяет, является ли пользователь master или director"""
    user = session.query(User).filter_by(tg_id=user_tg_id).first()
    if not user:
        return False
    return user.role in ["master", "director"]

def check_master_access(session, user_tg_id: int) -> bool:
    """Проверяет, является ли пользователь master"""
    user = session.query(User).filter_by(tg_id=user_tg_id).first()
    if not user:
        return False
    return user.role == "master"

def check_director_access(session, user_tg_id: int) -> bool:
    """Проверяет, является ли пользователь director"""
    user = session.query(User).filter_by(tg_id=user_tg_id).first()
    if not user:
        return False
    return user.role == "director"


def get_current_user_id(request: Request) -> Optional[int]:
    """Получить ID текущего пользователя из сессии/запроса"""
    user_id = request.query_params.get("user_id")
    if user_id:
        try:
            user_id_int = int(user_id)
            try:
                request.session["user_tg_id"] = user_id_int
            except Exception:
                pass
            return user_id_int
        except ValueError:
            return None
    return request.session.get("user_tg_id")


# Базовый шаблон для мастера
MASTER_BASE_TEMPLATE = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>{{ page_title or 'Панель мастера' }}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f8fafc;
      color: #1e293b;
      line-height: 1.6;
    }
    .header {
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      color: white;
      padding: 20px 0;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .header-content {
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .header-title {
      font-size: 24px;
      font-weight: 600;
    }
    .header-user {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .header-user-name {
      font-size: 14px;
    }
    .logout-btn {
      background: rgba(255,255,255,0.2);
      border: 1px solid rgba(255,255,255,0.3);
      color: white;
      padding: 6px 12px;
      border-radius: 6px;
      text-decoration: none;
      font-size: 13px;
      transition: all 0.2s;
    }
    .logout-btn:hover {
      background: rgba(255,255,255,0.3);
    }
    .nav {
      background: white;
      border-bottom: 1px solid #e2e8f0;
      padding: 0;
    }
    .nav-content {
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 20px;
      display: flex;
      gap: 8px;
    }
    .nav-link {
      padding: 16px 20px;
      text-decoration: none;
      color: #64748b;
      font-size: 14px;
      font-weight: 500;
      border-bottom: 2px solid transparent;
      transition: all 0.2s;
    }
    .nav-link:hover {
      color: #10b981;
    }
    .nav-link.active {
      color: #10b981;
      border-bottom-color: #10b981;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px 20px;
    }
    .card {
      background: white;
      border-radius: 12px;
      padding: 24px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      margin-bottom: 20px;
    }
    .card-title {
      font-size: 18px;
      font-weight: 600;
      margin-bottom: 16px;
      color: #1e293b;
    }
    .stat-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .stat-card {
      background: white;
      border-radius: 12px;
      padding: 20px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .stat-value {
      font-size: 32px;
      font-weight: 700;
      color: #10b981;
      margin-bottom: 4px;
    }
    .stat-label {
      font-size: 13px;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th, td {
      padding: 12px;
      text-align: left;
      border-bottom: 1px solid #e2e8f0;
    }
    th {
      font-size: 12px;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-weight: 600;
    }
    tbody tr:hover {
      background: #f8fafc;
    }
    .btn {
      display: inline-block;
      padding: 10px 20px;
      background: #10b981;
      color: white;
      border: none;
      border-radius: 8px;
      text-decoration: none;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
    }
    .btn:hover {
      background: #059669;
      transform: translateY(-1px);
    }
    .btn-secondary {
      background: #64748b;
    }
    .btn-secondary:hover {
      background: #475569;
    }
    .status-badge {
      display: inline-block;
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
    }
    .status-new { background: #dbeafe; color: #1e40af; }
    .status-accepted { background: #d1fae5; color: #065f46; }
    .status-on_place { background: #fef3c7; color: #92400e; }
    .status-to_sd { background: #e0e7ff; color: #3730a3; }
    .status-done_pending_sum { background: #fce7f3; color: #9f1239; }
    .status-completed { background: #d1fae5; color: #065f46; }
    .empty-state {
      text-align: center;
      padding: 60px 20px;
      color: #64748b;
    }
    .empty-state-icon {
      font-size: 48px;
      margin-bottom: 16px;
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="header-content">
      <div class="header-title">{% if user_role == 'director' %}👔 Панель директора{% else %}🔧 Панель мастера{% endif %}</div>
      <div class="header-user">
        {% if user %}
          <span class="header-user-name">{{ user.full_name or user.name or user.tg_id }}</span>
        {% endif %}
        <a href="/logout" class="logout-btn">Выйти</a>
      </div>
    </div>
  </div>
  
  <nav class="nav">
    <div class="nav-content">
      <a href="/" class="nav-link {{ 'active' if active_page == 'home' else '' }}">🏠 Главная</a>
      {% if user_role == 'director' %}
        <a href="/branch-orders" class="nav-link {{ 'active' if active_page == 'branch_orders' else '' }}">📋 Заявки филиала</a>
        <a href="/branch-sd" class="nav-link {{ 'active' if active_page == 'branch_sd' else '' }}">📦 СД филиала</a>
        <a href="/branch-cash" class="nav-link {{ 'active' if active_page == 'branch_cash' else '' }}">💰 Касса филиала</a>
        <a href="/branch-masters" class="nav-link {{ 'active' if active_page == 'branch_masters' else '' }}">👥 Мастера</a>
        <a href="/branch-stats" class="nav-link {{ 'active' if active_page == 'branch_stats' else '' }}">📊 Статистика</a>
      {% else %}
        <a href="/orders" class="nav-link {{ 'active' if active_page == 'orders' else '' }}">📋 Мои заявки</a>
        <a href="/sd" class="nav-link {{ 'active' if active_page == 'sd' else '' }}">📦 СД</a>
        <a href="/cash" class="nav-link {{ 'active' if active_page == 'cash' else '' }}">💰 Касса</a>
      {% endif %}
    </div>
  </nav>
  
  <div class="container">
    {% block content %}{% endblock %}
  </div>
</body>
</html>
"""

# Сохраняем базовый шаблон
with open("templates/master_base.html", "w", encoding="utf-8") as f:
    f.write(MASTER_BASE_TEMPLATE)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница входа"""
    return templates.TemplateResponse("master_login.html", {
        "request": request,
        "page_title": "Вход",
    })


@app.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request):
    """Обработка входа по VK ID"""
    form = await request.form()
    vk_id_str = (form.get("vk_id") or "").strip()
    
    if not vk_id_str:
        return templates.TemplateResponse("master_login.html", {
            "request": request,
            "page_title": "Вход",
            "error": "Введите VK ID",
        })
    
    try:
        vk_id = int(vk_id_str)
    except ValueError:
        return templates.TemplateResponse("master_login.html", {
            "request": request,
            "page_title": "Вход",
            "error": "Некорректный VK ID",
        })
    
    session = get_session()
    try:
        user = session.query(User).filter_by(tg_id=vk_id).first()
        if not user:
            return templates.TemplateResponse("master_login.html", {
                "request": request,
                "page_title": "Вход",
                "error": "Пользователь не найден",
            })
        
        if user.role not in ["master", "director"]:
            return templates.TemplateResponse("master_login.html", {
                "request": request,
                "page_title": "Вход",
                "error": "Доступ запрещён. Только для мастеров и директоров.",
            })
        
        request.session["user_tg_id"] = vk_id
        return RedirectResponse("/", status_code=303)
    finally:
        session.close()


@app.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    """Выход из системы"""
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def master_home(request: Request):
    """Главная страница мастера или директора"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id:
            return RedirectResponse("/login", status_code=303)
        
        if not check_master_or_director_access(session, user_id):
            return RedirectResponse("/login?error=access_denied", status_code=303)
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        user_role = user.role if user else None
        
        # Если директор - показываем статистику филиала
        if user_role == "director":
            city_id = user.city_id if user else None
            
            # Статистика филиала
            today = date.today()
            branch_orders_query = session.query(Order)
            if city_id:
                branch_orders_query = branch_orders_query.filter(Order.city_id == city_id)
            
            today_orders = branch_orders_query.filter(
                func.date(Order.created_at) == today
            ).count()
            
            active_orders = branch_orders_query.filter(
                Order.status.in_(["accepted", "on_place", "to_sd"])
            ).count()
            
            pending_cash = branch_orders_query.filter(
                Order.status == "done_pending_sum"
            ).count()
            
            completed_count = branch_orders_query.filter(
                Order.status == "completed",
                Order.is_warranty.is_(False)
            ).count()
            
            # Последние заявки филиала
            recent_orders = branch_orders_query.order_by(Order.created_at.desc()).limit(10).all()
            
            # Мастера филиала
            branch_masters = session.query(User).filter_by(role="master")
            if city_id:
                branch_masters = branch_masters.filter_by(city_id=city_id)
            branch_masters = branch_masters.all()
            
            return templates.TemplateResponse("director_home.html", {
                "request": request,
                "page_title": "Главная",
                "active_page": "home",
                "user": user,
                "user_role": user_role,
                "city": user.city_rel if user and user.city_rel else None,
                "today_orders": today_orders,
                "active_orders": active_orders,
                "pending_cash": pending_cash,
                "completed_count": completed_count,
                "recent_orders": recent_orders,
                "branch_masters": branch_masters,
                "get_equip_type_name": get_equip_type_name,
                "get_status_name_ru": get_status_name_ru,
            })
        
        # Если мастер - показываем статистику мастера
        master = user
        
        # Статистика
        today = date.today()
        today_orders = session.query(Order).filter(
            Order.assigned_to == user_id,
            func.date(Order.created_at) == today
        ).count()
        
        active_orders = session.query(Order).filter(
            Order.assigned_to == user_id,
            Order.status.in_(["accepted", "on_place", "to_sd"])
        ).count()
        
        pending_cash = session.query(Order).filter(
            Order.assigned_to == user_id,
            Order.status == "done_pending_sum"
        ).count()
        
        completed_count = session.query(Order).filter(
            Order.assigned_to == user_id,
            Order.status == "completed",
            Order.is_warranty.is_(False)
        ).count()
        
        # Последние заявки
        recent_orders = session.query(Order).filter(
            Order.assigned_to == user_id
        ).order_by(Order.created_at.desc()).limit(5).all()
        
        return templates.TemplateResponse("master_home.html", {
            "request": request,
            "page_title": "Главная",
            "active_page": "home",
            "master": master,
            "user_role": "master",
            "today_orders": today_orders,
            "active_orders": active_orders,
            "pending_cash": pending_cash,
            "completed_count": completed_count,
            "recent_orders": recent_orders,
            "get_equip_type_name": get_equip_type_name,
            "get_status_name_ru": get_status_name_ru,
            "user_role": "master",
        })
    finally:
        session.close()


# ===== Функционал директора =====

@app.get("/branch-orders", response_class=HTMLResponse)
async def director_branch_orders(
    request: Request,
    status: Optional[str] = Query(None),
    master_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """Заявки филиала для директора"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_director_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        city_id = user.city_id if user else None
        
        # Заявки филиала
        query = session.query(Order)
        if city_id:
            query = query.filter(Order.city_id == city_id)
        
        if status:
            query = query.filter(Order.status == status)
        if master_id:
            query = query.filter(Order.assigned_to == master_id)
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
                query = query.filter(func.date(Order.created_at) >= date_from_obj)
            except ValueError:
                pass
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
                date_to_obj = datetime.combine(date_to_obj, datetime.max.time())
                query = query.filter(Order.created_at <= date_to_obj)
            except ValueError:
                pass
        
        orders = query.order_by(Order.created_at.desc()).limit(100).all()
        
        # Мастера филиала
        branch_masters = session.query(User).filter_by(role="master")
        if city_id:
            branch_masters = branch_masters.filter_by(city_id=city_id)
        branch_masters = branch_masters.order_by(User.full_name, User.name).all()
        
        statuses = ["new", "assigned", "accepted", "on_place", "to_sd", "done_pending_sum", "cancelled", "completed"]
        
        return templates.TemplateResponse("director_branch_orders.html", {
            "request": request,
            "page_title": "Заявки филиала",
            "active_page": "branch_orders",
            "user": user,
            "user_role": "director",
            "city": user.city_rel if user and user.city_rel else None,
            "orders": orders,
            "branch_masters": branch_masters,
            "statuses": statuses,
            "current_filters": {
                "status": status,
                "master_id": master_id,
                "date_from": date_from,
                "date_to": date_to,
            },
            "get_equip_type_name": get_equip_type_name,
            "get_status_name_ru": get_status_name_ru,
        })
    finally:
        session.close()


@app.get("/branch-sd", response_class=HTMLResponse)
async def director_branch_sd(request: Request):
    """СД филиала - техника на руках у мастеров"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_director_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        city_id = user.city_id if user else None
        
        # Заявки со статусом СД
        query = session.query(Order).filter(
            Order.status.in_(["accepted", "on_place", "to_sd"])
        )
        if city_id:
            query = query.filter(Order.city_id == city_id)
        
        sd_orders = query.order_by(Order.created_at.desc()).all()
        
        # Группируем по мастерам
        masters_dict = {}
        for order in sd_orders:
            master_id = order.assigned_to
            if master_id not in masters_dict:
                master = session.query(User).filter_by(tg_id=master_id).first()
                masters_dict[master_id] = {
                    "master": master,
                    "orders": []
                }
            masters_dict[master_id]["orders"].append(order)
        
        return templates.TemplateResponse("director_branch_sd.html", {
            "request": request,
            "page_title": "СД филиала",
            "active_page": "branch_sd",
            "user": user,
            "user_role": "director",
            "city": user.city_rel if user and user.city_rel else None,
            "masters_dict": masters_dict,
            "get_equip_type_name": get_equip_type_name,
            "get_status_name_ru": get_status_name_ru,
        })
    finally:
        session.close()


@app.get("/branch-cash", response_class=HTMLResponse)
async def director_branch_cash(request: Request):
    """Касса филиала - заявки к сдаче"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_director_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        city_id = user.city_id if user else None
        
        # Заявки со статусом done_pending_sum
        query = session.query(Order).filter(Order.status == "done_pending_sum")
        if city_id:
            query = query.filter(Order.city_id == city_id)
        
        pending_orders = query.order_by(Order.created_at.desc()).all()
        
        # Группируем по мастерам и считаем суммы
        masters_cash = {}
        total_company = 0.0
        
        for order in pending_orders:
            master_id = order.assigned_to
            if master_id not in masters_cash:
                master = session.query(User).filter_by(tg_id=master_id).first()
                masters_cash[master_id] = {
                    "master": master,
                    "orders": [],
                    "total_company": 0.0
                }
            
            order_sum = float(order.sum_amount or 0)
            sd_price = float(order.sd_price or 0)
            zpch_sum = float(order.zpch_sum or 0)
            net_amount = max(order_sum - sd_price - zpch_sum, 0)
            pct = get_master_pct(order.equip_type or "other", net_amount)
            master_share = net_amount * (pct / 100.0)
            company_share = net_amount - master_share
            
            masters_cash[master_id]["orders"].append({
                "order": order,
                "order_sum": order_sum,
                "sd_price": sd_price,
                "zpch_sum": zpch_sum,
                "net_amount": net_amount,
                "pct": pct,
                "master_share": master_share,
                "company_share": company_share,
            })
            masters_cash[master_id]["total_company"] += company_share
            total_company += company_share
        
        return templates.TemplateResponse("director_branch_cash.html", {
            "request": request,
            "page_title": "Касса филиала",
            "active_page": "branch_cash",
            "user": user,
            "user_role": "director",
            "city": user.city_rel if user and user.city_rel else None,
            "masters_cash": masters_cash,
            "total_company": total_company,
            "get_equip_type_name": get_equip_type_name,
            "get_status_name_ru": get_status_name_ru,
        })
    finally:
        session.close()


@app.get("/branch-masters", response_class=HTMLResponse)
async def director_branch_masters(request: Request):
    """Мастера филиала"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_director_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        city_id = user.city_id if user else None
        
        # Мастера филиала
        query = session.query(User).filter_by(role="master")
        if city_id:
            query = query.filter_by(city_id=city_id)
        branch_masters = query.order_by(User.full_name, User.name).all()
        
        # Статистика по каждому мастеру
        masters_stats = []
        for master in branch_masters:
            active_orders = session.query(Order).filter(
                Order.assigned_to == master.tg_id,
                Order.status.in_(["accepted", "on_place", "to_sd"])
            ).count()
            
            completed_orders = session.query(Order).filter(
                Order.assigned_to == master.tg_id,
                Order.status == "completed"
            ).count()
            
            pending_cash = session.query(Order).filter(
                Order.assigned_to == master.tg_id,
                Order.status == "done_pending_sum"
            ).count()
            
            masters_stats.append({
                "master": master,
                "active_orders": active_orders,
                "completed_orders": completed_orders,
                "pending_cash": pending_cash,
            })
        
        return templates.TemplateResponse("director_branch_masters.html", {
            "request": request,
            "page_title": "Мастера филиала",
            "active_page": "branch_masters",
            "user": user,
            "user_role": "director",
            "city": user.city_rel if user and user.city_rel else None,
            "masters_stats": masters_stats,
        })
    finally:
        session.close()


@app.get("/branch-stats", response_class=HTMLResponse)
async def director_branch_stats(
    request: Request,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """Статистика филиала"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_director_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        city_id = user.city_id if user else None
        
        # Фильтры по дате
        query = session.query(Order)
        if city_id:
            query = query.filter(Order.city_id == city_id)
        
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
                query = query.filter(func.date(Order.created_at) >= date_from_obj)
            except ValueError:
                pass
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
                date_to_obj = datetime.combine(date_to_obj, datetime.max.time())
                query = query.filter(Order.created_at <= date_to_obj)
            except ValueError:
                pass
        
        # Статистика
        total_orders = query.count()
        completed_orders = query.filter(Order.status == "completed", Order.is_warranty.is_(False)).count()
        active_orders = query.filter(Order.status.in_(["accepted", "on_place", "to_sd"])).count()
        
        # Суммы
        completed_orders_list = query.filter(Order.status == "completed", Order.is_warranty.is_(False)).all()
        total_sum = 0.0
        total_net_sum = 0.0
        for order in completed_orders_list:
            order_sum = float(order.sum_amount or 0)
            sd_price = float(order.sd_price or 0)
            zpch_sum = float(order.zpch_sum or 0)
            net_amount = max(order_sum - sd_price - zpch_sum, 0)
            total_sum += order_sum
            total_net_sum += net_amount
        
        avg_check = total_net_sum / completed_orders if completed_orders > 0 else 0.0
        
        # Статистика по мастерам
        branch_masters = session.query(User).filter_by(role="master")
        if city_id:
            branch_masters = branch_masters.filter_by(city_id=city_id)
        branch_masters = branch_masters.all()
        
        masters_stats = []
        for master in branch_masters:
            master_orders = query.filter(Order.assigned_to == master.tg_id).all()
            master_completed = [o for o in master_orders if o.status == "completed" and not getattr(o, "is_warranty", False)]
            master_total = sum(float(o.sum_amount or 0) for o in master_completed)
            master_net = sum(
                max(float(o.sum_amount or 0) - float(o.sd_price or 0) - float(o.zpch_sum or 0), 0)
                for o in master_completed
            )
            
            # Средний чек мастера (чистая сумма / количество закрытых заявок)
            master_avg_check = master_net / len(master_completed) if len(master_completed) > 0 else 0.0
            
            masters_stats.append({
                "master": master,
                "total_orders": len(master_orders),
                "completed_orders": len(master_completed),
                "total_sum": master_total,
                "net_sum": master_net,
                "avg_check": master_avg_check,
            })
        
        return templates.TemplateResponse("director_branch_stats.html", {
            "request": request,
            "page_title": "Статистика филиала",
            "active_page": "branch_stats",
            "user": user,
            "user_role": "director",
            "city": user.city_rel if user and user.city_rel else None,
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "active_orders": active_orders,
            "total_sum": total_sum,
            "total_net_sum": total_net_sum,
            "avg_check": avg_check,
            "masters_stats": masters_stats,
            "current_filters": {
                "date_from": date_from,
                "date_to": date_to,
            },
        })
    finally:
        session.close()


@app.get("/order/{order_id}", response_class=HTMLResponse)
async def director_order_view(request: Request, order_id: int):
    """Просмотр заявки для директора"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_director_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        city_id = user.city_id if user else None
        
        order = session.query(Order).filter_by(id=order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        
        # Проверяем, что заявка из филиала директора
        if city_id and order.city_id != city_id:
            raise HTTPException(status_code=403, detail="Заявка не из вашего филиала")
        
        # Мастера филиала для назначения
        branch_masters = session.query(User).filter_by(role="master")
        if city_id:
            branch_masters = branch_masters.filter_by(city_id=city_id)
        branch_masters = branch_masters.order_by(User.full_name, User.name).all()
        
        return templates.TemplateResponse("director_order_view.html", {
            "request": request,
            "page_title": f"Заявка #{order.order_number}",
            "active_page": "branch_orders",
            "user": user,
            "user_role": "director",
            "order": order,
            "branch_masters": branch_masters,
            "get_equip_type_name": get_equip_type_name,
            "get_status_name_ru": get_status_name_ru,
        })
    finally:
        session.close()


@app.post("/order/{order_id}/assign", response_class=HTMLResponse)
async def director_assign_order(request: Request, order_id: int):
    """Назначение заявки мастеру директором"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_director_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        city_id = user.city_id if user else None
        
        order = session.query(Order).filter_by(id=order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        
        if city_id and order.city_id != city_id:
            raise HTTPException(status_code=403, detail="Заявка не из вашего филиала")
        
        form = await request.form()
        master_id_str = form.get("master_id", "").strip()
        
        if master_id_str and master_id_str != "-":
            try:
                master_id = int(master_id_str)
                master = session.query(User).filter_by(tg_id=master_id, role="master").first()
                if not master:
                    raise HTTPException(status_code=400, detail="Мастер не найден")
                if city_id and master.city_id != city_id:
                    raise HTTPException(status_code=403, detail="Мастер не из вашего филиала")
                order.assigned_to = master_id
                order.status = "assigned"
            except ValueError:
                pass
        elif master_id_str == "-":
            order.assigned_to = None
            order.status = "new"
        
        session.commit()
        return RedirectResponse(f"/order/{order_id}?assigned=1", status_code=303)
    finally:
        session.close()


@app.get("/orders", response_class=HTMLResponse)
async def master_orders(
    request: Request,
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """Список заявок мастера"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_master_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        query = session.query(Order).filter(Order.assigned_to == user_id)
        
        if status:
            query = query.filter(Order.status == status)
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
                query = query.filter(func.date(Order.created_at) >= date_from_obj)
            except ValueError:
                pass
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
                date_to_obj = datetime.combine(date_to_obj, datetime.max.time())
                query = query.filter(Order.created_at <= date_to_obj)
            except ValueError:
                pass
        
        orders = query.order_by(Order.created_at.desc()).limit(100).all()
        
        statuses = ["new", "assigned", "accepted", "on_place", "to_sd", "done_pending_sum", "cancelled", "completed"]
        
        return templates.TemplateResponse("master_orders.html", {
            "request": request,
            "page_title": "Мои заявки",
            "active_page": "orders",
            "user": user,
            "user_role": "master",
            "orders": orders,
            "statuses": statuses,
            "current_filters": {
                "status": status,
                "date_from": date_from,
                "date_to": date_to,
            },
            "get_equip_type_name": get_equip_type_name,
            "get_status_name_ru": get_status_name_ru,
        })
    finally:
        session.close()


@app.get("/sd", response_class=HTMLResponse)
async def master_sd(request: Request):
    """СД мастера - техника на руках"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_master_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        # Заявки со статусом СД
        sd_orders = session.query(Order).filter(
            Order.assigned_to == user_id,
            Order.status.in_(["accepted", "on_place", "to_sd"])
        ).order_by(Order.created_at.desc()).all()
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        return templates.TemplateResponse("master_sd.html", {
            "request": request,
            "page_title": "СД",
            "active_page": "sd",
            "user": user,
            "user_role": "master",
            "orders": sd_orders,
            "get_equip_type_name": get_equip_type_name,
            "get_status_name_ru": get_status_name_ru,
        })
    finally:
        session.close()


@app.get("/cash", response_class=HTMLResponse)
async def master_cash(request: Request):
    """Касса мастера - заявки к сдаче"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_master_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        # Заявки со статусом done_pending_sum
        pending_orders = session.query(Order).filter(
            Order.assigned_to == user_id,
            Order.status == "done_pending_sum"
        ).order_by(Order.created_at.desc()).all()
        
        # Подсчет сумм
        total_company = 0.0
        orders_with_calc = []
        for order in pending_orders:
            order_sum = float(order.sum_amount or 0)
            sd_price = float(order.sd_price or 0)
            zpch_sum = float(order.zpch_sum or 0)
            net_amount = max(order_sum - sd_price - zpch_sum, 0)
            pct = get_master_pct(order.equip_type or "other", net_amount)
            master_share = net_amount * (pct / 100.0)
            company_share = net_amount - master_share
            total_company += company_share
            orders_with_calc.append({
                "order": order,
                "order_sum": order_sum,
                "sd_price": sd_price,
                "zpch_sum": zpch_sum,
                "net_amount": net_amount,
                "pct": pct,
                "master_share": master_share,
                "company_share": company_share,
            })
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        return templates.TemplateResponse("master_cash.html", {
            "request": request,
            "page_title": "Касса",
            "active_page": "cash",
            "user": user,
            "user_role": "master",
            "orders": orders_with_calc,
            "total_company": total_company,
            "get_equip_type_name": get_equip_type_name,
            "get_status_name_ru": get_status_name_ru,
        })
    finally:
        session.close()


# ===== Функционал директора =====

@app.get("/branch-orders", response_class=HTMLResponse)
async def director_branch_orders(
    request: Request,
    status: Optional[str] = Query(None),
    master_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """Заявки филиала для директора"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_director_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        city_id = user.city_id if user else None
        
        # Заявки филиала
        query = session.query(Order)
        if city_id:
            query = query.filter(Order.city_id == city_id)
        
        if status:
            query = query.filter(Order.status == status)
        if master_id:
            query = query.filter(Order.assigned_to == master_id)
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
                query = query.filter(func.date(Order.created_at) >= date_from_obj)
            except ValueError:
                pass
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
                date_to_obj = datetime.combine(date_to_obj, datetime.max.time())
                query = query.filter(Order.created_at <= date_to_obj)
            except ValueError:
                pass
        
        orders = query.order_by(Order.created_at.desc()).limit(100).all()
        
        # Мастера филиала
        branch_masters = session.query(User).filter_by(role="master")
        if city_id:
            branch_masters = branch_masters.filter_by(city_id=city_id)
        branch_masters = branch_masters.order_by(User.full_name, User.name).all()
        
        statuses = ["new", "assigned", "accepted", "on_place", "to_sd", "done_pending_sum", "cancelled", "completed"]
        
        return templates.TemplateResponse("director_branch_orders.html", {
            "request": request,
            "page_title": "Заявки филиала",
            "active_page": "branch_orders",
            "user": user,
            "user_role": "director",
            "city": user.city_rel if user and user.city_rel else None,
            "orders": orders,
            "branch_masters": branch_masters,
            "statuses": statuses,
            "current_filters": {
                "status": status,
                "master_id": master_id,
                "date_from": date_from,
                "date_to": date_to,
            },
            "get_equip_type_name": get_equip_type_name,
            "get_status_name_ru": get_status_name_ru,
        })
    finally:
        session.close()


@app.get("/branch-sd", response_class=HTMLResponse)
async def director_branch_sd(request: Request):
    """СД филиала - техника на руках у мастеров"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_director_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        city_id = user.city_id if user else None
        
        # Заявки со статусом СД
        query = session.query(Order).filter(
            Order.status.in_(["accepted", "on_place", "to_sd"])
        )
        if city_id:
            query = query.filter(Order.city_id == city_id)
        
        sd_orders = query.order_by(Order.created_at.desc()).all()
        
        # Группируем по мастерам
        masters_dict = {}
        for order in sd_orders:
            master_id = order.assigned_to
            if master_id not in masters_dict:
                master = session.query(User).filter_by(tg_id=master_id).first()
                masters_dict[master_id] = {
                    "master": master,
                    "orders": []
                }
            masters_dict[master_id]["orders"].append(order)
        
        return templates.TemplateResponse("director_branch_sd.html", {
            "request": request,
            "page_title": "СД филиала",
            "active_page": "branch_sd",
            "user": user,
            "user_role": "director",
            "city": user.city_rel if user and user.city_rel else None,
            "masters_dict": masters_dict,
            "get_equip_type_name": get_equip_type_name,
            "get_status_name_ru": get_status_name_ru,
        })
    finally:
        session.close()


@app.get("/branch-cash", response_class=HTMLResponse)
async def director_branch_cash(request: Request):
    """Касса филиала - заявки к сдаче"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_director_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        city_id = user.city_id if user else None
        
        # Заявки со статусом done_pending_sum
        query = session.query(Order).filter(Order.status == "done_pending_sum")
        if city_id:
            query = query.filter(Order.city_id == city_id)
        
        pending_orders = query.order_by(Order.created_at.desc()).all()
        
        # Группируем по мастерам и считаем суммы
        masters_cash = {}
        total_company = 0.0
        
        for order in pending_orders:
            master_id = order.assigned_to
            if master_id not in masters_cash:
                master = session.query(User).filter_by(tg_id=master_id).first()
                masters_cash[master_id] = {
                    "master": master,
                    "orders": [],
                    "total_company": 0.0
                }
            
            order_sum = float(order.sum_amount or 0)
            sd_price = float(order.sd_price or 0)
            zpch_sum = float(order.zpch_sum or 0)
            net_amount = max(order_sum - sd_price - zpch_sum, 0)
            pct = get_master_pct(order.equip_type or "other", net_amount)
            master_share = net_amount * (pct / 100.0)
            company_share = net_amount - master_share
            
            masters_cash[master_id]["orders"].append({
                "order": order,
                "order_sum": order_sum,
                "sd_price": sd_price,
                "zpch_sum": zpch_sum,
                "net_amount": net_amount,
                "pct": pct,
                "master_share": master_share,
                "company_share": company_share,
            })
            masters_cash[master_id]["total_company"] += company_share
            total_company += company_share
        
        return templates.TemplateResponse("director_branch_cash.html", {
            "request": request,
            "page_title": "Касса филиала",
            "active_page": "branch_cash",
            "user": user,
            "user_role": "director",
            "city": user.city_rel if user and user.city_rel else None,
            "masters_cash": masters_cash,
            "total_company": total_company,
            "get_equip_type_name": get_equip_type_name,
            "get_status_name_ru": get_status_name_ru,
        })
    finally:
        session.close()


@app.get("/branch-masters", response_class=HTMLResponse)
async def director_branch_masters(request: Request):
    """Мастера филиала"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_director_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        city_id = user.city_id if user else None
        
        # Мастера филиала
        query = session.query(User).filter_by(role="master")
        if city_id:
            query = query.filter_by(city_id=city_id)
        branch_masters = query.order_by(User.full_name, User.name).all()
        
        # Статистика по каждому мастеру
        masters_stats = []
        for master in branch_masters:
            active_orders = session.query(Order).filter(
                Order.assigned_to == master.tg_id,
                Order.status.in_(["accepted", "on_place", "to_sd"])
            ).count()
            
            completed_orders = session.query(Order).filter(
                Order.assigned_to == master.tg_id,
                Order.status == "completed"
            ).count()
            
            pending_cash = session.query(Order).filter(
                Order.assigned_to == master.tg_id,
                Order.status == "done_pending_sum"
            ).count()
            
            masters_stats.append({
                "master": master,
                "active_orders": active_orders,
                "completed_orders": completed_orders,
                "pending_cash": pending_cash,
            })
        
        return templates.TemplateResponse("director_branch_masters.html", {
            "request": request,
            "page_title": "Мастера филиала",
            "active_page": "branch_masters",
            "user": user,
            "user_role": "director",
            "city": user.city_rel if user and user.city_rel else None,
            "masters_stats": masters_stats,
        })
    finally:
        session.close()


@app.get("/branch-stats", response_class=HTMLResponse)
async def director_branch_stats(
    request: Request,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """Статистика филиала"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_director_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        city_id = user.city_id if user else None
        
        # Фильтры по дате
        query = session.query(Order)
        if city_id:
            query = query.filter(Order.city_id == city_id)
        
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
                query = query.filter(func.date(Order.created_at) >= date_from_obj)
            except ValueError:
                pass
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
                date_to_obj = datetime.combine(date_to_obj, datetime.max.time())
                query = query.filter(Order.created_at <= date_to_obj)
            except ValueError:
                pass
        
        # Статистика
        total_orders = query.count()
        completed_orders = query.filter(Order.status == "completed", Order.is_warranty.is_(False)).count()
        active_orders = query.filter(Order.status.in_(["accepted", "on_place", "to_sd"])).count()
        
        # Суммы
        completed_orders_list = query.filter(Order.status == "completed", Order.is_warranty.is_(False)).all()
        total_sum = 0.0
        total_net_sum = 0.0
        for order in completed_orders_list:
            order_sum = float(order.sum_amount or 0)
            sd_price = float(order.sd_price or 0)
            zpch_sum = float(order.zpch_sum or 0)
            net_amount = max(order_sum - sd_price - zpch_sum, 0)
            total_sum += order_sum
            total_net_sum += net_amount
        
        avg_check = total_net_sum / completed_orders if completed_orders > 0 else 0.0
        
        # Статистика по мастерам
        branch_masters = session.query(User).filter_by(role="master")
        if city_id:
            branch_masters = branch_masters.filter_by(city_id=city_id)
        branch_masters = branch_masters.all()
        
        masters_stats = []
        for master in branch_masters:
            master_orders = query.filter(Order.assigned_to == master.tg_id).all()
            master_completed = [o for o in master_orders if o.status == "completed" and not getattr(o, "is_warranty", False)]
            master_total = sum(float(o.sum_amount or 0) for o in master_completed)
            master_net = sum(
                max(float(o.sum_amount or 0) - float(o.sd_price or 0) - float(o.zpch_sum or 0), 0)
                for o in master_completed
            )
            
            # Средний чек мастера (чистая сумма / количество закрытых заявок)
            master_avg_check = master_net / len(master_completed) if len(master_completed) > 0 else 0.0
            
            masters_stats.append({
                "master": master,
                "total_orders": len(master_orders),
                "completed_orders": len(master_completed),
                "total_sum": master_total,
                "net_sum": master_net,
                "avg_check": master_avg_check,
            })
        
        return templates.TemplateResponse("director_branch_stats.html", {
            "request": request,
            "page_title": "Статистика филиала",
            "active_page": "branch_stats",
            "user": user,
            "user_role": "director",
            "city": user.city_rel if user and user.city_rel else None,
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "active_orders": active_orders,
            "total_sum": total_sum,
            "total_net_sum": total_net_sum,
            "avg_check": avg_check,
            "masters_stats": masters_stats,
            "current_filters": {
                "date_from": date_from,
                "date_to": date_to,
            },
        })
    finally:
        session.close()


@app.get("/order/{order_id}", response_class=HTMLResponse)
async def master_order_view(request: Request, order_id: int):
    """Просмотр заявки"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id:
            return RedirectResponse("/login", status_code=303)
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        if not user:
            return RedirectResponse("/login", status_code=303)
        
        order = session.query(Order).filter_by(id=order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        
        # Проверка доступа
        if user.role == "master":
            if order.assigned_to != user_id:
                raise HTTPException(status_code=403, detail="Заявка не ваша")
        elif user.role == "director":
            city_id = user.city_id if user else None
            if city_id and order.city_id != city_id:
                raise HTTPException(status_code=403, detail="Заявка не из вашего филиала")
        else:
            return RedirectResponse("/login", status_code=303)
        
        # Мастера филиала для директора
        branch_masters = None
        if user.role == "director":
            city_id = user.city_id if user else None
            branch_masters_query = session.query(User).filter_by(role="master")
            if city_id:
                branch_masters_query = branch_masters_query.filter_by(city_id=city_id)
            branch_masters = branch_masters_query.order_by(User.full_name, User.name).all()
        
        template_name = "director_order_view.html" if user.role == "director" else "master_order_view.html"
        active_page = "branch_orders" if user.role == "director" else "orders"
        
        return templates.TemplateResponse(template_name, {
            "request": request,
            "page_title": f"Заявка #{order.order_number}",
            "active_page": active_page,
            "user": user,
            "user_role": user.role,
            "order": order,
            "branch_masters": branch_masters,
            "get_equip_type_name": get_equip_type_name,
            "get_status_name_ru": get_status_name_ru,
        })
    finally:
        session.close()


@app.post("/order/{order_id}/assign", response_class=HTMLResponse)
async def director_assign_order(request: Request, order_id: int):
    """Назначение заявки мастеру директором"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_director_access(session, user_id):
            return RedirectResponse("/login", status_code=303)
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        city_id = user.city_id if user else None
        
        order = session.query(Order).filter_by(id=order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        
        if city_id and order.city_id != city_id:
            raise HTTPException(status_code=403, detail="Заявка не из вашего филиала")
        
        form = await request.form()
        master_id_str = form.get("master_id", "").strip()
        
        if master_id_str and master_id_str != "-":
            try:
                master_id = int(master_id_str)
                master = session.query(User).filter_by(tg_id=master_id, role="master").first()
                if not master:
                    raise HTTPException(status_code=400, detail="Мастер не найден")
                if city_id and master.city_id != city_id:
                    raise HTTPException(status_code=403, detail="Мастер не из вашего филиала")
                order.assigned_to = master_id
                order.status = "assigned"
            except ValueError:
                pass
        elif master_id_str == "-":
            order.assigned_to = None
            order.status = "new"
        
        session.commit()
        return RedirectResponse(f"/order/{order_id}?assigned=1", status_code=303)
    finally:
        session.close()


def main():
    import uvicorn
    port = int(os.getenv("MASTER_PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

