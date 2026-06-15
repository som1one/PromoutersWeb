# PowerShell скрипт для применения миграции добавления полей username и password_hash
# Использует настройки из docker-compose.yml

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "📦 Применение миграции: добавление полей для веб-аутентификации" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Параметры из docker-compose.yml
$POSTGRES_USER = "serviceuser"
$POSTGRES_PASSWORD = "servicepass"
$POSTGRES_DB = "servicebot"
$CONTAINER_NAME = "postgres"

# Проверяем, запущен ли контейнер
$containerRunning = docker ps --format "{{.Names}}" | Select-String -Pattern $CONTAINER_NAME
if (-not $containerRunning) {
    Write-Host "❌ Контейнер $CONTAINER_NAME не запущен" -ForegroundColor Red
    Write-Host "💡 Запустите: docker-compose up -d postgres" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Контейнер $CONTAINER_NAME найден" -ForegroundColor Green
Write-Host ""

# SQL команды
$sqlCommands = @"
-- Добавить поле username (если его еще нет)
DO `$`$ 
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
END `$`$;

-- Добавить поле password_hash (если его еще нет)
DO `$`$ 
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
END `$`$;

-- Создать уникальный индекс для username (только для не-NULL значений)
DO `$`$ 
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
END `$`$;
"@

Write-Host "➕ Добавление полей username и password_hash..." -ForegroundColor Yellow

# Выполняем SQL команды
$sqlCommands | docker exec -i $CONTAINER_NAME psql -U $POSTGRES_USER -d $POSTGRES_DB

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Миграция успешно применена!" -ForegroundColor Green
    Write-Host "🎉 Поля username и password_hash добавлены в таблицу users" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "❌ Ошибка при применении миграции" -ForegroundColor Red
    exit 1
}

