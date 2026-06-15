"""
Рефакторированный модуль обработчиков пользователей.
Разделен на логические компоненты для лучшей читаемости и поддержки.
"""

import logging
import os
from telebot import types
from db import get_session
from services.user_service import ensure_user, get_role, require_role, generate_order_number
from services.equipment_service import get_equip_type_name
from handlers.menu_kb import main_keyboard, city_selection_keyboard
from _vk.state_manager import user_states
from handlers.form_handlers import FormHandler
from handlers.order_handlers import OrderHandler
from handlers.role_handlers import DispatcherHandler, MasterHandler, DirectorHandler, OwnerHandler
from handlers.validation import FormValidator, DataValidator
from handlers.error_handlers import ErrorHandler
from handlers.database_optimizer import db_optimizer
from model import User, Order, City

logger = logging.getLogger(__name__)


class UserHandlers:
    """Основной класс для обработки пользователей"""
    
    def __init__(self, bot):
        self.bot = bot
        self.states = user_states
        self.validator = FormValidator()
        self.error_handler = ErrorHandler(bot)
        self.form_handler = FormHandler(bot)
        self.order_handler = OrderHandler(bot)
        self.dispatcher_handler = DispatcherHandler(bot)
        self.master_handler = MasterHandler(bot)
        self.director_handler = DirectorHandler(bot)
        self.owner_handler = OwnerHandler(bot)
    
    def register_handlers(self):
        """Регистрация всех обработчиков"""
        self._register_commands()
        self._register_message_handlers()
        self._register_callback_handlers()
    
    def _register_commands(self):
        """Регистрация команд"""
        
        @self.bot.message_handler(commands=["start"])
        def cmd_start(message: types.Message):
            self._handle_start(message)
        
        @self.bot.message_handler(commands=["setrole"])
        def cmd_setrole(message: types.Message):
            self._handle_setrole(message)
    
    def _register_message_handlers(self):
        """Регистрация обработчиков сообщений"""
        
        # Обработчики кнопок
        @self.bot.message_handler(func=lambda m: m.text in ("➕ Новая заявка", "➕ Создать заявку"))
        def start_form(message: types.Message):
            self.form_handler.start_form(message)
        
        @self.bot.message_handler(func=lambda m: m.text == "📋 Мои заявки")
        def my_orders(message: types.Message):
            self.dispatcher_handler.handle_my_orders(message)
        
        @self.bot.message_handler(func=lambda m: m.text in ("📊 Статистика", "📊 Стата"))
        def stats(message: types.Message):
            self.dispatcher_handler.handle_stats(message)
        
        @self.bot.message_handler(func=lambda m: m.text == "👥 Управление мастерами")
        def manage_masters(message: types.Message):
            self.dispatcher_handler.handle_manage_masters(message)
        
        @self.bot.message_handler(func=lambda m: m.text == "📦 Мои СД")
        def master_sd(message: types.Message):
            self.master_handler.handle_my_sd(message)
        
        @self.bot.message_handler(func=lambda m: m.text == "💰 Касса")
        def master_cash(message: types.Message):
            self.master_handler.handle_cash(message)
        
        @self.bot.message_handler(func=lambda m: m.text == "🔄 Обновить")
        def master_refresh(message: types.Message):
            self.master_handler.handle_refresh(message)
        
        @self.bot.message_handler(func=lambda m: m.text == "⚙️ Админ-панель")
        def admin_panel(message: types.Message):
            self.director_handler.handle_admin_panel(message)
        
        @self.bot.message_handler(func=lambda m: m.text == "👤 Добавить мастера")
        def add_master_director(message: types.Message):
            self.director_handler.handle_add_master_director(message)
        
        @self.bot.message_handler(func=lambda m: m.text == "📦 СД")
        def director_sd(message: types.Message):
            self.director_handler.handle_director_sd(message)
        
        # Обработчики форм с валидацией
        @self.bot.message_handler(func=lambda m: m.from_user.id in self.states.form_state)
        def fill_form(message: types.Message):
            self._handle_fill_form_with_validation(message)
        
        @self.bot.message_handler(func=lambda m: m.from_user.id in self.states.sum_input_state)
        def handle_sum_input(message: types.Message):
            self._handle_sum_input_with_validation(message)
        
        @self.bot.message_handler(func=lambda m: m.from_user.id in self.states.master_creation_state)
        def handle_master_creation(message: types.Message):
            self._handle_master_creation_with_validation(message)
        
        @self.bot.message_handler(func=lambda m: m.from_user.id in self.states.city_management_state and self.states.city_management_state[m.from_user.id] == "add")
        def city_add_name_handler(message: types.Message):
            self._handle_city_add_with_validation(message)
        
        @self.bot.message_handler(func=lambda m: m.from_user.id in self.states.master_creation_state and self.states.master_creation_state[m.from_user.id]["method"] == "manual")
        def handle_manual_master_input_city(message: types.Message):
            self._handle_manual_master_input_with_validation(message)
        
        # Обработчик фото чека
        @self.bot.message_handler(content_types=['photo'], func=lambda m: m.from_user.id in self.states.sum_input_state and self.states.sum_input_state[m.from_user.id]["step"] == "waiting_receipt")
        def handle_receipt_photo(message: types.Message):
            self.order_handler.handle_receipt_photo(message)
    
    def _register_callback_handlers(self):
        """Регистрация обработчиков callback'ов"""
        
        # Обработчики форм
        @self.bot.callback_query_handler(func=lambda c: c.data.startswith("equip_type:"))
        def equip_type_callback(callback: types.CallbackQuery):
            self.form_handler.handle_equip_type_callback(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data == "cancel_form")
        def cancel_form_callback(callback: types.CallbackQuery):
            self.form_handler.handle_cancel_form_callback(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data.startswith("select_master:"))
        def select_master_callback(callback: types.CallbackQuery):
            self.form_handler.handle_select_master_callback(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data.startswith("select_city:") and c.from_user.id in self.states.form_state and self.states.form_state[c.from_user.id]["step"] == "city_selection")
        def select_city_for_order_callback(callback: types.CallbackQuery):
            self.form_handler.handle_select_city_callback(callback)
        
        # Обработчики заявок
        @self.bot.callback_query_handler(func=lambda c: c.data == "confirm_order")
        def confirm_order_callback(callback: types.CallbackQuery):
            self.order_handler.confirm_order_callback(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data.startswith("accept:"))
        def master_accept_callback(callback: types.CallbackQuery):
            self.order_handler.handle_master_accept_callback(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data.startswith("onway:"))
        def master_on_way_callback(callback: types.CallbackQuery):
            self.order_handler.handle_master_on_way_callback(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data.startswith("ready:"))
        def master_ready_callback(callback: types.CallbackQuery):
            self.order_handler.handle_master_ready_callback(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data == "zpch_zero")
        def zpch_zero_callback(callback: types.CallbackQuery):
            self.order_handler.handle_zpch_zero_callback(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data == "attach_receipt")
        def attach_receipt_callback(callback: types.CallbackQuery):
            self.order_handler.handle_attach_receipt_callback(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data == "skip_receipt")
        def skip_receipt_callback(callback: types.CallbackQuery):
            self.order_handler.handle_skip_receipt_callback(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data == "cancel_sum_input")
        def cancel_sum_input_callback(callback: types.CallbackQuery):
            self.order_handler.handle_cancel_sum_input_callback(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data.startswith("close_order:"))
        def close_order_callback(callback: types.CallbackQuery):
            self.order_handler.handle_close_order_callback(callback)
        
        # Обработчики редактирования заявки
        @self.bot.callback_query_handler(func=lambda c: c.data.startswith("edit:"))
        def edit_order_field_callback(callback: types.CallbackQuery):
            self._handle_edit_order_field(callback)
        
        # Обработчики создания мастеров
        @self.bot.callback_query_handler(func=lambda c: c.data == "create_master")
        def create_master_callback(callback: types.CallbackQuery):
            self._handle_create_master(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data == "create_master_by_id")
        def create_master_by_id_callback(callback: types.CallbackQuery):
            self._handle_create_master_by_id(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data == "create_master_manual")
        def create_master_manual_callback(callback: types.CallbackQuery):
            self._handle_create_master_manual(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data == "cancel_master_creation")
        def cancel_master_creation_callback(callback: types.CallbackQuery):
            self._handle_cancel_master_creation(callback)
        
        # Обработчики городов
        @self.bot.callback_query_handler(func=lambda c: c.data == 'admin_cities')
        def admin_cities_callback(callback: types.CallbackQuery):
            self.owner_handler.handle_city_management(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data == 'list_cities')
        def list_cities_callback(callback: types.CallbackQuery):
            self.owner_handler.handle_list_cities(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data == 'add_city')
        def add_city_callback(callback: types.CallbackQuery):
            self.owner_handler.handle_add_city(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data == 'delete_city')
        def delete_city_callback(callback: types.CallbackQuery):
            self.owner_handler.handle_delete_city(callback)
        
        @self.bot.callback_query_handler(func=lambda c: c.data.startswith('confirm_del_city:'))
        def confirm_del_city_callback(callback: types.CallbackQuery):
            self.owner_handler.handle_confirm_del_city(callback)
        
        # Обработчики назначения ролей
        @self.bot.callback_query_handler(func=lambda c: c.data.startswith("select_city:") and c.from_user.id in self.states.director_city_assign)
        def assign_city_director_callback(callback: types.CallbackQuery):
            self._handle_assign_city_director(callback)
    
    def _handle_start(self, message: types.Message):
        """Обработать команду /start с оптимизацией"""
        session = get_session()
        try:
            ensure_user(session, message.from_user)
            
            # Проверяем и обновляем роль для админов из .env
            admin_ids = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
            if message.from_user.id in admin_ids:
                u = session.query(User).filter_by(tg_id=message.from_user.id).first()
                if u and u.role != "owner":
                    old_role = u.role
                    u.role = "owner"
                    session.commit()
                    db_optimizer.invalidate_user_cache(message.from_user.id)
                    
                    # Уведомляем о смене роли
                    try:
                        role_names = {
                            "owner": "👑 Собственник",
                            "director": "👔 Директор", 
                            "dispatcher": "📞 Диспетчер",
                            "master": "🔧 Мастер"
                        }
                        old_role_name = role_names.get(old_role, old_role)
                        
                        new_kb = main_keyboard("owner")
                        self.bot.send_message(message.from_user.id, f"🎉 Ваша роль автоматически обновлена!\n\n"
                                                       f"Было: {old_role_name}\n"
                                                       f"Стало: 👑 Собственник\n\n"
                                                       f"Меню обновлено! ✨", reply_markup=new_kb)
                    except Exception as e:
                        logger.warning(f"Failed to notify user about auto role change: {e}")
            
            role = db_optimizer.get_role_cached(message.from_user.id)
            kb = main_keyboard(role)
            self.bot.send_message(message.chat.id, f"👋 Привет, {message.from_user.first_name}! 🎉\n\nРоль: {role}", reply_markup=kb)
        except Exception as e:
            self.error_handler.handle_general_error(message, e, "cmd_start")
        finally:
            session.close()
    
    def _handle_setrole(self, message: types.Message):
        """Обработать команду /setrole с оптимизацией"""
        session = get_session()
        try:
            role = db_optimizer.get_role_cached(message.from_user.id)
            if role != "owner":
                self.error_handler.handle_permission_error(message, "owner")
                return
            
            parts = message.text.split()
            if len(parts) < 3:
                self.bot.reply_to(message, "📝 Использование: /setrole <tg_id> <role>")
                return
            
            tg_id = int(parts[1])
            newrole = parts[2]
            if newrole != "director":
                return
            
            cities = db_optimizer.get_all_cities()
            if not cities:
                self.bot.reply_to(message, "❌ Нет городов. Добавьте сначала города через админку!")
                return
            
            self.states.set_director_city_assign(message.from_user.id, {"tg_id": tg_id})
            kb = city_selection_keyboard(cities)
            self.bot.reply_to(message, "📍 Введите город для директора:", reply_markup=kb)
        except Exception as e:
            self.error_handler.handle_general_error(message, e, "cmd_setrole")
        finally:
            session.close()
    
    def _handle_fill_form_with_validation(self, message: types.Message):
        """Обработать заполнение формы с валидацией"""
        user_id = message.from_user.id
        state = self.states.get_form_state(user_id)
        if not state:
            return
        
        step = state["step"]
        text = message.text.strip()
        
        # Валидация данных
        is_valid, error_message = self.validator.validate_form_step(step, text)
        if not is_valid:
            self.error_handler.handle_validation_error(message, step, error_message)
            return
        
        try:
            self.form_handler.fill_form(message)
        except Exception as e:
            self.error_handler.handle_general_error(message, e, "fill_form")
    
    def _handle_sum_input_with_validation(self, message: types.Message):
        """Обработать ввод суммы с валидацией"""
        user_id = message.from_user.id
        state = self.states.get_sum_input_state(user_id)
        if not state:
            return
        
        step = state["step"]
        text = message.text.strip()
        
        # Валидация суммы
        is_valid, error_message, sum_value = self.validator.validate_sum_input_step(step, text)
        if not is_valid:
            self.error_handler.handle_validation_error(message, step, error_message)
            return
        
        try:
            self.order_handler.handle_sum_input(message)
        except Exception as e:
            self.error_handler.handle_general_error(message, e, "sum_input")
    
    def _handle_master_creation_with_validation(self, message: types.Message):
        """Обработать создание мастера с валидацией"""
        user_id = message.from_user.id
        state = self.states.get_master_creation_state(user_id)
        if not state:
            return
        
        step = state["step"]
        text = message.text.strip()
        
        # Валидация данных мастера
        is_valid, error_message = self.validator.validate_master_creation_step(step, text)
        if not is_valid:
            self.error_handler.handle_validation_error(message, step, error_message)
            return
        
        try:
            self._handle_master_creation(message)
        except Exception as e:
            self.error_handler.handle_general_error(message, e, "master_creation")
    
    def _handle_city_add_with_validation(self, message: types.Message):
        """Обработать добавление города с валидацией"""
        city_name = message.text.strip()
        
        # Валидация названия города
        is_valid, error_message = self.validator.validator.validate_city(city_name)
        if not is_valid:
            self.error_handler.handle_validation_error(message, "city", error_message)
            return
        
        try:
            self.owner_handler.handle_city_add_name(message)
        except Exception as e:
            self.error_handler.handle_general_error(message, e, "city_add")
    
    def _handle_manual_master_input_with_validation(self, message: types.Message):
        """Обработать ввод данных мастера вручную с валидацией"""
        user_id = message.from_user.id
        state = self.states.get_master_creation_state(user_id)
        if not state:
            return
        
        step = state["step"]
        text = message.text.strip()
        
        # Валидация данных мастера
        is_valid, error_message = self.validator.validate_master_creation_step(step, text)
        if not is_valid:
            self.error_handler.handle_validation_error(message, step, error_message)
            return
        
        try:
            self._handle_manual_master_input_city(message)
        except Exception as e:
            self.error_handler.handle_general_error(message, e, "manual_master_input")
    
    def _handle_assign_city_director(self, callback: types.CallbackQuery):
        """Обработать назначение города директору с оптимизацией"""
        session = get_session()
        try:
            user_state = self.states.get_director_city_assign(callback.from_user.id)
            if not user_state:
                self.error_handler.handle_state_error_callback(callback, "director_city_assign")
                return
            
            tg_id = user_state["tg_id"]
            city_id = int(callback.data.split(":")[1])
            city = db_optimizer.get_city_cached(city_id)
            if not city:
                self.error_handler.handle_not_found_error_callback(callback, "city", str(city_id))
                return
            
            app_user = db_optimizer.get_user_cached(tg_id)
            if not app_user:
                app_user = User(tg_id=tg_id, name=str(tg_id), role="director", city_id=city_id)
                session.add(app_user)
            else:
                app_user.role = "director"
                app_user.city_id = city_id
            session.commit()
            db_optimizer.invalidate_user_cache(tg_id)
            self.states.clear_director_city_assign(callback.from_user.id)
            
            # Сообщение назначенному пользователю
            new_kb = main_keyboard("director")
            self.bot.send_message(tg_id, f"🎉 Ваша роль изменена!\nВы назначены директором городского филиала <b>{city.name}</b>", reply_markup=new_kb, parse_mode="HTML")
            self.bot.edit_message_text(f"✅ Директор с Telegram ID <b>{tg_id}</b> назначен на город <b>{city.name}</b>!", chat_id=callback.message.chat.id, message_id=callback.message.message_id, parse_mode="HTML")
            self.bot.answer_callback_query(callback.id, "Директор создан/назначен!")
        except Exception as e:
            self.error_handler.handle_general_error_callback(callback, e, "assign_city_director")
        finally:
            session.close()
    
    def _handle_edit_order_field(self, callback: types.CallbackQuery):
        """Обработать редактирование поля заявки с оптимизацией"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            state = self.states.get_form_state(user_id)
            if not state or state["step"] != "confirm":
                self.error_handler.handle_state_error_callback(callback, "form_confirm")
                return
            
            field = callback.data.split(":")[1]
            state["editing"] = True
            
            if field == "city":
                state["step"] = "city"
                kb = self._get_cancel_keyboard()
                self.bot.send_message(callback.message.chat.id, "🏙 Введите город (например: Краснодар, Москва, СПб):", reply_markup=kb)
            elif field == "address":
                state["step"] = "street"
                kb = self._get_cancel_keyboard()
                self.bot.send_message(callback.message.chat.id, "📍 Введите улицу (например: Красная, Ленина, Советская):", reply_markup=kb)
            elif field == "time":
                state["step"] = "time_from"
                kb = self._get_cancel_keyboard()
                self.bot.send_message(callback.message.chat.id, "⏰ Введите время от (например: 09:00, 14:30, 17:00):", reply_markup=kb)
            elif field == "equip_type":
                state["step"] = "equip_type"
                kb = self._get_equip_type_keyboard()
                self.bot.send_message(callback.message.chat.id, "🔧 Выберите тип техники:", reply_markup=kb)
            elif field == "description":
                state["step"] = "short_desc"
                kb = self._get_cancel_keyboard()
                self.bot.send_message(callback.message.chat.id, "📝 Введите краткое описание проблемы (например: не включается, не работает звук, зависает):", reply_markup=kb)
            elif field == "source":
                state["step"] = "source"
                kb = self._get_cancel_keyboard()
                self.bot.send_message(callback.message.chat.id, "📞 Введите имя источника (например: Роман, Яндекс, сайт):", reply_markup=kb)
            elif field == "client":
                state["step"] = "client_name"
                kb = self._get_cancel_keyboard()
                self.bot.send_message(callback.message.chat.id, "👤 Введите ФИО клиента (например: Иванов Иван Иванович):", reply_markup=kb)
            elif field == "phone":
                state["step"] = "client_phone"
                kb = self._get_cancel_keyboard()
                self.bot.send_message(callback.message.chat.id, "📱 Введите телефон клиента (например: +7(999)123-45-67):", reply_markup=kb)
            elif field == "comment":
                state["step"] = "comment"
                kb = self._get_cancel_keyboard()
                self.bot.send_message(callback.message.chat.id, "💬 Введите комментарий (необязательно, например: можно раньше, представился Романом):", reply_markup=kb)
            elif field == "master":
                state["step"] = "master_selection"
                role = db_optimizer.get_role_cached(user_id)
                masters = self._get_available_masters(session, role)
                if not masters:
                    self.bot.send_message(callback.message.chat.id, "❌ В системе нет мастеров. Обратитесь к администратору.", reply_markup=main_keyboard(role))
                    self.states.clear_form_state(user_id)
                    return
                
                kb = self._get_master_selection_keyboard(masters)
                self.bot.send_message(callback.message.chat.id, "🔧 Выберите мастера для назначения заявки:", reply_markup=kb)
            
            self.bot.answer_callback_query(callback.id, f"Редактирование поля: {field}")
        except Exception as e:
            self.error_handler.handle_general_error_callback(callback, e, "edit_order_field")
        finally:
            session.close()
    
    def _handle_create_master(self, callback: types.CallbackQuery):
        """Обработать создание мастера с оптимизацией"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            role = db_optimizer.get_role_cached(user_id)
            
            if role not in ("director", "owner"):
                self.error_handler.handle_permission_error_callback(callback, "director")
                return
            
            # Показываем выбор способа создания
            kb = self._get_master_creation_method_keyboard()
            self.bot.send_message(callback.message.chat.id, "👤 <b>Создание нового мастера:</b>\n\nВыберите способ создания:", reply_markup=kb, parse_mode="HTML")
            self.bot.answer_callback_query(callback.id, "Выбор способа создания")
        except Exception as e:
            self.error_handler.handle_general_error_callback(callback, e, "create_master")
        finally:
            session.close()
    
    def _handle_create_master_by_id(self, callback: types.CallbackQuery):
        """Обработать создание мастера по ID с оптимизацией"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            role = db_optimizer.get_role_cached(user_id)
            
            if role not in ("director", "owner"):
                self.error_handler.handle_permission_error_callback(callback, "director")
                return
            
            # Инициализируем состояние создания мастера по ID
            self.states.set_master_creation_state(user_id, {
                "step": "tg_id",
                "data": {},
                "method": "by_id"
            })
            
            kb = self._get_cancel_master_creation_keyboard()
            self.bot.send_message(callback.message.chat.id, "🆔 <b>Создание мастера по Telegram ID:</b>\n\nВведите Telegram ID мастера:", reply_markup=kb, parse_mode="HTML")
            self.bot.answer_callback_query(callback.id, "Создание по ID")
        except Exception as e:
            self.error_handler.handle_general_error_callback(callback, e, "create_master_by_id")
        finally:
            session.close()
    
    def _handle_create_master_manual(self, callback: types.CallbackQuery):
        """Обработать создание мастера вручную с оптимизацией"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            role = db_optimizer.get_role_cached(user_id)
            
            if role not in ("director", "owner"):
                self.error_handler.handle_permission_error_callback(callback, "director")
                return
            
            # Инициализируем состояние создания мастера вручную
            self.states.set_master_creation_state(user_id, {
                "step": "full_name",
                "data": {},
                "method": "manual"
            })
            
            kb = self._get_cancel_master_creation_keyboard()
            self.bot.send_message(callback.message.chat.id, "✍️ <b>Создание мастера вручную:</b>\n\nВыберите способ создания:", reply_markup=kb, parse_mode="HTML")
            self.bot.answer_callback_query(callback.id, "Создание вручную")
        except Exception as e:
            self.error_handler.handle_general_error_callback(callback, e, "create_master_manual")
        finally:
            session.close()
    
    def _handle_cancel_master_creation(self, callback: types.CallbackQuery):
        """Обработать отмену создания мастера с оптимизацией"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            self.states.clear_master_creation_state(user_id)
            
            role = db_optimizer.get_role_cached(user_id)
            self.bot.edit_message_text("❌ Создание мастера отменено", chat_id=callback.message.chat.id, message_id=callback.message.message_id)
            kb = main_keyboard(role)
            self.bot.send_message(callback.message.chat.id, "🏠 Главное меню:", reply_markup=kb)
            self.bot.answer_callback_query(callback.id, "Создание отменено")
        except Exception as e:
            self.error_handler.handle_general_error_callback(callback, e, "cancel_master_creation")
        finally:
            session.close()
    
    def _handle_master_creation(self, message: types.Message):
        """Обработать создание мастера с оптимизацией"""
        user_id = message.from_user.id
        state = self.states.get_master_creation_state(user_id)
        if not state:
            return
        
        step = state["step"]
        text = message.text.strip()
        session = get_session()
        method = state.get("method", "manual")
        
        try:
            if method == "by_id":
                # Создание по Telegram ID
                if step == "tg_id":
                    try:
                        tg_id = int(text)
                        state["data"]["tg_id"] = tg_id
                        
                        # Проверяем, не существует ли уже пользователь с таким tg_id
                        existing_user = db_optimizer.get_user_cached(tg_id)
                        if existing_user:
                            self.error_handler.handle_duplicate_error(message, "user", str(tg_id))
                            self.states.clear_master_creation_state(user_id)
                            return
                        
                        # Создаем мастера с базовой информацией
                        new_master = User(
                            tg_id=tg_id,
                            name=str(tg_id),
                            full_name=f"Мастер {tg_id}",
                            phone="Не указан",
                            city_id=None,
                            role="master"
                        )
                        
                        session.add(new_master)
                        session.commit()
                        db_optimizer.invalidate_user_cache(tg_id)
                        
                        # Показываем результат
                        result_text = f"✅ <b>Мастер успешно создан по Telegram ID!</b>\n\n"
                        result_text += f"🆔 Telegram ID: {tg_id}\n"
                        result_text += f"👤 Имя: Мастер {tg_id}\n"
                        result_text += f"📱 Телефон: Не указан\n"
                        result_text += f"🏙 Город: Не указан\n"
                        result_text += f"🔧 Роль: Мастер\n\n"
                        result_text += f"💡 <i>Мастер может обновить свою информацию через /start</i>"
                        
                        role = db_optimizer.get_role_cached(user_id)
                        kb = main_keyboard(role)
                        self.bot.send_message(message.chat.id, result_text, reply_markup=kb, parse_mode="HTML")
                        
                        # Очищаем состояние
                        self.states.clear_master_creation_state(user_id)
                        
                    except ValueError:
                        self.error_handler.handle_validation_error(message, "tg_id", "Введите корректный Telegram ID (число)")
                        
            else:
                # Создание вручную
                if step == "full_name":
                    state["data"]["full_name"] = text
                    state["step"] = "phone"
                    kb = self._get_cancel_master_creation_keyboard()
                    self.bot.send_message(message.chat.id, f"✅ ФИО: {text}\n\n📱 Введите номер телефона мастера:", reply_markup=kb)
                    
                elif step == "phone":
                    state["data"]["phone"] = text
                    state["step"] = "tg_id"
                    kb = self._get_cancel_master_creation_keyboard()
                    self.bot.send_message(message.chat.id, f"✅ Телефон: {text}\n\n🆔 Введите Telegram ID мастера:", reply_markup=kb)
                    
                elif step == "tg_id":
                    try:
                        tg_id = int(text)
                        state["data"]["tg_id"] = tg_id
                        state["step"] = "city_done"
                        new_master = User(
                            tg_id=tg_id,
                            name=str(tg_id),
                            full_name=state["data"]["full_name"],
                            phone=state["data"]["phone"],
                            city_id=state["data"]["city_id"],
                            role="master"
                        )
                        existing_user = db_optimizer.get_user_cached(tg_id)
                        if existing_user:
                            self.error_handler.handle_duplicate_error(message, "user", str(tg_id))
                            self.states.clear_master_creation_state(user_id)
                            return
                        session.add(new_master)
                        session.commit()
                        db_optimizer.invalidate_user_cache(tg_id)
                        result_text = f"✅ <b>Мастер создан!</b>\n\n👤 {state['data']['full_name']}\n📱 {state['data']['phone']}\n🆔 {tg_id}\n🏙 ID города: {state['data']['city_id']}\n🔧 Мастер"
                        kb = main_keyboard(db_optimizer.get_role_cached(user_id))
                        self.bot.send_message(message.chat.id, result_text, reply_markup=kb, parse_mode="HTML")
                        self.states.clear_master_creation_state(user_id)
                    except Exception as e:
                        self.error_handler.handle_general_error(message, e, "master_creation_tg_id")
                        
        except Exception as e:
            self.error_handler.handle_general_error(message, e, "master_creation")
            self.states.clear_master_creation_state(user_id)
        finally:
            session.close()
    
    def _handle_manual_master_input_city(self, message: types.Message):
        """Обработать ввод города для мастера вручную с оптимизацией"""
        user_id = message.from_user.id
        state = self.states.get_master_creation_state(user_id)
        if not state:
            return
        
        step = state["step"]
        text = message.text.strip()
        session = get_session()
        
        try:
            if step == "full_name":
                state["data"]["full_name"] = text
                state["step"] = "phone"
                kb = self._get_cancel_master_creation_keyboard()
                self.bot.send_message(message.chat.id, f"✅ ФИО: {text}\n\n📱 Введите номер телефона мастера:", reply_markup=kb)
                return
            elif step == "phone":
                state["data"]["phone"] = text
                state["step"] = "tg_id"
                kb = self._get_cancel_master_creation_keyboard()
                self.bot.send_message(message.chat.id, f"✅ Телефон: {text}\n\n🆔 Введите Telegram ID мастера:", reply_markup=kb)
                return
            elif step == "tg_id":
                try:
                    tg_id = int(text)
                    state["data"]["tg_id"] = tg_id
                    state["step"] = "city_done"
                    new_master = User(
                        tg_id=tg_id,
                        name=str(tg_id),
                        full_name=state["data"]["full_name"],
                        phone=state["data"]["phone"],
                        city_id=state["data"]["city_id"],
                        role="master"
                    )
                    existing_user = db_optimizer.get_user_cached(tg_id)
                    if existing_user:
                        self.error_handler.handle_duplicate_error(message, "user", str(tg_id))
                        self.states.clear_master_creation_state(user_id)
                        return
                    session.add(new_master)
                    session.commit()
                    db_optimizer.invalidate_user_cache(tg_id)
                    result_text = f"✅ <b>Мастер создан!</b>\n\n👤 {state['data']['full_name']}\n📱 {state['data']['phone']}\n🆔 {tg_id}\n🏙 ID города: {state['data']['city_id']}\n🔧 Мастер"
                    kb = main_keyboard(db_optimizer.get_role_cached(user_id))
                    self.bot.send_message(message.chat.id, result_text, reply_markup=kb, parse_mode="HTML")
                    self.states.clear_master_creation_state(user_id)
                except Exception as e:
                    self.error_handler.handle_general_error(message, e, "manual_master_tg_id")
        except Exception as e:
            self.error_handler.handle_general_error(message, e, "manual_master_input")
        finally:
            session.close()
    
    # Вспомогательные методы для получения клавиатур
    def _get_cancel_keyboard(self):
        from handlers.menu_kb import cancel_keyboard
        return cancel_keyboard()
    
    def _get_equip_type_keyboard(self):
        from handlers.menu_kb import equip_type_keyboard
        return equip_type_keyboard()
    
    def _get_master_selection_keyboard(self, masters):
        from handlers.menu_kb import master_selection_keyboard
        return master_selection_keyboard(masters)
    
    def _get_master_creation_method_keyboard(self):
        from handlers.menu_kb import master_creation_method_keyboard
        return master_creation_method_keyboard()
    
    def _get_cancel_master_creation_keyboard(self):
        from handlers.menu_kb import cancel_master_creation_keyboard
        return cancel_master_creation_keyboard()
    
    def _get_available_masters(self, session, role: str):
        """Получить список доступных мастеров в зависимости от роли с оптимизацией"""
        if role == "dispatcher":
            return db_optimizer.get_all_masters()
        elif role == "director":
            return db_optimizer.get_all_masters()
        else:
            return db_optimizer.get_all_masters()


def register(bot):
    """Регистрация обработчиков (для обратной совместимости)"""
    handlers = UserHandlers(bot)
    handlers.register_handlers()
    return handlers
