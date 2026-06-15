from model import User, Order

NEXT_ORDER_BASE = 60000

def generate_order_number(session):
    r = session.query(Order).order_by(Order.order_number.desc()).first()
    if r:
        return r.order_number + 1
    return NEXT_ORDER_BASE + 1

def ensure_user(session, tg_user):
    u = session.query(User).filter_by(tg_id=tg_user.id).first()
    if not u:
        # Проверяем, является ли пользователь админом из переменных окружения
        import os
        admin_ids = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
        role = "owner" if tg_user.id in admin_ids else "master"
        u = User(tg_id=tg_user.id, name=tg_user.first_name or "", role=role)
        session.add(u)
        session.commit()
    return u

def get_role(session, tg_id: int):
    u = session.query(User).filter_by(tg_id=tg_id).first()
    if not u:
        return "user"
    return u.role

def require_role(session, tg_id: int, allowed_roles):
    return get_role(session, tg_id) in allowed_roles

# Иерархия ролей: собственник > директор > диспетчер > мастер
ROLE_HIERARCHY = {
    "owner": 4,      # собственник (суперадмин)
    "director": 3,    # директор
    "dispatcher": 2,  # диспетчер
    "master": 1       # мастер
}

def can_manage_role(current_role, target_role):
    """Проверяет, может ли текущая роль управлять целевой ролью"""
    current_level = ROLE_HIERARCHY.get(current_role, 0)
    target_level = ROLE_HIERARCHY.get(target_role, 0)
    return current_level > target_level

def get_available_roles_for_role(role):
    """Возвращает роли, которые может назначать текущая роль"""
    if role == "owner":
        return ["director", "dispatcher", "master"]
    elif role == "director":
        return ["master"]  # директор может добавлять только мастеров
    elif role == "dispatcher":
        return []  # диспетчер не может назначать роли
    else:
        return []

def is_dispatcher_hidden_from_role(role):
    """Проверяет, скрыты ли диспетчеры от данной роли"""
    return role == "director"  # диспетчеры скрыты от директоров
