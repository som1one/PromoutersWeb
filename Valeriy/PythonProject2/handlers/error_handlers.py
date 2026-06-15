"""
Модуль для обработки ошибок.
Содержит функции для централизованной обработки ошибок.
"""

import logging
import traceback
from typing import Optional, Dict, Any
from telebot import types
from db import get_session
from services.user_service import get_role
from handlers.menu_kb import main_keyboard
from handlers.validation import get_validation_error_message

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Класс для обработки ошибок"""
    
    def __init__(self, bot):
        self.bot = bot
    
    def handle_validation_error(self, message: types.Message, field_name: str, error: str) -> None:
        """Обработать ошибку валидации"""
        error_message = get_validation_error_message(field_name, error)
        self.bot.send_message(message.chat.id, error_message)
    
    def handle_database_error(self, message: types.Message, error: Exception) -> None:
        """Обработать ошибку базы данных"""
        logger.error(f"Database error: {error}")
        self.bot.send_message(
            message.chat.id, 
            "❌ Произошла ошибка при работе с базой данных. Попробуйте позже."
        )
    
    def handle_session_error(self, message: types.Message, error: Exception) -> None:
        """Обработать ошибку сессии"""
        logger.error(f"Session error: {error}")
        self.bot.send_message(
            message.chat.id, 
            "❌ Произошла ошибка сессии. Попробуйте позже."
        )
    
    def handle_permission_error(self, message: types.Message, required_role: str) -> None:
        """Обработать ошибку прав доступа"""
        role_names = {
            "owner": "👑 Собственник",
            "director": "👔 Директор",
            "dispatcher": "📞 Диспетчер",
            "master": "🔧 Мастер"
        }
        required_role_name = role_names.get(required_role, required_role)
        self.bot.send_message(
            message.chat.id, 
            f"🚫 Недостаточно прав. Требуется роль: {required_role_name}"
        )
    
    def handle_general_error(self, message: types.Message, error: Exception, context: str = "") -> None:
        """Обработать общую ошибку"""
        logger.error(f"General error in {context}: {error}")
        logger.error(traceback.format_exc())
        self.bot.send_message(
            message.chat.id, 
            "❌ Произошла неожиданная ошибка. Попробуйте позже или обратитесь к администратору."
        )
    
    def handle_callback_error(self, callback: types.CallbackQuery, error: Exception, context: str = "") -> None:
        """Обработать ошибку в callback"""
        logger.error(f"Callback error in {context}: {error}")
        logger.error(traceback.format_exc())
        self.bot.answer_callback_query(callback.id, "❌ Произошла ошибка")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Произошла ошибка. Попробуйте позже."
        )
    
    def handle_state_error(self, message: types.Message, state_name: str) -> None:
        """Обработать ошибку состояния"""
        self.bot.send_message(
            message.chat.id, 
            f"❌ Ошибка состояния {state_name}. Попробуйте начать заново."
        )
    
    def handle_user_not_found(self, message: types.Message, user_id: int) -> None:
        """Обработать ошибку "пользователь не найден" """
        self.bot.send_message(
            message.chat.id, 
            f"❌ Пользователь с ID {user_id} не найден в системе."
        )
    
    def handle_order_not_found(self, message: types.Message, order_id: int) -> None:
        """Обработать ошибку "заявка не найдена" """
        self.bot.send_message(
            message.chat.id, 
            f"❌ Заявка #{order_id} не найдена."
        )
    
    def handle_master_not_found(self, message: types.Message, master_id: int) -> None:
        """Обработать ошибку "мастер не найден" """
        self.bot.send_message(
            message.chat.id, 
            f"❌ Мастер с ID {master_id} не найден в системе."
        )
    
    def handle_city_not_found(self, message: types.Message, city_name: str) -> None:
        """Обработать ошибку "город не найден" """
        self.bot.send_message(
            message.chat.id, 
            f"❌ Город '{city_name}' не найден в системе."
        )
    
    def handle_duplicate_error(self, message: types.Message, entity_type: str, entity_name: str) -> None:
        """Обработать ошибку дублирования"""
        entity_names = {
            "user": "пользователь",
            "city": "город",
            "order": "заявка"
        }
        entity_name_localized = entity_names.get(entity_type, entity_type)
        self.bot.send_message(
            message.chat.id, 
            f"❌ {entity_name_localized.capitalize()} '{entity_name}' уже существует в системе."
        )
    
    def handle_network_error(self, message: types.Message) -> None:
        """Обработать сетевую ошибку"""
        self.bot.send_message(
            message.chat.id, 
            "❌ Ошибка сети. Проверьте подключение к интернету."
        )
    
    def handle_timeout_error(self, message: types.Message) -> None:
        """Обработать ошибку таймаута"""
        self.bot.send_message(
            message.chat.id, 
            "❌ Превышено время ожидания. Попробуйте позже."
        )
    
    def handle_telegram_error(self, message: types.Message, error: Exception) -> None:
        """Обработать ошибку Telegram API"""
        logger.error(f"Telegram API error: {error}")
        self.bot.send_message(
            message.chat.id, 
            "❌ Ошибка Telegram API. Попробуйте позже."
        )
    
    def handle_file_error(self, message: types.Message, error: Exception) -> None:
        """Обработать ошибку работы с файлами"""
        logger.error(f"File error: {error}")
        self.bot.send_message(
            message.chat.id, 
            "❌ Ошибка при работе с файлом. Попробуйте другой файл."
        )
    
    def handle_photo_error(self, message: types.Message, error: Exception) -> None:
        """Обработать ошибку обработки фото"""
        logger.error(f"Photo processing error: {error}")
        self.bot.send_message(
            message.chat.id, 
            "❌ Ошибка при обработке фото. Попробуйте другое изображение."
        )
    
    def handle_validation_error_callback(self, callback: types.CallbackQuery, field_name: str, error: str) -> None:
        """Обработать ошибку валидации в callback"""
        error_message = get_validation_error_message(field_name, error)
        self.bot.answer_callback_query(callback.id, "❌ Ошибка валидации")
        self.bot.send_message(callback.message.chat.id, error_message)
    
    def handle_permission_error_callback(self, callback: types.CallbackQuery, required_role: str) -> None:
        """Обработать ошибку прав доступа в callback"""
        role_names = {
            "owner": "👑 Собственник",
            "director": "👔 Директор",
            "dispatcher": "📞 Диспетчер",
            "master": "🔧 Мастер"
        }
        required_role_name = role_names.get(required_role, required_role)
        self.bot.answer_callback_query(callback.id, "❌ Недостаточно прав")
        self.bot.send_message(
            callback.message.chat.id, 
            f"🚫 Недостаточно прав. Требуется роль: {required_role_name}"
        )
    
    def handle_state_error_callback(self, callback: types.CallbackQuery, state_name: str) -> None:
        """Обработать ошибку состояния в callback"""
        self.bot.answer_callback_query(callback.id, "❌ Ошибка состояния")
        self.bot.send_message(
            callback.message.chat.id, 
            f"❌ Ошибка состояния {state_name}. Попробуйте начать заново."
        )
    
    def handle_not_found_error_callback(self, callback: types.CallbackQuery, entity_type: str, entity_id: str) -> None:
        """Обработать ошибку "не найдено" в callback"""
        entity_names = {
            "user": "пользователь",
            "order": "заявка",
            "city": "город",
            "master": "мастер"
        }
        entity_name_localized = entity_names.get(entity_type, entity_type)
        self.bot.answer_callback_query(callback.id, "❌ Не найдено")
        self.bot.send_message(
            callback.message.chat.id, 
            f"❌ {entity_name_localized.capitalize()} с ID {entity_id} не найден."
        )
    
    def handle_duplicate_error_callback(self, callback: types.CallbackQuery, entity_type: str, entity_name: str) -> None:
        """Обработать ошибку дублирования в callback"""
        entity_names = {
            "user": "пользователь",
            "city": "город",
            "order": "заявка"
        }
        entity_name_localized = entity_names.get(entity_type, entity_type)
        self.bot.answer_callback_query(callback.id, "❌ Уже существует")
        self.bot.send_message(
            callback.message.chat.id, 
            f"❌ {entity_name_localized.capitalize()} '{entity_name}' уже существует в системе."
        )
    
    def handle_network_error_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать сетевую ошибку в callback"""
        self.bot.answer_callback_query(callback.id, "❌ Ошибка сети")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Ошибка сети. Проверьте подключение к интернету."
        )
    
    def handle_timeout_error_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать ошибку таймаута в callback"""
        self.bot.answer_callback_query(callback.id, "❌ Таймаут")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Превышено время ожидания. Попробуйте позже."
        )
    
    def handle_telegram_error_callback(self, callback: types.CallbackQuery, error: Exception) -> None:
        """Обработать ошибку Telegram API в callback"""
        logger.error(f"Telegram API error in callback: {error}")
        self.bot.answer_callback_query(callback.id, "❌ Ошибка API")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Ошибка Telegram API. Попробуйте позже."
        )
    
    def handle_file_error_callback(self, callback: types.CallbackQuery, error: Exception) -> None:
        """Обработать ошибку работы с файлами в callback"""
        logger.error(f"File error in callback: {error}")
        self.bot.answer_callback_query(callback.id, "❌ Ошибка файла")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Ошибка при работе с файлом. Попробуйте другой файл."
        )
    
    def handle_photo_error_callback(self, callback: types.CallbackQuery, error: Exception) -> None:
        """Обработать ошибку обработки фото в callback"""
        logger.error(f"Photo processing error in callback: {error}")
        self.bot.answer_callback_query(callback.id, "❌ Ошибка фото")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Ошибка при обработке фото. Попробуйте другое изображение."
        )
    
    def handle_general_error_callback(self, callback: types.CallbackQuery, error: Exception, context: str = "") -> None:
        """Обработать общую ошибку в callback"""
        logger.error(f"General error in callback {context}: {error}")
        logger.error(traceback.format_exc())
        self.bot.answer_callback_query(callback.id, "❌ Ошибка")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Произошла неожиданная ошибка. Попробуйте позже или обратитесь к администратору."
        )
    
    def handle_database_error_callback(self, callback: types.CallbackQuery, error: Exception) -> None:
        """Обработать ошибку базы данных в callback"""
        logger.error(f"Database error in callback: {error}")
        self.bot.answer_callback_query(callback.id, "❌ Ошибка БД")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Произошла ошибка при работе с базой данных. Попробуйте позже."
        )
    
    def handle_session_error_callback(self, callback: types.CallbackQuery, error: Exception) -> None:
        """Обработать ошибку сессии в callback"""
        logger.error(f"Session error in callback: {error}")
        self.bot.answer_callback_query(callback.id, "❌ Ошибка сессии")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Произошла ошибка сессии. Попробуйте позже."
        )
    
    def handle_validation_error_callback(self, callback: types.CallbackQuery, field_name: str, error: str) -> None:
        """Обработать ошибку валидации в callback"""
        error_message = get_validation_error_message(field_name, error)
        self.bot.answer_callback_query(callback.id, "❌ Ошибка валидации")
        self.bot.send_message(callback.message.chat.id, error_message)
    
    def handle_permission_error_callback(self, callback: types.CallbackQuery, required_role: str) -> None:
        """Обработать ошибку прав доступа в callback"""
        role_names = {
            "owner": "👑 Собственник",
            "director": "👔 Директор",
            "dispatcher": "📞 Диспетчер",
            "master": "🔧 Мастер"
        }
        required_role_name = role_names.get(required_role, required_role)
        self.bot.answer_callback_query(callback.id, "❌ Недостаточно прав")
        self.bot.send_message(
            callback.message.chat.id, 
            f"🚫 Недостаточно прав. Требуется роль: {required_role_name}"
        )
    
    def handle_state_error_callback(self, callback: types.CallbackQuery, state_name: str) -> None:
        """Обработать ошибку состояния в callback"""
        self.bot.answer_callback_query(callback.id, "❌ Ошибка состояния")
        self.bot.send_message(
            callback.message.chat.id, 
            f"❌ Ошибка состояния {state_name}. Попробуйте начать заново."
        )
    
    def handle_not_found_error_callback(self, callback: types.CallbackQuery, entity_type: str, entity_id: str) -> None:
        """Обработать ошибку "не найдено" в callback"""
        entity_names = {
            "user": "пользователь",
            "order": "заявка",
            "city": "город",
            "master": "мастер"
        }
        entity_name_localized = entity_names.get(entity_type, entity_type)
        self.bot.answer_callback_query(callback.id, "❌ Не найдено")
        self.bot.send_message(
            callback.message.chat.id, 
            f"❌ {entity_name_localized.capitalize()} с ID {entity_id} не найден."
        )
    
    def handle_duplicate_error_callback(self, callback: types.CallbackQuery, entity_type: str, entity_name: str) -> None:
        """Обработать ошибку дублирования в callback"""
        entity_names = {
            "user": "пользователь",
            "city": "город",
            "order": "заявка"
        }
        entity_name_localized = entity_names.get(entity_type, entity_type)
        self.bot.answer_callback_query(callback.id, "❌ Уже существует")
        self.bot.send_message(
            callback.message.chat.id, 
            f"❌ {entity_name_localized.capitalize()} '{entity_name}' уже существует в системе."
        )
    
    def handle_network_error_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать сетевую ошибку в callback"""
        self.bot.answer_callback_query(callback.id, "❌ Ошибка сети")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Ошибка сети. Проверьте подключение к интернету."
        )
    
    def handle_timeout_error_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать ошибку таймаута в callback"""
        self.bot.answer_callback_query(callback.id, "❌ Таймаут")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Превышено время ожидания. Попробуйте позже."
        )
    
    def handle_telegram_error_callback(self, callback: types.CallbackQuery, error: Exception) -> None:
        """Обработать ошибку Telegram API в callback"""
        logger.error(f"Telegram API error in callback: {error}")
        self.bot.answer_callback_query(callback.id, "❌ Ошибка API")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Ошибка Telegram API. Попробуйте позже."
        )
    
    def handle_file_error_callback(self, callback: types.CallbackQuery, error: Exception) -> None:
        """Обработать ошибку работы с файлами в callback"""
        logger.error(f"File error in callback: {error}")
        self.bot.answer_callback_query(callback.id, "❌ Ошибка файла")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Ошибка при работе с файлом. Попробуйте другой файл."
        )
    
    def handle_photo_error_callback(self, callback: types.CallbackQuery, error: Exception) -> None:
        """Обработать ошибку обработки фото в callback"""
        logger.error(f"Photo processing error in callback: {error}")
        self.bot.answer_callback_query(callback.id, "❌ Ошибка фото")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Ошибка при обработке фото. Попробуйте другое изображение."
        )
    
    def handle_general_error_callback(self, callback: types.CallbackQuery, error: Exception, context: str = "") -> None:
        """Обработать общую ошибку в callback"""
        logger.error(f"General error in callback {context}: {error}")
        logger.error(traceback.format_exc())
        self.bot.answer_callback_query(callback.id, "❌ Ошибка")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Произошла неожиданная ошибка. Попробуйте позже или обратитесь к администратору."
        )
    
    def handle_database_error_callback(self, callback: types.CallbackQuery, error: Exception) -> None:
        """Обработать ошибку базы данных в callback"""
        logger.error(f"Database error in callback: {error}")
        self.bot.answer_callback_query(callback.id, "❌ Ошибка БД")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Произошла ошибка при работе с базой данных. Попробуйте позже."
        )
    
    def handle_session_error_callback(self, callback: types.CallbackQuery, error: Exception) -> None:
        """Обработать ошибку сессии в callback"""
        logger.error(f"Session error in callback: {error}")
        self.bot.answer_callback_query(callback.id, "❌ Ошибка сессии")
        self.bot.send_message(
            callback.message.chat.id, 
            "❌ Произошла ошибка сессии. Попробуйте позже."
        )
