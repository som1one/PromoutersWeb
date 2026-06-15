"""
Веб-админка для диспетчеров.
Позволяет создавать заявки через веб-интерфейс.
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
from services.user_service import generate_order_number
from handlers.menu_kb import EQUIP_TYPES
from handlers.utils import get_equip_type_name, get_status_name_ru
from sqlalchemy import func

app = FastAPI(title="Dispatcher Admin", version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("DISPATCHER_SECRET_KEY", "dispatcher-secret-key"))

# Шаблоны
templates = Jinja2Templates(directory="templates")

# Создаём папку для шаблонов если её нет
os.makedirs("templates", exist_ok=True)


# Функция проверки прав доступа (dispatcher)
def check_dispatcher_access(session, user_tg_id: int) -> bool:
    """Проверяет, является ли пользователь dispatcher"""
    user = session.query(User).filter_by(tg_id=user_tg_id).first()
    if not user:
        return False
    return user.role == "dispatcher"


# TODO: Временная авторизация - в продакшене нужна реальная авторизация
# Пока используем query параметр ?user_id=XXX для тестирования
def get_current_user_id(request: Request) -> Optional[int]:
    """Получить ID текущего пользователя из сессии/запроса"""
    # TODO: Реализовать реальную авторизацию
    user_id = request.query_params.get("user_id")
    if user_id:
        try:
            return int(user_id)
        except ValueError:
            return None
    return request.session.get("user_tg_id")


@app.get("/", response_class=HTMLResponse)
async def dispatcher_home(request: Request):
    """Главная страница диспетчерской админки"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id:
            return templates.TemplateResponse("dispatcher_login.html", {
                "request": request,
                "page_title": "Вход",
            })

        # Сохраняем ID пользователя в сессию, чтобы не таскать ?user_id в URL
        try:
            request.session["user_tg_id"] = user_id
        except Exception:
            # Если по какой-то причине сессия недоступна, продолжаем только с параметром
            pass

        if not check_dispatcher_access(session, user_id):
            raise HTTPException(status_code=403, detail="Доступ запрещён. Только для диспетчеров.")
        
        dispatcher = session.query(User).filter_by(tg_id=user_id).first()
        
        # Получаем последние заявки, созданные этим диспетчером
        recent_orders = session.query(Order).filter_by(created_by=user_id).order_by(Order.created_at.desc()).limit(10).all()
        
        # Статистика за сегодня
        today = date.today()
        today_orders = session.query(Order).filter(
            Order.created_by == user_id,
            func.date(Order.created_at) == today
        ).count()
        
        return templates.TemplateResponse("dispatcher_home.html", {
            "request": request,
            "page_title": "Панель диспетчера",
            "active_page": "home",
            "dispatcher": dispatcher,
            "recent_orders": recent_orders,
            "today_orders": today_orders,
            "get_equip_type_name": get_equip_type_name,
            "get_status_name_ru": get_status_name_ru,
        })
    finally:
        session.close()


@app.get("/sd", response_class=HTMLResponse)
async def dispatcher_sd(request: Request):
    """Просмотр СД для диспетчера и собственника"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id:
            return templates.TemplateResponse("dispatcher_login.html", {
                "request": request,
                "page_title": "Вход",
            })
        
        user = session.query(User).filter_by(tg_id=user_id).first()
        if not user or user.role not in ["dispatcher", "owner"]:
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        
        # Заявки со статусом СД
        sd_orders = session.query(Order).filter(
            Order.status.in_(["accepted", "on_place", "to_sd"])
        ).order_by(Order.created_at.desc()).all()
        
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
        
        return templates.TemplateResponse("dispatcher_sd.html", {
            "request": request,
            "page_title": "СД",
            "active_page": "sd",
            "dispatcher": user,
            "masters_dict": masters_dict,
            "get_equip_type_name": get_equip_type_name,
            "get_status_name_ru": get_status_name_ru,
        })
    finally:
        session.close()


@app.get("/create-order", response_class=HTMLResponse)
async def create_order_form(request: Request):
    """Форма создания заявки"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_dispatcher_access(session, user_id):
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        
        cities = session.query(City).order_by(City.name).all()
        masters = session.query(User).filter_by(role="master").order_by(User.full_name, User.name).all()
        directors = session.query(User).filter_by(role="director").order_by(User.full_name, User.name).all()
        
        return templates.TemplateResponse("dispatcher_create_order.html", {
            "request": request,
            "page_title": "Создать заявку",
            "active_page": "create_order",
            "cities": cities,
            "masters": masters,
            "directors": directors,
            "equip_types": EQUIP_TYPES,
            "initial": None,
            "error": None,
        })
    finally:
        session.close()


