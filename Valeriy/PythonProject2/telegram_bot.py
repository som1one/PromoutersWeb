#!/usr/bin/env python3
"""
Telegram бот для управления заявками.
Полная синхронизация с VK ботом, адаптированная под Telegram API.
"""

import os
import logging
import time
from typing import Any, Dict, Optional
from pathlib import Path
import json
from datetime import datetime, timedelta, timezone, time as dt_time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dotenv import load_dotenv

import telebot
from telebot import types

from db import get_session
from model import User, Order, City, Stat, Attendance
from services.user_service import get_role, ensure_user, require_role, generate_order_number
from handlers.utils import get_equip_type_name, get_status_name_ru
from services.commission_service import load_settings, save_settings
from services.dashboard_stats import (
    calculate_dashboard_stats,
    get_period_bounds,
    summarize_dashboard,
)
from _vk.config import DEFAULT_TZ, DEFAULT_TZ_NAME
from _vk.state_manager import user_states
from _vk.services.city import CityCreationFlow
from services.bso_storage import save_bso_from_url, save_bso_from_bytes, find_bso_file

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("TelegramBot")


class TelegramBot:
    """Класс Telegram бота с полной функциональностью, синхронизированной с VK ботом"""
    
    def __init__(self):
        """Инициализация бота"""
        logger.info("🚀 Инициализация Telegram бота...")

        # Загружаем переменные окружения
        try:
            if os.path.exists('local.env'):
                load_dotenv('local.env')
            else:
                load_dotenv()
        except Exception:
            pass

        self.token = os.getenv("TELEGRAM_TOKEN")
        if not self.token:
            raise ValueError("❌ Переменная окружения TELEGRAM_TOKEN не найдена")
            
        self.bot = telebot.TeleBot(self.token, parse_mode="HTML")
        self.logger = logger
        self.states = user_states
        self.city_flow = CityCreationFlow(self, user_states)
        
        # Регистрируем обработчики
        self._register_handlers()
        
        logger.info("✅ Telegram бот успешно инициализирован")

    # ===== 🔧 Служебные =====
    
    def send_message(self, user_id: int, message: str, keyboard: Optional[Any] = None):
        """Отправить сообщение пользователю"""
        try:
            self.bot.send_message(user_id, message, reply_markup=keyboard)
            logger.info(f"📤 Отправлено сообщение пользователю {user_id}")
        except Exception as e:
            logger.exception(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")

    def get_keyboard(self, role: str):
        """Получить клавиатуру по роли"""
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)

        # Универсальное меню для всех ролей (как на скриншоте)
        kb.row(
            types.KeyboardButton("Список заказов"),
            types.KeyboardButton("Доработки")
        )
        kb.row(
            types.KeyboardButton("Долги"),
            types.KeyboardButton("Сдача")
        )
        kb.row(
            types.KeyboardButton("Статистика"),
            types.KeyboardButton("Переносы")
        )
        kb.add(types.KeyboardButton("Помощь"))

        return kb

    def _get_user_info(self, user_id: int):
        """Получить информацию о пользователе Telegram"""
        try:
            user = self.bot.get_chat(user_id)
            return {
                'first_name': user.first_name,
                'last_name': getattr(user, 'last_name', ''),
                'username': getattr(user, 'username', '')
            }
        except Exception:
            logger.exception(f"Ошибка получения информации о пользователе {user_id}")
        return {}

    # ===== 🧠 Логика =====
    
    def _register_handlers(self):
        """Регистрация всех обработчиков"""
        
        @self.bot.message_handler(commands=["start"])
        def cmd_start(message: types.Message):
            self.handle_start(message.from_user.id, get_role(get_session(), message.from_user.id) or "user")
        
        @self.bot.message_handler(commands=["help"])
        def cmd_help(message: types.Message):
            self.handle_help(message.from_user.id)
        
        @self.bot.message_handler(commands=["setrole"])
        def cmd_setrole(message: types.Message):
            session = get_session()
            try:
                role = get_role(session, message.from_user.id) or "user"
                self.handle_setrole(message.from_user.id, message.text, role, session)
            finally:
                session.close()
        
        @self.bot.message_handler(content_types=["text"])
        def handle_text_message(message: types.Message):
            self.handle_message(message)
        
        @self.bot.message_handler(content_types=["photo", "document"])
        def handle_media(message: types.Message):
            self.handle_media(message)
        
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback(call: types.CallbackQuery):
            self.handle_callback(call)
    
    def handle_message(self, message: types.Message):
        """Обработка входящего сообщения"""
        user_id = message.from_user.id
        text = message.text or ""
        text = text.strip()
        
        if not text:
            return
        
        session = get_session()
        try:
            # Создаем объект пользователя для ensure_user
            class TelegramUser:
                def __init__(self, uid, name):
                    self.id = uid
                    self.first_name = name
            
            tg_user = TelegramUser(user_id, message.from_user.first_name or "")
            ensure_user(session, tg_user)
            role = get_role(session, user_id) or "user"
            
            text_lower = text.lower()
            
            # Обработка команд
            if text_lower in ("/start", "старт", "start", "начать"):
                self.handle_start(user_id, role)
            elif text_lower == "/help":
                self.handle_help(user_id)
            elif text_lower.startswith("/setrole"):
                self.handle_setrole(user_id, text, role, session)
            elif text_lower.startswith("/add_city"):
                self._handle_add_city_command(user_id, text, role, session)
            elif text_lower.startswith("/list_cities"):
                self._handle_list_cities(user_id, role, session)
            elif text_lower.startswith("/del_city"):
                self._handle_del_city_command(user_id, text, role, session)
            elif text_lower.startswith("/assign_director"):
                self._handle_assign_director_command(user_id, text, role, session)
            elif text_lower.startswith("/assign_order"):
                self._handle_assign_order_command(user_id, text, role, session)
            elif text_lower.startswith("/seed_cities"):
                self._handle_seed_cities(user_id, text, role, session)
            else:
                self.handle_text(user_id, text, text_lower, role, session)
        finally:
            session.close()
    
    def handle_media(self, message: types.Message):
        """Обработка медиа-файлов (фото/документы)"""
        user_id = message.from_user.id
        session = get_session()
        try:
            role = get_role(session, user_id) or "user"
            
            state = self.states.get_sum_input_state(user_id)
            if not state:
                return
            
            step = state.get("step")
            
            if step == "waiting_bso":
                # Обработка загрузки БСО
                filename = self._save_bso_from_telegram(message, state["order_id"])
                if filename:
                    state["data"]["bso_local_path"] = filename
                    self.states.set_sum_input_state(user_id, state)
                    self.send_message(user_id, "✅ БСО сохранён и прикреплён!")
                    
                    # Проверяем, нужно ли запрашивать чек ЗПЧ
                    zpch_sum = float(state["data"].get("zpch_sum", 0) or 0)
                    if zpch_sum > 0:
                        state["step"] = "waiting_receipt"
                        self.states.set_sum_input_state(user_id, state)
                        self._prompt_receipt_upload(user_id)
                    else:
                        self._calculate_and_show_result(user_id)
                else:
                    self.send_message(user_id, "❌ Не удалось сохранить БСО. Отправьте фото или файл ещё раз.")
            elif step == "waiting_receipt":
                # Обработка загрузки чека ЗПЧ
                receipt_path = self._save_receipt_from_telegram(message, state["order_id"])
                if receipt_path:
                    state["data"]["receipt_local_path"] = receipt_path
                    self.states.set_sum_input_state(user_id, state)
                    self.send_message(user_id, "✅ Чек получен!")
                    self._calculate_and_show_result(user_id)
                else:
                    self.send_message(user_id, "❌ Не удалось сохранить чек. Отправьте фото или файл ещё раз.")
        finally:
            session.close()
    
    def handle_callback(self, call: types.CallbackQuery):
        """Обработка callback-запросов от inline-кнопок"""
        user_id = call.from_user.id
        session = get_session()
        try:
            role = get_role(session, user_id) or "user"
            
            try:
                payload = json.loads(call.data) if isinstance(call.data, str) else call.data
            except Exception:
                payload = {"cmd": call.data} if call.data else {}
            
            if isinstance(payload, dict) and payload.get("cmd"):
                self.handle_payload(user_id, payload, role, session)
        finally:
            session.close()
    
    def handle_start(self, user_id: int, role: str):
        """Обработка команды /start"""
        session = get_session()
        try:
            # Проверяем ADMIN_IDS и устанавливаем роль owner если нужно
            admin_ids = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
            if user_id in admin_ids:
                user = session.query(User).filter_by(tg_id=user_id).first()
                if user and user.role != "owner":
                    user.role = "owner"
                    session.commit()
                    role = "owner"
                    self.send_message(user_id, "✅ Ваша роль автоматически установлена как 'owner'")
        except Exception as e:
            logger.exception(f"Ошибка при проверке ADMIN_IDS: {e}")
        finally:
            session.close()
        
        kb = self.get_keyboard(role)
        user_info = self._get_user_info(user_id)
        user_name = user_info.get('first_name', 'Пользователь')
        msg = (
            f"Привет!\n"
            f"Я - Бот Индустрии. Ваш ID: {user_id}\n"
            f"Включите трансляцию геолокации:\n"
            f"Скрепка -> Геолокация -> Транслировать геолокацию.\n"
            f'"Помощь" - получить инструкцию по работе в новом сервисе.'
        )
        self.send_message(user_id, msg, kb)

    def handle_help(self, user_id: int):
        """Обработка команды /help"""
        msg = (
            "📋 Команды:\n"
            "/start — начать работу\n"
            "/help — помощь\n"
            "/setrole — назначить роль (только owner)\n"
            "  Форматы: /setrole <role> <tg_id> [city_id] | /setrole <tg_id> <role> [city_id]\n"
            "/add_city <name> — добавить город (owner)\n"
            "/list_cities — список городов\n"
            "/del_city <id> — удалить город (owner)\n"
            "/assign_director <tg_id> <city_id> — назначить директора (owner)\n"
            "/assign_order <order_number> <tg_id> — назначить заявку (director/dispatcher/owner)\n"
            "/seed_cities City1,City2 — массовое добавление городов (owner)"
        )
        self.send_message(user_id, msg)
    
    def handle_setrole(self, user_id: int, text: str, role: str, session):
        """Обработка команды /setrole"""
        if role != "owner":
            self.send_message(user_id, "🚫 Только собственник (owner) может назначать роли.")
            return
        
        parts = text.split()
        if len(parts) < 3:
            help_text = (
                "📝 Использование:\n"
                "  /setrole <role> <tg_id> [city_id]  (рекомендуется)\n"
                "  /setrole <tg_id> <role> [city_id]  (поддерживается)\n\n"
                "Примеры:\n"
                "/setrole owner 123456789\n"
                "/setrole director 123456789 1\n"
                "/setrole dispatcher 123456789\n"
                "/setrole master 123456789\n\n"
                "💡 Как получить Telegram ID:\n"
                "1. Откройте @userinfobot в Telegram\n"
                "2. Отправьте ему любое сообщение\n"
                "3. Бот покажет ваш Telegram ID\n\n"
                "Доступные роли: owner, director, dispatcher, master, user"
            )
            self.send_message(user_id, help_text)
            return
        
        try:
            allowed_roles = {"owner", "director", "dispatcher", "master", "user"}
            args = parts[1:]
            # Определяем порядок аргументов
            if args[0].lower() in allowed_roles:
                newrole = args[0].lower()
                tg_id_str = args[1]
                city_id_str = args[2] if len(args) >= 3 else None
            else:
                tg_id_str = args[0]
                newrole = args[1].lower()
                city_id_str = args[2] if len(args) >= 3 else None

            if newrole not in allowed_roles:
                self.send_message(user_id, f"❌ Неверная роль. Доступные: {', '.join(allowed_roles)}")
                return

            tg_id = int(tg_id_str)

            # Создаём/обновляем пользователя
            app_user = session.query(User).filter_by(tg_id=tg_id).first()
            if not app_user:
                app_user = User(tg_id=tg_id, name=str(tg_id), role=newrole)
                session.add(app_user)
            else:
                app_user.role = newrole

            # Обработка city_id для директора
            if newrole == "director" and city_id_str:
                try:
                    city_id = int(city_id_str)
                except ValueError:
                    self.send_message(user_id, "❌ city_id должен быть числом")
                    session.rollback()
                    return
                city = session.query(City).filter_by(id=city_id).first()
                if not city:
                    self.send_message(user_id, f"❌ Город с ID {city_id} не найден")
                    session.rollback()
                    return
                app_user.city_id = city_id
            
            session.commit()
            session.refresh(app_user)
            
            if tg_id == user_id:
                kb = self.get_keyboard(newrole)
                msg = f"✅ Ваша роль изменена на: {newrole}\n\n💡 Отправьте любое сообщение, чтобы обновить меню."
                self.send_message(user_id, msg, kb)
            else:
                try:
                    user_info = self.bot.get_chat(tg_id)
                    user_name = user_info.first_name or str(tg_id)
                except:
                    user_name = str(tg_id)
                
                self.send_message(user_id, f"✅ Роль пользователя {user_name} (ID: {tg_id}) изменена на: {newrole}")
                
        except ValueError:
            self.send_message(user_id, "❌ Telegram ID должен быть числом. Пример: /setrole 123456789 owner")
        except Exception as e:
            logger.exception(f"Ошибка при назначении роли: {e}")
            self.send_message(user_id, f"❌ Ошибка при назначении роли: {e}")

    def _handle_list_cities(self, user_id: int, role: str, session):
        cities = session.query(City).all()
        if not cities:
            self.send_message(user_id, "❌ Города не заданы")
            return
        lines = [f"{i}. {c.name} [ID: {c.id}]" for i, c in enumerate(cities, 1)]
        self.send_message(user_id, "🏙 Города:\n" + "\n".join(lines))

    def _handle_del_city_command(self, user_id: int, text: str, role: str, session):
        if role != "owner":
            self.send_message(user_id, "🚫 Только owner может удалять города.")
            return
        parts = text.split()
        if len(parts) < 2:
            self.send_message(user_id, "📝 Использование: /del_city <id>")
            return
        try:
            city_id = int(parts[1])
        except ValueError:
            self.send_message(user_id, "❌ id должен быть числом")
            return
        city = session.query(City).filter_by(id=city_id).first()
        if not city:
            self.send_message(user_id, "❌ Город не найден")
            return
        # Проверяем наличие зависимостей
        users_cnt = session.query(User).filter_by(city_id=city_id).count()
        orders_cnt = session.query(Order).filter_by(city_id=city_id).count()
        if users_cnt or orders_cnt:
            self.send_message(user_id, "❌ Нельзя удалить: есть связанные пользователи или заявки")
            return
        session.delete(city)
        session.commit()
        self.send_message(user_id, f"✅ Город ID {city_id} удален")

    def _handle_assign_director_command(self, user_id: int, text: str, role: str, session):
        if role != "owner":
            self.send_message(user_id, "🚫 Только owner может назначать директоров.")
            return
        parts = text.split()
        if len(parts) < 3:
            self.send_message(user_id, "📝 Использование: /assign_director <tg_id> <city_id>")
            return
        try:
            tg_id = int(parts[1]); city_id = int(parts[2])
        except ValueError:
            self.send_message(user_id, "❌ tg_id и city_id должны быть числами")
            return
        if not session.query(City).filter_by(id=city_id).first():
            self.send_message(user_id, f"❌ Город с ID {city_id} не найден")
            return
        user = session.query(User).filter_by(tg_id=tg_id).first()
        if not user:
            user = User(tg_id=tg_id, name=str(tg_id))
            session.add(user)
            session.flush()
        user.role = "director"
        user.city_id = city_id
        session.commit()
        self.send_message(user_id, f"✅ Назначен директор: {tg_id} для города ID {city_id}")

    def _handle_add_city_command(self, user_id: int, text: str, role: str, session):
        if role != "owner":
            self.send_message(user_id, "🚫 Только owner может добавлять города.")
            return

        tokens = text.split()
        if len(tokens) < 2:
            self.send_message(user_id, "📝 Использование: /add_city <название> [часовой_пояс]")
            return

        args = tokens[1:]
        tz_candidate = None
        if len(args) >= 2:
            potential_tz = args[-1]
            if "/" in potential_tz or potential_tz.lower() in (
                "default",
                "defaults",
                "по",
                "по_умолчанию",
                "поумолчанию",
                "умолчанию",
                "skip",
                "-",
            ):
                tz_candidate = DEFAULT_TZ_NAME
            else:
                tz_candidate = potential_tz
            city_name = " ".join(args[:-1])
        else:
            city_name = args[0]
            tz_candidate = DEFAULT_TZ_NAME

        try:
            tz = ZoneInfo(tz_candidate) if tz_candidate else DEFAULT_TZ
        except ZoneInfoNotFoundError:
            self.send_message(user_id, f"❌ Неверный часовой пояс: {tz_candidate}. Используется {DEFAULT_TZ_NAME}")
            tz = DEFAULT_TZ

        city = City(name=city_name.strip(), timezone=tz_candidate)
        session.add(city)
        session.commit()
        self.send_message(user_id, f"✅ Город '{city_name}' добавлен (часовой пояс: {tz_candidate})")

    def _handle_assign_order_command(self, user_id: int, text: str, role: str, session):
        if role not in ("director", "dispatcher", "owner"):
            self.send_message(user_id, "🚫 Нет доступа.")
            return
        parts = text.split()
        if len(parts) < 3:
            self.send_message(user_id, "📝 Использование: /assign_order <order_number> <tg_id>")
            return
        try:
            order_number = int(parts[1]); tg_id = int(parts[2])
        except ValueError:
            self.send_message(user_id, "❌ order_number и tg_id должны быть числами")
            return
        order = session.query(Order).filter_by(order_number=order_number).first()
        if not order:
            self.send_message(user_id, f"❌ Заявка #{order_number} не найдена")
            return
        order.assigned_to = tg_id
        order.status = "assigned"
        session.commit()
        self.send_message(user_id, f"✅ Заявка #{order_number} назначена на {tg_id}")

    def _handle_seed_cities(self, user_id: int, text: str, role: str, session):
        if role != "owner":
            self.send_message(user_id, "🚫 Только owner может добавлять города массово.")
            return
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            self.send_message(user_id, "📝 Использование: /seed_cities City1,City2,City3")
            return
        cities_str = parts[1]
        city_names = [c.strip() for c in cities_str.split(",")]
        added = 0
        for name in city_names:
            if name:
                city = City(name=name, timezone=DEFAULT_TZ_NAME)
                session.add(city)
                added += 1
        session.commit()
        self.send_message(user_id, f"✅ Добавлено городов: {added}")

    def handle_text(self, user_id: int, text: str, text_lower: str, role: str, session):
        """Обработка текстовых сообщений"""
        # Проверяем состояние формы создания заявки
        form_state = self.states.get_form_state(user_id)
        if form_state:
            self._handle_form_step(user_id, text, role, session)
            return
        
        # Проверяем состояние ввода сумм
        sum_state = self.states.get_sum_input_state(user_id)
        if sum_state:
            self._handle_sum_input(user_id, text, session)
            return
        
        # Проверяем состояние создания мастера
        master_state = self.states.get_master_creation_state(user_id)
        if master_state:
            self._handle_master_creation_step(user_id, text, role, session)
            return
        
        # Проверяем состояние создания города
        city_state = self.states.get_city_creation_state(user_id)
        if city_state:
            self.city_flow.handle_message(user_id, text, role, session)
            return
        
        # Проверяем состояние редактирования процентов
        equipment_edit_state = self.states.get_equipment_edit_state(user_id)
        if equipment_edit_state and equipment_edit_state.get("step") == "pct":
            self._handle_pct_edit_input(user_id, text, role)
            return
        
        # Обработка кнопок нового меню
        if text == "Список заказов":
            self.handle_my_orders(user_id, role, session)
        elif text == "Доработки":
            self._handle_improvements(user_id, role, session)
        elif text == "Долги":
            self._handle_debts(user_id, role, session)
        elif text == "Сдача":
            if role == "master":
                self.handle_cash(user_id, role, session)
            elif role in ("director", "owner"):
                self._handle_cash_overview(user_id, role, session)
            else:
                self.send_message(user_id, "🚫 У вас нет доступа к этой функции.")
        elif text == "Статистика":
            self.handle_stats(user_id, role, session)
        elif text == "Переносы":
            self._handle_transfers(user_id, role, session)
        elif text == "Помощь":
            self.handle_help(user_id)
        # Старые кнопки для обратной совместимости
        elif text == "✅ На смене":
            self.handle_check_in(user_id, role, session)
        elif text == "➕ Создать заявку" or text == "➕ Новая заявка":
            self._start_form(user_id, role, session)
        elif text == "📋 Мои заявки":
            self.handle_my_orders(user_id, role, session)
        elif text in ("📊 Статистика", "📊 Стата"):
            self.handle_stats(user_id, role, session)
        elif text == "👥 Управление мастерами":
            self._handle_manage_masters(user_id, role, session)
        elif text == "📦 Мои СД":
            self.handle_my_sd(user_id, role, session)
        elif text == "💰 Касса":
            self.handle_cash(user_id, role, session)
        elif text in ("💼 Касса", "Касса"):
            self._handle_cash_overview(user_id, role, session)
        elif text == "🔄 Обновить":
            kb = self.get_keyboard(role)
            self.send_message(user_id, "🔄 Обновлено!", kb)
        elif text == "⚙️ Админ-панель":
            self._handle_admin_panel_entry(user_id, role, session)
        elif text == "👤 Добавить мастера":
            self._start_add_master(user_id, role, session)
        elif text == "📦 СД":
            self._handle_director_sd(user_id, role, session)
        elif text == "🏙 Добавить город":
            self.city_flow.start(user_id, role, session)
        else:
            # Неизвестная команда
            pass

    # Продолжение следует - остальные методы будут добавлены в следующем сообщении
    # Для экономии места здесь только базовая структура

    def _save_bso_from_telegram(self, message: types.Message, order_id: int) -> Optional[str]:
        """Сохранить БСО из Telegram сообщения"""
        try:
            if message.photo:
                # Получаем фото в максимальном размере
                file_id = message.photo[-1].file_id
                file_info = self.bot.get_file(file_id)
                file_url = f"https://api.telegram.org/file/bot{self.token}/{file_info.file_path}"
                return save_bso_from_url(order_id, file_url)
            elif message.document:
                file_id = message.document.file_id
                file_info = self.bot.get_file(file_id)
                file_url = f"https://api.telegram.org/file/bot{self.token}/{file_info.file_path}"
                return save_bso_from_url(order_id, file_url)
        except Exception as e:
            logger.error(f"❌ Не удалось сохранить БСО из Telegram для заявки {order_id}: {e}")
        return None

    def _save_receipt_from_telegram(self, message: types.Message, order_id: int) -> Optional[str]:
        """Сохранить чек из Telegram сообщения"""
        try:
            from pathlib import Path
            import requests
            
            storage_dir = Path("/app/data/receipts")
            storage_dir.mkdir(parents=True, exist_ok=True)
            
            if message.photo:
                file_id = message.photo[-1].file_id
            elif message.document:
                file_id = message.document.file_id
            else:
                return None
            
            file_info = self.bot.get_file(file_id)
            file_url = f"https://api.telegram.org/file/bot{self.token}/{file_info.file_path}"
            
            response = requests.get(file_url, timeout=30)
            response.raise_for_status()
            
            ext = Path(file_info.file_path).suffix or ".jpg"
            filename = f"receipt_{order_id}_{int(time.time())}{ext}"
            file_path = storage_dir / filename
            
            with open(file_path, "wb") as f:
                f.write(response.content)
            
            return str(file_path)
        except Exception as e:
            logger.error(f"❌ Не удалось сохранить чек из Telegram для заявки {order_id}: {e}")
        return None

    def _handle_sum_input(self, user_id: int, text: str, session):
        """Обработка ввода сумм"""
        state = self.states.get_sum_input_state(user_id)
        if not state:
            return
        step = state.get("step")
        t = text.strip()
        if step == "waiting_bso":
            self.send_message(user_id, "📄 Отправьте фото или файл БСО (договор/квитанция/акт выполненных работ):")
            return
        if step == "waiting_receipt":
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("⏭ Пропустить чек", callback_data=json.dumps({"cmd": "skip_receipt"})))
            self.send_message(user_id, "📷 Отправьте фото чека на расходы (ЗПЧ) или нажмите 'Пропустить чек':", kb)
            return
        try:
            if step == "order_sum":
                order_sum = float(t)
                state["data"]["order_sum"] = order_sum
                state["data"].setdefault("sd_price", 0.0)
                state["data"].setdefault("receipt_local_path", None)
                state["data"].setdefault("receipt_file_id", None)
                state["step"] = "paid_amount"
                self.states.set_sum_input_state(user_id, state)
                self.send_message(user_id, f"✅ Сумма заказа: {order_sum:.2f}\n\n💰 Введите сколько забрали (оплатили):", self._kb_sum_cancel())
                return
            if step == "paid_amount":
                paid_amount = float(t)
                order_sum = float(state["data"].get("order_sum", 0) or 0)
                if paid_amount > order_sum:
                    self.send_message(user_id, f"❌ Оплаченная сумма ({paid_amount:.2f}) не может быть больше суммы заказа ({order_sum:.2f}). Введите корректную сумму:", self._kb_sum_cancel())
                    return
                state["data"]["paid_amount"] = paid_amount
                debt_amount = order_sum - paid_amount
                state["data"]["debt_amount"] = debt_amount
                
                if debt_amount > 0:
                    state["step"] = "debt_payment_date"
                    self.states.set_sum_input_state(user_id, state)
                    self.send_message(user_id, f"✅ Оплачено: {paid_amount:.2f} руб.\n⚠️ Долг: {debt_amount:.2f} руб.\n\n📅 Введите дату погашения долга (ДД.ММ.ГГГГ):", self._kb_sum_cancel())
                else:
                    state["step"] = "zpch_sum"
                    self.states.set_sum_input_state(user_id, state)
                    self.send_message(user_id, f"✅ Оплачено: {paid_amount:.2f} руб.\n\n💰 Введите сумму ЗПЧ:", self._kb_zpch_zero())
                return
            if step == "debt_payment_date":
                try:
                    debt_date = datetime.strptime(t, "%d.%m.%Y")
                    state["data"]["debt_payment_date"] = debt_date
                    state["step"] = "zpch_sum"
                    self.states.set_sum_input_state(user_id, state)
                    self.send_message(user_id, f"✅ Дата погашения долга: {debt_date.strftime('%d.%m.%Y')}\n\n💰 Введите сумму ЗПЧ:", self._kb_zpch_zero())
                except ValueError:
                    self.send_message(user_id, "❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ (например, 25.12.2024):", self._kb_sum_cancel())
                return
            if step == "zpch_sum":
                zpch_sum = float(t)
                state["data"]["zpch_sum"] = zpch_sum
                state["data"]["sd_price"] = state["data"].get("sd_price", 0)
                state["step"] = "waiting_bso"
                self.states.set_sum_input_state(user_id, state)
                self.send_message(user_id, f"✅ ЗПЧ: {zpch_sum:.2f}")
                self._prompt_bso_upload(user_id)
                return
            if step == "sd_price":
                sd_price = float(t)
                state["data"]["sd_price"] = sd_price
                zpch_sum = float(state["data"].get("zpch_sum", 0) or 0)
                if zpch_sum > 0:
                    state["step"] = "waiting_receipt"
                    self.states.set_sum_input_state(user_id, state)
                    self._prompt_receipt_upload(user_id)
                else:
                    self._calculate_and_show_result(user_id)
                return
        except ValueError:
            self.send_message(user_id, "❌ Введите корректное число")

    def _calculate_and_show_result(self, user_id: int):
        """Рассчитать и показать результат закрытия заявки"""
        state = self.states.get_sum_input_state(user_id)
        if not state:
            return
        order_id = state["order_id"]
        order_sum = float(state["data"].get("order_sum", 0) or 0)
        paid_amount = float(state["data"].get("paid_amount", order_sum) or order_sum)
        debt_amount = float(state["data"].get("debt_amount", 0) or 0)
        debt_payment_date = state["data"].get("debt_payment_date")
        zpch_sum = float(state["data"].get("zpch_sum", 0) or 0)
        sd_price = float(state["data"].get("sd_price", 0) or 0)
        session = get_session()
        try:
            order = session.query(Order).filter_by(id=order_id).first()
            if not order:
                self.send_message(user_id, "❌ Заявка не найдена")
                return
            
            net_amount = max(order_sum - zpch_sum, 0)
            
            master = None
            if order.assigned_to:
                master = session.query(User).filter_by(tg_id=order.assigned_to).first()
            
            if master and master.master_percentage is not None:
                master_pct = float(master.master_percentage)
            else:
                try:
                    from services.commission_service import get_master_pct
                    master_pct = get_master_pct(order.equip_type, net_amount)
                except Exception:
                    master_pct = 40.0
            master_share = net_amount * (master_pct / 100.0)
            company_sum = max(net_amount - master_share, 0)
            order.sum_amount = order_sum
            order.paid_amount = paid_amount
            order.debt_amount = debt_amount if debt_amount > 0 else None
            order.debt_payment_date = debt_payment_date
            order.sd_price = sd_price
            try:
                setattr(order, 'zpch_sum', float(zpch_sum))
            except Exception:
                pass
            bso_local_path = state["data"].get("bso_local_path")
            if bso_local_path:
                order.bso_file_path = bso_local_path
            receipt_local_path = state["data"].get("receipt_local_path")
            if receipt_local_path:
                order.receipt_file_path = receipt_local_path
            else:
                order.receipt_file_path = None
            order.status = "done_pending_sum"
            session.commit()
            bso_status = "✅ Прикреплен" if bso_local_path else "❌ Не прикреплен"
            receipt_status = "✅ Прикреплен" if receipt_local_path else ("⏭ Пропущен" if zpch_sum > 0 else "—")
            result_text = (
                f"📊 Итог:\n\n"
                f"💰 Сумма заказа: {order_sum:.2f}\n"
            )
            if debt_amount > 0:
                result_text += f"💵 Оплачено: {paid_amount:.2f}\n"
                result_text += f"⚠️ Долг: {debt_amount:.2f}\n"
                if debt_payment_date:
                    result_text += f"📅 Дата погашения: {debt_payment_date.strftime('%d.%m.%Y')}\n"
            result_text += (
                f"🔧 ЗПЧ: {zpch_sum:.2f}\n"
                f"🧮 Чистый чек: {net_amount:.2f}\n"
                f"👨‍🔧 Доля мастера ({master_pct}%): {master_share:.2f}\n"
                f"🏢 Доля компании: {company_sum:.2f}\n"
                f"📄 БСО: {bso_status}\n"
                f"📷 Чек ЗПЧ: {receipt_status}\n\n"
                f"📋 Заявка #{order.order_number} готова к закрытию"
            )
            self.send_message(user_id, result_text, self._kb_close_order(order_id))
            self.states.clear_sum_input_state(user_id)
        finally:
            session.close()

    def _prompt_bso_upload(self, user_id: int):
        """Запросить загрузку БСО"""
        state = self.states.get_sum_input_state(user_id)
        if not state:
            return
        
        order_sum = float(state["data"].get("order_sum", 0) or 0)
        if order_sum < 5000:
            state["data"]["bso_local_path"] = None
            self.states.set_sum_input_state(user_id, state)
            
            zpch_sum = float(state["data"].get("zpch_sum", 0) or 0)
            if zpch_sum > 0:
                state["step"] = "waiting_receipt"
                self.states.set_sum_input_state(user_id, state)
                self.send_message(user_id, "✅ БСО пропущен (сумма заявки менее 5000 руб.)")
                self._prompt_receipt_upload(user_id)
            else:
                self.send_message(user_id, "✅ БСО пропущен (сумма заявки менее 5000 руб.)")
                self._calculate_and_show_result(user_id)
            return
        
        self.send_message(user_id, "📄 Отправьте фото или файл БСО (договор/квитанция/акт выполненных работ).")

    def _prompt_receipt_upload(self, user_id: int):
        """Запросить загрузку чека"""
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⏭ Пропустить чек", callback_data=json.dumps({"cmd": "skip_receipt"})))
        self.send_message(user_id, "📷 Отправьте фото или файл чека на расходы (ЗПЧ) или нажмите 'Пропустить чек':", kb)

    # ===== Вспомогательные методы =====
    
    def _get_city_director(self, city_id: Optional[int], session):
        """Получить директора города"""
        if not city_id:
            return None
        return session.query(User).filter_by(role="director", city_id=city_id).first()

    def _get_timezone_for_city(self, city: Optional[City]) -> ZoneInfo:
        """Получить часовой пояс для города"""
        tz_name = None
        if city:
            tz_name = getattr(city, "timezone", None)
        if tz_name:
            try:
                return ZoneInfo(tz_name)
            except ZoneInfoNotFoundError:
                logger.warning(f"Не удалось загрузить таймзону '{tz_name}', используем по умолчанию ({DEFAULT_TZ_NAME})")
            except Exception as e:
                logger.warning(f"Не удалось загрузить таймзону '{tz_name}' ({e}), используем по умолчанию.")
        return DEFAULT_TZ

    def _format_local_datetime(self, dt: Optional[datetime], tz: ZoneInfo) -> str:
        """Форматировать дату/время в локальном часовом поясе"""
        if not dt:
            return "-"
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.astimezone(tz).strftime("%d.%m.%Y %H:%M")

    def _build_order_preview(self, data: dict, session) -> str:
        """Построить превью заявки для подтверждения"""
        city = session.query(City).filter_by(id=data.get("city_id")).first()
        city_name = city.name if city else "-"
        assigned_label = "не назначен"
        if data.get("assigned_to"):
            user = session.query(User).filter_by(tg_id=data["assigned_to"]).first()
            if user:
                assigned_label = user.full_name or user.name or str(user.tg_id)
            else:
                assigned_label = str(data["assigned_to"])
        equip_name = get_equip_type_name(data.get("equip_type"))
        return (
            f"📋 Подтвердите создание заявки:\n"
            f"🏙 {city_name}\n"
            f"📍 {data.get('street','-')}, {data.get('house','-')}\n"
            f"Кв.: {data.get('flat','')}\n"
            f"⏰ {data.get('time_from','')} - {data.get('time_to','')}\n"
            f"🔧 {equip_name}\n"
            f"📝 {data.get('short_desc','')}\n"
            f"👤 Клиент: {data.get('client_name','')} ({data.get('client_phone','')})\n"
            f"💬 Комментарий: {data.get('comment','')}\n"
            f"📞 Источник: {data.get('source','')}\n"
            f"👤 Ответственный: {assigned_label}\n\n"
            "Ответьте: 'да' для создания или 'нет' для отмены"
        )

    def _format_order_details(self, order, master_name: Optional[str] = None, hide_phone: bool = False) -> str:
        """Сформировать подробную информацию по заявке"""
        equip_type_name = get_equip_type_name(order.equip_type)
        city_name = order.city_rel.name if order.city_rel else "Не указан"
        address_line = f"ул. {order.street or '-'}, д.{order.house or '-'}"
        if order.flat:
            address_line += f", кв.{order.flat}"
        time_window = ""
        if order.time_from or order.time_to:
            time_window = f"{order.time_from or '-'} - {order.time_to or '-'}"
        tz = self._get_timezone_for_city(order.city_rel)
        client_info = ""
        if not hide_phone:
            client_name = getattr(order, "client_name", None) or "Не указан"
            client_phone = getattr(order, "client_phone", None) or "Не указан"
            client_info = f"👤 Клиент: {client_name} ({client_phone})"
        master_line = ""
        if master_name:
            master_line = f"🔧 Мастер: {master_name}"
        sum_amount = float(getattr(order, "sum_amount", 0) or 0)
        sd_price = float(getattr(order, "sd_price", 0) or 0)
        zpch_sum = float(getattr(order, "zpch_sum", 0) or 0)
        net_amount = max(sum_amount - zpch_sum, 0)
        has_receipt = bool(getattr(order, "receipt_file_id", None) or getattr(order, "receipt_file_path", None))
        receipt_status = "✅ Есть" if has_receipt else "❌ Нет"
        created = self._format_local_datetime(getattr(order, "created_at", None), tz)
        lines = [
            f"📋 Заявка #{order.order_number}",
            f"🏙 Город: {city_name}",
            f"📍 Адрес: {address_line}",
        ]
        if time_window:
            lines.append(f"⏰ Окно: {time_window}")
        if client_info:
            lines.append(client_info)
        if master_line:
            lines.append(master_line)
        lines.extend([
            f"🔧 Тип: {equip_type_name}",
            f"📊 Статус: {get_status_name_ru(order.status)}",
            f"📅 Создана: {created}",
            f"💰 Сумма закрытия: {sum_amount:.2f}",
            f"🔩 ЗПЧ: {zpch_sum:.2f}",
            f"🧮 Чистый чек: {net_amount:.2f}",
            f"📷 Фото чека: {receipt_status}",
        ])
        comment = getattr(order, "comment", None)
        if comment:
            lines.append(f"💬 Комментарий: {comment}")
        return "\n".join([line for line in lines if line])

    def _send_receipt_if_exists(self, user_id: int, order):
        """Отправить прикреплённый чек, если есть"""
        receipt_path = getattr(order, "receipt_file_path", None)
        if receipt_path and os.path.exists(receipt_path):
            try:
                with open(receipt_path, "rb") as f:
                    self.bot.send_document(user_id, f, caption="📷 Фото чека")
                return
            except Exception as e:
                logger.warning(f"Не удалось отправить чек по пути {receipt_path}: {e}")

    def _notify_master_telegram(self, order: Order, session):
        """Уведомить мастера о новой заявке"""
        try:
            if order.assigned_to:
                equip = get_equip_type_name(order.equip_type)
                city_name = order.city_rel.name if order.city_rel else "Не указан"
                
                msg = (
                    f"🎯 Вам назначена новая заявка №{order.order_number}\n\n"
                    f"🏙 Город: {city_name}\n"
                    f"⏰ Время: {order.time_from} - {order.time_to}\n"
                    f"📍 Адрес: ул. {order.street}, дом {order.house}, кв. {order.flat or '-'}\n"
                    f"🔧 Техника: {equip}\n"
                )
                
                if order.short_desc:
                    msg += f"📝 Описание: {order.short_desc}\n"
                
                client_name = order.client_name if order.client_name else "Не указано"
                msg += f"👤 Клиент: {client_name}\n"
                
                if order.source:
                    msg += f"📞 Источник: {order.source}\n"
                
                if order.comment:
                    msg += f"💬 Комментарий: {order.comment}\n"
                
                kb = self._kb_master_new_order(order.id)
                self.send_message(order.assigned_to, msg, kb)
        except Exception as e:
            logger.warning(f"Не удалось уведомить мастера {order.assigned_to}: {e}")

    def _notify_director_new_order(self, order, director):
        """Уведомить директора о новой заявке"""
        try:
            city_name = order.city_rel.name if order.city_rel else "Не указан"
            equip = get_equip_type_name(order.equip_type)
            
            text = (
                f"🆕 Новая заявка №{order.order_number}\n\n"
                f"🏙 Город: {city_name}\n"
                f"⏰ Время: {order.time_from} - {order.time_to}\n"
                f"📍 Адрес: ул. {order.street}, дом {order.house}, кв. {order.flat or '-'}\n"
                f"🔧 Техника: {equip}\n"
            )
            
            if order.short_desc:
                text += f"📝 Описание: {order.short_desc}\n"
            
            text += f"👤 Клиент: {order.client_name or 'Не указано'}\n"
            
            if order.source:
                text += f"📞 Источник: {order.source}\n"
            
            if order.comment:
                text += f"💬 Комментарий: {order.comment}\n"
            
            text += "\n👉 Вы можете назначить мастера или взять заявку на себя."
            
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("✅ Взять себе", callback_data=json.dumps({"cmd": "take_order", "order_id": order.id})))
            kb.add(types.InlineKeyboardButton("👤 Назначить мастеру", callback_data=json.dumps({"cmd": "assign_menu", "order_id": order.id})))
            
            self.send_message(director.tg_id, text, kb)
        except Exception as e:
            logger.warning(f"Не удалось уведомить директора {director.tg_id}: {e}")

    # ===== Клавиатуры =====
    
    def _kb_equip_type(self):
        """Клавиатура для выбора типа техники"""
        from handlers.menu_kb import EQUIP_TYPES
        kb = types.InlineKeyboardMarkup()
        # Добавляем кнопки по 2 в ряд
        for i in range(0, len(EQUIP_TYPES), 2):
            row = []
            name, code = EQUIP_TYPES[i]
            row.append(types.InlineKeyboardButton(name, callback_data=json.dumps({"cmd": "select_equip_type", "equip_type": code})))
            if i + 1 < len(EQUIP_TYPES):
                name, code = EQUIP_TYPES[i + 1]
                row.append(types.InlineKeyboardButton(name, callback_data=json.dumps({"cmd": "select_equip_type", "equip_type": code})))
            kb.add(*row)
        return kb

    def _kb_master_selection(self, masters, session):
        """Клавиатура для выбора мастера из списка"""
        kb = types.InlineKeyboardMarkup()
        for master in masters[:10]:  # Ограничиваем до 10 мастеров
            display_name = master.full_name or master.name or str(master.tg_id)
            city_info = f" ({master.city_rel.name})" if master.city_rel else ""
            button_text = f"🔧 {display_name}{city_info}"
            if len(button_text) > 40:
                button_text = button_text[:37] + "..."
            kb.add(types.InlineKeyboardButton(button_text, callback_data=json.dumps({"cmd": "select_master", "master_id": master.tg_id})))
        kb.add(types.InlineKeyboardButton("⏭ Пропустить", callback_data=json.dumps({"cmd": "skip_master"})))
        return kb

    def _kb_close_order(self, order_id: int):
        """Клавиатура для закрытия заявки"""
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ Закрыть заявку", callback_data=json.dumps({"cmd": "close_order", "order_id": order_id})))
        return kb

    def _kb_zpch_zero(self):
        """Клавиатура для установки ЗПЧ = 0"""
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("ЗПЧ = 0", callback_data=json.dumps({"cmd": "zpch_zero"})))
        return kb

    def _kb_sum_cancel(self):
        """Клавиатура отмены (пустая)"""
        return None

    def _kb_master_new_order(self, order_id: int):
        """Клавиатура для новой заявки мастера"""
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ Принять", callback_data=json.dumps({"cmd": "accept", "order_id": order_id})))
        return kb

    def _kb_master_on_way(self, order_id: int):
        """Клавиатура: мастер в пути"""
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🚗 В пути", callback_data=json.dumps({"cmd": "onway", "order_id": order_id})))
        return kb

    def _kb_master_ready(self, order_id: int):
        """Клавиатура: либо забрал на СД, либо готово"""
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("📦 Забрал на СД", callback_data=json.dumps({"cmd": "to_sd", "order_id": order_id})))
        kb.add(types.InlineKeyboardButton("⚡ Готово", callback_data=json.dumps({"cmd": "ready", "order_id": order_id})))
        return kb

    def _kb_sd_ready(self, order_id: int):
        """Клавиатура для закрытия заявки из раздела СД"""
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⚡ Готово", callback_data=json.dumps({"cmd": "ready", "order_id": order_id})))
        kb.add(types.InlineKeyboardButton("✅ Закрыть СД", callback_data=json.dumps({"cmd": "close_sd", "order_id": order_id})))
        return kb

    def _kb_pct_main(self):
        """Клавиатура главного меню процентов"""
        kb = types.InlineKeyboardMarkup()
        settings = load_settings()
        for cat in settings.keys():
            kb.add(types.InlineKeyboardButton(cat, callback_data=json.dumps({"cmd": "pct_cat", "cat": cat})))
        kb.add(types.InlineKeyboardButton("Закрыть", callback_data=json.dumps({"cmd": "pct_close"})))
        return kb

    def _kb_pct_cat(self, cat: str):
        """Клавиатура для категории процентов"""
        kb = types.InlineKeyboardMarkup()
        settings = load_settings()
        tiers = (settings.get(cat) or {}).get("tiers", [])
        for idx, t in enumerate(tiers):
            lo, hi, pct = t
            range_str = f"{lo}-{hi}" if hi is not None else f"{lo}+"
            kb.add(types.InlineKeyboardButton(
                f"Изм. {idx+1} ({range_str}: {pct}%)",
                callback_data=json.dumps({"cmd": "pct_tier", "cat": cat, "tier": idx})
            ))
        kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data=json.dumps({"cmd": "pct_menu"})))
        return kb

    def _get_local_day_bounds(self, local_date, tz: ZoneInfo):
        """Получить границы дня в UTC"""
        start_local = datetime.combine(local_date, dt_time.min, tzinfo=tz)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = (start_local + timedelta(days=1)).astimezone(timezone.utc)
        return start_utc, end_utc

    def _render_order(self, order: Order) -> str:
        """Отформатировать заявку для отображения"""
        equip_type_name = get_equip_type_name(order.equip_type)
        city_name = order.city_rel.name if order.city_rel else "Не указан"
        client_name = order.client_name if order.client_name else "Не указано"
        text = (
            f"📋 Номер: {order.order_number}\n"
            f"🏙 Город: {city_name}\n"
            f"⏰ Время: {order.time_from} - {order.time_to}\n"
            f"📍 Адрес: ул. {order.street}, дом {order.house}, кв. {order.flat or '-'}\n"
            f"🔧 Техника: {equip_type_name}\n"
            f"👤 Клиент: {client_name}\n"
            f"📝 Описание: {order.short_desc}"
        )
        return text

    def _show_pct_menu(self, user_id: int):
        """Показать меню процентов"""
        kb = self._kb_pct_main()
        settings = load_settings()
        msg = "📊 Выберите категорию для редактирования процентов:\n\n"
        for cat, conf in settings.items():
            title = conf.get("title", cat)
            tiers_count = len(conf.get("tiers", []))
            msg += f"• {title} ({tiers_count} порогов)\n"
        self.send_message(user_id, msg, kb)

    def _show_pct_cat(self, user_id: int, cat: str):
        """Показать категорию процентов"""
        settings = load_settings()
        conf = settings.get(cat) or {}
        title = conf.get("title", cat)
        tiers = conf.get("tiers", [])
        lines = [f"{i+1}) {(str(lo) if lo is not None else '0')} - {(str(hi) if hi is not None else '+')} : {pct}%" for i, (lo, hi, pct) in enumerate(tiers)]
        text = f"📈 {title} ({cat})\n\n" + ("\n".join(lines) if lines else "Нет порогов")
        kb = self._kb_pct_cat(cat)
        self.send_message(user_id, text, kb)

    # ===== Создание заявки =====
    
    def _start_form(self, user_id: int, role: str, session):
        """Начать создание заявки"""
        if not require_role(session, user_id, ("dispatcher", "owner")):
            self.send_message(user_id, "🚫 Только диспетчер и собственник могут создавать заявки.")
            return
        cities = session.query(City).all()
        if not cities:
            self.send_message(user_id, "❌ Нет городов! Обратитесь к администратору.")
            return
        self.states.set_form_state(user_id, {"step": "city", "data": {}})
        city_lines = "\n".join([f"{c.id} — {c.name}" for c in cities])
        self.send_message(user_id, "🏙 Укажите город (ID или название):\n" + city_lines)

    def _handle_form_step(self, user_id: int, text: str, role: str, session):
        """Обработка шагов формы создания заявки"""
        state = self.states.get_form_state(user_id)
        if not isinstance(state, dict):
            state = {}
        step = state.get("step")
        data = state.get("data") or {}
        if not isinstance(data, dict):
            logger.warning("Форма: некорректные данные state['data']=%r (user_id=%s). Сбрасываем.", data, user_id)
            data = {}
        state["data"] = data
        t_original = text.strip()
        t = t_original.lower()

        logger.info("Форма Telegram (user_id=%s): step=%s, text=%r", user_id, step, t_original)
        
        # Проверка на отмену формы
        if t in ("отмена", "cancel", "отменить", "стоп", "/cancel"):
            self.states.clear_form_state(user_id)
            kb = self.get_keyboard(role)
            self.send_message(user_id, "❌ Создание заявки отменено.", kb)
            return
        
        if not step:
            self.states.clear_form_state(user_id)
            self.send_message(user_id, "❌ Произошла ошибка при заполнении формы. Пожалуйста, начните заново.")
            return
        
        if step == "city":
            city = None
            try:
                city_id = int(t_original)
                city = session.query(City).filter_by(id=city_id).first()
            except ValueError:
                try:
                    city = session.query(City).filter(City.name.ilike(f"%{t_original}%")).first()
                    if not city:
                        city = session.query(City).filter(City.name.ilike(t_original)).first()
                except Exception:
                    all_cities = session.query(City).all()
                    t_lower = t_original.lower()
                    for c in all_cities:
                        if c.name and t_lower in c.name.lower():
                            city = c
                            break
            
            if not city:
                cities = session.query(City).all()
                if cities:
                    city_lines = "\n".join([f"{c.id} — {c.name}" for c in cities])
                    self.send_message(user_id, f"❌ Город '{t_original}' не найден.\n\n🏙 Доступные города:\n{city_lines}\n\nВведите ID или название города:\n💡 Для отмены напишите 'отмена'")
                else:
                    self.send_message(user_id, "❌ Нет городов в системе. Обратитесь к администратору.")
                self.states.clear_form_state(user_id)
                return
            
            data["city_id"] = city.id
            state.update({"step": "street", "data": data})
            self.states.set_form_state(user_id, state)
            self.send_message(user_id, f"✅ Выбран город: {city.name}\n\n📍 Укажите улицу:")
            return
        
        if step == "street":
            data["street"] = t_original
            state.update({"step": "house", "data": data})
            self.states.set_form_state(user_id, state)
            self.send_message(user_id, "🏠 Укажите дом:\n💡 Для отмены напишите 'отмена'")
            return
        
        if step == "house":
            data["house"] = t_original
            state.update({"step": "flat", "data": data})
            self.states.set_form_state(user_id, state)
            self.send_message(user_id, "🏢 Укажите квартиру (или '-' если нет):\n💡 Для отмены напишите 'отмена'")
            return
        
        if step == "flat":
            data["flat"] = (t_original if t != "-" else "")
            state.update({"step": "time_from", "data": data})
            self.states.set_form_state(user_id, state)
            self.send_message(user_id, "⏰ Укажите время с (например 09:00):\n💡 Для отмены напишите 'отмена'")
            return
        
        if step == "time_from":
            data["time_from"] = t_original
            state.update({"step": "time_to", "data": data})
            self.states.set_form_state(user_id, state)
            self.send_message(user_id, "⏰ Укажите время до (например 18:00):\n💡 Для отмены напишите 'отмена'")
            return
        
        if step == "time_to":
            data["time_to"] = t_original
            state.update({"step": "equip_type", "data": data})
            self.states.set_form_state(user_id, state)
            kb = self._kb_equip_type()
            self.send_message(user_id, "🔧 Выберите тип техники:", kb)
            return
        
        if step == "equip_type":
            code = t_original
            from handlers.menu_kb import EQUIP_TYPES
            names = {name.lower(): code for name, code in EQUIP_TYPES}
            codes_map = {code.lower(): code for _, code in EQUIP_TYPES}
            if t in names:
                code = names[t]
            elif t in codes_map:
                code = codes_map[t]
            data["equip_type"] = code
            state.update({"step": "short_desc", "data": data})
            self.states.set_form_state(user_id, state)
            self.send_message(user_id, "📝 Кратко опишите проблему:\n💡 Для отмены напишите 'отмена'")
            return
        
        if step == "short_desc":
            data["short_desc"] = t_original
            state.update({"step": "client_name", "data": data})
            self.states.set_form_state(user_id, state)
            self.send_message(user_id, "👤 Имя клиента:\n💡 Для отмены напишите 'отмена'")
            return
        
        if step == "client_name":
            data["client_name"] = t_original
            state.update({"step": "client_phone", "data": data})
            self.states.set_form_state(user_id, state)
            self.send_message(user_id, "📱 Телефон клиента:\n💡 Для отмены напишите 'отмена'")
            return
        
        if step == "client_phone":
            data["client_phone"] = t_original
            state.update({"step": "comment", "data": data})
            self.states.set_form_state(user_id, state)
            self.send_message(user_id, "💬 Комментарий (или '-' если нет):\n💡 Для отмены напишите 'отмена'")
            return
        
        if step == "comment":
            data["comment"] = (t_original if t != "-" else "")
            state.update({"step": "source", "data": data})
            self.states.set_form_state(user_id, state)
            self.send_message(user_id, "📞 Источник (например Яндекс/сайт/имя):\n💡 Для отмены напишите 'отмена'")
            return
        
        if step == "source":
            data["source"] = t_original
            if role == "dispatcher":
                director = self._get_city_director(data.get("city_id"), session)
                if director:
                    data["assigned_to"] = director.tg_id
                    state.update({"step": "confirm", "data": data})
                    self.states.set_form_state(user_id, state)
                    preview = self._build_order_preview(data, session)
                    self.send_message(user_id, preview)
                    return
                else:
                    self.send_message(user_id, "⚠️ Для этого города не найден директор. Укажите Telegram ID ответственного вручную или '-' чтобы пропустить.")
            state.update({"step": "assign", "data": data})
            self.states.set_form_state(user_id, state)
            masters = session.query(User).filter_by(role="master").all()
            if masters:
                kb = self._kb_master_selection(masters, session)
                self.send_message(user_id, "👤 Выберите мастера из списка или пропустите:", kb)
            else:
                self.send_message(user_id, "👤 Мастера не найдены. Назначить мастера позже?\nВведите Telegram ID мастера или '-' чтобы пропустить:")
            return
        
        if step == "assign":
            assigned_to = None
            if t_original.strip() and t_original.strip() != "-":
                try:
                    assigned_to = int(t_original.strip())
                except ValueError:
                    self.send_message(user_id, "❌ Введите числовой Telegram ID мастера или '-' чтобы пропустить:\n💡 Для отмены напишите 'отмена'")
                    return
            data["assigned_to"] = assigned_to
            preview = self._build_order_preview(data, session)
            state.update({"step": "confirm", "data": data})
            self.states.set_form_state(user_id, state)
            self.send_message(user_id, preview)
            return
        
        if step == "confirm":
            if t not in ("да", "нет"):
                self.send_message(user_id, "Введите 'да' для создания или 'нет' для отмены")
                return
            if t == "нет":
                self.states.clear_form_state(user_id)
                kb = self.get_keyboard(role)
                self.send_message(user_id, "❌ Создание заявки отменено.", kb)
                return
            try:
                order = Order(
                    order_number=generate_order_number(session),
                    city_id=data.get("city_id"),
                    street=data.get("street"),
                    house=data.get("house"),
                    flat=data.get("flat", ""),
                    time_from=data.get("time_from", ""),
                    time_to=data.get("time_to", ""),
                    equip_type=data.get("equip_type"),
                    short_desc=data.get("short_desc"),
                    source=data.get("source", "telegram"),
                    created_by=user_id,
                    assigned_to=data.get("assigned_to"),
                    client_name=data.get("client_name"),
                    client_phone=data.get("client_phone"),
                    comment=data.get("comment", ""),
                )
                if order.assigned_to:
                    order.status = "assigned"
                session.add(order)
                session.commit()
                if order.assigned_to:
                    assigned_user = session.query(User).filter_by(tg_id=order.assigned_to).first()
                    if assigned_user:
                        if assigned_user.role == "master":
                            self._notify_master_telegram(order, session)
                        elif assigned_user.role == "director":
                            self._notify_director_new_order(order, assigned_user)
                self.states.clear_form_state(user_id)
                self.send_message(user_id, f"✅ Заявка создана! №{order.order_number}")
                kb = self.get_keyboard(role)
                self.send_message(user_id, "🏠 Главное меню:", kb)
            except Exception:
                logger.exception("Ошибка при создании заявки")
                self.send_message(user_id, "❌ Не удалось создать заявку. Проверьте данные и попробуйте еще раз.")
                return

    def _handle_pct_edit_input(self, user_id: int, text: str, role: str):
        """Обработка ввода процента для редактирования"""
        if role != "owner":
            self.send_message(user_id, "🚫 Нет доступа.")
            return
        state = self.states.get_equipment_edit_state(user_id)
        if not state:
            return
        cat = state.get("cat")
        tier_idx = state.get("tier")
        try:
            pct = float(text.strip().replace(',', '.'))
            if not (0 <= pct <= 100):
                self.send_message(user_id, "❌ Процент должен быть от 0 до 100")
                return
        except ValueError:
            self.send_message(user_id, "❌ Введите число (0-100)")
            return
        settings = load_settings()
        if cat not in settings:
            self.send_message(user_id, "❌ Категория не найдена")
            self.states.clear_equipment_edit_state(user_id)
            return
        tiers = settings[cat].get("tiers", [])
        if tier_idx is None or tier_idx < 0 or tier_idx >= len(tiers):
            self.send_message(user_id, "❌ Порог не найден")
            self.states.clear_equipment_edit_state(user_id)
            return
        lo, hi, old_pct = tiers[tier_idx]
        tiers[tier_idx] = [lo, hi, float(pct)]
        settings[cat]["tiers"] = tiers
        try:
            save_settings(settings)
            range_str = f"{lo} - {hi}" if hi is not None else f"от {lo}+"
            cat_title = settings.get(cat, {}).get("title", cat)
            self.send_message(user_id, 
                f"✅ Обновлено!\n\n"
                f"📈 {cat_title}\n"
                f"Диапазон: {range_str}\n"
                f"Было: {old_pct}%\n"
                f"Стало: {pct:.2f}%")
        except Exception as e:
            self.send_message(user_id, f"❌ Не удалось сохранить: {e}")
        self.states.clear_equipment_edit_state(user_id)
        self._show_pct_cat(user_id, cat)

    def handle_check_in(self, user_id: int, role: str, session):
        """Обработка отметки о начале смены"""
        try:
            if role != "master":
                self.send_message(user_id, "🚫 Эта функция доступна только мастерам.")
                return
            
            master = session.query(User).filter_by(tg_id=user_id).first()
            if not master:
                self.send_message(user_id, "❌ Ошибка: мастер не найден.")
                return
            
            tz = self._get_timezone_for_city(master.city_rel)
            now_local = datetime.now(tz)
            now_utc = now_local.astimezone(timezone.utc)
            today_local = now_local.date()
            start_utc, end_utc = self._get_local_day_bounds(today_local, tz)
            
            existing = session.query(Attendance).filter(
                Attendance.master_tg_id == user_id,
                Attendance.date >= start_utc,
                Attendance.date < end_utc
            ).first()
            
            if existing:
                check_time = self._format_local_datetime(existing.check_in_time, tz) if existing.check_in_time else "-"
                self.send_message(user_id, f"✅ Вы уже отметились сегодня в {check_time}")
                return
            
            is_late = now_local.time() > dt_time(9, 0)
            attendance = Attendance(
                master_tg_id=user_id,
                check_in_time=now_utc,
                date=start_utc,
                is_penalty=False
            )
            session.add(attendance)
            session.commit()
            
            check_time = now_local.strftime("%H:%M")
            if is_late:
                deadline = dt_time(9, 0)
                minutes_late = int((datetime.combine(today_local, now_local.time()) - datetime.combine(today_local, deadline)).total_seconds() / 60)
                self.send_message(user_id, 
                    f"✅ Отметка принята!\n"
                    f"⏰ Время (локальное): {check_time}\n"
                    f"⚠️ Вы опоздали на {minutes_late} минут")
            else:
                self.send_message(user_id, 
                    f"✅ Отметка принята!\n"
                    f"⏰ Время (локальное): {check_time}\n"
                    f"👍 Вовремя!")
        except Exception:
            logger.exception("Ошибка при обработке отметки")
            self.send_message(user_id, "❌ Ошибка при обработке отметки")

    def handle_my_sd(self, user_id: int, role: str, session):
        """Показать технику на руках у мастера"""
        try:
            if role != "master":
                self.send_message(user_id, "🚫 Эта функция доступна только мастерам.")
                return
            
            active_orders = session.query(Order).filter(
                Order.assigned_to == user_id,
                Order.status.in_(["accepted", "on_place", "to_sd"])
            ).order_by(Order.created_at.desc()).all()
            
            if not active_orders:
                self.send_message(user_id, "📦 У вас нет техники на руках (СД)")
                return

            text = f"📦 Техника на руках ({len(active_orders)} заявок)\n\n"
            kb = types.InlineKeyboardMarkup()
            for order in active_orders:
                equip_type_name = get_equip_type_name(order.equip_type)
                city_name = order.city_rel.name if order.city_rel else "Не указан"
                text += (
                    f"🔧 Заявка #{order.order_number} — {equip_type_name}\n"
                    f"🏙 {city_name}\n"
                    f"📍 {order.street}, д.{order.house}\n"
                    f"📊 Статус: {get_status_name_ru(order.status)}\n\n"
                )
            
            for order in active_orders[:10]:
                equip_type_name = get_equip_type_name(order.equip_type)
                kb.add(types.InlineKeyboardButton(
                    f"#{order.order_number} {equip_type_name}",
                    callback_data=json.dumps({"cmd": "sd_order", "order_id": order.id})
                ))
            
            self.send_message(user_id, text, kb)
        except Exception:
            logger.exception("Ошибка при получении СД")

    def handle_cash(self, user_id: int, role: str, session):
        """Показать кассу мастера - сумма к сдаче компании"""
        try:
            if role != "master":
                self.send_message(user_id, "🚫 Эта функция доступна только мастерам.")
                return
                    
            pending_orders = session.query(Order).filter(
                Order.assigned_to == user_id,
                Order.status == "done_pending_sum"
            ).all()
            
            if not pending_orders:
                msg = "💰 Все заявки по кассе сданы ✅"
                self.send_message(user_id, msg)
                return
            
            total_company = 0.0
            lines = []
            from services.commission_service import get_master_pct
            
            for order in pending_orders:
                order_sum = order.sum_amount or 0
                sd_price = getattr(order, 'sd_price', 0) or 0
                zpch_sum = getattr(order, 'zpch_sum', 0) or 0
                net_amount = max(order_sum - zpch_sum, 0)
                
                master = None
                if order.assigned_to:
                    master = session.query(User).filter_by(tg_id=order.assigned_to).first()
                
                if master and master.master_percentage is not None:
                    master_pct = float(master.master_percentage)
                else:
                    try:
                        master_pct = get_master_pct(order.equip_type, net_amount)
                    except Exception:
                        master_pct = 40.0
                
                master_share = net_amount * (master_pct / 100.0)
                company_sum = max(net_amount - master_share, 0)
                total_company += company_sum
                
                lines.append(f"#{order.order_number}: {company_sum:.2f} руб.")
            
            msg = (
                f"💰 Ваша касса (к сдаче)\n\n"
                + "\n".join(lines)
                + f"\n\n💰 Итого к сдаче: {total_company:.2f} руб.\n"
                f"📋 Всего заявок: {len(pending_orders)}"
            )
            
            kb = types.InlineKeyboardMarkup()
            for order in pending_orders[:10]:
                has_receipt = bool(getattr(order, "receipt_file_id", None) or getattr(order, "receipt_file_path", None))
                if has_receipt:
                    kb.add(types.InlineKeyboardButton(
                        f"📷 Чек #{order.order_number}",
                        callback_data=json.dumps({"cmd": "view_receipt", "order_id": order.id})
                    ))
            
            self.send_message(user_id, msg, kb if kb.keyboard else None)
        except Exception:
            logger.exception("Ошибка при получении кассы")

    def handle_my_orders(self, user_id: int, role: str, session):
        """Показать заявки пользователя"""
        try:
            if role == "dispatcher":
                self.send_message(user_id, "🚫 У диспетчеров нет доступа к заявкам.")
                return
            
            q = session.query(Order).filter(Order.status.notin_(["completed", "declined"]))
            if role == "master":
                orders = q.filter(Order.assigned_to == user_id).order_by(Order.created_at.desc()).limit(20).all()
            elif role == "director":
                orders = q.order_by(Order.created_at.desc()).limit(20).all()
            else:
                orders = q.filter(
                    (Order.assigned_to == user_id) | (Order.created_by == user_id)
                ).order_by(Order.created_at.desc()).limit(20).all()
                
            if not orders:
                self.send_message(user_id, "📭 Заявок нет.")
                return
                
            for o in orders:
                master_name = None
                if o.assigned_to:
                    master = session.query(User).filter_by(tg_id=o.assigned_to).first()
                    if master:
                        master_name = master.full_name or master.name or str(o.assigned_to)
                
                hide_phone = (role == "director")
                text = self._format_order_details(o, master_name=master_name, hide_phone=hide_phone)
                self.send_message(user_id, text)
                self._send_receipt_if_exists(user_id, o)
                
            self.send_message(user_id, "✅ Готово!")
        except Exception:
            logger.exception("Ошибка при получении заявок")

    def handle_stats(self, user_id: int, role: str, session):
        """Показать статистику"""
        try:
            if role == "dispatcher":
                self.send_message(user_id, "🚫 У диспетчеров нет доступа к статистике.")
                return

            date_from, date_to = get_period_bounds("month")
            city_id = None
            city_name = None
            master_id = None

            if role == "master":
                master_id = user_id
            elif role == "director":
                director = session.query(User).filter_by(tg_id=user_id).first()
                if not director or not director.city_id:
                    self.send_message(user_id, "❌ У директора не привязан город. Свяжитесь с собственником.")
                    return
                city_id = director.city_id
                city_name = director.city_rel.name if director.city_rel else None

            stats = calculate_dashboard_stats(
                session,
                date_from=date_from,
                date_to=date_to,
                city_id=city_id,
                city_name=city_name,
                master_id=master_id,
            )

            if stats["cards"]["total"] == 0:
                self.send_message(user_id, "📭 Нет данных за текущий месяц.")
                return

            summary_lines = summarize_dashboard(stats, role)
            self.send_message(user_id, "\n".join(summary_lines))
        except Exception:
            logger.exception("Ошибка при формировании статистики")
            self.send_message(user_id, "❌ Не удалось получить статистику, попробуйте позже.")

    def _handle_admin_panel_entry(self, user_id: int, role: str, session):
        """Вход в админ-панель"""
        if role not in ("owner", "director"):
            self.send_message(user_id, "🚫 Нет доступа.")
            return
        if role == "director":
            self.send_message(user_id, "⚙️ Админ-панель (директор):\n- Заявки\n- Статистика\n- Касса\n- СД")
        else:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("📊 Проценты техники", callback_data=json.dumps({"cmd": "pct_menu"})))
            admin_url = os.getenv("ADMIN_WEB_URL", "http://localhost:8000")
            self.send_message(user_id, f"⚙️ Админ-панель (собственник):\n\n📊 Проценты техники - редактирование процентных ставок по категориям и диапазонам\n\n🌐 Веб-панель: {admin_url}", kb)

    def _handle_manage_masters(self, user_id: int, role: str, session):
        """Управление мастерами"""
        if role == "dispatcher":
            masters = session.query(User).filter_by(role="master").all()
            if not masters:
                self.send_message(user_id, "📭 Мастеров пока нет в системе.")
                return
            text = "👥 Управление мастерами:\n\n"
            for i, master in enumerate(masters, 1):
                active_orders = session.query(Order).filter(
                    Order.assigned_to == master.tg_id,
                    Order.status.in_(["accepted", "on_place"])
                ).count()
                text += f"{i}. {master.name or master.full_name or master.tg_id} (ID: {master.tg_id})\n   📋 Активных заявок: {active_orders}\n\n"
            self.send_message(user_id, text)
            return
        elif role in ("director", "owner"):
            masters = session.query(User).filter_by(role="master").all()
            if not masters:
                self.send_message(user_id, "📭 Мастеров пока нет в системе.")
                return
            lines = []
            for i, m in enumerate(masters, 1):
                city_name = m.city_rel.name if m.city_rel else "Не указан"
                lines.append(f"{i}. {m.full_name or m.name or ('ID ' + str(m.tg_id))}\n   📱 {m.phone or '—'}\n   🏙 {city_name}\n   🆔 {m.tg_id}")
            self.send_message(user_id, "👥 Управление мастерами:\n\n" + "\n\n".join(lines))
            return
        else:
            self.send_message(user_id, "🚫 Нет доступа.")
            return

    def _start_add_master(self, user_id: int, role: str, session):
        """Начать процесс добавления мастера"""
        if role not in ("director", "owner"):
            self.send_message(user_id, "🚫 У вас нет доступа к этой функции. Доступно только директорам и собственникам.")
            return
        self.states.set_master_creation_state(user_id, {"step": "ask_id", "data": {}})
        self.send_message(user_id, "Введите Telegram ID нового мастера:")

    def _handle_master_creation_step(self, user_id: int, text: str, role: str, session):
        """Обработка шагов создания мастера"""
        state = self.states.get_master_creation_state(user_id) or {}
        step = state.get("step")
        data = state.get("data", {})
        t = text.strip()
        if step == "ask_id":
            try:
                data["tg_id"] = int(t)
            except ValueError:
                self.send_message(user_id, "❌ Введите числовой Telegram ID:")
                return
            state.update({"step": "ask_name", "data": data})
            self.states.set_master_creation_state(user_id, state)
            self.send_message(user_id, "Введите имя мастера:")
            return
        if step == "ask_name":
            data["name"] = t
            director = session.query(User).filter_by(tg_id=user_id).first()
            new_master = User(tg_id=data["tg_id"], name=data.get("name"), role="master", city_id=getattr(director, "city_id", None))
            session.add(new_master)
            session.commit()
            self.states.clear_master_creation_state(user_id)
            self.send_message(user_id, f"✅ Мастер добавлен: {new_master.name} ({new_master.tg_id})")
            kb = self.get_keyboard(role)
            self.send_message(user_id, "🏠 Главное меню:", kb)
            return

    def _handle_director_sd(self, user_id: int, role: str, session):
        """Показать СД для директора/собственника"""
        if role not in ("director", "owner"):
            self.send_message(user_id, "🚫 У вас нет доступа к этой функции. Доступно только директорам и собственникам.")
            return
        orders = session.query(Order).filter(Order.status.in_(["accepted", "on_place", "to_sd"]))\
            .order_by(Order.created_at.desc()).limit(50).all()
        if not orders:
            self.send_message(user_id, "📦 Нет техники на руках у мастеров (СД пусто)")
            return
        
        from collections import defaultdict
        masters_dict = defaultdict(list)
        for o in orders:
            master_id = o.assigned_to
            if master_id:
                masters_dict[master_id].append(o)
        
        text = f"📦 СД (активные заявки)\n\n"
        text += f"Всего заявок: {len(orders)}\n"
        text += f"Мастеров: {len(masters_dict)}\n\n"
        
        for master_id, master_orders in masters_dict.items():
            master = session.query(User).filter_by(tg_id=master_id).first()
            master_name = master.full_name or master.name or str(master_id) if master else str(master_id)
            text += f"👤 {master_name} — {len(master_orders)} заявок\n"
        
        kb = types.InlineKeyboardMarkup()
        for master_id, master_orders in list(masters_dict.items())[:10]:
            master = session.query(User).filter_by(tg_id=master_id).first()
            master_name = master.full_name or master.name or str(master_id) if master else str(master_id)
            kb.add(types.InlineKeyboardButton(
                f"👤 {master_name} ({len(master_orders)})",
                callback_data=json.dumps({"cmd": "sd_master", "master_id": master_id})
            ))
        
        self.send_message(user_id, text, kb)

    def _handle_improvements(self, user_id: int, role: str, session):
        """Показать заявки на доработку (статус to_sd или done_pending_sum)"""
        try:
            if role == "master":
                orders = session.query(Order).filter(
                    Order.assigned_to == user_id,
                    Order.status.in_(["to_sd", "done_pending_sum"])
                ).order_by(Order.created_at.desc()).limit(50).all()
            elif role in ("director", "owner"):
                city_id = None
                if role == "director":
                    director = session.query(User).filter_by(tg_id=user_id).first()
                    if director and director.city_id:
                        city_id = director.city_id
                
                query = session.query(Order).filter(
                    Order.status.in_(["to_sd", "done_pending_sum"])
                )
                if city_id:
                    query = query.filter(Order.city_id == city_id)
                orders = query.order_by(Order.created_at.desc()).limit(50).all()
            else:
                self.send_message(user_id, "🚫 У вас нет доступа к этой функции.")
                return
            
            if not orders:
                self.send_message(user_id, "📭 Нет заявок на доработку.")
                return
            
            text = f"🔧 Заявки на доработку ({len(orders)} шт.):\n\n"
            for order in orders[:20]:
                equip_type_name = get_equip_type_name(order.equip_type)
                city_name = order.city_rel.name if order.city_rel else "Не указан"
                master_name = "Не назначен"
                if order.assigned_to:
                    master = session.query(User).filter_by(tg_id=order.assigned_to).first()
                    if master:
                        master_name = master.full_name or master.name or str(order.assigned_to)
                
                text += (
                    f"#{order.order_number} — {equip_type_name}\n"
                    f"🏙 {city_name} | 👤 {master_name}\n"
                    f"📊 {get_status_name_ru(order.status)}\n\n"
                )
            
            if len(orders) > 20:
                text += f"... и еще {len(orders) - 20} заявок"
            
            self.send_message(user_id, text)
        except Exception:
            logger.exception("Ошибка при получении заявок на доработку")
            self.send_message(user_id, "❌ Ошибка при получении заявок на доработку")

    def _handle_debts(self, user_id: int, role: str, session):
        """Показать заявки с долгами"""
        try:
            if role == "master":
                orders = session.query(Order).filter(
                    Order.assigned_to == user_id,
                    Order.debt_amount > 0
                ).order_by(Order.debt_payment_date.asc().nullslast(), Order.created_at.desc()).limit(50).all()
            elif role in ("director", "owner"):
                city_id = None
                if role == "director":
                    director = session.query(User).filter_by(tg_id=user_id).first()
                    if director and director.city_id:
                        city_id = director.city_id
                
                query = session.query(Order).filter(Order.debt_amount > 0)
                if city_id:
                    query = query.filter(Order.city_id == city_id)
                orders = query.order_by(Order.debt_payment_date.asc().nullslast(), Order.created_at.desc()).limit(50).all()
            else:
                self.send_message(user_id, "🚫 У вас нет доступа к этой функции.")
                return
            
            if not orders:
                self.send_message(user_id, "✅ Нет заявок с долгами.")
                return
            
            total_debt = sum(float(order.debt_amount or 0) for order in orders)
            text = f"💳 Заявки с долгами ({len(orders)} шт., всего: {total_debt:.2f} руб.):\n\n"
            
            for order in orders[:20]:
                equip_type_name = get_equip_type_name(order.equip_type)
                city_name = order.city_rel.name if order.city_rel else "Не указан"
                debt_amount = float(order.debt_amount or 0)
                debt_date = ""
                if order.debt_payment_date:
                    tz = self._get_timezone_for_city(order.city_rel)
                    debt_date = f" | 📅 {self._format_local_datetime(order.debt_payment_date, tz)}"
                
                text += (
                    f"#{order.order_number} — {equip_type_name}\n"
                    f"💳 Долг: {debt_amount:.2f} руб.{debt_date}\n"
                    f"🏙 {city_name}\n\n"
                )
            
            if len(orders) > 20:
                text += f"... и еще {len(orders) - 20} заявок"
            
            self.send_message(user_id, text)
        except Exception:
            logger.exception("Ошибка при получении заявок с долгами")
            self.send_message(user_id, "❌ Ошибка при получении заявок с долгами")

    def _handle_transfers(self, user_id: int, role: str, session):
        """Показать заявки с переносами (заявки со статусом scheduled или с измененной датой)"""
        try:
            if role == "master":
                orders = session.query(Order).filter(
                    Order.assigned_to == user_id,
                    Order.status == "scheduled"
                ).order_by(Order.order_date.asc().nullslast(), Order.created_at.desc()).limit(50).all()
            elif role in ("director", "owner"):
                city_id = None
                if role == "director":
                    director = session.query(User).filter_by(tg_id=user_id).first()
                    if director and director.city_id:
                        city_id = director.city_id
                
                query = session.query(Order).filter(Order.status == "scheduled")
                if city_id:
                    query = query.filter(Order.city_id == city_id)
                orders = query.order_by(Order.order_date.asc().nullslast(), Order.created_at.desc()).limit(50).all()
            else:
                self.send_message(user_id, "🚫 У вас нет доступа к этой функции.")
                return
            
            if not orders:
                self.send_message(user_id, "📅 Нет заявок с переносами.")
                return
            
            text = f"📅 Заявки с переносами ({len(orders)} шт.):\n\n"
            
            for order in orders[:20]:
                equip_type_name = get_equip_type_name(order.equip_type)
                city_name = order.city_rel.name if order.city_rel else "Не указан"
                order_date = ""
                if order.order_date:
                    tz = self._get_timezone_for_city(order.city_rel)
                    order_date = f" | 📅 {self._format_local_datetime(order.order_date, tz)}"
                
                text += (
                    f"#{order.order_number} — {equip_type_name}\n"
                    f"🏙 {city_name}{order_date}\n\n"
                )
            
            if len(orders) > 20:
                text += f"... и еще {len(orders) - 20} заявок"
            
            self.send_message(user_id, text)
        except Exception:
            logger.exception("Ошибка при получении заявок с переносами")
            self.send_message(user_id, "❌ Ошибка при получении заявок с переносами")

    def _handle_cash_overview(self, user_id: int, role: str, session):
        """Показать кассу по мастерам с возможностью приема"""
        if role not in ("director", "owner"):
            self.send_message(user_id, "🚫 У вас нет доступа к этой функции. Доступно только директорам и собственникам.")
            return
        
        city_id = None
        if role == "director":
            user = session.query(User).filter_by(tg_id=user_id).first()
            city_id = user.city_id if user else None
        
        query = session.query(Order).filter(Order.status == "done_pending_sum")
        if role == "director" and city_id:
            query = query.filter(Order.city_id == city_id)
        
        pending_orders = query.all()
        
        if not pending_orders:
            self.send_message(user_id, "✅ Все заявки по кассе приняты")
            return
        
        from collections import defaultdict
        masters_cash = defaultdict(list)
        for order in pending_orders:
            master_id = order.assigned_to
            if master_id:
                masters_cash[master_id].append(order)
        
        if not masters_cash:
            self.send_message(user_id, "✅ Нет заявок для приема кассы")
            return
        
        from services.commission_service import get_master_pct
        total_all = 0.0
        
        for master_id, orders in masters_cash.items():
            master = session.query(User).filter_by(tg_id=master_id).first()
            master_name = (master.full_name or master.name or str(master_id)) if master else str(master_id)
            
            master_total = 0.0
            order_lines = []
            
            for order in orders:
                order_sum = order.sum_amount or 0
                sd_price = getattr(order, 'sd_price', 0) or 0
                zpch_sum = getattr(order, 'zpch_sum', 0) or 0
                net_amount = max(order_sum - zpch_sum, 0)
                
                if master and master.master_percentage is not None:
                    master_pct = float(master.master_percentage)
                else:
                    try:
                        master_pct = get_master_pct(order.equip_type, net_amount)
                    except Exception:
                        master_pct = 40.0
                
                master_share = net_amount * (master_pct / 100.0)
                company_sum = max(net_amount - master_share, 0)
                master_total += company_sum
                order_lines.append(f"  #{order.order_number}: {company_sum:.2f} руб.")
            
            total_all += master_total
            
            master_msg = (
                f"🔧 Мастер: {master_name}\n"
                + "\n".join(order_lines)
                + f"\n\n💰 Итого к приему: {master_total:.2f} руб."
            )
            
            kb = types.InlineKeyboardMarkup()
            button_text = f"✅ Принять кассу от {master_name}" if len(master_name) <= 20 else f"✅ Принять кассу"
            kb.add(types.InlineKeyboardButton(
                button_text,
                callback_data=json.dumps({"cmd": "accept_cash", "master_id": master_id, "city_id": city_id})
            ))
            self.send_message(user_id, master_msg, kb)
        
        if len(masters_cash) > 1:
            self.send_message(user_id, f"\n💰 Общая сумма к приему: {total_all:.2f} руб.")

    # ===== 📲 Payload Router =====

    def handle_payload(self, user_id: int, payload: dict, role: str, session):
        """Роутер inline-кнопок (аналог VK бота)"""
        cmd = payload.get("cmd")
        try:
            if cmd == "accept":
                self._payload_accept(user_id, payload, role, session)
            elif cmd == "onway":
                self._payload_onway(user_id, payload, role, session)
            elif cmd == "to_sd":
                self._payload_to_sd(user_id, payload, role, session)
            elif cmd == "ready":
                self._payload_ready(user_id, payload, role, session)
            elif cmd == "close_sd":
                self._payload_close_sd(user_id, payload, role, session)
            elif cmd == "sd_master":
                self._payload_sd_master(user_id, payload, role, session)
            elif cmd == "sd_order":
                self._payload_sd_order(user_id, payload, role, session)
            elif cmd == "accept_cash":
                self._payload_accept_cash(user_id, payload, role, session)
            elif cmd == "take_order":
                self._payload_take_order(user_id, payload, role, session)
            elif cmd == "assign_menu":
                self._payload_assign_menu(user_id, payload, role, session)
            elif cmd == "assign_to":
                self._payload_assign_to(user_id, payload, role, session)
            elif cmd == "cancel_sum_input":
                self.states.clear_sum_input_state(user_id)
                self.send_message(user_id, "❌ Ввод суммы отменен")
            elif cmd == "zpch_zero":
                self._payload_zpch_zero(user_id)
            elif cmd == "skip_bso":
                self._payload_skip_bso(user_id, session)
            elif cmd == "skip_receipt":
                self._payload_skip_receipt(user_id, session)
            elif cmd == "close_order":
                self._payload_close_order(user_id, payload, role, session)
            elif cmd == "view_receipt":
                self._payload_view_receipt(user_id, payload, role, session)
            elif cmd == "pct_menu":
                if role != "owner":
                    self.send_message(user_id, "🚫 Нет доступа.")
                else:
                    self._show_pct_menu(user_id)
            elif cmd == "pct_cat":
                if role != "owner":
                    self.send_message(user_id, "🚫 Нет доступа.")
                else:
                    cat = payload.get("cat")
                    if cat:
                        self._show_pct_cat(user_id, cat)
            elif cmd == "pct_tier":
                if role != "owner":
                    self.send_message(user_id, "🚫 Нет доступа.")
                else:
                    cat = payload.get("cat")
                    tier = payload.get("tier")
                    try:
                        tier_idx = int(tier)
                    except Exception:
                        self.send_message(user_id, "❌ Неверный индекс порога")
                        return
                    self.states.set_equipment_edit_state(user_id, {"cat": cat, "tier": tier_idx, "step": "pct"})
                    self.send_message(user_id, f"Введите новый процент для {cat} порог #{tier_idx+1} (0-100):", self._kb_pct_cat(cat))
            elif cmd == "pct_close":
                self.send_message(user_id, "Админ-панель закрыта.")
            elif cmd == "select_equip_type":
                state = self.states.get_form_state(user_id) or {}
                if state.get("step") == "equip_type":
                    equip_type = payload.get("equip_type")
                    if equip_type:
                        data = state.get("data", {})
                        data["equip_type"] = equip_type
                        state.update({"step": "short_desc", "data": data})
                        self.states.set_form_state(user_id, state)
                        equip_name = get_equip_type_name(equip_type)
                        self.send_message(user_id, f"✅ Выбрано: {equip_name}\n\n📝 Кратко опишите проблему:")
            elif cmd == "select_master":
                state = self.states.get_form_state(user_id) or {}
                if state.get("step") == "assign":
                    master_id = payload.get("master_id")
                    if master_id:
                        try:
                            master_id = int(master_id)
                            data = state.get("data", {})
                            data["assigned_to"] = master_id
                            state.update({"step": "confirm", "data": data})
                            self.states.set_form_state(user_id, state)
                            master = session.query(User).filter_by(tg_id=master_id).first()
                            master_name = master.full_name or master.name or str(master_id) if master else str(master_id)
                            city_name = session.query(City).filter_by(id=data["city_id"]).first().name
                            equip_name = get_equip_type_name(data.get("equip_type"))
                            preview = (
                                f"📋 Подтвердите создание заявки:\n"
                                f"🏙 {city_name}\n📍 {data['street']}, {data['house']}\n"
                                f"Кв.: {data.get('flat','')}\n⏰ {data.get('time_from','')} - {data.get('time_to','')}\n"
                                f"🔧 {equip_name}\n📝 {data['short_desc']}\n"
                                f"👤 Клиент: {data.get('client_name','')} ({data.get('client_phone','')})\n"
                                f"💬 Комментарий: {data.get('comment','')}\n"
                                f"📞 Источник: {data.get('source','')}\n"
                                f"👤 Мастер: {master_name}\n\n"
                                f"Ответьте: 'да' для создания или 'нет' для отмены"
                            )
                            self.send_message(user_id, preview)
                        except (ValueError, TypeError):
                            self.send_message(user_id, "❌ Ошибка выбора мастера")
            elif cmd == "skip_master":
                state = self.states.get_form_state(user_id) or {}
                if state.get("step") == "assign":
                    data = state.get("data", {})
                    data["assigned_to"] = None
                    state.update({"step": "confirm", "data": data})
                    self.states.set_form_state(user_id, state)
                    city_name = session.query(City).filter_by(id=data["city_id"]).first().name
                    equip_name = get_equip_type_name(data.get("equip_type"))
                    preview = (
                        f"📋 Подтвердите создание заявки:\n"
                        f"🏙 {city_name}\n📍 {data['street']}, {data['house']}\n"
                        f"Кв.: {data.get('flat','')}\n⏰ {data.get('time_from','')} - {data.get('time_to','')}\n"
                        f"🔧 {equip_name}\n📝 {data['short_desc']}\n"
                        f"👤 Клиент: {data.get('client_name','')} ({data.get('client_phone','')})\n"
                        f"💬 Комментарий: {data.get('comment','')}\n"
                        f"📞 Источник: {data.get('source','')}\n"
                        f"👤 Мастер: не назначен\n\n"
                        f"Ответьте: 'да' для создания или 'нет' для отмены"
                    )
                    self.send_message(user_id, preview)
            elif cmd == "cancel_form":
                self.states.clear_form_state(user_id)
                kb = self.get_keyboard(role)
                self.send_message(user_id, "❌ Создание заявки отменено", kb)
            else:
                logger.info(f"Неизвестный payload: {payload}")
        except Exception:
            logger.exception("Ошибка обработки payload")

    # ===== Payload обработчики =====

    def _payload_accept(self, user_id: int, payload: dict, role: str, session):
        """Мастер принимает заявку"""
        order_id = int(payload.get("order_id", 0))
        order = session.query(Order).filter_by(id=order_id).first()
        if not order or order.assigned_to != user_id:
            self.send_message(user_id, "🚫 Вы не можете выполнить это действие. Заявка не назначена на вас.")
            return
        order.status = "accepted"
        session.commit()
        self.send_message(user_id, f"✅ Заявка №{order.order_number} принята!", self._kb_master_on_way(order.id))

    def _payload_onway(self, user_id: int, payload: dict, role: str, session):
        """Мастер в пути"""
        order_id = int(payload.get("order_id", 0))
        order = session.query(Order).filter_by(id=order_id).first()
        if not order or order.assigned_to != user_id:
            self.send_message(user_id, "🚫 Вы не можете выполнить это действие. Заявка не назначена на вас.")
            return
        order.status = "on_place"
        session.commit()
        text = self._render_order(order)
        self.send_message(user_id, f"🚗 В пути!\n\n{text}\n\nКак будете готовы — нажмите 'Готово'", self._kb_master_ready(order.id))

    def _payload_to_sd(self, user_id: int, payload: dict, role: str, session):
        """Мастер забрал технику на СД"""
        order_id = int(payload.get("order_id", 0))
        order = session.query(Order).filter_by(id=order_id).first()
        if not order or order.assigned_to != user_id:
            self.send_message(user_id, "🚫 Вы не можете выполнить это действие. Заявка не назначена на вас.")
            return
        order.status = "to_sd"
        session.commit()
        self.send_message(user_id, f"✅ Техника по заявке #{order.order_number} отправлена на СД")
        kb = self.get_keyboard(role)
        self.send_message(user_id, "🏠 Главное меню:", kb)

    def _payload_ready(self, user_id: int, payload: dict, role: str, session):
        """Мастер закончил — переход к вводу суммы"""
        order_id = int(payload.get("order_id", 0))
        order = session.query(Order).filter_by(id=order_id).first()
        if not order or order.assigned_to != user_id:
            self.send_message(user_id, "🚫 Вы не можете выполнить это действие. Заявка не назначена на вас.")
            return
        if order.status == "done_pending_sum":
            self.send_message(user_id, "⚠️ Заявка уже была закрыта ранее.")
            return
        order.status = "done_pending_sum"
        session.commit()
        self.states.set_sum_input_state(user_id, {"order_id": order_id, "step": "order_sum", "data": {}})
        self.send_message(user_id, "💰 Введите сумму заказа:", self._kb_sum_cancel())

    def _payload_sd_master(self, user_id: int, payload: dict, role: str, session):
        """Показать заявки конкретного мастера (для директора/owner)"""
        if role not in ("director", "owner"):
            self.send_message(user_id, "🚫 У вас нет доступа к этой функции.")
            return

        master_id = int(payload.get("master_id", 0))
        master = session.query(User).filter_by(tg_id=master_id).first()
        master_name = master.full_name or master.name or str(master_id) if master else str(master_id)

        orders = session.query(Order).filter(
            Order.assigned_to == master_id,
            Order.status.in_(["accepted", "on_place", "to_sd"])
        ).order_by(Order.created_at.desc()).all()

        if not orders:
            self.send_message(user_id, f"📦 У мастера {master_name} нет техники на руках")
            return

        text = f"📦 СД мастера {master_name}\n\n"
        kb = types.InlineKeyboardMarkup()

        for order in orders[:10]:
            equip_type_name = get_equip_type_name(order.equip_type)
            city_name = order.city_rel.name if order.city_rel else "Не указан"
            text += (
                f"🔧 Заявка #{order.order_number} — {equip_type_name}\n"
                f"🏙 {city_name}, {order.street}, д.{order.house}\n"
                f"📊 Статус: {get_status_name_ru(order.status)}\n\n"
            )
            kb.add(types.InlineKeyboardButton(
                f"#{order.order_number}",
                callback_data=json.dumps({"cmd": "sd_order", "order_id": order.id})
            ))

        self.send_message(user_id, text, kb)

    def _payload_sd_order(self, user_id: int, payload: dict, role: str, session):
        """Показать детали заявки и кнопку для закрытия СД"""
        order_id = int(payload.get("order_id", 0))
        order = session.query(Order).filter_by(id=order_id).first()

        if not order:
            self.send_message(user_id, "❌ Заявка не найдена.")
            return

        if role == "master" and order.assigned_to != user_id:
            self.send_message(user_id, "🚫 Вы не можете просматривать эту заявку.")
            return

        if role not in ("master", "director", "owner"):
            self.send_message(user_id, "🚫 Нет доступа")
            return

        if order.status not in ["accepted", "on_place", "to_sd"]:
            self.send_message(user_id, f"⚠️ Заявка не находится в статусе СД (текущий статус: {get_status_name_ru(order.status)})")
            return

        equip_type_name = get_equip_type_name(order.equip_type)
        city_name = order.city_rel.name if order.city_rel else "Не указан"
        master = session.query(User).filter_by(tg_id=order.assigned_to).first()
        master_name = master.full_name or master.name or str(order.assigned_to) if master else str(order.assigned_to)

        text = (
            f"📦 Заявка #{order.order_number}\n\n"
            f"🔧 Тип техники: {equip_type_name}\n"
            f"👤 Мастер: {master_name}\n"
            f"🏙 Город: {city_name}\n"
            f"📍 Адрес: {order.street}, д.{order.house}"
        )
        if order.flat:
            text += f", кв.{order.flat}"
        text += f"\n⏰ Время: {order.time_from} - {order.time_to}\n"
        if order.short_desc:
            text += f"📝 Описание: {order.short_desc}\n"
        text += f"📊 Статус: {get_status_name_ru(order.status)}"

        kb = self._kb_sd_ready(order.id)
        self.send_message(user_id, text, kb)

    def _payload_close_sd(self, user_id: int, payload: dict, role: str, session):
        """Закрытие СД — переводит заявку в done_pending_sum и запускает процесс закрытия"""
        order_id = int(payload.get("order_id", 0))
        order = session.query(Order).filter_by(id=order_id).first()

        if not order:
            self.send_message(user_id, "❌ Заявка не найдена.")
            return

        if role == "master" and order.assigned_to != user_id:
            self.send_message(user_id, "🚫 Вы не можете выполнить это действие.")
            return

        if role not in ("master", "director", "owner"):
            self.send_message(user_id, "🚫 Нет доступа")
            return

        if order.status not in ["accepted", "on_place", "to_sd"]:
            self.send_message(user_id, f"⚠️ Заявка не находится в статусе СД (текущий статус: {get_status_name_ru(order.status)})")
            return

        if order.status == "done_pending_sum":
            self.send_message(user_id, "⚠️ Заявка уже была закрыта ранее.")
            return

        order.status = "done_pending_sum"
        session.commit()
        self.states.set_sum_input_state(user_id, {"order_id": order_id, "step": "order_sum", "data": {}})
        self.send_message(user_id, f"✅ СД закрыт для заявки #{order.order_number}\n\n💰 Введите сумму заказа:", self._kb_sum_cancel())

    def _payload_accept_cash(self, user_id: int, payload: dict, role: str, session):
        """Приемка кассы мастера директором/собственником"""
        if role not in ("director", "owner"):
            self.send_message(user_id, "🚫 У вас нет доступа к этой функции.")
            return

        master_id = int(payload.get("master_id", 0))
        if not master_id:
            self.send_message(user_id, "❌ Не указан мастер.")
            return

        # Проверяем, что директор может принимать кассу мастера из своего города
        if role == "director":
            director = session.query(User).filter_by(tg_id=user_id).first()
            if not director or not director.city_id:
                self.send_message(user_id, "❌ У вас не указан город.")
                return

            master = session.query(User).filter_by(tg_id=master_id).first()
            if not master or master.city_id != director.city_id:
                self.send_message(user_id, "🚫 Вы можете принимать кассу только мастеров из своего города")
                return

        # Получаем все заявки мастера со статусом done_pending_sum
        orders = session.query(Order).filter(
            Order.assigned_to == master_id,
            Order.status == "done_pending_sum"
        ).all()

        if not orders:
            self.send_message(user_id, "✅ У этого мастера нет заявок для приема кассы")
            return

        # Рассчитываем сумму и создаем записи в Stat
        from services.commission_service import get_master_pct
        total_company = 0.0

        for order in orders:
            order_sum = order.sum_amount or 0
            sd_price = getattr(order, 'sd_price', 0) or 0
            zpch_sum = getattr(order, 'zpch_sum', 0) or 0
            net_amount = max(order_sum - zpch_sum, 0)

            # Проверяем индивидуальный процент мастера
            master_user = None
            if order.assigned_to:
                master_user = session.query(User).filter_by(tg_id=order.assigned_to).first()

            if master_user and master_user.master_percentage is not None:
                master_pct = float(master_user.master_percentage)
            else:
                try:
                    master_pct = get_master_pct(order.equip_type, net_amount)
                except Exception:
                    master_pct = 40.0

            master_share = net_amount * (master_pct / 100.0)
            company_sum = max(net_amount - master_share, 0)
            total_company += company_sum

            # Создаем запись в статистике
            if not getattr(order, "is_warranty", False):
                stat = Stat(
                    order_id=order.id,
                    equip_type=order.equip_type,
                    sum=order_sum,
                    refused=(order_sum == 0),
                    master_tg=master_id
                )
                session.add(stat)

            # Меняем статус заявки на completed
            order.status = "completed"

            # Автосрок гарантии
            if not getattr(order, "is_warranty", False) and order.status != "cancelled":
                try:
                    from services.warranty_service import compute_warranty
                    closed_amount = float(order.sum_amount or order.paid_amount or 0)
                    winfo = compute_warranty(closed_amount, datetime.now(timezone.utc))
                    order.warranty_days = int(winfo.days)
                    order.warranty_until = winfo.until
                except Exception:
                    pass

        session.commit()

        master = session.query(User).filter_by(tg_id=master_id).first()
        master_name = (master.full_name or master.name or str(master_id)) if master else str(master_id)

        self.send_message(user_id, f"✅ Касса мастера {master_name} принята!\n\nСумма: {total_company:.2f} руб.\nЗаявок: {len(orders)}")

        # Уведомляем мастера
        try:
            self.send_message(master_id, f"✅ Ваша касса принята!\n\nСумма: {total_company:.2f} руб.\nЗаявок: {len(orders)}")
        except Exception:
            pass

    def _payload_take_order(self, user_id: int, payload: dict, role: str, session):
        """Директор берёт заявку на себя как мастер"""
        if role != "director":
            self.send_message(user_id, "🚫 Только директор может взять заявку на себя.")
            return
        order_id = int(payload.get("order_id", 0))
        from sqlalchemy.orm import selectinload
        order = session.query(Order).options(selectinload(Order.city_rel)).filter_by(id=order_id).first()
        if not order:
            self.send_message(user_id, "❌ Заявка не найдена.")
            return
        if order.status == "completed":
            self.send_message(user_id, "⚠️ Заявка уже закрыта.")
            return

        # Уведомляем старого мастера
        old_master_id = order.assigned_to
        if old_master_id and old_master_id != user_id:
            old_master = session.query(User).filter_by(tg_id=old_master_id).first()
            if old_master and old_master.role == "master":
                try:
                    self.send_message(old_master_id, f"❌ Заявка №{order.order_number} отменена")
                except Exception:
                    pass

        order.assigned_to = user_id
        order.status = "accepted"
        session.commit()

        city_name = order.city_rel.name if order.city_rel else "Не указан"
        equip = get_equip_type_name(order.equip_type)

        text = (
            f"✅ Вы взяли заявку №{order.order_number} на себя\n\n"
            f"🏙 Город: {city_name}\n"
            f"⏰ Время: {order.time_from} - {order.time_to}\n"
            f"📍 Адрес: ул. {order.street}, дом {order.house}, кв. {order.flat or '-'}\n"
            f"🔧 Техника: {equip}\n"
        )

        if order.short_desc:
            text += f"📝 Описание: {order.short_desc}\n"
        text += f"👤 Клиент: {order.client_name or 'Не указано'}\n"
        if order.source:
            text += f"📞 Источник: {order.source}\n"
        if order.comment:
            text += f"💬 Комментарий: {order.comment}\n"
        text += "\n🚗 Нажмите 'В пути', когда начнете движение к клиенту."

        self.send_message(user_id, text, self._kb_master_on_way(order.id))

    def _payload_assign_menu(self, user_id: int, payload: dict, role: str, session):
        """Показать список, кому назначить заявку"""
        if role not in ("owner", "director", "dispatcher"):
            self.send_message(user_id, "🚫 Нет доступа.")
            return
        order_id = int(payload.get("order_id", 0))
        from sqlalchemy.orm import selectinload
        order = session.query(Order).options(selectinload(Order.city_rel)).filter_by(id=order_id).first()
        if not order:
            self.send_message(user_id, "❌ Заявка не найдена.")
            return

        # Берём мастеров
        q = session.query(User).filter(User.role == "master").options(selectinload(User.city_rel))
        if role == "director":
            director = session.query(User).filter_by(tg_id=user_id).first()
            city_id = order.city_id or (director.city_id if director else None)
            if city_id:
                q = q.filter(User.city_id == city_id)
        masters = q.order_by(User.full_name.asc().nullslast(), User.name.asc().nullslast()).all()
        if not masters and role != "director":
            self.send_message(user_id, "❌ В системе нет мастеров для назначения.")
            return

        kb = types.InlineKeyboardMarkup()

        # Кнопка "Себе"
        if role in ("owner", "director"):
            btn_text = "👤 Себе (директору)" if role == "director" else "👤 Себе"
            kb.add(types.InlineKeyboardButton(
                btn_text,
                callback_data=json.dumps({"cmd": "assign_to", "order_id": order.id, "master_id": "self"})
            ))

        # Формируем информативное сообщение
        city_name = order.city_rel.name if order.city_rel else "Не указан"
        equip = get_equip_type_name(order.equip_type)

        lines = [
            f"📋 Назначение заявки №{order.order_number}",
            f"🏙 Город заявки: {city_name}",
            f"🔧 Техника: {equip}",
            f"📍 Адрес: ул. {order.street}, дом {order.house}",
            "",
            "👤 Список мастеров:"
        ]

        for idx, m in enumerate(masters, 1):
            master_name = m.full_name or m.name or str(m.tg_id)
            master_city = m.city_rel.name if m.city_rel else "Без города"
            lines.append(f"{idx}. {master_name} | 🏙 {master_city}")

            button_text = f"{idx}. {master_name[:25]}" if len(master_name) <= 25 else f"{idx}. {master_name[:22]}..."
            kb.add(types.InlineKeyboardButton(
                button_text,
                callback_data=json.dumps({"cmd": "assign_to", "order_id": order.id, "master_id": str(m.tg_id)})
            ))

        text = "\n".join(lines)
        self.send_message(user_id, text, kb)

    def _payload_assign_to(self, user_id: int, payload: dict, role: str, session):
        """Назначить заявку на выбранного человека"""
        if role not in ("owner", "director", "dispatcher"):
            self.send_message(user_id, "🚫 Нет доступа.")
            return
        order_id = int(payload.get("order_id", 0))
        from sqlalchemy.orm import selectinload
        order = session.query(Order).options(selectinload(Order.city_rel)).filter_by(id=order_id).first()
        if not order:
            self.send_message(user_id, "❌ Заявка не найдена.")
            return
        if order.status == "completed":
            self.send_message(user_id, "⚠️ Заявка уже закрыта.")
            return

        master_id_raw = payload.get("master_id")
        if master_id_raw == "self":
            master_id = user_id
        else:
            try:
                master_id = int(master_id_raw)
            except (TypeError, ValueError):
                self.send_message(user_id, "❌ Неверный ID мастера.")
                return

        target_user = session.query(User).filter_by(tg_id=master_id).first()
        if not target_user and master_id != user_id:
            self.send_message(user_id, "❌ Пользователь не найден.")
            return

        # Уведомляем старого мастера
        old_master_id = order.assigned_to
        if old_master_id and old_master_id != master_id:
            old_master = session.query(User).filter_by(tg_id=old_master_id).first()
            if old_master and old_master.role == "master":
                try:
                    self.send_message(old_master_id, f"❌ Заявка №{order.order_number} отменена")
                except Exception:
                    pass

        order.assigned_to = master_id
        order.status = "assigned"
        session.commit()

        if master_id == user_id:
            if role == "director":
                self.send_message(
                    user_id,
                    f"✅ Заявка №{order.order_number} назначена вам.\n\n"
                    f"Нажмите 'В пути', когда начнете движение.",
                    self._kb_master_on_way(order.id)
                )
            else:
                self.send_message(user_id, f"✅ Заявка #{order.order_number} назначена вам.")
        else:
            target_name = target_user.full_name or target_user.name or str(master_id)
            city_name = order.city_rel.name if order.city_rel else "Не указан"
            self.send_message(
                user_id,
                f"✅ Заявка №{order.order_number} назначена мастеру {target_name}\n"
                f"🏙 Город: {city_name}\n"
                f"📋 Мастер получит уведомление о новой заявке."
            )

        # Уведомляем нового мастера
        if target_user and target_user.role == "master":
            try:
                self._notify_master_telegram(order, session)
            except Exception:
                pass
        elif target_user and target_user.role == "director":
            try:
                text = (
                    f"✅ Заявка №{order.order_number} назначена вам\n\n"
                    f"{self._format_order_details(order, hide_phone=True)}\n\n"
                    "Вы можете начать работу с заявкой."
                )
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton(
                    "🚗 В пути",
                    callback_data=json.dumps({"cmd": "onway", "order_id": order.id})
                ))
                self.send_message(target_user.tg_id, text, kb)
            except Exception:
                pass

    def _payload_zpch_zero(self, user_id: int):
        """ЗПЧ = 0"""
        state = self.states.get_sum_input_state(user_id)
        if not state:
            return
        state["data"]["zpch_sum"] = 0
        state["data"]["sd_price"] = state["data"].get("sd_price", 0)
        state["step"] = "waiting_bso"
        self.states.set_sum_input_state(user_id, state)
        self._prompt_bso_upload(user_id)

    def _payload_skip_bso(self, user_id: int, session):
        """Пропустить загрузку БСО"""
        state = self.states.get_sum_input_state(user_id)
        if not state:
            return

        state["data"]["bso_file_id"] = None
        local_path = state["data"].get("bso_local_path")
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass
        state["data"]["bso_local_path"] = None

        zpch_sum = float(state["data"].get("zpch_sum", 0) or 0)
        if zpch_sum > 0:
            state["step"] = "waiting_receipt"
            self.states.set_sum_input_state(user_id, state)
            self.send_message(user_id, "✅ БСО пропущен")
            self._prompt_receipt_upload(user_id)
        else:
            self.states.set_sum_input_state(user_id, state)
            self.send_message(user_id, "✅ БСО пропущен")
            self._calculate_and_show_result(user_id)

    def _payload_skip_receipt(self, user_id: int, session):
        """Пропустить загрузку чека"""
        state = self.states.get_sum_input_state(user_id)
        if state:
            state["data"]["receipt_file_id"] = None
            local_path = state["data"].get("receipt_local_path")
            if local_path and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except Exception:
                    pass
            state["data"]["receipt_local_path"] = None
            self.states.set_sum_input_state(user_id, state)
        self._calculate_and_show_result(user_id)

    def _payload_close_order(self, user_id: int, payload: dict, role: str, session):
        """Закрытие заявки мастером"""
        order_id = int(payload.get("order_id", 0))
        order = session.query(Order).filter_by(id=order_id, assigned_to=user_id).first()
        if not order:
            self.send_message(user_id, "🚫 Нет доступа к заявке")
            return
        session.commit()
        self.send_message(user_id, "✅ Заявка готова к сдаче кассы!")
        kb = self.get_keyboard(role)
        self.send_message(user_id, "🏠 Главное меню:", kb)

    def _payload_view_receipt(self, user_id: int, payload: dict, role: str, session):
        """Показать чек по заявке"""
        try:
            order_id = payload.get("order_id")
            if not order_id:
                self.send_message(user_id, "❌ Ошибка: не указан ID заявки")
                return

            order = session.query(Order).filter_by(id=order_id).first()
            if not order:
                self.send_message(user_id, "❌ Заявка не найдена")
                return

            if role == "master" and order.assigned_to != user_id:
                self.send_message(user_id, "🚫 Нет доступа к этой заявке")
                return

            self._send_receipt_if_exists(user_id, order)
        except Exception:
            logger.exception("Ошибка при просмотре чека")
            self.send_message(user_id, "❌ Ошибка при открытии чека")

    # ===== 🚀 Запуск =====
    
    def run(self):
        """Запустить бота"""
        logger.info("🔄 Запуск Telegram бота...")
        try:
            # Удаляем webhook, если он активен
            try:
                self.bot.delete_webhook(drop_pending_updates=True)
                logger.info("✅ Webhook удален (если был активен)")
            except Exception as e:
                logger.warning(f"Не удалось удалить webhook (возможно, его не было): {e}")
            
            logger.info("✅ Telegram бот запущен и готов к работе")
            self.bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except KeyboardInterrupt:
            logger.info("⚠️ Остановка бота пользователем")
        except Exception:
            logger.exception("❌ Неожиданная ошибка в основном цикле")


if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()
