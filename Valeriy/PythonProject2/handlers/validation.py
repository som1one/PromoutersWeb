"""
Модуль для валидации данных пользователей.
Содержит функции проверки корректности вводимых данных.
"""

import re
from typing import Optional, Tuple, List
from telebot import types


class ValidationError(Exception):
    """Исключение для ошибок валидации"""
    pass


class DataValidator:
    """Класс для валидации данных"""
    
    @staticmethod
    def validate_phone(phone: str) -> Tuple[bool, str]:
        """
        Валидация номера телефона
        Возвращает (is_valid, error_message)
        """
        if not phone:
            return False, "Номер телефона не может быть пустым"
        
        # Убираем все символы кроме цифр и +
        clean_phone = re.sub(r'[^\d+]', '', phone)
        
        # Проверяем формат российского номера
        if clean_phone.startswith('+7'):
            if len(clean_phone) == 12:
                return True, ""
            else:
                return False, "Номер должен содержать 11 цифр после +7"
        elif clean_phone.startswith('8'):
            if len(clean_phone) == 11:
                return True, ""
            else:
                return False, "Номер должен содержать 10 цифр после 8"
        elif clean_phone.startswith('7'):
            if len(clean_phone) == 11:
                return True, ""
            else:
                return False, "Номер должен содержать 10 цифр после 7"
        else:
            return False, "Номер должен начинаться с +7, 8 или 7"
    
    @staticmethod
    def validate_time(time_str: str) -> Tuple[bool, str]:
        """
        Валидация времени
        Возвращает (is_valid, error_message)
        """
        if not time_str:
            return False, "Время не может быть пустым"
        
        # Проверяем формат HH:MM
        time_pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        if not re.match(time_pattern, time_str):
            return False, "Время должно быть в формате HH:MM (например: 09:00, 14:30)"
        
        return True, ""
    
    @staticmethod
    def validate_house_number(house: str) -> Tuple[bool, str]:
        """
        Валидация номера дома
        Возвращает (is_valid, error_message)
        """
        if not house:
            return False, "Номер дома не может быть пустым"
        
        # Проверяем, что номер дома содержит только цифры, буквы, слэши и дефисы
        if not re.match(r'^[0-9а-яА-Яa-zA-Z/\\-]+$', house):
            return False, "Номер дома может содержать только цифры, буквы, слэши и дефисы"
        
        return True, ""
    
    @staticmethod
    def validate_flat_number(flat: str) -> Tuple[bool, str]:
        """
        Валидация номера квартиры
        Возвращает (is_valid, error_message)
        """
        if not flat:
            return False, "Номер квартиры не может быть пустым"
        
        # Проверяем, что номер квартиры содержит только цифры, буквы и дефисы
        if not re.match(r'^[0-9а-яА-Яa-zA-Z-]+$', flat):
            return False, "Номер квартиры может содержать только цифры, буквы и дефисы"
        
        return True, ""
    
    @staticmethod
    def validate_name(name: str) -> Tuple[bool, str]:
        """
        Валидация имени
        Возвращает (is_valid, error_message)
        """
        if not name:
            return False, "Имя не может быть пустым"
        
        if len(name) < 2:
            return False, "Имя должно содержать минимум 2 символа"
        
        if len(name) > 100:
            return False, "Имя не может быть длиннее 100 символов"
        
        # Проверяем, что имя содержит только буквы, пробелы и дефисы
        if not re.match(r'^[а-яА-Яa-zA-Z\s\-]+$', name):
            return False, "Имя может содержать только буквы, пробелы и дефисы"
        
        return True, ""
    
    @staticmethod
    def validate_telegram_id(tg_id: str) -> Tuple[bool, str]:
        """
        Валидация Telegram ID
        Возвращает (is_valid, error_message)
        """
        if not tg_id:
            return False, "Telegram ID не может быть пустым"
        
        try:
            tg_id_int = int(tg_id)
            if tg_id_int <= 0:
                return False, "Telegram ID должен быть положительным числом"
            return True, ""
        except ValueError:
            return False, "Telegram ID должен быть числом"
    
    @staticmethod
    def validate_sum(sum_str: str) -> Tuple[bool, str, float]:
        """
        Валидация суммы
        Возвращает (is_valid, error_message, sum_value)
        """
        if not sum_str:
            return False, "Сумма не может быть пустой", 0.0
        
        try:
            sum_value = float(sum_str)
            if sum_value < 0:
                return False, "Сумма не может быть отрицательной", 0.0
            if sum_value > 1000000:
                return False, "Сумма не может быть больше 1,000,000", 0.0
            return True, "", sum_value
        except ValueError:
            return False, "Сумма должна быть числом", 0.0
    
    @staticmethod
    def validate_city(city: str) -> Tuple[bool, str]:
        """
        Валидация города
        Возвращает (is_valid, error_message)
        """
        if not city:
            return False, "Город не может быть пустым"
        
        if len(city) < 2:
            return False, "Название города должно содержать минимум 2 символа"
        
        if len(city) > 50:
            return False, "Название города не может быть длиннее 50 символов"
        
        # Проверяем, что город содержит только буквы, пробелы и дефисы
        if not re.match(r'^[а-яА-Яa-zA-Z\s\-]+$', city):
            return False, "Название города может содержать только буквы, пробелы и дефисы"
        
        return True, ""
    
    @staticmethod
    def validate_street(street: str) -> Tuple[bool, str]:
        """
        Валидация улицы
        Возвращает (is_valid, error_message)
        """
        if not street:
            return False, "Улица не может быть пустой"
        
        if len(street) < 2:
            return False, "Название улицы должно содержать минимум 2 символа"
        
        if len(street) > 100:
            return False, "Название улицы не может быть длиннее 100 символов"
        
        return True, ""
    
    @staticmethod
    def validate_description(description: str) -> Tuple[bool, str]:
        """
        Валидация описания
        Возвращает (is_valid, error_message)
        """
        if not description:
            return False, "Описание не может быть пустым"
        
        if len(description) < 5:
            return False, "Описание должно содержать минимум 5 символов"
        
        if len(description) > 500:
            return False, "Описание не может быть длиннее 500 символов"
        
        return True, ""
    
    @staticmethod
    def validate_comment(comment: str) -> Tuple[bool, str]:
        """
        Валидация комментария (может быть пустым)
        Возвращает (is_valid, error_message)
        """
        if not comment:
            return True, ""  # Комментарий может быть пустым
        
        if len(comment) > 1000:
            return False, "Комментарий не может быть длиннее 1000 символов"
        
        return True, ""


