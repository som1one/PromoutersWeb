"""Pydantic схемы для валидации данных"""
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import re


class CompanyDataSchema(BaseModel):
    """Схема для данных компании"""
    website: Optional[str] = Field(None, description="Сайт компании")
    social_networks: Optional[List[str]] = Field(default_factory=list, description="Социальные сети")
    categories: Optional[List[str]] = Field(default_factory=list, description="Категории")
    photos: Optional[List[str]] = Field(default_factory=list, description="Фотографии (максимум 6)")
    description: Optional[str] = Field(None, description="Описание компании")
    prepayment_available: bool = Field(False, description="Доступна предоплата")
    phone_number: Optional[str] = Field(None, description="Номер телефона")
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        """Валидация номера телефона с поддержкой международных форматов"""
        if not v:
            return v
        
        # Убираем все символы кроме цифр и +
        clean_phone = re.sub(r'[^\d+]', '', v)
        
        # Если номер начинается с +, разрешаем международный формат
        if clean_phone.startswith('+'):
            # Минимум 10 цифр после кода страны (например, +375652345667)
            digits_only = re.sub(r'[^\d]', '', clean_phone)
            if len(digits_only) >= 10:
                return v
            else:
                raise ValueError("Номер телефона должен содержать минимум 10 цифр")
        
        # Для номеров без + проверяем, что это 10 цифр
        digits_only = re.sub(r'[^\d]', '', clean_phone)
        if len(digits_only) == 10:
            return v
        elif len(digits_only) == 11 and clean_phone.startswith('8'):
            # Российский формат 8XXXXXXXXXX
            return v
        elif len(digits_only) == 11 and clean_phone.startswith('7'):
            # Российский формат 7XXXXXXXXXX
            return v
        else:
            raise ValueError(
                "Номер телефона должен быть в формате: "
                "+XXXXXXXXXX (международный) или 8XXXXXXXXXX/7XXXXXXXXXX (российский)"
            )
    
    @field_validator('photos')
    @classmethod
    def validate_photos(cls, v: Optional[List[str]]) -> List[str]:
        """Валидация количества фотографий"""
        if not v:
            return []
        if len(v) > 6:
            raise ValueError("Максимум 6 фотографий")
        return v
    
    @field_validator('website')
    @classmethod
    def validate_website(cls, v: Optional[str]) -> Optional[str]:
        """Валидация URL сайта"""
        if not v:
            return v
        # Простая проверка формата URL
        if not (v.startswith('http://') or v.startswith('https://')):
            v = 'https://' + v
        return v