@app.post("/create-order", response_class=HTMLResponse)
async def create_order_submit(request: Request):
    """Обработка создания заявки"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_dispatcher_access(session, user_id):
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        
        form = await request.form()

        # Получаем данные формы
        city_id = (form.get("city_id") or "").strip()
        street = (form.get("street") or "").strip()
        house = (form.get("house") or "").strip()
        flat = (form.get("flat") or "").strip()
        time_from = (form.get("time_from") or "").strip()
        time_to = (form.get("time_to") or "").strip()
        equip_type = (form.get("equip_type") or "").strip()
        short_desc = (form.get("short_desc") or "").strip()
        source = (form.get("source") or "").strip()
        client_name = (form.get("client_name") or "").strip()
        client_phone = (form.get("client_phone") or "").strip()
        comment = (form.get("comment") or "").strip()

        # Валидация обязательных полей — диспетчер должен заполнить всё
        missing_fields = []
        if not city_id:
            missing_fields.append("город")
        if not street:
            missing_fields.append("улицу")
        if not house:
            missing_fields.append("дом")
        if not time_from:
            missing_fields.append("время с")
        if not time_to:
            missing_fields.append("время до")
        if not equip_type:
            missing_fields.append("тип техники")
        if not short_desc:
            missing_fields.append("краткое описание")
        if not source:
            missing_fields.append("источник")
        if not client_name:
            missing_fields.append("имя клиента")
        if not client_phone:
            missing_fields.append("телефон клиента")

        if missing_fields:
            error_msg = "Заполните все поля: " + ", ".join(missing_fields)
            initial = {
                "city_id": city_id,
                "street": street,
                "house": house,
                "flat": flat,
                "time_from": time_from,
                "time_to": time_to,
                "order_date": form.get("order_date", "").strip(),
                "equip_type": equip_type,
                "short_desc": short_desc,
                "source": source,
                "client_name": client_name,
                "client_phone": client_phone,
                "comment": comment,
                "assigned_to": form.get("assigned_to", "").strip(),
            }
            return templates.TemplateResponse("dispatcher_create_order.html", {
                "request": request,
                "page_title": "Создать заявку",
                "active_page": "create_order",
                "cities": session.query(City).order_by(City.name).all(),
                "masters": session.query(User).filter_by(role="master").order_by(User.full_name, User.name).all(),
                "directors": session.query(User).filter_by(role="director").order_by(User.full_name, User.name).all(),
                "equip_types": EQUIP_TYPES,
                "error": error_msg,
                "initial": initial,
            })

        try:
            city_id = int(city_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный ID города")

        # Генерируем номер заявки
        order_number = generate_order_number(session)
        
        # Дата выполнения (опционально)
        order_date_str = form.get("order_date", "").strip()
        order_date = None
        if order_date_str:
            try:
                order_date = datetime.strptime(order_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        
        # Назначение мастера/директора
        assigned_to = None
        assigned_to_str = form.get("assigned_to", "").strip()
        if assigned_to_str and assigned_to_str != "-":
            try:
                assigned_to = int(assigned_to_str)
            except ValueError:
                pass
        
        # Если не назначен мастер, но есть директор города - назначаем его
        if not assigned_to:
            city = session.query(City).filter_by(id=city_id).first()
            if city:
                # Ищем директора для этого города
                director = session.query(User).filter_by(role="director", city_id=city_id).first()
                if director:
                    assigned_to = director.tg_id
        
        # Определяем статус
        status = "new"
        if order_date and order_date > date.today():
            status = "scheduled"
        
        # Создаём заявку
        order = Order(
            order_number=order_number,
            city_id=city_id,
            street=street,
            house=house,
            flat=flat,
            time_from=time_from,
            time_to=time_to,
            order_date=datetime.combine(order_date, datetime.min.time()) if order_date else None,
            equip_type=equip_type,
            short_desc=short_desc,
            source=source,
            status=status,
            created_by=user_id,
            assigned_to=assigned_to,
            client_name=client_name if client_name else None,
            client_phone=client_phone if client_phone else None,
            comment=comment if comment else None,
        )
        
        session.add(order)
        session.commit()
        
        return RedirectResponse(f"/order/{order.id}?created=1", status_code=303)
    except Exception as e:
        session.rollback()
        return templates.TemplateResponse("dispatcher_create_order.html", {
            "request": request,
            "page_title": "Создать заявку",
            "active_page": "create_order",
            "cities": session.query(City).order_by(City.name).all(),
            "masters": session.query(User).filter_by(role="master").order_by(User.full_name, User.name).all(),
            "directors": session.query(User).filter_by(role="director").order_by(User.full_name, User.name).all(),
            "equip_types": EQUIP_TYPES,
            "error": f"Ошибка при создании заявки: {str(e)}",
        })
    finally:
        session.close()


@app.get("/order/{order_id}", response_class=HTMLResponse)
async def view_order(request: Request, order_id: int):
    """Просмотр заявки"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_dispatcher_access(session, user_id):
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        
        order = session.query(Order).filter_by(id=order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        
        # Проверяем, что заявка создана этим диспетчером
        if order.created_by != user_id:
            raise HTTPException(status_code=403, detail="Нет доступа к этой заявке")
        
        masters = session.query(User).filter_by(role="master").order_by(User.full_name, User.name).all()
        directors = session.query(User).filter_by(role="director").order_by(User.full_name, User.name).all()

        # История клиента по телефону
        client_orders = []
        if order.client_phone:
            client_orders = (
                session.query(Order)
                .filter(
                    Order.client_phone == order.client_phone,
                    Order.id != order.id,
                )
                .order_by(Order.created_at.desc())
                .limit(10)
                .all()
            )
        
        return templates.TemplateResponse("dispatcher_order_view.html", {
            "request": request,
            "page_title": f"Заявка #{order.order_number}",
            "active_page": "orders",
            "order": order,
            "masters": masters,
            "directors": directors,
            "get_equip_type_name": get_equip_type_name,
            "client_orders": client_orders,
        })
    finally:
        session.close()


@app.get("/order/{order_id}/duplicate", response_class=HTMLResponse)
async def duplicate_order(request: Request, order_id: int):
    """Создать новую заявку на основе существующей"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_dispatcher_access(session, user_id):
            raise HTTPException(status_code=403, detail="Доступ запрещён")

        order = session.query(Order).filter_by(id=order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Заявка не найдена")

        # Только свои заявки
        if order.created_by != user_id:
            raise HTTPException(status_code=403, detail="Нет доступа к этой заявке")

        cities = session.query(City).order_by(City.name).all()
        masters = session.query(User).filter_by(role="master").order_by(User.full_name, User.name).all()
        directors = session.query(User).filter_by(role="director").order_by(User.full_name, User.name).all()

        initial = {
            "city_id": order.city_id,
            "street": order.street or "",
            "house": order.house or "",
            "flat": order.flat or "",
            "time_from": order.time_from or "",
            "time_to": order.time_to or "",
            "order_date": order.order_date.date().isoformat() if order.order_date else "",
            "equip_type": order.equip_type or "",
            "short_desc": order.short_desc or "",
            "source": order.source or "",
            "client_name": order.client_name or "",
            "client_phone": order.client_phone or "",
            "comment": order.comment or "",
            "assigned_to": order.assigned_to or "",
        }

        return templates.TemplateResponse("dispatcher_create_order.html", {
            "request": request,
            "page_title": "Создать заявку",
            "active_page": "create_order",
            "cities": cities,
            "masters": masters,
            "directors": directors,
            "equip_types": EQUIP_TYPES,
            "initial": initial,
            "error": None,
        })
    finally:
        session.close()


@app.get("/orders", response_class=HTMLResponse)
async def orders_list(
    request: Request,
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """Список заявок диспетчера с фильтрацией"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_dispatcher_access(session, user_id):
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        
        query = session.query(Order).filter_by(created_by=user_id)
        
        # Фильтры
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
                query = query.filter(func.date(Order.created_at) <= date_to_obj)
            except ValueError:
                pass
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Order.order_number.like(search_term)) |
                (Order.street.ilike(search_term)) |
                (Order.client_name.ilike(search_term)) |
                (Order.client_phone.ilike(search_term)) |
                (Order.short_desc.ilike(search_term))
            )
        
        orders = query.order_by(Order.created_at.desc()).limit(100).all()
        
        statuses = ["new", "assigned", "accepted", "on_place", "done_pending_sum", "done", "cancelled", "declined", "completed", "scheduled"]
        
        return templates.TemplateResponse("dispatcher_orders.html", {
            "request": request,
            "page_title": "Мои заявки",
            "active_page": "orders",
            "orders": orders,
            "statuses": statuses,
            "current_filters": {
                "status": status,
                "search": search,
                "date_from": date_from,
                "date_to": date_to,
            },
            "get_equip_type_name": get_equip_type_name,
        })
    finally:
        session.close()