class FormValidator:
    """Класс для валидации форм"""
    
    def __init__(self):
        self.validator = DataValidator()
    
    def validate_form_step(self, step: str, value: str) -> Tuple[bool, str]:
        """
        Валидация шага формы
        Возвращает (is_valid, error_message)
        """
        if step == "city":
            return self.validator.validate_city(value)
        elif step == "street":
            return self.validator.validate_street(value)
        elif step == "house":
            return self.validator.validate_house_number(value)
        elif step == "flat":
            return self.validator.validate_flat_number(value)
        elif step in ["time_from", "time_to"]:
            return self.validator.validate_time(value)
        elif step == "short_desc":
            return self.validator.validate_description(value)
        elif step == "client_name":
            return self.validator.validate_name(value)
        elif step == "client_phone":
            return self.validator.validate_phone(value)
        elif step == "comment":
            return self.validator.validate_comment(value)
        else:
            return True, ""  # Для остальных полей валидация не требуется
    
    def validate_master_creation_step(self, step: str, value: str) -> Tuple[bool, str]:
        """
        Валидация шага создания мастера
        Возвращает (is_valid, error_message)
        """
        if step == "full_name":
            return self.validator.validate_name(value)
        elif step == "phone":
            return self.validator.validate_phone(value)
        elif step == "tg_id":
            return self.validator.validate_telegram_id(value)
        else:
            return True, ""
    
    def validate_sum_input_step(self, step: str, value: str) -> Tuple[bool, str, float]:
        """
        Валидация шага ввода суммы
        Возвращает (is_valid, error_message, sum_value)
        """
        if step in ["order_sum", "zpch_sum"]:
            return self.validator.validate_sum(value)
        else:
            return True, "", 0.0


def get_validation_error_message(field_name: str, error: str) -> str:
    """
    Получить локализованное сообщение об ошибке валидации
    """
    field_names = {
        "city": "Город",
        "street": "Улица", 
        "house": "Номер дома",
        "flat": "Номер квартиры",
        "time_from": "Время от",
        "time_to": "Время до",
        "short_desc": "Описание",
        "client_name": "ФИО клиента",
        "client_phone": "Телефон клиента",
        "comment": "Комментарий",
        "full_name": "ФИО мастера",
        "phone": "Телефон мастера",
        "tg_id": "Telegram ID",
        "order_sum": "Сумма заказа",
        "zpch_sum": "Сумма ЗПЧ"
    }
    
    field_name_localized = field_names.get(field_name, field_name)
    return f"❌ Ошибка в поле '{field_name_localized}': {error}"
