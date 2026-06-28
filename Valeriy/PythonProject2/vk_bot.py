#!/usr/bin/env python3
"""
ВК бот для управления заявками.
Полный перенос функциональности Telegram бота с адаптацией под VK API.
"""

import os
import logging
import threading
import time
from typing import Any, Dict, Optional
from pathlib import Path
import json
from datetime import datetime, timedelta, timezone, time as dt_time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dotenv import load_dotenv

import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.exceptions import ApiError
try:
    from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
except ImportError:
    VkBotLongPoll = None
    VkBotEventType = None

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

# Route management integration (promouters package)
try:
    from promouters.integrations.vk_bot.handlers.routes import RouteCommandHandler
    from promouters.integrations.vk_bot.geo_tracker import GeoTracker

    # Create a separate DB session for promouters database.
    # Uses PROMOUTERS_DATABASE_URL if set, otherwise builds from POSTGRES_* env vars,
    # and ultimately falls back to the bot's own DATABASE_URL.
    from sqlalchemy import create_engine as _promo_create_engine
    from sqlalchemy.orm import sessionmaker as _promo_sessionmaker
    _promo_db_url = os.getenv("PROMOUTERS_DATABASE_URL")
    if not _promo_db_url:
        _pg_user = os.getenv("POSTGRES_USER", "")
        _pg_pass = os.getenv("POSTGRES_PASSWORD", "")
        _pg_host = os.getenv("POSTGRES_HOST", "localhost")
        _pg_port = os.getenv("POSTGRES_PORT", "5432")
        _pg_db = os.getenv("POSTGRES_DB", "")
        if _pg_user and _pg_db:
            _promo_db_url = f"postgresql+psycopg2://{_pg_user}:{_pg_pass}@{_pg_host}:{_pg_port}/{_pg_db}"
        else:
            # Last resort: use the same DATABASE_URL as the bot itself
            _promo_db_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://suupr:suupr_password@localhost:5432/suupr")
    _promo_engine = _promo_create_engine(_promo_db_url, future=True, pool_pre_ping=True)
    PromoSessionLocal = _promo_sessionmaker(bind=_promo_engine, autoflush=False, autocommit=False)

    ROUTE_INTEGRATION_AVAILABLE = True
except Exception as _route_import_err:
    ROUTE_INTEGRATION_AVAILABLE = False
    RouteCommandHandler = None  # type: ignore[assignment,misc]
    GeoTracker = None  # type: ignore[assignment,misc]
    PromoSessionLocal = None  # type: ignore[assignment,misc]

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("VKBot")

