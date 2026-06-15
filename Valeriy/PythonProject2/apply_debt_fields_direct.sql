-- Добавление полей для отслеживания долгов в таблицу orders
ALTER TABLE orders ADD COLUMN IF NOT EXISTS paid_amount FLOAT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS debt_amount FLOAT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS debt_payment_date TIMESTAMP WITH TIME ZONE;

