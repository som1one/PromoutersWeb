-- Добавление полей для отслеживания долгов в таблицу orders
-- Миграция: add_debt_fields_001

-- Добавляем поле paid_amount (сколько фактически оплатили)
ALTER TABLE orders ADD COLUMN IF NOT EXISTS paid_amount FLOAT;

-- Добавляем поле debt_amount (сумма долга)
ALTER TABLE orders ADD COLUMN IF NOT EXISTS debt_amount FLOAT;

-- Добавляем поле debt_payment_date (дата погашения долга)
ALTER TABLE orders ADD COLUMN IF NOT EXISTS debt_payment_date TIMESTAMP WITH TIME ZONE;

-- Обновляем версию миграции в alembic_version (если нужно)
-- Это нужно сделать вручную после применения SQL

