#!/bin/bash
# Скрипт для применения миграции добавления полей username и password_hash
# Использует настройки из docker-compose.yml

echo "============================================================"
echo "📦 Применение миграции: добавление полей для веб-аутентификации"
echo "============================================================"
echo ""

# Параметры из docker-compose.yml
POSTGRES_USER="serviceuser"
POSTGRES_PASSWORD="servicepass"
POSTGRES_DB="servicebot"
CONTAINER_NAME="postgres"

# Проверяем, запущен ли контейнер
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Контейнер $CONTAINER_NAME не запущен"
    echo "💡 Запустите: docker-compose up -d postgres"
    exit 1
fi

echo "✅ Контейнер $CONTAINER_NAME найден"
echo ""

# Выполняем SQL команды
echo "➕ Добавление полей username и password_hash..."
docker exec -i $CONTAINER_NAME psql -U $POSTGRES_USER -d $POSTGRES_DB <<EOF
-- Добавить поле username (если его еще нет)
DO \$\$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'username'
    ) THEN
        ALTER TABLE users ADD COLUMN username VARCHAR(100);
        RAISE NOTICE 'Поле username добавлено';
    ELSE
        RAISE NOTICE 'Поле username уже существует';
    END IF;
END \$\$;

-- Добавить поле password_hash (если его еще нет)
DO \$\$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'password_hash'
    ) THEN
        ALTER TABLE users ADD COLUMN password_hash VARCHAR(255);
        RAISE NOTICE 'Поле password_hash добавлено';
    ELSE
        RAISE NOTICE 'Поле password_hash уже существует';
    END IF;
END \$\$;

-- Создать уникальный индекс для username (только для не-NULL значений)
DO \$\$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename = 'users' AND indexname = 'ix_users_username'
    ) THEN
        CREATE UNIQUE INDEX ix_users_username ON users(username) WHERE username IS NOT NULL;
        RAISE NOTICE 'Индекс ix_users_username создан';
    ELSE
        RAISE NOTICE 'Индекс ix_users_username уже существует';
    END IF;
END \$\$;
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Миграция успешно применена!"
    echo "🎉 Поля username и password_hash добавлены в таблицу users"
else
    echo ""
    echo "❌ Ошибка при применении миграции"
    exit 1
fi