@app.post("/order/{order_id}", response_class=HTMLResponse)
async def dispatcher_order_edit(request: Request, order_id: int):
    """Редактирование заявки диспетчером"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_dispatcher_access(session, user_id):
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        
        order = session.query(Order).filter_by(id=order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        
        # Проверяем, что заявка создана этим диспетчером
        if order.created_by != user_id:
            raise HTTPException(status_code=403, detail="Нет доступа к этой заявке")
        
        form = await request.form()
        
        # Обновляем поля (диспетчер может редактировать только основные поля)
        if "city_id" in form and form["city_id"]:
            try:
                order.city_id = int(form["city_id"])
            except ValueError:
                pass
        
        if "street" in form:
            order.street = form["street"].strip() or None
        if "house" in form:
            order.house = form["house"].strip() or None
        if "flat" in form:
            order.flat = form["flat"].strip() or None
        if "time_from" in form:
            order.time_from = form["time_from"].strip() or None
        if "time_to" in form:
            order.time_to = form["time_to"].strip() or None
        if "equip_type" in form:
            order.equip_type = form["equip_type"].strip() or None
        if "short_desc" in form:
            order.short_desc = form["short_desc"].strip() or None
        if "source" in form:
            order.source = form["source"].strip() or None
        if "client_name" in form:
            order.client_name = form["client_name"].strip() or None
        if "client_phone" in form:
            order.client_phone = form["client_phone"].strip() or None
        if "comment" in form:
            order.comment = form["comment"].strip() or None
        
        # Дата выполнения
        if "order_date" in form and form["order_date"]:
            try:
                order_date = datetime.strptime(form["order_date"], "%Y-%m-%d").date()
                order.order_date = datetime.combine(order_date, datetime.min.time())
            except ValueError:
                pass
        elif "order_date" in form and not form["order_date"]:
            order.order_date = None
        
        # Назначение мастера (диспетчер может переназначить)
        if "assigned_to" in form:
            assigned_to_str = form["assigned_to"].strip()
            if assigned_to_str and assigned_to_str != "-":
                try:
                    order.assigned_to = int(assigned_to_str)
                except ValueError:
                    pass
            elif assigned_to_str == "-":
                order.assigned_to = None
        
        session.commit()
        
        return RedirectResponse(f"/order/{order_id}?updated=1", status_code=303)
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении заявки: {str(e)}")
    finally:
        session.close()


@app.get("/order/{order_id}/edit", response_class=HTMLResponse)
async def dispatcher_order_edit_form(request: Request, order_id: int):
    """Форма редактирования заявки для диспетчера"""
    session = get_session()
    try:
        user_id = get_current_user_id(request)
        if not user_id or not check_dispatcher_access(session, user_id):
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        
        order = session.query(Order).filter_by(id=order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        
        # Проверяем, что заявка создана этим диспетчером
        if order.created_by != user_id:
            raise HTTPException(status_code=403, detail="Нет доступа к этой заявке")
        
        cities = session.query(City).order_by(City.name).all()
        masters = session.query(User).filter_by(role="master").order_by(User.full_name, User.name).all()
        directors = session.query(User).filter_by(role="director").order_by(User.full_name, User.name).all()
        
        return templates.TemplateResponse("dispatcher_order_edit.html", {
            "request": request,
            "page_title": f"Редактировать заявку #{order.order_number}",
            "active_page": "orders",
            "order": order,
            "cities": cities,
            "masters": masters,
            "directors": directors,
            "equip_types": EQUIP_TYPES,
        })
    finally:
        session.close()


def main():
    import uvicorn
    port = int(os.getenv("DISPATCHER_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

