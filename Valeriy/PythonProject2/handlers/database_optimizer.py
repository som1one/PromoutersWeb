"""
Модуль для оптимизации работы с базой данных.
Содержит функции для кэширования и оптимизации запросов.
"""

import logging
from typing import Dict, List, Optional, Any
from functools import lru_cache
from db import get_session
from model import User, Order, City, Stat
from services.user_service import get_role

logger = logging.getLogger(__name__)


class DatabaseOptimizer:
    """Класс для оптимизации работы с базой данных"""
    
    def __init__(self):
        self._user_cache: Dict[int, User] = {}
        self._city_cache: Dict[int, City] = {}
        self._role_cache: Dict[int, str] = {}
    
    @lru_cache(maxsize=1000)
    def get_user_cached(self, user_id: int) -> Optional[User]:
        """Получить пользователя с кэшированием"""
        session = get_session()
        try:
            user = session.query(User).filter_by(tg_id=user_id).first()
            if user:
                self._user_cache[user_id] = user
            return user
        finally:
            session.close()
    
    @lru_cache(maxsize=100)
    def get_city_cached(self, city_id: int) -> Optional[City]:
        """Получить город с кэшированием"""
        session = get_session()
        try:
            city = session.query(City).filter_by(id=city_id).first()
            if city:
                self._city_cache[city_id] = city
            return city
        finally:
            session.close()
    
    @lru_cache(maxsize=1000)
    def get_role_cached(self, user_id: int) -> str:
        """Получить роль пользователя с кэшированием"""
        return get_role(get_session(), user_id)
    
    def get_masters_by_city(self, city_id: int) -> List[User]:
        """Получить мастеров по городу с оптимизацией"""
        session = get_session()
        try:
            return session.query(User).filter_by(role="master", city_id=city_id).all()
        finally:
            session.close()
    
    def get_active_orders_by_master(self, master_id: int) -> List[Order]:
        """Получить активные заявки мастера с оптимизацией"""
        session = get_session()
        try:
            return session.query(Order).filter(
                Order.assigned_to == master_id,
                Order.status.in_(["accepted", "on_place"])
            ).all()
        finally:
            session.close()
    
    def get_orders_by_status(self, status: str, limit: int = 20) -> List[Order]:
        """Получить заявки по статусу с оптимизацией"""
        session = get_session()
        try:
            return session.query(Order).filter_by(status=status).limit(limit).all()
        finally:
            session.close()
    
    def get_stats_by_master(self, master_id: int) -> List[Stat]:
        """Получить статистику мастера с оптимизацией"""
        session = get_session()
        try:
            return session.query(Stat).filter_by(master_tg=master_id).all()
        finally:
            session.close()
    
    def get_all_cities(self) -> List[City]:
        """Получить все города с кэшированием"""
        session = get_session()
        try:
            cities = session.query(City).all()
            for city in cities:
                self._city_cache[city.id] = city
            return cities
        finally:
            session.close()
    
    def get_all_masters(self) -> List[User]:
        """Получить всех мастеров с оптимизацией"""
        session = get_session()
        try:
            return session.query(User).filter_by(role="master").all()
        finally:
            session.close()
    
    def get_orders_by_user(self, user_id: int, role: str, limit: int = 20) -> List[Order]:
        """Получить заявки пользователя в зависимости от роли"""
        session = get_session()
        try:
            q = session.query(Order)
            if role == "master":
                return q.filter(Order.assigned_to == user_id).order_by(Order.created_at.desc()).limit(limit).all()
            elif role == "director":
                return q.order_by(Order.created_at.desc()).limit(limit).all()
            else:
                return q.filter((Order.assigned_to == user_id) | (Order.created_by == user_id)).order_by(Order.created_at.desc()).limit(limit).all()
        finally:
            session.close()
    
    def clear_cache(self):
        """Очистить кэш"""
        self._user_cache.clear()
        self._city_cache.clear()
        self._role_cache.clear()
        self.get_user_cached.cache_clear()
        self.get_city_cached.cache_clear()
        self.get_role_cached.cache_clear()
    
    def invalidate_user_cache(self, user_id: int):
        """Инвалидировать кэш пользователя"""
        if user_id in self._user_cache:
            del self._user_cache[user_id]
        if user_id in self._role_cache:
            del self._role_cache[user_id]
        self.get_user_cached.cache_clear()
        self.get_role_cached.cache_clear()
    
    def invalidate_city_cache(self, city_id: int):
        """Инвалидировать кэш города"""
        if city_id in self._city_cache:
            del self._city_cache[city_id]
        self.get_city_cached.cache_clear()


# Глобальный экземпляр для использования
db_optimizer = DatabaseOptimizer()
