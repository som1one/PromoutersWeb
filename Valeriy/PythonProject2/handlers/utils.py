"""
Утилиты для работы с типами техники.
Содержит функции для преобразования кодов в названия.
"""

def get_equip_type_name(code):
    """Получает название типа техники по коду"""
    from handlers.menu_kb import EQUIP_TYPES
    for name, equip_code in EQUIP_TYPES:
        if equip_code == code:
            return name
    return code  # Возвращаем код, если название не найдено


def get_status_name_ru(status: str) -> str:
    """Получает русское название статуса заявки"""
    status_map = {
        "new": "Заявка создана",
        "assigned": "Назначена",
        "accepted": "Принята",
        "on_place": "В пути",
        "to_sd": "На СД",
        "done_pending_sum": "Ожидает приема кассы",
        "done": "Готова",
        "cancelled": "Отмена",
        "declined": "Отклонена",
        "completed": "Закрыта",
        "scheduled": "Запланирована",
    }
    return status_map.get(status, status)