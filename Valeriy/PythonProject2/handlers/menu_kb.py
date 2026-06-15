from telebot import types
from services.user_service import get_available_roles_for_role, is_dispatcher_hidden_from_role

EQUIP_TYPES = [
    ("Бытовая", "appliance"),
    ("ПК", "pc"),
    ("Телевизоры", "phones"),
    ("Другое", "other"),
]

# Главное меню с учетом новых ролей

def main_keyboard(role="master"):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    if role == "master":
        # Панель мастера как на картинке
        kb.row("📦 Мои СД", "💰 Касса")
        kb.row("🔄 Обновить", "📊 Стата")
    elif role == "dispatcher":
        # Панель диспетчера
        kb.add("➕ Создать заявку")
        kb.add("👥 Управление мастерами")
    elif role == "director":
        # Панель директора
        kb.row("📋 Мои заявки", "👤 Добавить мастера")
        kb.row("📊 Статистика", "📦 СД")
    else:
        # Панель для собственника
        kb.add("📋 Мои заявки", "📊 Статистика")
        if role == "owner":
            kb.add("⚙️ Админ-панель")
    
    return kb

# Клавиатура типов техники для заявки

def equip_type_keyboard():
    kb = types.InlineKeyboardMarkup()
    # Группируем кнопки по 2 в ряд для компактности
    for i in range(0, len(EQUIP_TYPES), 2):
        row = []
        for j in range(2):
            if i + j < len(EQUIP_TYPES):
                name, val = EQUIP_TYPES[i + j]
                row.append(types.InlineKeyboardButton(name, callback_data=f"equip_type:{val}"))
        if len(row) == 2:
            kb.row(*row)
        else:
            kb.add(*row)
    return kb

# Клавиатура отмены для форм

def cancel_keyboard():
    # Кнопки отмены отключены по требованию (оставляем совместимость с вызовами).
    return None

# Клавиатура "Назад" для навигации

def back_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    return kb

# Клавиатура с кнопкой "Назад" для админки

def admin_back_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Назад в админку", callback_data="back_to_admin"))
    return kb

# Клавиатура подтверждения заявки

def confirm_order_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Подтвердить заявку", callback_data="confirm_order"))
    return kb

# Инлайн для админки с учетом ролей

def admin_keyboard(role="user"):
    kb = types.InlineKeyboardMarkup()
    
    if role == "director":
        # Панель директора как на картинке
        kb.row(
            types.InlineKeyboardButton("Заявки", callback_data="admin_orders"),
            types.InlineKeyboardButton("Статистика", callback_data="admin_stats")
        )
        kb.row(
            types.InlineKeyboardButton("Касса", callback_data="admin_cashier"),
            types.InlineKeyboardButton("СД", callback_data="admin_warehouse")
        )
    else:
        # Панель собственника
        kb.add(types.InlineKeyboardButton("Список мастеров", callback_data="admin_masters"))
        kb.add(types.InlineKeyboardButton("Типы техники", callback_data="admin_types"))
        kb.add(types.InlineKeyboardButton("Проценты техники", callback_data="admin_equipment_percentages"))
        kb.add(types.InlineKeyboardButton("Управление пользователями", callback_data="admin_users"))
        kb.add(types.InlineKeyboardButton("Список диспетчеров", callback_data="admin_dispatchers"))
    
    return kb

# Клавиатура для выбора ролей при назначении

def role_selection_keyboard(current_role):
    kb = types.InlineKeyboardMarkup()
    available_roles = get_available_roles_for_role(current_role)
    
    role_names = {
        "director": "Директор",
        "dispatcher": "Диспетчер", 
        "master": "Мастер"
    }
    
    for role in available_roles:
        kb.add(types.InlineKeyboardButton(role_names.get(role, role), callback_data=f"set_role:{role}"))
    
    return kb

def master_new_order_kb(order_id):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Принять", callback_data=f"accept:{order_id}"))
    return kb

def master_way_kb(order_id, street, house, city_name=None):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🚗 В пути", callback_data=f"onway:{order_id}"))
    # Кнопка Яндекс карты с адресом
    from urllib.parse import quote
    if city_name:
        address = f"{city_name}, {street}, {house}"
    else:
        address = f"{street}, {house}"
    yandex_url = f"https://yandex.ru/maps/?text={quote(address)}"
    kb.add(types.InlineKeyboardButton("🗺 Яндекс карты", url=yandex_url))
    return kb

def master_ready_kb(order_id):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Готово", callback_data=f"ready:{order_id}"))
    return kb

# Клавиатура для ввода суммы заказа
def order_sum_keyboard():
    # Кнопки отмены отключены
    return None

# Клавиатура для ввода ЗПЧ
def zpch_sum_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💰 ЗПЧ = 0", callback_data="zpch_zero"))
    return kb

# Клавиатура для ввода цены СД
def sd_price_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📄 СД = 0", callback_data="sd_zero"))
    return kb

# Клавиатура для прикрепления чека
def receipt_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📎 Прикрепить чек", callback_data="attach_receipt"))
    kb.add(types.InlineKeyboardButton("⏭ Пропустить", callback_data="skip_receipt"))
    return kb

# Клавиатура для закрытия заявки
def close_order_keyboard(order_id):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Закрыть заявку", callback_data=f"close_order:{order_id}"))
    return kb

