-- Миграция: добавление полей username и password_hash в таблицу users
-- Выполните этот SQL скрипт в вашей базе данных PostgreSQL

-- Добавить поле username (если его еще нет)
DO $$ 
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
END $$;

-- Добавить поле password_hash (если его еще нет)
DO $$ 
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
END $$;

-- Создать уникальный индекс для username (только для не-NULL значений)
DO $$ 
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
END $$;

