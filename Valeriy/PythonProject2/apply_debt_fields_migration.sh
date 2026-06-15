#!/bin/bash
# Скрипт для применения миграции полей долга напрямую через SQL

echo "Применение миграции add_debt_fields_001..."

# Применяем SQL через docker compose
docker compose exec -T admin psql $DATABASE_URL << EOF
-- Добавление полей для отслеживания долгов в таблицу orders
ALTER TABLE orders ADD COLUMN IF NOT EXISTS paid_amount FLOAT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS debt_amount FLOAT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS debt_payment_date TIMESTAMP WITH TIME ZONE;

-- Обновляем версию миграции в alembic_version
-- Вставляем запись о применении миграции, если её ещё нет
INSERT INTO alembic_version (version_num)
SELECT 'add_debt_fields_001'
WHERE NOT EXISTS (
    SELECT 1 FROM alembic_version WHERE version_num = 'add_debt_fields_001'
);
EOF

echo "Миграция применена!"