# Клавиатура для создания мастера
def create_master_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("👤 Создать мастера", callback_data="create_master"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin"))
    return kb

# Клавиатура выбора способа создания мастера
def master_creation_method_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🆔 По Telegram ID", callback_data="create_master_by_id"))
    kb.add(types.InlineKeyboardButton("✍️ Вручную", callback_data="create_master_manual"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin"))
    return kb

# Клавиатура отмены создания мастера
def cancel_master_creation_keyboard():
    # Кнопки отмены отключены
    return None

# Клавиатура для выбора мастера
def master_selection_keyboard(masters):
    kb = types.InlineKeyboardMarkup()
    for master in masters:
        # Показываем ФИО или имя, город и ID
        display_name = master.full_name or master.name or f"ID {master.tg_id}"
        city_info = f" ({master.city_rel.name})" if master.city_rel else ""
        button_text = f"🔧 {display_name}{city_info}"
        kb.add(types.InlineKeyboardButton(button_text, callback_data=f"select_master:{master.tg_id}"))
    return kb

# Клавиатура для редактирования заявки
def edit_order_keyboard(is_warranty: bool = False):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🏙 Город", callback_data="edit:city"))
    kb.add(types.InlineKeyboardButton("📍 Адрес", callback_data="edit:address"))
    kb.add(types.InlineKeyboardButton("⏰ Время", callback_data="edit:time"))
    kb.add(types.InlineKeyboardButton("🔧 Тип техники", callback_data="edit:equip_type"))
    kb.add(types.InlineKeyboardButton(f"🛡 Гарантия: {'✅' if is_warranty else '❌'}", callback_data="edit:warranty"))
    kb.add(types.InlineKeyboardButton("📝 Описание", callback_data="edit:description"))
    kb.add(types.InlineKeyboardButton("📞 Источник", callback_data="edit:source"))
    kb.add(types.InlineKeyboardButton("👤 Клиент", callback_data="edit:client"))
    kb.add(types.InlineKeyboardButton("📱 Телефон", callback_data="edit:phone"))
    kb.add(types.InlineKeyboardButton("💬 Комментарий", callback_data="edit:comment"))
    kb.add(types.InlineKeyboardButton("🔧 Мастер", callback_data="edit:master"))
    kb.add(types.InlineKeyboardButton("👔 Передать директору", callback_data="transfer_to_director"))
    kb.row(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_order")
    )
    return kb

# Клавиатура выбора города для диспетчера и директора

def city_selection_keyboard(cities):
    kb = types.InlineKeyboardMarkup()
    for city in cities:
        kb.add(types.InlineKeyboardButton(f"🏙 {city.name}", callback_data=f"select_city:{city.id}"))
    return kb

# Клавиатура для управления городами (только для собственника)
def city_management_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("➕ Добавить город", callback_data="add_city"))
    kb.add(types.InlineKeyboardButton("🗑 Удалить город", callback_data="delete_city"))
    kb.add(types.InlineKeyboardButton("📋 Список городов", callback_data="list_cities"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin"))
    return kb

# Клавиатура выбора директора в городе
def director_selection_keyboard(directors):
    kb = types.InlineKeyboardMarkup()
    for director in directors:
        display_name = director.full_name or director.name or f"ID {director.tg_id}"
        city_info = f" ({getattr(director, 'city_id', '-')})"
        kb.add(types.InlineKeyboardButton(f"👔 {display_name}{city_info}", callback_data=f"select_director:{director.tg_id}"))
    return kb

# Клавиатура выбора мастера в городе
def master_city_selection_keyboard(masters):
    kb = types.InlineKeyboardMarkup()
    for master in masters:
        display_name = master.full_name or master.name or f"ID {master.tg_id}"
        city_info = f" ({getattr(master, 'city_id', '-')})"
        kb.add(types.InlineKeyboardButton(f"🔧 {display_name}{city_info}", callback_data=f"select_master_city:{master.tg_id}"))
    return kb

# Клавиатура управления процентами типов техники
def equipment_percentages_keyboard(equip_settings):
    kb = types.InlineKeyboardMarkup()
    for equip_type, settings in equip_settings.items():
        name = settings.get('name', equip_type)
        master_pct = settings.get('master_pct', 60)
        company_pct = settings.get('company_pct', 40)
        kb.add(types.InlineKeyboardButton(
            f"🔧 {name} (Мастер: {master_pct}%, Компания: {company_pct}%)", 
            callback_data=f"edit_equipment_pct:{equip_type}"
        ))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin"))
    return kb

# Клавиатура для статистики
def stats_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔍 Поиск заказов", callback_data="search_orders"))
    kb.add(types.InlineKeyboardButton("📷 Просмотр фотографий", callback_data="view_photos"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    return kb

# Клавиатура поиска заказов
def order_search_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📅 По дате", callback_data="search_by_date"))
    kb.add(types.InlineKeyboardButton("👤 По мастеру", callback_data="search_by_master"))
    kb.add(types.InlineKeyboardButton("💰 По сумме", callback_data="search_by_amount"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_stats"))
    return kb

# Клавиатура списка фотографий
def photos_list_keyboard(orders):
    kb = types.InlineKeyboardMarkup()
    for order in orders[:10]:  # Показываем первые 10
        kb.add(types.InlineKeyboardButton(
            f"📷 #{order.order_number} - {order.created_at.strftime('%d.%m.%Y')}", 
            callback_data=f"show_photo:{order.id}"
        ))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_stats"))
    return kb

# Клавиатура подтверждения очистки кассы
def cash_clear_confirm_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Да, очистить кассу", callback_data="cash_clear_confirm"))
    return kb
