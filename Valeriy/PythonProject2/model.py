# models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base

class City(Base):
    __tablename__ = "cities"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    cash_company_percentage = Column(Float, default=50.0)  # процент компании по кассе для города
    timezone = Column(String(100), default="Europe/Moscow")
    # Связи будут описаны на сторонах User и Order

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)  # telegram id
    tg_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(200))
    role = Column(String(50), default="user")  # admin/dispatcher/manager/master/user
    phone = Column(String(50), nullable=True)  # номер телефона
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True)  # теперь как внешний ключ, а не строка
    full_name = Column(String(200), nullable=True)  # полное ФИО
    master_percentage = Column(Float, default=None, nullable=True)  # индивидуальный процент мастера
    passport_photo_path = Column(String(500), nullable=True)  # путь к фото паспорта
    # Поля для веб-аутентификации
    username = Column(String(100), unique=True, nullable=True)  # логин для веб-интерфейса
    password_hash = Column(String(255), nullable=True)  # хеш пароля
    # Связь с городом пользователя
    city_rel = relationship("City")

class EquipmentType(Base):
    __tablename__ = "equipment_types"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    master_pct = Column(Float, default=60.0)
    company_pct = Column(Float, default=40.0)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    order_number = Column(Integer, unique=True, nullable=False)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True)  # привязка заявки к городу
    street = Column(String(500))
    house = Column(String(100))
    flat = Column(String(100))
    time_from = Column(String(50))
    time_to = Column(String(50))
    order_date = Column(DateTime(timezone=True), nullable=True)  # дата выполнения заявки - временно закомментировано
    equip_type = Column(String(100))
    short_desc = Column(Text)
    source = Column(String(200))
    status = Column(String(50), default="new")  # new, assigned, accepted, on_place, done_pending_sum, done, declined, completed, scheduled
    created_by = Column(Integer, ForeignKey("users.tg_id"))
    assigned_to = Column(Integer, ForeignKey("users.tg_id"), nullable=True)
    client_phone = Column(String(100), nullable=True)
    client_name = Column(String(200), nullable=True)
    comment = Column(Text, nullable=True)
    sum_amount = Column(Float, nullable=True)  # полная сумма заказа
    paid_amount = Column(Float, nullable=True)  # сколько фактически забрали/оплатили
    debt_amount = Column(Float, nullable=True)  # сумма долга (разница между sum_amount и paid_amount)
    debt_payment_date = Column(DateTime(timezone=True), nullable=True)  # дата погашения долга
    sd_price = Column(Float, nullable=True)  # цена сервисного документа
    zpch_sum = Column(Float, nullable=True)  # сумма ЗПЧ (запчасти)
    is_warranty = Column(Boolean, default=False, nullable=False)  # повторный гарантийный выезд
    warranty_until = Column(DateTime(timezone=True), nullable=True)  # срок гарантии до (для исходной заявки)
    warranty_days = Column(Integer, nullable=True)  # сколько дней гарантии выдано (для исходной заявки)
    warranty_source_order_id = Column(Integer, nullable=True)  # ссылка на исходную заявку (для гарантийной заявки)
    receipt_file_id = Column(String(500), nullable=True)
    receipt_file_path = Column(String(500), nullable=True)
    bso_file_path = Column(String(500), nullable=True)  # БСО/договор/квитанция
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Связь с городом заявки
    city_rel = relationship("City", foreign_keys=[city_id])

class Stat(Base):
    __tablename__ = "stats"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer)
    equip_type = Column(String(100))
    sum = Column(Float, default=0.0)
    refused = Column(Boolean, default=False)
    master_tg = Column(Integer, nullable=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

class Attendance(Base):
    """Отметки о начале смены мастеров"""
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True)
    master_tg_id = Column(Integer, ForeignKey("users.tg_id"), nullable=False)
    check_in_time = Column(DateTime(timezone=True), server_default=func.now())
    date = Column(DateTime(timezone=True), nullable=False)  # Дата смены (только дата, без времени)
    is_penalty = Column(Boolean, default=False)  # Была ли начислена пеня за опоздание
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Penalty(Base):
    """Штрафы за опоздание на смену"""
    __tablename__ = "penalties"
    id = Column(Integer, primary_key=True)
    master_tg_id = Column(Integer, ForeignKey("users.tg_id"), nullable=False)
    attendance_id = Column(Integer, ForeignKey("attendance.id"), nullable=True)
    date = Column(DateTime(timezone=True), nullable=False)  # Дата смены
    amount = Column(Float, default=0.0)  # Сумма штрафа
    reason = Column(String(500), default="Опоздание на смену (отметка не сделана до 9:00)")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SystemSettings(Base):
    """Настройки системы"""
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)  # Ключ настройки
    value = Column(String(500), nullable=True)  # Значение настройки (может быть JSON)
    description = Column(String(500), nullable=True)  # Описание настройки
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
