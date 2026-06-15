-- Исправление проблемы с миграцией timezone
-- Выполнить на сервере через: docker compose exec postgres psql -U serviceuser -d servicebot -f /path/to/fix_migration_timezone.sql
-- Или скопировать содержимое и выполнить напрямую

-- Проверяем и добавляем колонку timezone только если её нет
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'cities' AND column_name = 'timezone'
    ) THEN
        ALTER TABLE cities ADD COLUMN timezone VARCHAR(100);
    END IF;
END $$;

-- Помечаем миграцию как примененную (если она еще не применена)
-- Это нужно только если миграция застряла
-- INSERT INTO alembic_version (version_num) VALUES ('47d580f2bd85') 
-- ON CONFLICT DO NOTHING;