class VKBot:
    """Класс ВК бота с полной функциональностью"""
    
    def __init__(self):
        """Инициализация бота"""
        logger.info("🚀 Инициализация ВК бота...")

        # Загружаем переменные окружения (включая ADMIN_IDS) если не запущено через main.py
        try:
            if os.path.exists('local.env'):
                load_dotenv('local.env')
            else:
                load_dotenv()
        except Exception:
            pass

        self.token = os.getenv("VK_BOT_TOKEN")
        if not self.token:
            raise ValueError("❌ Переменная окружения VK_BOT_TOKEN не найдена")
            
        self.vk_session = vk_api.VkApi(token=self.token)
        self.vk = self.vk_session.get_api()
        
        # Пробуем использовать VkBotLongPoll если доступен
        self.use_bot_longpoll = False
        use_bot_longpoll = False
        bot_longpoll_error: Optional[str] = None
        if VkBotLongPoll is not None:
            group_id = os.getenv("VK_GROUP_ID")
            if group_id:
                gid_str = str(group_id).strip()
                if gid_str.startswith("club"):
                    gid_str = gid_str[4:]

                try:
                    gid = abs(int(gid_str))
                    self.longpoll = VkBotLongPoll(self.vk_session, gid)
                    use_bot_longpoll = True
                    logger.info(f"✅ Используется VkBotLongPoll для группы {gid}")
                except ApiError as e:
                    if e.code == 38:
                        bot_longpoll_error = (
                            "❌ VK вернул ошибку 38 (Unknown application) при инициализации VkBotLongPoll.\n"
                            "Проверьте, что используется токен сообщества с доступом к сообщениям и "
                            "включён чат-бот в настройках группы. После обновления настроек пересоздайте токен "
                            "и перезапустите контейнер."
                        )
                        logger.error(bot_longpoll_error)


        if not use_bot_longpoll:
            if bot_longpoll_error:
                raise RuntimeError(bot_longpoll_error)
            group_id = os.getenv("VK_GROUP_ID")
            if not group_id:
                self.use_bot_longpoll = False
                self.longpoll = VkLongPoll(self.vk_session)
                logger.info("✅ Используется обычный VkLongPoll (user long poll)")
            else:
                raise RuntimeError(
                    "❌ Не удалось инициализировать VkBotLongPoll. Проверьте токен сообщества, включите чат-бот и доступ к сообщениям. "
                    "Если вам нужен пользовательский токен, удалите VK_GROUP_ID из окружения."
                )
        else:
            self.use_bot_longpoll = True

        self.logger = logger
        self.states = user_states
        self.city_flow = CityCreationFlow(self, user_states)

        # Initialize route management integration
        self.route_handler = None
        self.geo_tracker = None
        if ROUTE_INTEGRATION_AVAILABLE:
            try:
                self.geo_tracker = GeoTracker(vk_api=self.vk, interval_minutes=30)
                logger.info("✅ GeoTracker инициализирован (интервал 30 мин)")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось инициализировать GeoTracker: {e}")

        logger.info("✅ Бот успешно инициализирован")

    # ===== 🔧 Служебные =====
    
    def send_message(self, user_id: int, message: str, keyboard: Optional[Any] = None):
        """Отправить сообщение пользователю"""
        try:
            params = {
                "user_id": user_id,
                "message": message,
                "random_id": get_random_id(),
            }
            
            if keyboard:
                params["keyboard"] = keyboard.get_keyboard()

            self.vk.messages.send(**params)
            logger.info(f"📤 Отправлено сообщение пользователю {user_id}")
        except ApiError as e:
            if e.code == 912:
                error_msg = (
                    "❌ ОШИБКА: Функция чат-бота не включена в настройках сообщества!\n\n"
                    "📝 Для исправления:\n"
                    "1. Откройте настройки вашего сообщества ВК\n"
                    "2. Перейдите в раздел 'Управление сообществом'\n"
                    "3. В разделе 'Сообщения' включите 'Сообщения сообщества'\n"
                    "4. Ниже включите 'Чат-бот' (или 'Сообщения ботов')\n"
                    "5. Сохраните настройки\n"
                    "6. Перезапустите бота\n\n"
                    "Альтернатива: используйте USER token вместо bot token"
                )
                logger.error(error_msg)
                print("\n" + "=" * 60)
                print(error_msg)
                print("=" * 60 + "\n")
            else:
                logger.error(f"VK API ошибка [{e.code}]: {e.message}")
            logger.exception(f"Ошибка при отправке сообщения пользователю {user_id}")
        except Exception as e:
            logger.exception(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")

    def _extract_geo_from_message(self, message: dict) -> Optional[dict]:
        """Extract geolocation from VK message attachments or geo field.

        VK messages can contain geo in two ways:
        1. message['geo'] - built-in geo location sharing
        2. Attachments with type 'geo' (less common)

        Returns:
            dict with 'latitude', 'longitude' and optionally 'accuracy' keys,
            or None if no geo found.
        """
        # Check message-level geo field (VK built-in location sharing)
        geo = message.get("geo")
        if geo and isinstance(geo, dict):
            coords = geo.get("coordinates")
            if coords and isinstance(coords, dict):
                lat = coords.get("latitude")
                lon = coords.get("longitude")
                if lat is not None and lon is not None:
                    return {"latitude": float(lat), "longitude": float(lon)}

        # Check attachments for geo type
        attachments = message.get("attachments", [])
        for att in attachments:
            if att.get("type") == "geo":
                geo_data = att.get("geo", {})
                coords = geo_data.get("coordinates", {})
                lat = coords.get("latitude")
                lon = coords.get("longitude")
                if lat is not None and lon is not None:
                    return {"latitude": float(lat), "longitude": float(lon)}

        return None

    def get_keyboard(self, role: str):
        """Получить клавиатуру по роли"""
        kb = VkKeyboard(one_time=False)

        if role == "master":
            kb.add_button("✅ На смене", color=VkKeyboardColor.POSITIVE)
            kb.add_button("📦 Мои СД", color=VkKeyboardColor.POSITIVE)
            kb.add_line()
            kb.add_button("💰 Касса", color=VkKeyboardColor.SECONDARY)
            kb.add_button("🔄 Обновить", color=None)
        elif role == "dispatcher":
            kb.add_button("➕ Создать заявку", color=VkKeyboardColor.PRIMARY)
            kb.add_line()
            kb.add_button("👥 Управление мастерами", color=None)
        elif role == "director":
            kb.add_button("📋 Мои заявки", color=VkKeyboardColor.POSITIVE)
            kb.add_button("👤 Добавить мастера", color=VkKeyboardColor.POSITIVE)
            kb.add_line()
            kb.add_button("📊 Статистика", color=None)
            kb.add_button("📦 СД", color=None)
        elif role == "owner":
            kb.add_button("➕ Создать заявку", color=VkKeyboardColor.PRIMARY)
            kb.add_button("📋 Мои заявки", color=VkKeyboardColor.POSITIVE)
            kb.add_line()
            kb.add_button("💼 Касса", color=VkKeyboardColor.PRIMARY)
            kb.add_button("📊 Статистика", color=None)
            kb.add_line()
            kb.add_button("🏙 Добавить город", color=VkKeyboardColor.POSITIVE)
            kb.add_line()
            kb.add_button("⚙️ Админ-панель", color=VkKeyboardColor.NEGATIVE)
        elif role == "promoter":
            kb.add_button("🚀 В работе", color=VkKeyboardColor.POSITIVE)
            kb.add_button("🏁 Завершить", color=VkKeyboardColor.NEGATIVE)
        else:
            # Для остальных ролей (user и т.д.) - только заявки
            kb.add_button("📋 Мои заявки", color=None)

        return kb

    def _get_user_info(self, user_id: int):
        """Получить информацию о пользователе VK"""
        try:
            users = self.vk.users.get(user_ids=[user_id])
            if users:
                return users[0]
        except Exception:
            logger.exception(f"Ошибка получения информации о пользователе {user_id}")
        return {}

    # ===== 🧠 Логика =====
    
    def handle_message(self, message):
        """Обработка входящего сообщения"""
        user_id = message["from_id"]
        text = message.get("text", "").strip()
        # Обработка нажатий на inline-кнопки (payload)
        payload_raw = message.get("payload")
        if payload_raw:
            try:
                payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
            except Exception:
                payload = None
            if isinstance(payload, dict) and payload.get("cmd"):
                session = get_session()
                try:
                    role = get_role(session, user_id) or "user"
                    self.handle_payload(user_id, payload, role, session)
                finally:
                    session.close()
                return

        # Обработка вложений (фото БСО или чека)
        attachments = message.get("attachments", [])
        if attachments:
            state = self.states.get_sum_input_state(message["from_id"])
            if state:
                step = state.get("step")
                if step == "waiting_bso":
                    # Обработка загрузки БСО
                    for att in attachments:
                        bso_attachment = None
                        att_type = att.get("type")
                        if att_type == "photo":
                            photo = att.get("photo", {})
                            owner_id = photo.get("owner_id")
                            photo_id = photo.get("id")
                            if owner_id and photo_id:
                                bso_attachment = f"photo{owner_id}_{photo_id}"
                                access_key = photo.get("access_key")
                                if access_key:
                                    bso_attachment += f"_{access_key}"
                        elif att_type == "doc":
                            doc = att.get("doc", {})
                            owner_id = doc.get("owner_id")
                            doc_id = doc.get("id")
                            if owner_id and doc_id:
                                bso_attachment = f"doc{owner_id}_{doc_id}"
                                access_key = doc.get("access_key")
                                if access_key:
                                    bso_attachment += f"_{access_key}"
                        else:
                            continue

                        if bso_attachment:
                            local_path = self._save_bso_locally(state["order_id"], att)
                            if not local_path:
                                logger.warning(
                                    "Не удалось сохранить БСО локально (order_id=%s, att_type=%s). attachment_id=%s",
                                    state.get("order_id"),
                                    att_type,
                                    bso_attachment,
                                )
                                continue

                            # Сохраняем только если файл реально записался на диск
                            state["data"]["bso_local_path"] = local_path
                            state["data"]["bso_file_id"] = bso_attachment
                            self.states.set_sum_input_state(message["from_id"], state)
                            self.send_message(message["from_id"], "✅ БСО сохранён и прикреплён!")
                            
                            # Проверяем, нужно ли запрашивать чек ЗПЧ
                            zpch_sum = float(state["data"].get("zpch_sum", 0) or 0)
                            if zpch_sum > 0:
                                # Если ЗПЧ > 0, запрашиваем чек
                                state["step"] = "waiting_receipt"
                                self.states.set_sum_input_state(message["from_id"], state)
                                self._prompt_receipt_upload(message["from_id"])
                            else:
                                # Если ЗПЧ = 0, сразу переходим к расчету
                                self._calculate_and_show_result_vk(message["from_id"])
                            return

                    self.send_message(message["from_id"], "❌ Не удалось распознать БСО. Отправьте фото или файл ещё раз.")
                    return
                elif step == "waiting_receipt":
                    # Обработка загрузки чека ЗПЧ
                    for att in attachments:
                        receipt_attachment = None
                        att_type = att.get("type")
                        if att_type == "photo":
                            photo = att.get("photo", {})
                            owner_id = photo.get("owner_id")
                            photo_id = photo.get("id")
                            if owner_id and photo_id:
                                receipt_attachment = f"photo{owner_id}_{photo_id}"
                                access_key = photo.get("access_key")
                                if access_key:
                                    receipt_attachment += f"_{access_key}"
                        elif att_type == "doc":
                            doc = att.get("doc", {})
                            owner_id = doc.get("owner_id")
                            doc_id = doc.get("id")
                            if owner_id and doc_id:
                                receipt_attachment = f"doc{owner_id}_{doc_id}"
                                access_key = doc.get("access_key")
                                if access_key:
                                    receipt_attachment += f"_{access_key}"
                        else:
                            continue

                        if receipt_attachment:
                            local_path = self._save_receipt_locally(state["order_id"], att)
                            if local_path:
                                state["data"]["receipt_local_path"] = local_path
                                logger.info(f"Чек сохранен локально для заявки {state['order_id']}: {local_path}")
                            else:
                                logger.warning(f"Не удалось сохранить чек локально для заявки {state['order_id']}, но receipt_file_id сохранен")
                            state["data"]["receipt_file_id"] = receipt_attachment
                            self.states.set_sum_input_state(message["from_id"], state)
                            self.send_message(message["from_id"], "✅ Чек получен!")
                            self._calculate_and_show_result_vk(message["from_id"])
                            return

                    self.send_message(message["from_id"], "❌ Не удалось распознать чек. Отправьте фото или файл ещё раз.")
                    return

        # Handle geo location attachments for GeoTracker
        if ROUTE_INTEGRATION_AVAILABLE and self.geo_tracker and attachments:
            geo = self._extract_geo_from_message(message)
            if geo is not None:
                self.geo_tracker.on_geo_received(
                    user_id=user_id,
                    lat=geo["latitude"],
                    lon=geo["longitude"],
                    accuracy=geo.get("accuracy"),
                )

        if not text:
            return

        # --- Route command handling (promouters integration) ---
        if ROUTE_INTEGRATION_AVAILABLE:
            geo = self._extract_geo_from_message(message)
            text_lower_route = text.lower().strip()

            # Check if user is awaiting leaflet count input
            if RouteCommandHandler._awaiting_leaflet.get(user_id):
                try:
                    db = PromoSessionLocal()
                    handler = RouteCommandHandler(db=db)
                    response = handler.handle_leaflet_count(user_id, text)
                    self.send_message(user_id, response)
                except Exception as e:
                    logger.exception("Ошибка обработки ввода количества (user_id=%s): %s", user_id, e)
                finally:
                    db.close()
                return

            # "В работе" command - start shift
            if "в работе" in text_lower_route:
                try:
                    db = PromoSessionLocal()
                    handler = RouteCommandHandler(db=db)
                    response = handler.handle_start_shift(user_id, geo)
                    self.send_message(user_id, response)
                except Exception as e:
                    logger.exception("Ошибка старта смены (user_id=%s): %s", user_id, e)
                    self.send_message(user_id, f"Ошибка старта смены: {type(e).__name__}: {e}")
                finally:
                    db.close()
                return

            # "Завершить" command - finish shift
            if "завершить" in text_lower_route:
                try:
                    db = PromoSessionLocal()
                    handler = RouteCommandHandler(db=db)
                    response = handler.handle_finish_shift(user_id, geo)
                    self.send_message(user_id, response)
                except Exception as e:
                    logger.exception("Ошибка завершения смены (user_id=%s): %s", user_id, e)
                    self.send_message(user_id, "Произошла ошибка при завершении смены. Попробуйте позже.")
                finally:
                    db.close()
                return

        session = get_session()
        try:
            # Получаем имя пользователя из VK
            first_name = ""
            try:
                user_info = self.vk.users.get(user_ids=[user_id])
                if user_info:
                    first_name = user_info[0].get('first_name', '')
            except:
                pass
            
            # Создаем объект пользователя для ensure_user
            class VKUser:
                def __init__(self, uid, name):
                    self.id = uid
                    self.first_name = name
            
            vk_user = VKUser(user_id, first_name)
            ensure_user(session, vk_user)
            # Получаем роль пользователя (ensure_user уже установит owner для новых пользователей из ADMIN_IDS)
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
        msg = f"👋 Привет! Добро пожаловать в ВК бот.\n\nВаша роль: {role}"
        self.send_message(user_id, msg, kb)

    def handle_help(self, user_id: int):
        """Обработка команды /help"""
        msg = (
            "📋 Команды:\n"
            "/start — начать работу\n"
            "/help — помощь\n"
            "/setrole — назначить роль (только owner)\n"
            "  Форматы: /setrole <role> <vk_id> [city_id] | /setrole <vk_id> <role> [city_id]\n"
            "/add_city <name> — добавить город (owner)\n"
            "/list_cities — список городов\n"
            "/del_city <id> — удалить город (owner)\n"
            "/assign_director <vk_id> <city_id> — назначить директора (owner)\n"
            "/assign_order <order_number> <vk_id> — назначить заявку (director/dispatcher/owner)\n"
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
                "  /setrole <role> <vk_id> [city_id]  (рекомендуется)\n"
                "  /setrole <vk_id> <role> [city_id]  (поддерживается)\n\n"
                "Примеры:\n"
                "/setrole owner 123456789\n"
                "/setrole director 123456789 1\n"
                "/setrole dispatcher 123456789\n"
                "/setrole master 123456789\n\n"
                "💡 Как получить VK ID:\n"
                "1. Откройте профиль пользователя в VK\n"
                "2. Посмотрите URL: https://vk.com/id123456789\n"
                "3. Цифры после 'id' — это VK ID (123456789)\n\n"
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
                vk_id_str = args[1]
                city_id_str = args[2] if len(args) >= 3 else None
            else:
                vk_id_str = args[0]
                newrole = args[1].lower()
                city_id_str = args[2] if len(args) >= 3 else None

            if newrole not in allowed_roles:
                self.send_message(user_id, f"❌ Неверная роль. Доступные: {', '.join(allowed_roles)}")
                return

            vk_id = int(vk_id_str)

            # Создаём/обновляем пользователя
            app_user = session.query(User).filter_by(tg_id=vk_id).first()
            if not app_user:
                app_user = User(tg_id=vk_id, name=str(vk_id), role=newrole)
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
            # Явно обновляем объект из базы после commit
            session.refresh(app_user)
            
            if vk_id == user_id:
                # Обновляем клавиатуру с новой ролью
                kb = self.get_keyboard(newrole)
                msg = f"✅ Ваша роль изменена на: {newrole}\n\n💡 Отправьте любое сообщение, чтобы обновить меню."
                self.send_message(user_id, msg, kb)
            else:
                # Получаем имя пользователя для отображения
                try:
                    vk_info = self.vk.users.get(user_ids=[vk_id])
                    user_name = vk_info[0].get('first_name', str(vk_id)) if vk_info else str(vk_id)
                except:
                    user_name = str(vk_id)
                
                self.send_message(user_id, f"✅ Роль пользователя {user_name} (ID: {vk_id}) изменена на: {newrole}")
                
        except ValueError:
            self.send_message(user_id, "❌ VK ID должен быть числом. Пример: /setrole 123456789 owner")
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
            self.send_message(user_id, "📝 Использование: /assign_director <vk_id> <city_id>")
            return
        try:
            vk_id = int(parts[1]); city_id = int(parts[2])
        except ValueError:
            self.send_message(user_id, "❌ vk_id и city_id должны быть числами")
            return
        if not session.query(City).filter_by(id=city_id).first():
            self.send_message(user_id, f"❌ Город с ID {city_id} не найден")
            return
        user = session.query(User).filter_by(tg_id=vk_id).first()
        if not user:
            user = User(tg_id=vk_id, name=str(vk_id))
            session.add(user)
            session.flush()
        user.role = "director"
        user.city_id = city_id
        session.commit()
        self.send_message(user_id, f"✅ Назначен директор: {vk_id} для города ID {city_id}")

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
                "умолчание",
            ):
                tz_candidate = potential_tz
                args = args[:-1]

        name = " ".join(args).strip()
        if not name:
            self.send_message(user_id, "❌ Укажите название города.")
            return

        if tz_candidate:
            self.city_flow.create_immediate(user_id, session, name, tz_candidate)
        else:
            self.city_flow.start_with_name(user_id, name)

    def _handle_assign_order_command(self, user_id: int, text: str, role: str, session):
        if role not in ("owner", "director", "dispatcher"):
            self.send_message(user_id, "🚫 Нет доступа.")
            return
        parts = text.split()
        if len(parts) < 3:
            self.send_message(user_id, "📝 Использование: /assign_order <order_number> <vk_id>")
            return
        try:
            order_number = int(parts[1]); vk_id = int(parts[2])
        except ValueError:
            self.send_message(user_id, "❌ order_number и vk_id должны быть числами")
            return
        order = session.query(Order).filter_by(order_number=order_number).first()
        if not order:
            self.send_message(user_id, f"❌ Заявка №{order_number} не найдена")
            return
        
        # Сохраняем старого мастера для уведомления об отмене
        old_master_id = order.assigned_to
        old_master = None
        if old_master_id and old_master_id != vk_id:
            old_master = session.query(User).filter_by(tg_id=old_master_id).first()
        
        order.assigned_to = vk_id
        order.status = "assigned"
        session.commit()
        
        # Уведомляем старого мастера об отмене, если заявка была переназначена
        if old_master and old_master.role == "master":
            try:
                self.send_message(old_master_id, f"❌ Заявка №{order.order_number} отменена")
            except Exception:
                pass
        
        # Уведомляем нового мастера
        try:
            self._notify_master_vk(order, session)
        except Exception:
            pass
        self.send_message(user_id, f"✅ Заявка №{order_number} назначена пользователю {vk_id}")

    def _handle_seed_cities(self, user_id: int, text: str, role: str, session):
        if role != "owner":
            self.send_message(user_id, "🚫 Только owner может добавлять города.")
            return
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            self.send_message(user_id, "📝 Использование: /seed_cities City1,City2,City3")
            return
        names = [x.strip() for x in parts[1].split(',') if x.strip()]
        added = 0; skipped = 0
        for name in names:
            if session.query(City).filter(City.name.ilike(name)).first():
                skipped += 1; continue
            session.add(City(name=name)); added += 1
        session.commit()
        self.send_message(user_id, f"✅ Добавлено городов: {added}. Пропущено (существуют): {skipped}")

    def handle_text(self, user_id: int, text: str, text_lower: str, role: str, session):
        """Обработка обычного текста"""
        # Проверяем состояние пользователя
        form_state = self.states.get_form_state(user_id)
        sum_input_state = self.states.get_sum_input_state(user_id)
        master_creation_state = self.states.get_master_creation_state(user_id)
        city_creation_state = self.states.get_city_creation_state(user_id)
        
        if form_state:
            # Пользователь заполняет форму заявки
            try:
                self._handle_form_step(user_id, text, role, session)
            except Exception as e:
                logger.exception("Ошибка в сценарии создания заявки (user_id=%s): %s", user_id, e)
                # Не зависаем молча — даем пользователю понятный ответ
                self.send_message(
                    user_id,
                    "❌ Ошибка при обработке шага создания заявки. Попробуйте еще раз.\n"
                    "Если повторяется — напишите 'отмена' и начните заново."
                )
            return
        elif sum_input_state:
            # Пользователь вводит сумму (VK)
            self._handle_sum_input_vk(user_id, text, session)
            return
        elif master_creation_state:
            # Создание мастера (директор/собственник)
            self._handle_master_creation_step(user_id, text, role, session)
            return
        elif city_creation_state:
            if self.city_flow.handle(user_id, text, role, session):
                return
            # Если обработчик не завершил сценарий, продолжаем без возврата
            return
        else:
            # Редактирование процентов (owner)
            pct_state = self.states.get_equipment_edit_state(user_id)
        if pct_state and pct_state.get("step") == "pct":
            self._handle_pct_edit_input(user_id, text, role)
            return
        elif text_lower == "📋 мои заявки":
            self.handle_my_orders(user_id, role, session)
        elif text_lower in ("📊 статистика", "📊 стата"):
            if role == "master":
                # Для мастеров открываем веб-версию статистики
                self._open_master_web_stats(user_id, session)
            else:
                # Для остальных ролей показываем статистику в боте
                self.handle_stats(user_id, role, session)
        elif text_lower == "✅ на смене" and role != "master":
            # Кнопка "В работе" только для не-мастеров (пока убираем у мастеров)
            self.handle_check_in(user_id, role, session)
        elif text_lower == "📦 мои сд":
            self.handle_my_sd(user_id, role, session)
        elif text_lower == "💰 касса":
            self.handle_cash(user_id, role, session)
        elif text_lower in ("💼 касса", "касса") and role in ("director", "owner"):
            self._handle_cash_overview(user_id, role, session)
        elif text.strip() == "🏙 Добавить город" or text_lower == "добавить город":
            self.city_flow.start(user_id)
        elif text_lower == "➕ создать заявку":
            self._start_form(user_id, role, session)
        elif text_lower == "👥 управление мастерами":
            self._handle_manage_masters(user_id, role, session)
        elif text_lower == "👤 добавить мастера":
            self._start_add_master(user_id, role, session)
        elif text_lower == "📦 сд":
            self._handle_director_sd(user_id, role, session)
        elif text_lower == "⚙️ админ-панель":
            self._handle_admin_panel_entry(user_id, role, session)
        elif text_lower == "🔄 обновить":
            kb = self.get_keyboard(role)
            self.send_message(user_id, "🔄 Меню обновлено!", kb)
        else:
            kb = self.get_keyboard(role)
            self.send_message(user_id, "🤔 Не понимаю. Используйте кнопки меню или команды.", kb)

    # ====== Создание заявки (диспетчер и собственник) ======
    def _start_form(self, user_id: int, role: str, session):
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
        state = self.states.get_form_state(user_id)
        if not isinstance(state, dict):
            state = {}
        step = state.get("step")
        data = state.get("data") or {}
        # Защита от поломанных состояний (data может быть None/строкой и т.п.)
        if not isinstance(data, dict):
            logger.warning("Форма: некорректные данные state['data']=%r (user_id=%s). Сбрасываем.", data, user_id)
            data = {}
        state["data"] = data
        t_original = text.strip()  # Оригинальный текст для использования
        t = t_original.lower()  # Для проверок

        logger.info("Форма VK (user_id=%s): step=%s, text=%r", user_id, step, t_original)
        
        # Проверка на отмену формы
        if t in ("отмена", "cancel", "отменить", "стоп", "/cancel"):
            self.states.clear_form_state(user_id)
            kb = self.get_keyboard(role)
            self.send_message(user_id, "❌ Создание заявки отменено.", kb)
            return
        
        # Если шаг не определен, сбрасываем форму
        if not step:
            self.states.clear_form_state(user_id)
            self.send_message(user_id, "❌ Произошла ошибка при заполнении формы. Пожалуйста, начните заново.")
            return
        
        if step == "city":
            city = None
            # Пробуем найти по ID
            try:
                city_id = int(t_original)
                city = session.query(City).filter_by(id=city_id).first()
            except ValueError:
                # Пробуем найти по названию (регистронезависимо)
                try:
                    # Используем ilike для PostgreSQL или upper для совместимости
                    city = session.query(City).filter(City.name.ilike(f"%{t_original}%")).first()
                    # Если не сработало, пробуем точное совпадение
                    if not city:
                        city = session.query(City).filter(City.name.ilike(t_original)).first()
                except Exception as e:
                    # Fallback для баз, которые не поддерживают ilike
                    all_cities = session.query(City).all()
                    t_lower = t_original.lower()
                    for c in all_cities:
                        if c.name and t_lower in c.name.lower():
                            city = c
                            break
            
            if not city:
                # Показываем список городов еще раз
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
            # допускаем ввод имени или кода
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
                    self.send_message(user_id, "⚠️ Для этого города не найден директор. Укажите VK ID ответственного вручную или '-' чтобы пропустить.")
            state.update({"step": "assign", "data": data})
            self.states.set_form_state(user_id, state)
            masters = session.query(User).filter_by(role="master").all()
            if masters:
                kb = self._kb_master_selection(masters, session)
                self.send_message(user_id, "👤 Выберите мастера из списка или пропустите:", kb)
            else:
                self.send_message(user_id, "👤 Мастера не найдены. Назначить мастера позже?\nВведите VK ID мастера или '-' чтобы пропустить:")
            return
        if step == "assign":
            assigned_to = None
            if t_original.strip() and t_original.strip() != "-":
                try:
                    assigned_to = int(t_original.strip())
                except ValueError:
                    self.send_message(user_id, "❌ Введите числовой VK ID мастера или '-' чтобы пропустить:\n💡 Для отмены напишите 'отмена'")
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
                    source=data.get("source", "vk"),
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
                            self._notify_master_vk(order, session)
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

    # ====== Управление мастерами / добавление ======
    def _handle_manage_masters(self, user_id: int, role: str, session):
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
        if role not in ("director", "owner"):
            self.send_message(user_id, "🚫 У вас нет доступа к этой функции. Доступно только директорам и собственникам.")
            return
        self.states.set_master_creation_state(user_id, {"step": "ask_id", "data": {}})
        self.send_message(user_id, "Введите VK ID нового мастера:")

    def _handle_master_creation_step(self, user_id: int, text: str, role: str, session):
        state = self.states.get_master_creation_state(user_id) or {}
        step = state.get("step")
        data = state.get("data", {})
        t = text.strip()
        if step == "ask_id":
            try:
                data["tg_id"] = int(t)
            except ValueError:
                self.send_message(user_id, "❌ Введите числовой VK ID:")
                return
            state.update({"step": "ask_name", "data": data})
            self.states.set_master_creation_state(user_id, state)
            self.send_message(user_id, "Введите имя мастера:")
            return
        if step == "ask_name":
            data["name"] = t
            # попытка проставить город как у директора
            director = session.query(User).filter_by(tg_id=user_id).first()
            new_master = User(tg_id=data["tg_id"], name=data.get("name"), role="master", city_id=getattr(director, "city_id", None))
            session.add(new_master)
            session.commit()
            self.states.clear_master_creation_state(user_id)
            self.send_message(user_id, f"✅ Мастер добавлен: {new_master.name} ({new_master.tg_id})")
            kb = self.get_keyboard(role)
            self.send_message(user_id, "🏠 Главное меню:", kb)
            return

    # ====== Директор: СД и касса ======
    def _handle_director_sd(self, user_id: int, role: str, session):
        if role not in ("director", "owner"):
            self.send_message(user_id, "🚫 У вас нет доступа к этой функции. Доступно только директорам и собственникам.")
            return
        orders = session.query(Order).filter(Order.status.in_(["accepted", "on_place", "to_sd"]))\
            .order_by(Order.created_at.desc()).limit(50).all()
        if not orders:
            self.send_message(user_id, "📦 Нет техники на руках у мастеров (СД пусто)")
            return
        
        # Группируем по мастерам
        masters_dict = {}
        for o in orders:
            master_id = o.assigned_to
            if master_id not in masters_dict:
                masters_dict[master_id] = []
            masters_dict[master_id].append(o)
        
        # Показываем статистику по мастерам
        text = f"📦 СД (активные заявки)\n\n"
        text += f"Всего заявок: {len(orders)}\n"
        text += f"Мастеров: {len(masters_dict)}\n\n"
        
        # Показываем по мастерам
        for master_id, master_orders in masters_dict.items():
            master = session.query(User).filter_by(tg_id=master_id).first()
            master_name = master.full_name or master.name or str(master_id) if master else str(master_id)
            text += f"👤 {master_name} — {len(master_orders)} заявок\n"
        
        # Клавиатура для выбора мастера
        kb = VkKeyboard(inline=True)
        for master_id, master_orders in list(masters_dict.items())[:10]:  # Максимум 10 кнопок
            master = session.query(User).filter_by(tg_id=master_id).first()
            master_name = master.full_name or master.name or str(master_id) if master else str(master_id)
            kb.add_button(f"👤 {master_name} ({len(master_orders)})", 
                         color=VkKeyboardColor.SECONDARY, 
                         payload={"cmd": "sd_master", "master_id": master_id})
        
        self.send_message(user_id, text, kb)

    def _handle_cash_overview(self, user_id: int, role: str, session):
        """Показать кассу по мастерам с возможностью приема"""
        if role not in ("director", "owner"):
            self.send_message(user_id, "🚫 У вас нет доступа к этой функции. Доступно только директорам и собственникам.")
            return
        
        # Получаем город директора (если директор)
        city_id = None
        if role == "director":
            user = session.query(User).filter_by(tg_id=user_id).first()
            city_id = user.city_id if user else None
        
        # Получаем заявки со статусом done_pending_sum (не принятые кассой)
        from model import Order
        query = session.query(Order).filter(Order.status == "done_pending_sum")
        
        # Если директор - фильтруем по городу
        if role == "director" and city_id:
            query = query.filter(Order.city_id == city_id)
        
        pending_orders = query.all()
        
        if not pending_orders:
            self.send_message(user_id, "✅ Все заявки по кассе приняты")
            return
        
        # Группируем по мастерам
        from collections import defaultdict
        masters_cash = defaultdict(list)
        
        for order in pending_orders:
            master_id = order.assigned_to
            if master_id:
                masters_cash[master_id].append(order)
        
        if not masters_cash:
            self.send_message(user_id, "✅ Нет заявок для приема кассы")
            return
        
        # Формируем сообщение с кассой по каждому мастеру
        from services.commission_service import get_master_pct
        lines = []
        total_all = 0.0
        
        for master_id, orders in masters_cash.items():
            master = session.query(User).filter_by(tg_id=master_id).first()
            master_name = (master.full_name or master.name or str(master_id)) if master else str(master_id)
            
            master_total = 0.0
            order_lines = []
            
            for order in orders:
                order_sum = order.sum_amount or 0
                zpch_sum = getattr(order, 'zpch_sum', 0) or 0
                net_amount = max(order_sum - zpch_sum, 0)
                
                # Проверяем индивидуальный процент мастера
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
            
            # Формируем сообщение для мастера
            master_msg = (
                f"🔧 Мастер: {master_name}\n"
                + "\n".join(order_lines)
                + f"\n\n💰 Итого к приему: {master_total:.2f} руб."
            )
            
            # Кнопка приема кассы мастера
            kb = VkKeyboard(inline=True)
            button_text = f"✅ Принять кассу" if len(master_name) > 20 else f"✅ Принять кассу {master_name}"
            kb.add_button(button_text, color=VkKeyboardColor.POSITIVE, 
                         payload={"cmd": "accept_cash", "master_id": master_id})
            self.send_message(user_id, master_msg, kb)
        
        # Общая сумма
        if len(masters_cash) > 1:
            self.send_message(user_id, f"\n💰 Общая сумма к приему: {total_all:.2f} руб.")
    
    def _payload_accept_cash(self, user_id: int, payload: dict, role: str, session):
        """Приемка кассы мастера директором/собственником"""
        if role not in ("director", "owner"):
            self.send_message(user_id, "🚫 У вас нет доступа к этой функции. Доступно только директорам и собственникам.")
            return
        
        master_id = int(payload.get("master_id", 0))
        if not master_id:
            self.send_message(user_id, "❌ Не указан мастер. Попробуйте еще раз.")
            return
        
        # Проверяем, что директор может принимать кассу мастера из своего города
        if role == "director":
            director = session.query(User).filter_by(tg_id=user_id).first()
            if not director or not director.city_id:
                self.send_message(user_id, "❌ У вас не указан город. Обратитесь к администратору для настройки профиля.")
                return
            
            master = session.query(User).filter_by(tg_id=master_id).first()
            if not master or master.city_id != director.city_id:
                self.send_message(user_id, "🚫 Вы можете принимать кассу только мастеров из своего города")
                return
        
        # Получаем все заявки мастера со статусом done_pending_sum
        from model import Order
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
            zpch_sum = getattr(order, 'zpch_sum', 0) or 0
            net_amount = max(order_sum - zpch_sum, 0)
            
            # Проверяем индивидуальный процент мастера
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
            
            # Создаем запись в статистике (гарантийные выезды не учитываем)
            if not getattr(order, "is_warranty", False):
                stat = Stat(
                    order_id=order.id,
                    equip_type=order.equip_type,
                    sum=net_amount,
                    refused=(order_sum == 0),
                    master_tg=master_id
                )
                session.add(stat)
            
            # Меняем статус заявки на completed
            order.status = "completed"

            # Автосрок гарантии по сумме закрытия (для не-гарантийных и не-отменённых)
            if not getattr(order, "is_warranty", False) and order.status != "cancelled":
                from services.warranty_service import compute_warranty
                from datetime import datetime, timezone
                closed_amount = float(order.sum_amount or order.paid_amount or 0)
                winfo = compute_warranty(closed_amount, datetime.now(timezone.utc))
                order.warranty_days = int(winfo.days)
                order.warranty_until = winfo.until
        
        session.commit()
        
        master = session.query(User).filter_by(tg_id=master_id).first()
        master_name = (master.full_name or master.name or str(master_id)) if master else str(master_id)
        
        self.send_message(user_id, f"✅ Касса мастера {master_name} принята!\n\nСумма: {total_company:.2f} руб.\nЗаявок: {len(orders)}")
        
        # Уведомляем мастера
        try:
            self.send_message(master_id, f"✅ Ваша касса принята!\n\nСумма: {total_company:.2f} руб.\nЗаявок: {len(orders)}")
        except Exception:
            pass

    def _handle_admin_panel_entry(self, user_id: int, role: str, session):
        if role not in ("owner", "director"):
            self.send_message(user_id, "🚫 Нет доступа.")
            return
        if role == "director":
            self.send_message(user_id, "⚙️ Админ-панель (директор):\n- Заявки\n- Статистика\n- Касса\n- СД")
        else:
            # Владелец: показываем меню процентов и пр.
            kb = VkKeyboard(inline=True)
            kb.add_button("📊 Проценты техники", color=VkKeyboardColor.PRIMARY, payload={"cmd": "pct_menu"})
            self.send_message(user_id, "⚙️ Админ-панель (собственник):\n\n📊 Проценты техники - редактирование процентных ставок по категориям и диапазонам", kb)

    # ===== VK inline keyboards =====
    def _kb_master_new_order(self, order_id: int):
        kb = VkKeyboard(inline=True)
        kb.add_button("✅ Принять", color=VkKeyboardColor.POSITIVE, payload={"cmd": "accept", "order_id": order_id})
        return kb

    def _kb_master_on_way(self, order_id: int):
        kb = VkKeyboard(inline=True)
        kb.add_button("🚗 В пути", color=VkKeyboardColor.PRIMARY, payload={"cmd": "onway", "order_id": order_id})
        return kb

    def _kb_master_ready(self, order_id: int):
        """Клавиатура: либо забрал на СД, либо готово"""
        kb = VkKeyboard(inline=True)
        kb.add_button("📦 Забрал на СД", color=VkKeyboardColor.SECONDARY, payload={"cmd": "to_sd", "order_id": order_id})
        kb.add_button("⚡ Готово", color=VkKeyboardColor.POSITIVE, payload={"cmd": "ready", "order_id": order_id})
        return kb

    def _kb_sd_ready(self, order_id: int):
        """Клавиатура для закрытия заявки из раздела СД"""
        kb = VkKeyboard(inline=True)
        kb.add_button("⚡ Готово", color=VkKeyboardColor.POSITIVE, payload={"cmd": "ready", "order_id": order_id})
        kb.add_button("✅ Закрыть СД", color=VkKeyboardColor.SECONDARY, payload={"cmd": "close_sd", "order_id": order_id})
        return kb

    def _get_city_director(self, city_id: Optional[int], session):
        if not city_id:
            return None
        return session.query(User).filter_by(role="director", city_id=city_id).first()

    def _get_timezone_for_city(self, city: Optional[City]) -> ZoneInfo:
        tz_name = None
        if city:
            tz_name = getattr(city, "timezone", None)
        if tz_name:
            try:
                return ZoneInfo(tz_name)
            except ZoneInfoNotFoundError:
                logger.warning(
                    "Не удалось загрузить таймзону '%s', используем по умолчанию (%s). "
                    "Убедитесь, что tzdata установлена или поправьте поле timezone города.",
                    tz_name,
                    DEFAULT_TZ_NAME,
                )
            except Exception as e:
                logger.warning(f"Не удалось загрузить таймзону '{tz_name}' ({e}), используем по умолчанию.")
        return DEFAULT_TZ

    def _format_local_datetime(self, dt: Optional[datetime], tz: ZoneInfo) -> str:
        if not dt:
            return "-"
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.astimezone(tz).strftime("%d.%m.%Y %H:%M")

    def _get_local_day_bounds(self, local_date, tz: ZoneInfo):
        start_local = datetime.combine(local_date, dt_time.min, tzinfo=tz)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = (start_local + timedelta(days=1)).astimezone(timezone.utc)
        return start_utc, end_utc

    def _build_order_preview(self, data: dict, session) -> str:
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
        tz = self._get_timezone_for_city(order.city_rel)
        address_parts = [order.street or "-", f"д.{order.house or '-'}"]
        if getattr(order, "flat", None):
            address_parts.append(f"кв.{order.flat}")
        address_line = ", ".join(address_parts)
        time_window = ""
        if getattr(order, "time_from", None) or getattr(order, "time_to", None):
            time_window = f"{order.time_from or '-'} - {order.time_to or '-'}"
        # Всегда показываем информацию о клиенте, даже если поля пустые
        client_name = getattr(order, "client_name", None) or "Не указано"
        if hide_phone:
            client_info = f"👤 Клиент: {client_name}"
        else:
            client_phone = getattr(order, "client_phone", None) or "Не указан"
            client_info = f"👤 Клиент: {client_name} ({client_phone})"
        master_line = ""
        if master_name:
            master_line = f"🔧 Мастер: {master_name}"
        sum_amount = float(getattr(order, "sum_amount", 0) or 0)
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
            title = os.path.basename(receipt_path)
            if self._send_doc(user_id, receipt_path, title=title):
                return

        receipt_id = getattr(order, "receipt_file_id", None)
        if receipt_id:
            try:
                self.vk.messages.send(
                    user_id=user_id,
                    random_id=get_random_id(),
                    attachment=receipt_id,
                    message="📷 Фото чека",
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить чек по заявке {order.id}: {e}")

    def _notify_director_new_order(self, order, director):
        try:
            # Директору показываем заявку без телефона клиента
            city_name = order.city_rel.name if order.city_rel else "Не указан"
            equip = get_equip_type_name(order.equip_type)
            
            text = (
                f"🆕 Новая заявка №{order.order_number}\n\n"
                f"🏙 Город: {city_name}\n"
                f"⏰ Время: {order.time_from} - {order.time_to}\n"
                f"📍 Адрес: ул. {order.street}, дом {order.house}, кв. {order.flat or '-'}\n"
                f"🔧 Техника: {equip}\n"
            )
            
            # Добавляем описание, если есть
            if order.short_desc:
                text += f"📝 Описание: {order.short_desc}\n"
            
            # Добавляем имя клиента, если есть (но без телефона)
            text += f"👤 Клиент: {order.client_name or 'Не указано'}\n"
            
            # Добавляем источник, если есть
            if order.source:
                text += f"📞 Источник: {order.source}\n"
            
            # Добавляем комментарий, если есть
            if order.comment:
                text += f"💬 Комментарий: {order.comment}\n"
            
            text += "\n👉 Вы можете назначить мастера или взять заявку на себя."
            
            kb = VkKeyboard(inline=True)
            kb.add_button(
                "✅ Взять себе",
                color=VkKeyboardColor.POSITIVE,
                payload={"cmd": "take_order", "order_id": order.id},
            )
            kb.add_line()
            kb.add_button(
                "👤 Назначить мастеру",
                color=VkKeyboardColor.PRIMARY,
                payload={"cmd": "assign_menu", "order_id": order.id},
            )
            self.send_message(director.tg_id, text, kb)
        except Exception as e:
            logger.warning(f"Не удалось уведомить директора {director.tg_id}: {e}")

    def _kb_sum_cancel(self):
        # Кнопки отмены отключены по требованию
        return None

    def _kb_zpch_zero(self):
        kb = VkKeyboard(inline=True)
        kb.add_button("ЗПЧ = 0", color=VkKeyboardColor.SECONDARY, payload={"cmd": "zpch_zero"})
        return kb

    def _kb_receipt_prompt(self):
        """Клавиатура для загрузки чека или пропуска"""
        kb = VkKeyboard(inline=True)
        kb.add_button("⏭ Пропустить чек", color=VkKeyboardColor.SECONDARY, payload={"cmd": "skip_receipt"})
        return kb

    def _prompt_receipt_upload(self, user_id: int):
        """Отправить пользователю запрос на загрузку чека"""
        state = self.states.get_sum_input_state(user_id)
        if not state:
            return
        kb = self._kb_receipt_prompt()
        message = (
            "📷 Отправьте фото или файл чека (можно загрузить doc/pdf).\n"
            "Если чека нет — нажмите «Пропустить чек»."
        )
        self.send_message(user_id, message, kb)

    def _prompt_bso_upload(self, user_id: int):
        """Отправить пользователю запрос на загрузку БСО"""
        state = self.states.get_sum_input_state(user_id)
        if not state:
            return
        
        # Проверяем сумму заявки - если < 5000, пропускаем БСО автоматически
        order_sum = float(state["data"].get("order_sum", 0) or 0)
        if order_sum < 5000:
            # Автоматически пропускаем БСО для заявок менее 5000
            state["data"]["bso_local_path"] = None
            state["data"]["bso_file_id"] = None
            self.states.set_sum_input_state(user_id, state)
            
            # Проверяем, нужно ли запрашивать чек (если ЗПЧ > 0)
            zpch_sum = float(state["data"].get("zpch_sum", 0) or 0)
            if zpch_sum > 0:
                state["step"] = "waiting_receipt"
                self.states.set_sum_input_state(user_id, state)
                self.send_message(user_id, "✅ БСО пропущен (сумма заявки менее 5000 руб.)")
                self._prompt_receipt_upload(user_id)
            else:
                # Если ЗПЧ = 0, сразу переходим к расчету
                self.send_message(user_id, "✅ БСО пропущен (сумма заявки менее 5000 руб.)")
                self._calculate_and_show_result_vk(user_id)
            return
        
        kb = None
        message = (
            "📄 Отправьте фото или файл БСО (договор/квитанция/акт выполненных работ)."
        )
        self.send_message(user_id, message, kb)

    def _save_bso_locally(self, order_id: int, attachment: dict) -> Optional[str]:
        """Сохранить БСО на диск и вернуть имя файла для сохранения в БД"""
        try:
            from services.bso_storage import save_bso_from_url
            
            att_type = attachment.get("type")
            url = None

            if att_type == "photo":
                photo = attachment.get("photo", {})
                sizes = photo.get("sizes") or []
                if sizes:
                    size = max(sizes, key=lambda s: (s.get("width", 0) * s.get("height", 0)))
                    url = size.get("url")
                else:
                    url = photo.get("orig_photo", {}).get("url")
            elif att_type == "doc":
                doc = attachment.get("doc", {})
                url = doc.get("url")
            else:
                return None

            if not url:
                return None

            # Используем единый сервис для сохранения БСО
            # Сервис сам определит расширение из URL или по типу файла
            filename = save_bso_from_url(order_id, url)
            return filename
            
        except Exception as e:
            logger.error(f"❌ Не удалось сохранить БСО локально для заявки {order_id}: {e}")
            return None

    def _save_receipt_locally(self, order_id: int, attachment: dict) -> Optional[str]:
        """Сохранить чек на диск и вернуть путь до файла"""
        try:
            import requests
            from urllib.parse import urlparse

            att_type = attachment.get("type")
            url = None
            filename = None

            if att_type == "photo":
                photo = attachment.get("photo", {})
                sizes = photo.get("sizes") or []
                if sizes:
                    size = max(sizes, key=lambda s: (s.get("width", 0) * s.get("height", 0)))
                    url = size.get("url")
                else:
                    url = photo.get("orig_photo", {}).get("url")
                filename = f"receipt_{order_id}_{int(time.time())}.jpg"
            elif att_type == "doc":
                doc = attachment.get("doc", {})
                url = doc.get("url")
                title = doc.get("title") or f"receipt_{order_id}"
                _, ext = os.path.splitext(title)
                if not ext:
                    ext = ".doc"
                filename = f"receipt_{order_id}_{int(time.time())}{ext}"
            else:
                return None

            if not url:
                return None

            parsed = urlparse(url)
            if not filename:
                base = os.path.basename(parsed.path) or f"receipt_{order_id}"
                filename = base

            # Используем ту же директорию, что и для БСО (абсолютный путь)
            receipt_dir = Path("bso_files").resolve()
            receipt_dir.mkdir(exist_ok=True)
            file_path = receipt_dir / filename

            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                return None

            with open(file_path, "wb") as f:
                f.write(response.content)

            # Возвращаем абсолютный путь для сохранения в БД
            logger.info(f"Чек сохранен локально для заявки {order_id}: {file_path.resolve()}")
            return str(file_path.resolve())
        except Exception as e:
            logger.error(f"Ошибка при сохранении чека локально для заявки {order_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _kb_close_order(self, order_id: int):
        kb = VkKeyboard(inline=True)
        kb.add_button("✅ Закрыть заявку", color=VkKeyboardColor.POSITIVE, payload={"cmd": "close_order", "order_id": order_id})
        return kb

    def _kb_equip_type(self):
        """Клавиатура для выбора типа техники (русские названия)"""
        from handlers.menu_kb import EQUIP_TYPES
        kb = VkKeyboard(inline=True)
        # Добавляем кнопки по 2 в ряд
        for i in range(0, len(EQUIP_TYPES), 2):
            # Первая кнопка ряда
            name, code = EQUIP_TYPES[i]
            kb.add_button(name, color=VkKeyboardColor.SECONDARY, payload={"cmd": "select_equip_type", "equip_type": code})
            # Вторая кнопка ряда (если есть)
            if i + 1 < len(EQUIP_TYPES):
                name, code = EQUIP_TYPES[i + 1]
                kb.add_button(name, color=VkKeyboardColor.SECONDARY, payload={"cmd": "select_equip_type", "equip_type": code})
            # Новая строка перед следующим рядом
            if i + 2 < len(EQUIP_TYPES):
                kb.add_line()
        return kb

    def _kb_master_selection(self, masters, session):
        """Клавиатура для выбора мастера из списка"""
        kb = VkKeyboard(inline=True)
        for master in masters[:10]:  # Ограничиваем до 10 мастеров
            display_name = master.full_name or master.name or str(master.tg_id)
            city_info = f" ({master.city_rel.name})" if master.city_rel else ""
            button_text = f"🔧 {display_name}{city_info}"
            if len(button_text) > 40:  # VK ограничение длины кнопки
                button_text = button_text[:37] + "..."
            kb.add_button(button_text, color=VkKeyboardColor.PRIMARY, payload={"cmd": "select_master", "master_id": master.tg_id})
        kb.add_line()
        kb.add_button("⏭ Пропустить", color=VkKeyboardColor.SECONDARY, payload={"cmd": "skip_master"})
        return kb

    # ===== Проценты техники (владельцу) =====
    def _kb_pct_main(self):
        kb = VkKeyboard(inline=True)
        settings = load_settings()
        # Кнопки категорий
        for cat in settings.keys():
            kb.add_button(cat, color=VkKeyboardColor.SECONDARY, payload={"cmd": "pct_cat", "cat": cat})
        kb.add_line()
        kb.add_button("Закрыть", color=VkKeyboardColor.NEGATIVE, payload={"cmd": "pct_close"})
        return kb

    def _kb_pct_cat(self, cat: str):
        kb = VkKeyboard(inline=True)
        settings = load_settings()
        tiers = (settings.get(cat) or {}).get("tiers", [])
        # Кнопки по каждому порогу для редактирования
        for idx, t in enumerate(tiers):
            kb.add_button(f"Изм. {idx+1}", color=VkKeyboardColor.PRIMARY, payload={"cmd": "pct_tier", "cat": cat, "tier": idx})
            if (idx + 1) % 3 == 0 and idx != len(tiers) - 1:
                kb.add_line()
        kb.add_line()
        kb.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY, payload={"cmd": "pct_menu"})
        return kb

    def _show_pct_menu(self, user_id: int):
        kb = self._kb_pct_main()
        settings = load_settings()
        msg = "📊 Выберите категорию для редактирования процентов:\n\n"
        for cat, conf in settings.items():
            title = conf.get("title", cat)
            tiers_count = len(conf.get("tiers", []))
            msg += f"• {title} ({tiers_count} порогов)\n"
        self.send_message(user_id, msg, kb)

    def _show_pct_cat(self, user_id: int, cat: str):
        settings = load_settings()
        conf = settings.get(cat) or {}
        title = conf.get("title", cat)
        tiers = conf.get("tiers", [])
        lines = [f"{i+1}) { (str(lo) if lo is not None else '0') } - { (str(hi) if hi is not None else '+') } : {pct}%" for i, (lo, hi, pct) in enumerate(tiers)]
        text = f"📈 {title} ({cat})\n\n" + ("\n".join(lines) if lines else "Нет порогов")
        kb = self._kb_pct_cat(cat)
        self.send_message(user_id, text, kb)

    # ===== Payload router =====
    def handle_payload(self, user_id: int, payload: dict, role: str, session):
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
                # Отменяем весь ввод суммы
                self.states.clear_sum_input_state(user_id)
                self.send_message(user_id, "❌ Ввод суммы отменен")
            elif cmd == "zpch_zero":
                self._payload_zpch_zero(user_id)
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
                    cat = payload.get("cat"); tier = payload.get("tier")
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
                # Обработка выбора типа техники через inline-кнопку
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
                # Обработка выбора мастера через inline-кнопку
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
                            # Получаем имя мастера
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
                # Пропустить назначение мастера
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
                    # Отмена создания заявки
                    self.states.clear_form_state(user_id)
                    kb = self.get_keyboard(role)
                    self.send_message(user_id, "❌ Создание заявки отменено", kb)
                else:
                    logger.info(f"Неизвестный payload: {payload}")
        except Exception:
            logger.exception("Ошибка обработки payload")

    def _payload_accept(self, user_id: int, payload: dict, role: str, session):
        order_id = int(payload.get("order_id", 0))
        order = session.query(Order).filter_by(id=order_id).first()
        if not order or order.assigned_to != user_id:
            self.send_message(user_id, "🚫 Вы не можете выполнить это действие. Заявка не назначена на вас.")
            return
        order.status = "accepted"
        session.commit()
        # Просто подтверждаем принятие, так как полная информация уже была отправлена при назначении
        self.send_message(user_id, f"✅ Заявка №{order.order_number} принята!", self._kb_master_on_way(order.id))

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

        # Берём мастеров с загрузкой городов
        q = session.query(User).filter(User.role == "master").options(selectinload(User.city_rel))
        if role == "director":
            # Для директора – мастера только из его города / города заявки
            director = session.query(User).filter_by(tg_id=user_id).first()
            city_id = order.city_id or (director.city_id if director else None)
            if city_id:
                q = q.filter(User.city_id == city_id)
        masters = q.order_by(User.full_name.asc().nullslast(), User.name.asc().nullslast()).all()
        if not masters and role != "director":
            self.send_message(user_id, "❌ В системе нет мастеров для назначения.")
            return

        kb = VkKeyboard(inline=True)
        # Кнопка "Себе" — для директора и владельца
        if role in ("owner", "director"):
            kb.add_button(
                "👤 Себе (директору)" if role == "director" else "👤 Себе",
                color=VkKeyboardColor.PRIMARY,
                payload={"cmd": "assign_to", "order_id": order.id, "master_id": "self"},
            )
            kb.add_line()

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
        
        # Добавляем каждого мастера на отдельной строке с полным именем и городом
        for idx, m in enumerate(masters, 1):
            master_name = m.full_name or m.name or str(m.tg_id)
            master_city = m.city_rel.name if m.city_rel else "Без города"
            lines.append(f"{idx}. {master_name} | 🏙 {master_city}")
            
            # В кнопках используем номер для экономии места, но с полной информацией в тексте
            button_text = f"{idx}. {master_name[:25]}" if len(master_name) <= 25 else f"{idx}. {master_name[:22]}..."
            kb.add_button(
                button_text,
                color=VkKeyboardColor.SECONDARY,
                payload={"cmd": "assign_to", "order_id": order.id, "master_id": str(m.tg_id)},
            )
            kb.add_line()

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

        # Проверяем, что пользователь существует
        target_user = session.query(User).filter_by(tg_id=master_id).first()
        if not target_user and master_id != user_id:
            self.send_message(user_id, "❌ Пользователь не найден.")
            return

        # Сохраняем старого мастера для уведомления об отмене
        old_master_id = order.assigned_to
        old_master = None
        if old_master_id and old_master_id != master_id:
            old_master = session.query(User).filter_by(tg_id=old_master_id).first()

        order.assigned_to = master_id
        order.status = "assigned"
        session.commit()

        # Уведомляем старого мастера об отмене, если заявка была переназначена
        if old_master and old_master.role == "master":
            try:
                self.send_message(old_master_id, f"❌ Заявка №{order.order_number} отменена")
            except Exception:
                pass

        # Имя для сообщения и уведомление
        if master_id == user_id:
            # Директор назначил заявку на себя
            if role == "director":
                self.send_message(
                    user_id, 
                    f"✅ Заявка №{order.order_number} назначена вам.\n\n"
                    f"Вы можете начать работу с заявкой. Нажмите 'В пути', когда начнете движение.",
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

        # Уведомляем нового мастера, если это мастер
        if target_user and target_user.role == "master":
            try:
                self._notify_master_vk(order, session)
            except Exception:
                pass
        # Уведомляем директора, если заявка назначена на директора
        elif target_user and target_user.role == "director":
            try:
                text = (
                    f"✅ Заявка №{order.order_number} назначена вам\n\n"
                    f"{self._format_order_details(order, hide_phone=True)}\n\n"
                    "Вы можете начать работу с заявкой."
                )
                kb = VkKeyboard(inline=True)
                kb.add_button(
                    "🚗 В пути",
                    color=VkKeyboardColor.POSITIVE,
                    payload={"cmd": "onway", "order_id": order.id},
                )
                self.send_message(target_user.tg_id, text, kb)
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
        
        # Сохраняем старого мастера для уведомления об отмене
        old_master_id = order.assigned_to
        old_master = None
        if old_master_id and old_master_id != user_id:
            old_master = session.query(User).filter_by(tg_id=old_master_id).first()
        
        # Если уже назначена на кого-то другого
        if old_master and old_master.role == "master":
            # Уведомляем старого мастера об отмене
            try:
                self.send_message(old_master_id, f"❌ Заявка №{order.order_number} отменена")
            except Exception:
                pass

        order.assigned_to = user_id
        order.status = "accepted"
        session.commit()

        # Формируем подробное сообщение для директора
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
        
        self.send_message(
            user_id,
            text,
            self._kb_master_on_way(order.id),
        )

    def _payload_onway(self, user_id: int, payload: dict, role: str, session):
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
        """Обработка: мастер забрал технику на СД"""
        order_id = int(payload.get("order_id", 0))
        order = session.query(Order).filter_by(id=order_id).first()
        if not order or order.assigned_to != user_id:
            self.send_message(user_id, "🚫 Вы не можете выполнить это действие. Заявка не назначена на вас.")
            return
        order.status = "to_sd"  # Новый статус: техника на СД
        session.commit()
        self.send_message(user_id, f"✅ Техника по заявке #{order.order_number} отправлена на СД")
        kb = self.get_keyboard(role)
        self.send_message(user_id, "🏠 Главное меню:", kb)

    def _payload_ready(self, user_id: int, payload: dict, role: str, session):
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
        """Показать заявки конкретного мастера для директора"""
        if role not in ("director", "owner"):
            self.send_message(user_id, "🚫 У вас нет доступа к этой функции. Доступно только директорам и собственникам.")
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
        kb = VkKeyboard(inline=True)
        
        for order in orders[:10]:  # Максимум 10 заявок
            equip_type_name = get_equip_type_name(order.equip_type)
            city_name = order.city_rel.name if order.city_rel else "Не указан"
            text += (
                f"🔧 Заявка #{order.order_number} — {equip_type_name}\n"
                f"🏙 {city_name}, {order.street}, д.{order.house}\n"
                f"📊 Статус: {get_status_name_ru(order.status)}\n\n"
            )
            kb.add_button(f"#{order.order_number}", 
                         color=VkKeyboardColor.SECONDARY, 
                         payload={"cmd": "sd_order", "order_id": order.id})
        
        self.send_message(user_id, text, kb)
    
    def _payload_sd_order(self, user_id: int, payload: dict, role: str, session):
        """Показать детали заявки и кнопку для закрытия СД"""
        order_id = int(payload.get("order_id", 0))
        order = session.query(Order).filter_by(id=order_id).first()
        
        if not order:
            self.send_message(user_id, "❌ Заявка не найдена. Возможно, она была удалена или номер указан неверно.")
            return
        
        # Проверяем доступ: мастер может видеть только свои заявки, директор/owner - все
        if role == "master" and order.assigned_to != user_id:
            self.send_message(user_id, "🚫 Вы не можете просматривать эту заявку. Доступна только вашим заявкам.")
            return
        
        if role not in ("master", "director", "owner"):
            self.send_message(user_id, "🚫 Нет доступа")
            return
        
        # Проверяем статус
        if order.status not in ["accepted", "on_place", "to_sd"]:
            self.send_message(user_id, f"⚠️ Заявка не находится в статусе СД (текущий статус: {get_status_name_ru(order.status)})")
            return
        
        # Показываем детали заявки
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
        
        # Клавиатура для закрытия СД
        kb = self._kb_sd_ready(order.id)
        self.send_message(user_id, text, kb)
    
    def _payload_close_sd(self, user_id: int, payload: dict, role: str, session):
        """Закрытие СД - переводит заявку в статус done_pending_sum и запускает процесс закрытия"""
        order_id = int(payload.get("order_id", 0))
        order = session.query(Order).filter_by(id=order_id).first()
        
        if not order:
            self.send_message(user_id, "❌ Заявка не найдена. Возможно, она была удалена или номер указан неверно.")
            return
        
        # Проверяем доступ: мастер может закрывать только свои заявки, директор/owner - все
        if role == "master" and order.assigned_to != user_id:
            self.send_message(user_id, "🚫 Вы не можете выполнить это действие. Заявка не назначена на вас.")
            return
        
        if role not in ("master", "director", "owner"):
            self.send_message(user_id, "🚫 Нет доступа")
            return
        
        # Проверяем, что заявка в статусе СД
        if order.status not in ["accepted", "on_place", "to_sd"]:
            self.send_message(user_id, f"⚠️ Заявка не находится в статусе СД (текущий статус: {get_status_name_ru(order.status)})")
            return
        
        if order.status == "done_pending_sum":
            self.send_message(user_id, "⚠️ Заявка уже была закрыта ранее.")
            return
        
        # Переводим в статус done_pending_sum и запускаем процесс закрытия
        order.status = "done_pending_sum"
        session.commit()
        self.states.set_sum_input_state(user_id, {"order_id": order_id, "step": "order_sum", "data": {}})
        self.send_message(user_id, f"✅ СД закрыт для заявки #{order.order_number}\n\n💰 Введите сумму заказа:", self._kb_sum_cancel())

    def _payload_zpch_zero(self, user_id: int):
        state = self.states.get_sum_input_state(user_id)
        if not state:
            return
        state["data"]["zpch_sum"] = 0
        state["data"]["sd_price"] = state["data"].get("sd_price", 0)
        state["step"] = "waiting_bso"
        self.states.set_sum_input_state(user_id, state)
        # _prompt_bso_upload автоматически проверит сумму и пропустит БСО если < 5000
        self._prompt_bso_upload(user_id)

    def _payload_skip_bso(self, user_id: int, session):
        """Пропустить загрузку БСО"""
        state = self.states.get_sum_input_state(user_id)
        if not state:
            return
        
        # Очищаем данные БСО
        state["data"]["bso_file_id"] = None
        local_path = state["data"].get("bso_local_path")
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass
        state["data"]["bso_local_path"] = None
        
        # Проверяем, нужно ли запрашивать чек (если ЗПЧ > 0)
        zpch_sum = float(state["data"].get("zpch_sum", 0) or 0)
        if zpch_sum > 0:
            state["step"] = "waiting_receipt"
            self.states.set_sum_input_state(user_id, state)
            self.send_message(user_id, "✅ БСО пропущен")
            self._prompt_receipt_upload(user_id)
        else:
            # Если ЗПЧ = 0, сразу переходим к расчету
            self.states.set_sum_input_state(user_id, state)
            self.send_message(user_id, "✅ БСО пропущен")
            self._calculate_and_show_result_vk(user_id)

    def _payload_skip_receipt(self, user_id: int, session):
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
        self._calculate_and_show_result_vk(user_id)

    def _payload_close_order(self, user_id: int, payload: dict, role: str, session):
        """Закрытие заявки мастером - статус остается done_pending_sum, запись в Stat создается при приемке кассы"""
        order_id = int(payload.get("order_id", 0))
        order = session.query(Order).filter_by(id=order_id, assigned_to=user_id).first()
        if not order:
            self.send_message(user_id, "🚫 Нет доступа к заявке")
            return
        # Статус остается done_pending_sum - заявка готова к приемке кассы
        # Запись в Stat будет создана при приемке кассы директором/собственником
        session.commit()
        self.send_message(user_id, "✅ Заявка готова к сдаче кассы!")
        kb = self.get_keyboard(role)
        self.send_message(user_id, "🏠 Главное меню:", kb)

    # ===== Вспомогательные: уведомления и форматирование =====
    def _notify_master_vk(self, order: Order, session):
        try:
            if order.assigned_to:
                equip = get_equip_type_name(order.equip_type)
                city_name = order.city_rel.name if order.city_rel else "Не указан"
                
                # Формируем подробное сообщение без номера телефона
                msg = (
                    f"🎯 Вам назначена новая заявка №{order.order_number}\n\n"
                    f"🏙 Город: {city_name}\n"
                    f"⏰ Время: {order.time_from} - {order.time_to}\n"
                    f"📍 Адрес: ул. {order.street}, дом {order.house}, кв. {order.flat or '-'}\n"
                    f"🔧 Техника: {equip}\n"
                )
                
                # Добавляем описание, если есть
                if order.short_desc:
                    msg += f"📝 Описание: {order.short_desc}\n"
                
                # Добавляем имя клиента (всегда показываем, даже если пустое)
                client_name = order.client_name if order.client_name else "Не указано"
                msg += f"👤 Клиент: {client_name}\n"
                
                # Добавляем источник, если есть
                if order.source:
                    msg += f"📞 Источник: {order.source}\n"
                
                # Добавляем комментарий, если есть
                if order.comment:
                    msg += f"💬 Комментарий: {order.comment}\n"
                
                # Отправляем одно сообщение с кнопкой "Принять"
                self.send_message(order.assigned_to, msg, self._kb_master_new_order(order.id))
        except Exception as e:
            logger.warning(f"Не удалось уведомить мастера {order.assigned_to}: {e}")

    def _render_order(self, order: Order) -> str:
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

    # ===== Ввод сумм (VK текст + payload) =====
    def _handle_sum_input_vk(self, user_id: int, text: str, session):
        state = self.states.get_sum_input_state(user_id)
        if not state:
            return
        step = state.get("step")
        t = text.strip()
        # Если пользователь в состоянии ожидания БСО или чека, но отправляет текст
        if step == "waiting_bso":
            self.send_message(user_id, "📄 Отправьте фото или файл БСО (договор/квитанция/акт выполненных работ):", None)
            return
        if step == "waiting_receipt":
            kb = VkKeyboard(inline=True)
            kb.add_button("⏭ Пропустить чек", color=VkKeyboardColor.SECONDARY, payload={"cmd": "skip_receipt"})
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
                    # Есть долг - спрашиваем дату погашения
                    state["step"] = "debt_payment_date"
                    self.states.set_sum_input_state(user_id, state)
                    self.send_message(user_id, f"✅ Оплачено: {paid_amount:.2f} руб.\n⚠️ Долг: {debt_amount:.2f} руб.\n\n📅 Введите дату погашения долга (ДД.ММ.ГГГГ):", self._kb_sum_cancel())
                else:
                    # Нет долга - переходим к ЗПЧ
                    state["step"] = "zpch_sum"
                    self.states.set_sum_input_state(user_id, state)
                    self.send_message(user_id, f"✅ Оплачено: {paid_amount:.2f} руб.\n\n💰 Введите сумму ЗПЧ:", self._kb_zpch_zero())
                return
            if step == "debt_payment_date":
                # Парсим дату в формате ДД.ММ.ГГГГ
                try:
                    from datetime import datetime
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
                # Проверяем, нужно ли запрашивать чек (если ЗПЧ > 0)
                zpch_sum = float(state["data"].get("zpch_sum", 0) or 0)
                if zpch_sum > 0:
                    state["step"] = "waiting_receipt"
                    self.states.set_sum_input_state(user_id, state)
                    self._prompt_receipt_upload(user_id)
                else:
                    # Если ЗПЧ = 0, сразу переходим к расчету
                    self._calculate_and_show_result_vk(user_id)
                return
        except ValueError:
            self.send_message(user_id, "❌ Введите корректное число")

    def _calculate_and_show_result_vk(self, user_id: int):
        state = self.states.get_sum_input_state(user_id)
        if not state:
            return
        order_id = state["order_id"]
        order_sum = float(state["data"].get("order_sum", 0) or 0)
        paid_amount = float(state["data"].get("paid_amount", order_sum) or order_sum)  # По умолчанию равна сумме заказа
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
            
            # Комиссия считается от полной суммы заказа минус запчасти (sd_price исключён из расчёта)
            net_amount = max(order_sum - zpch_sum, 0)
            
            # Проверяем индивидуальный процент мастера
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
            # Сохраняем БСО если есть
            bso_local_path = state["data"].get("bso_local_path")
            if bso_local_path:
                order.bso_file_path = bso_local_path
            # Сохраняем receipt_file_id если есть
            receipt_file_id = state["data"].get("receipt_file_id")
            if receipt_file_id:
                order.receipt_file_id = receipt_file_id
            receipt_local_path = state["data"].get("receipt_local_path")
            if receipt_local_path:
                # Если файл был сохранен локально, используем его путь
                order.receipt_file_path = receipt_local_path
            elif receipt_file_id:
                # Если есть только receipt_file_id, но нет локального файла
                # Пробуем найти файл по паттерну receipt_{order_id}_*
                from pathlib import Path
                bso_dir = Path("bso_files").resolve()
                bso_dir.mkdir(exist_ok=True)
                possible_files = list(bso_dir.glob(f"receipt_{order_id}_*"))
                if possible_files:
                    # Найден файл по паттерну - используем его
                    order.receipt_file_path = str(possible_files[0].resolve())
                # Если файл не найден, оставляем receipt_file_path как есть (может быть None или старое значение)
                # Админка попытается найти файл по паттерну при запросе
            else:
                # Нет ни receipt_file_id, ни receipt_local_path - очищаем receipt_file_path
                order.receipt_file_path = None
            order.status = "done_pending_sum"
            session.commit()
            bso_status = "✅ Прикреплен" if bso_local_path else "❌ Не прикреплен"
            receipt_status = "✅ Прикреплен" if receipt_file_id else ("⏭ Пропущен" if zpch_sum > 0 else "—")
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

    def _handle_pct_edit_input(self, user_id: int, text: str, role: str):
        if role != "owner":
            self.send_message(user_id, "🚫 Нет доступа.")
            return
        state = self.states.get_equipment_edit_state(user_id)
        if not state:
            return
        cat = state.get("cat"); tier_idx = state.get("tier")
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
            # Форматируем диапазон для сообщения
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
        # Показать обратно категорию с обновленными данными
        self._show_pct_cat(user_id, cat)

    # ===== Генерация отчёта и отправка файла =====
    def _generate_stats_excel(self, orders, session):
        from services.statistics_service import generate_city_stats_excel

        return generate_city_stats_excel(orders)


    def _send_doc(self, user_id: int, file_path: str, title: str) -> bool:
        """Отправить документ пользователю через VK API (для группового токена)"""
        try:
            import requests
            
            # Шаг 1: Получаем URL для загрузки документа в личные сообщения
            try:
                upload_server = self.vk.docs.getMessagesUploadServer(type='doc', peer_id=user_id)
            except ApiError as e:
                if e.code == 27:
                    # Метод недоступен для группового токена, пробуем альтернативный способ
                    logger.warning("docs.getMessagesUploadServer недоступен, пробуем альтернативный метод")
                    # Пробуем получить через docs.getUploadServer без peer_id
                    try:
                        upload_server = self.vk.docs.getUploadServer()
                    except ApiError as e2:
                        logger.error(f"Не удалось получить upload server: {e2.code} - {e2.message}")
                        return False
                else:
                    logger.error(f"Ошибка при получении upload server: {e.code} - {e.message}")
                    return False
            
            upload_url = upload_server.get('upload_url')
            if not upload_url:
                logger.error(f"Не получен upload_url из ответа: {upload_server}")
                return False
            
            # Шаг 2: Загружаем файл на сервер VK
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f)}
                response = requests.post(upload_url, files=files)
            
            if response.status_code != 200:
                logger.error(f"Ошибка загрузки файла на VK сервер: {response.status_code} - {response.text}")
                return False
            
            upload_result = response.json()
            if 'error' in upload_result:
                logger.error(f"Ошибка при загрузке файла: {upload_result['error']}")
                return False
            
            # Шаг 3: Сохраняем документ через docs.save
            try:
                file_data = upload_result.get('file')
                if not file_data:
                    logger.error(f"Не получен file из ответа загрузки: {upload_result}")
                    return False
                
                doc_save = self.vk.docs.save(file=file_data, title=title)
                
                if not doc_save or not isinstance(doc_save, dict):
                    logger.error(f"Неожиданный формат ответа docs.save: {doc_save}")
                    return False
                
                # Получаем информацию о документе
                doc_info = doc_save.get('doc') or doc_save
                if isinstance(doc_info, dict):
                    owner_id = doc_info.get('owner_id')
                    doc_id = doc_info.get('id')
                else:
                    owner_id = getattr(doc_info, 'owner_id', None)
                    doc_id = getattr(doc_info, 'id', None)
                
                if not owner_id or not doc_id:
                    logger.error(f"Не удалось получить owner_id или doc_id из ответа: {doc_save}")
                    return False
                
                attachment = f"doc{owner_id}_{doc_id}"
                
                # Шаг 4: Отправляем сообщение с документом
                self.vk.messages.send(
                    user_id=user_id,
                    random_id=get_random_id(),
                    attachment=attachment,
                    message=f"📊 {title}"
                )
                logger.info(f"Документ {title} успешно отправлен пользователю {user_id}")
                return True
                
            except ApiError as e:
                logger.error(f"VK API ошибка при сохранении/отправке документа: {e.code} - {e.message}")
                return False
                
        except Exception as e:
            logger.exception(f"Не удалось отправить документ VK: {e}")
            return False

    def handle_my_orders(self, user_id: int, role: str, session):
        """Показать заявки пользователя"""
        try:
            if role == "dispatcher":
                self.send_message(user_id, "🚫 У диспетчеров нет доступа к заявкам.")
                return
            
            # Для собственника - показываем заявки по каждому мастеру
            if role == "owner":
                # Получаем всех мастеров
                masters = session.query(User).filter_by(role="master").all()
                
                if not masters:
                    self.send_message(user_id, "📭 Мастеров нет в системе.")
                    return
                
                # Группируем заявки по мастерам
                from collections import defaultdict
                masters_orders = defaultdict(list)
                
                for master in masters:
                    orders = session.query(Order).filter(
                        Order.assigned_to == master.tg_id,
                        Order.status.notin_(["completed", "declined"])
                    ).order_by(Order.created_at.desc()).limit(50).all()
                    if orders:
                        masters_orders[master] = orders
                
                if not masters_orders:
                    self.send_message(user_id, "📭 Заявок нет.")
                    return
                
                # Выводим заявки по каждому мастеру
                for master, orders in masters_orders.items():
                    master_name = master.full_name or master.name or str(master.tg_id)
                    city_name = master.city_rel.name if master.city_rel else "Не указан"
                    
                    header = f"🔧 Мастер: {master_name}\n🏙 Город: {city_name}\n📋 Заявок: {len(orders)}\n"
                    self.send_message(user_id, header)
                    
                    # Показываем последние 10 заявок мастера
                    for o in orders[:10]:
                        # Собственнику можно показывать телефон клиента
                        text = self._format_order_details(o, master_name=master_name, hide_phone=False)
                        self.send_message(user_id, text)
                        self._send_receipt_if_exists(user_id, o)
                    
                    if len(orders) > 10:
                        self.send_message(user_id, f"... и еще {len(orders) - 10} заявок")
                
                self.send_message(user_id, "✅ Готово!")
                return
            
            # Для остальных ролей - стандартный вывод (только активные заявки)
            q = session.query(Order).filter(
                Order.status.notin_(["completed", "declined"])
            )
            if role == "master":
                orders = q.filter(Order.assigned_to == user_id).order_by(Order.created_at.desc()).limit(20).all()
            elif role == "director":
                # Директор видит все активные заявки
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
                
                # Для директора скрываем номер телефона клиента
                hide_phone = (role == "director")
                text = self._format_order_details(o, master_name=master_name, hide_phone=hide_phone)

                # Для директора добавляем кнопки назначения для свободных заявок
                kb = None
                if role == "director":
                    if not o.assigned_to:
                        kb = VkKeyboard(inline=True)
                        kb.add_button(
                            "✅ Взять себе",
                            color=VkKeyboardColor.POSITIVE,
                            payload={"cmd": "take_order", "order_id": o.id},
                        )
                        kb.add_line()
                        kb.add_button(
                            "👤 Назначить",
                            color=VkKeyboardColor.PRIMARY,
                            payload={"cmd": "assign_menu", "order_id": o.id},
                        )
                self.send_message(user_id, text, kb)
                self._send_receipt_if_exists(user_id, o)
                
            self.send_message(user_id, "✅ Готово!")
        except Exception:
            logger.exception("Ошибка при получении заявок")

    def handle_stats(self, user_id: int, role: str, session):
        """Показать агрегированную статистику"""
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
    
    def _open_master_web_stats(self, user_id: int, session):
        """Открыть веб-версию статистики для мастера"""
        try:
            # Получаем URL веб-версии для мастера
            # Предполагаем, что веб-версия работает на порту 8002 (из docker-compose.yml)
            web_url = os.getenv("MASTER_WEB_URL", "http://localhost:8002")
            
            # Формируем URL с параметром user_id для автоматического входа
            stats_url = f"{web_url}/?user_id={user_id}"
            
            # Отправляем сообщение со ссылкой на веб-версию
            self.send_message(
                user_id,
                f"📊 <b>Статистика мастера</b>\n\n"
                f"Откройте ссылку ниже в браузере для просмотра статистики:\n\n"
                f"{stats_url}\n\n"
                f"💡 Ссылка автоматически откроет вашу статистику"
            )
        except Exception as e:
            logger.exception(f"Ошибка при открытии веб-версии статистики: {e}")
            self.send_message(user_id, "❌ Ошибка при открытии веб-версии статистики")

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
            for order in active_orders:
                equip_type_name = get_equip_type_name(order.equip_type)
                city_name = order.city_rel.name if order.city_rel else "Не указан"
                text += (
                    f"🔧 Заявка #{order.order_number} — {equip_type_name}\n"
                    f"🏙 {city_name}\n"
                    f"📍 {order.street}, д.{order.house}\n"
                    f"📊 Статус: {get_status_name_ru(order.status)}\n\n"
                )
            
            # Клавиатура для выбора заявки
            kb = VkKeyboard(inline=True)
            for order in active_orders[:10]:  # Максимум 10 кнопок
                equip_type_name = get_equip_type_name(order.equip_type)
                kb.add_button(f"#{order.order_number} {equip_type_name}", 
                             color=VkKeyboardColor.SECONDARY, 
                             payload={"cmd": "sd_order", "order_id": order.id})
            
            self.send_message(user_id, text, kb)
        except Exception:
            logger.exception("Ошибка при получении СД")

    def handle_cash(self, user_id: int, role: str, session):
        """Показать кассу мастера - сумма к сдаче компании"""
        try:
            if role != "master":
                self.send_message(user_id, "🚫 Эта функция доступна только мастерам.")
                return
                    
            # Получаем заявки мастера со статусом done_pending_sum (не принятые кассой)
            from model import Order
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
                zpch_sum = getattr(order, 'zpch_sum', 0) or 0
                net_amount = max(order_sum - zpch_sum, 0)
                
                # Проверяем индивидуальный процент мастера
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
            
            # Добавляем кнопки для просмотра чеков
            kb = VkKeyboard(inline=True)
            for order in pending_orders[:10]:  # Максимум 10 кнопок
                has_receipt = bool(getattr(order, "receipt_file_id", None) or getattr(order, "receipt_file_path", None))
                if has_receipt:
                    kb.add_button(
                        f"📎 Чек #{order.order_number}",
                        color=VkKeyboardColor.SECONDARY,
                        payload={"cmd": "view_receipt", "order_id": order.id}
                    )
                    kb.add_line()
            
            if kb.keyboard:
                self.send_message(user_id, msg, kb)
            else:
                self.send_message(user_id, msg)
        except Exception:
            logger.exception("Ошибка при получении кассы")

    def _payload_view_receipt(self, user_id: int, payload: dict, role: str, session):
        """Показать чек по заявке"""
        try:
            order_id = payload.get("order_id")
            if not order_id:
                self.send_message(user_id, "❌ Ошибка: не указан ID заявки")
                return
            
            from model import Order
            order = session.query(Order).filter_by(id=order_id).first()
            if not order:
                self.send_message(user_id, "❌ Заявка не найдена")
                return
            
            # Проверяем доступ: мастер может видеть только свои заявки
            if role == "master" and order.assigned_to != user_id:
                self.send_message(user_id, "🚫 Нет доступа к этой заявке")
                return
            
            # Отправляем чек
            self._send_receipt_if_exists(user_id, order)
        except Exception:
            logger.exception("Ошибка при просмотре чека")
            self.send_message(user_id, "❌ Ошибка при открытии чека")

    # ===== 🚀 Запуск =====

    def run(self):
        """Запустить бота"""
        logger.info("🔄 Запуск бота...")

        # Start GeoTracker background thread
        if ROUTE_INTEGRATION_AVAILABLE and self.geo_tracker:
            try:
                self.geo_tracker.start()
                logger.info("🌍 GeoTracker фоновый поток запущен")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось запустить GeoTracker: {e}")

        try:
            for event in self.longpoll.listen():
                # Обработка разных типов long poll
                if self.use_bot_longpoll:
                    # Режим бота сообщества (VkBotLongPoll)
                    if VkBotEventType is not None and event.type == VkBotEventType.MESSAGE_NEW:
                        msg = event.obj.message
                        self.handle_message(msg)
                else:
                    # Режим пользовательского long poll (VkLongPoll)
                    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                        message = {
                            "from_id": event.user_id,
                            "text": event.text,
                        }
                        self.handle_message(message)
        except KeyboardInterrupt:
            logger.info("⚠️ Остановка бота пользователем")
        except Exception:
            logger.exception("❌ Неожиданная ошибка в основном цикле")
        finally:
            # Stop GeoTracker on shutdown
            if self.geo_tracker:
                try:
                    self.geo_tracker.stop()
                    logger.info("🌍 GeoTracker остановлен")
                except Exception:
                    pass






