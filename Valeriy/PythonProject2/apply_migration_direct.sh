#!/bin/bash
# Полный скрипт для применения миграции напрямую через SQL

echo "=== Применение миграции add_debt_fields_001 ==="

# Получаем DATABASE_URL из переменных окружения контейнера
DB_URL=$(docker compose exec -T admin printenv DATABASE_URL)

if [ -z "$DB_URL" ]; then
    echo "Ошибка: DATABASE_URL не найден"
    exit 1
fi

echo "Применение SQL команд..."

# Применяем SQL команды
docker compose exec -T admin psql "$DB_URL" << 'EOF'
-- Добавление полей для отслеживания долгов
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='orders' AND column_name='paid_amount') THEN
        ALTER TABLE orders ADD COLUMN paid_amount FLOAT;
        RAISE NOTICE 'Добавлено поле paid_amount';
    ELSE
        RAISE NOTICE 'Поле paid_amount уже существует';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='orders' AND column_name='debt_amount') THEN
        ALTER TABLE orders ADD COLUMN debt_amount FLOAT;
        RAISE NOTICE 'Добавлено поле debt_amount';
    ELSE
        RAISE NOTICE 'Поле debt_amount уже существует';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='orders' AND column_name='debt_payment_date') THEN
        ALTER TABLE orders ADD COLUMN debt_payment_date TIMESTAMP WITH TIME ZONE;
        RAISE NOTICE 'Добавлено поле debt_payment_date';
    ELSE
        RAISE NOTICE 'Поле debt_payment_date уже существует';
    END IF;
END $$;
EOF

echo ""
echo "=== Миграция применена! ==="
echo ""
echo "Проверка полей:"
docker compose exec -T admin psql "$DB_URL" -c "\d orders" | grep -E "(paid_amount|debt_amount|debt_payment_date)"

echo ""
echo "Примечание: Если нужно обновить alembic_version, выполните:"
echo "docker compose exec admin psql \$DATABASE_URL -c \"UPDATE alembic_version SET version_num = 'add_debt_fields_001' WHERE version_num IN ('21c200b24705', 'add_web_auth_001');\""

