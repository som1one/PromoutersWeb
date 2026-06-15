"""
Рефакторированный модуль обработчиков пользователей.
Разделен на логические компоненты для лучшей читаемости и поддержки.
"""

import logging
import os
from telebot import types
from db import get_session
from services.user_service import ensure_user, get_role, require_role
from services.equipment_service import get_equip_type_name
from handlers.menu_kb import main_keyboard, city_selection_keyboard
from _vk.state_manager import user_states
from handlers.form_handlers import FormHandler
from handlers.order_handlers import OrderHandler
from handlers.role_handlers import DispatcherHandler, MasterHandler, DirectorHandler, OwnerHandler
from model import User, Order, City

logger = logging.getLogger(__name__)


class UserHandlers:
    """Основной класс для обработки пользователей"""
    
    def __init__(self, bot):
        self.bot = bot
        self.states = user_states
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
        
        # Обработчики форм
        @self.bot.message_handler(func=lambda m: m.from_user.id in self.states.form_state)
        def fill_form(message: types.Message):
            self.form_handler.fill_form(message)
        
        @self.bot.message_handler(func=lambda m: m.from_user.id in self.states.sum_input_state)
        def handle_sum_input(message: types.Message):
            self.order_handler.handle_sum_input(message)
        
        @self.bot.message_handler(func=lambda m: m.from_user.id in self.states.master_creation_state)
        def handle_master_creation(message: types.Message):
            self._handle_master_creation(message)
        
        @self.bot.message_handler(func=lambda m: m.from_user.id in self.states.city_management_state and self.states.city_management_state[m.from_user.id] == "add")
        def city_add_name_handler(message: types.Message):
            self.owner_handler.handle_city_add_name(message)
        
        @self.bot.message_handler(func=lambda m: m.from_user.id in self.states.master_creation_state and self.states.master_creation_state[m.from_user.id]["method"] == "manual")
        def handle_manual_master_input_city(message: types.Message):
            self._handle_manual_master_input_city(message)
        
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
        """Обработать команду /start"""
        session = get_session()
        try:
            ensure_user(session, message.from_user)
            
            # Проверяем и обновляем роль для админов из .env
            admin_ids = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
            print(f"Admin IDs: {admin_ids}, User ID: {message.from_user.id}")  # Отладка
            if message.from_user.id in admin_ids:
                u = session.query(User).filter_by(tg_id=message.from_user.id).first()
                if u and u.role != "owner":
                    old_role = u.role
                    u.role = "owner"
                    session.commit()
                    print(f"Updated user {message.from_user.id} to owner role")  # Отладка
                    
                    # Уведомляем о смене роли
                    try:
                        role_names = {
                            "owner": "👑 Собственник",
                            "director": "👔 Директор", 
                            "dispatcher": "📞 Диспетчер",
                            "master": "🔧 Мастер"
                        }
                        old_role_name = role_names.get(old_role, old_role)
                        
                        # Отправляем новое меню с обновленной клавиатурой
                        new_kb = main_keyboard("owner")
                        self.bot.send_message(message.from_user.id, f"🎉 Ваша роль автоматически обновлена!\n\n"
                                                       f"Было: {old_role_name}\n"
                                                       f"Стало: 👑 Собственник\n\n"
                                                       f"Меню обновлено! ✨", reply_markup=new_kb)
                    except Exception as e:
                        logger.warning(f"Failed to notify user about auto role change: {e}")
            
            role = get_role(session, message.from_user.id)
            kb = main_keyboard(role)
            self.bot.send_message(message.chat.id, f"👋 Привет, {message.from_user.first_name}! 🎉\n\nРоль: {role}", reply_markup=kb)
        except Exception as e:
            logger.error(f"Error in cmd_start: {e}")
            self.bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        finally:
            session.close()
    
    def _handle_setrole(self, message: types.Message):
        """Обработать команду /setrole"""
        session = get_session()
        try:
            role = get_role(session, message.from_user.id)
            if role != "owner":
                self.bot.reply_to(message, "🚫 Только собственник может добавлять директоров!")
                return
            
            parts = message.text.split()
            if len(parts) < 3:
                self.bot.reply_to(message, "📝 Использование: /setrole <tg_id> <role>")
                return
            
            tg_id = int(parts[1])
            newrole = parts[2]
            if newrole != "director":
                # как раньше — только мастеров и диспетчеров назначать без города
                # ... existing code ...
                return
            
            # если director — показать города
            cities = session.query(City).all()
            if not cities:
                self.bot.reply_to(message, "❌ Нет городов. Добавьте сначала города через админку!")
                return
            
            self.states.set_director_city_assign(message.from_user.id, {"tg_id": tg_id})
            kb = city_selection_keyboard(cities)
            self.bot.reply_to(message, "📍 Введите город для директора:", reply_markup=kb)
        finally:
            session.close()
    
    def _handle_assign_city_director(self, callback: types.CallbackQuery):
        """Обработать назначение города директору"""
        session = get_session()
        try:
            user_state = self.states.get_director_city_assign(callback.from_user.id)
            if not user_state:
                self.bot.answer_callback_query(callback.id, "Состояние не найдено")
                return
            
            tg_id = user_state["tg_id"]
            city_id = int(callback.data.split(":")[1])
            city = session.query(City).filter_by(id=city_id).first()
            if not city:
                self.bot.answer_callback_query(callback.id, "Город не найден!")
                return
            
            app_user = session.query(User).filter_by(tg_id=tg_id).first()
            if not app_user:
                app_user = User(tg_id=tg_id, name=str(tg_id), role="director", city_id=city_id)
                session.add(app_user)
            else:
                app_user.role = "director"
                app_user.city_id = city_id
            session.commit()
            self.states.clear_director_city_assign(callback.from_user.id)
            
            # Сообщение назначенному пользователю
            new_kb = main_keyboard("director")
            self.bot.send_message(tg_id, f"🎉 Ваша роль изменена!\nВы назначены директором городского филиала <b>{city.name}</b>", reply_markup=new_kb, parse_mode="HTML")
            self.bot.edit_message_text(f"✅ Директор с Telegram ID <b>{tg_id}</b> назначен на город <b>{city.name}</b>!", chat_id=callback.message.chat.id, message_id=callback.message.message_id, parse_mode="HTML")
            self.bot.answer_callback_query(callback.id, "Директор создан/назначен!")
        finally:
            session.close()
    
    def _handle_edit_order_field(self, callback: types.CallbackQuery):
        """Обработать редактирование поля заявки"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            state = self.states.get_form_state(user_id)
            if not state or state["step"] != "confirm":
                self.bot.answer_callback_query(callback.id, "Форма не активна")
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
                role = get_role(session, user_id)
                masters = self._get_available_masters(session, role)
                if not masters:
                    self.bot.send_message(callback.message.chat.id, "❌ В системе нет мастеров. Обратитесь к администратору.", reply_markup=main_keyboard(role))
                    self.states.clear_form_state(user_id)
                    return
                
                kb = self._get_master_selection_keyboard(masters)
                self.bot.send_message(callback.message.chat.id, "🔧 Выберите мастера для назначения заявки:", reply_markup=kb)
            
            self.bot.answer_callback_query(callback.id, f"Редактирование поля: {field}")
        finally:
            session.close()
    
    def _handle_master_creation(self, callback: types.CallbackQuery):
        """Обработать создание мастера"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            role = get_role(session, user_id)
            
            if role not in ("director", "owner"):
                self.bot.answer_callback_query(callback.id, "Нет доступа")
                return
            
            # Показываем выбор способа создания
            kb = self._get_master_creation_method_keyboard()
            self.bot.send_message(callback.message.chat.id, "👤 <b>Создание нового мастера:</b>\n\nВыберите способ создания:", reply_markup=kb, parse_mode="HTML")
            self.bot.answer_callback_query(callback.id, "Выбор способа создания")
        finally:
            session.close()
    
    def _handle_create_master_by_id(self, callback: types.CallbackQuery):
        """Обработать создание мастера по ID"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            role = get_role(session, user_id)
            
            if role not in ("director", "owner"):
                self.bot.answer_callback_query(callback.id, "Нет доступа")
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
        finally:
            session.close()
    
    def _handle_create_master_manual(self, callback: types.CallbackQuery):
        """Обработать создание мастера вручную"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            role = get_role(session, user_id)
            
            if role not in ("director", "owner"):
                self.bot.answer_callback_query(callback.id, "Нет доступа")
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
        finally:
            session.close()
    
    def _handle_cancel_master_creation(self, callback: types.CallbackQuery):
        """Обработать отмену создания мастера"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            self.states.clear_master_creation_state(user_id)
            
            role = get_role(session, user_id)
            self.bot.edit_message_text("❌ Создание мастера отменено", chat_id=callback.message.chat.id, message_id=callback.message.message_id)
            kb = main_keyboard(role)
            self.bot.send_message(callback.message.chat.id, "🏠 Главное меню:", reply_markup=kb)
            self.bot.answer_callback_query(callback.id, "Создание отменено")
        finally:
            session.close()
    
    def _handle_master_creation(self, message: types.Message):
        """Обработать создание мастера"""
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
                        existing_user = session.query(User).filter_by(tg_id=tg_id).first()
                        if existing_user:
                            self.bot.send_message(message.chat.id, f"❌ Пользователь с ID {tg_id} уже существует!")
                            self.states.clear_master_creation_state(user_id)
                            return
                        
                        # Пытаемся получить информацию о пользователе из Telegram
                        try:
                            # Здесь можно попробовать получить информацию о пользователе
                            # Но для простоты создаем мастера с базовой информацией
                            new_master = User(
                                tg_id=tg_id,
                                name=str(tg_id),  # Временное имя
                                full_name=f"Мастер {tg_id}",
                                phone="Не указан",
                                city_id=None,
                                role="master"
                            )
                            
                            session.add(new_master)
                            session.commit()
                            
                            # Показываем результат
                            result_text = f"✅ <b>Мастер успешно создан по Telegram ID!</b>\n\n"
                            result_text += f"🆔 Telegram ID: {tg_id}\n"
                            result_text += f"👤 Имя: Мастер {tg_id}\n"
                            result_text += f"📱 Телефон: Не указан\n"
                            result_text += f"🏙 Город: Не указан\n"
                            result_text += f"🔧 Роль: Мастер\n\n"
                            result_text += f"💡 <i>Мастер может обновить свою информацию через /start</i>"
                            
                            role = get_role(session, user_id)
                            kb = main_keyboard(role)
                            self.bot.send_message(message.chat.id, result_text, reply_markup=kb, parse_mode="HTML")
                            
                            # Очищаем состояние
                            self.states.clear_master_creation_state(user_id)
                            
                        except Exception as e:
                            self.bot.send_message(message.chat.id, f"❌ Ошибка при создании мастера: {e}")
                            self.states.clear_master_creation_state(user_id)
                            
                    except ValueError:
                        self.bot.send_message(message.chat.id, "❌ Введите корректный Telegram ID (число)")
                        
            else:
                # Создание вручную (старый способ)
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
                        state["step"] = "city_done"  # этап city уже выбран!
                        new_master = User(
                            tg_id=tg_id,
                            name=str(tg_id),
                            full_name=state["data"]["full_name"],
                            phone=state["data"]["phone"],
                            city_id=state["data"]["city_id"],
                            role="master"
                        )
                        existing_user = session.query(User).filter_by(tg_id=tg_id).first()
                        if existing_user:
                            self.bot.send_message(message.chat.id, f"❌ Пользователь с ID {tg_id} уже существует!")
                            self.states.clear_master_creation_state(user_id)
                            return
                        session.add(new_master)
                        session.commit()
                        result_text = f"✅ <b>Мастер создан!</b>\n\n👤 {state['data']['full_name']}\n📱 {state['data']['phone']}\n🆔 {tg_id}\n🏙 ID города: {state['data']['city_id']}\n🔧 Мастер"
                        kb = main_keyboard(get_role(session, user_id))
                        self.bot.send_message(message.chat.id, result_text, reply_markup=kb, parse_mode="HTML")
                        self.states.clear_master_creation_state(user_id)
                    except Exception as e:
                        self.bot.send_message(message.chat.id, f"Ошибка: {e}")
                        
        except Exception as e:
            logger.error(f"Error in handle_master_creation: {e}")
            self.bot.send_message(message.chat.id, "❌ Произошла ошибка при создании мастера.")
            self.states.clear_master_creation_state(user_id)
        finally:
            session.close()
    
    def _handle_manual_master_input_city(self, message: types.Message):
        """Обработать ввод города для мастера вручную"""
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
                    state["step"] = "city_done"  # этап city уже выбран!
                    new_master = User(
                        tg_id=tg_id,
                        name=str(tg_id),
                        full_name=state["data"]["full_name"],
                        phone=state["data"]["phone"],
                        city_id=state["data"]["city_id"],
                        role="master"
                    )
                    existing_user = session.query(User).filter_by(tg_id=tg_id).first()
                    if existing_user:
                        self.bot.send_message(message.chat.id, f"❌ Пользователь с ID {tg_id} уже существует!")
                        self.states.clear_master_creation_state(user_id)
                        return
                    session.add(new_master)
                    session.commit()
                    result_text = f"✅ <b>Мастер создан!</b>\n\n👤 {state['data']['full_name']}\n📱 {state['data']['phone']}\n🆔 {tg_id}\n🏙 ID города: {state['data']['city_id']}\n🔧 Мастер"
                    kb = main_keyboard(get_role(session, user_id))
                    self.bot.send_message(message.chat.id, result_text, reply_markup=kb, parse_mode="HTML")
                    self.states.clear_master_creation_state(user_id)
                except Exception as e:
                    self.bot.send_message(message.chat.id, f"Ошибка: {e}")
        except Exception as e:
            self.bot.send_message(message.chat.id, f"Ошибка создания мастера: {e}")
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
        """Получить список доступных мастеров в зависимости от роли"""
        if role == "dispatcher":
            return session.query(User).filter_by(role="master").all()
        elif role == "director":
            return session.query(User).filter_by(role="master").all()
        else:
            return session.query(User).filter_by(role="master").all()


def register(bot):
    """Регистрация обработчиков (для обратной совместимости)"""
    handlers = UserHandlers(bot)
    handlers.register_handlers()
    return handlers
