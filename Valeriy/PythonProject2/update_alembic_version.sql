-- Обновление версии миграции в alembic_version
-- После применения миграции add_debt_fields_001 напрямую через SQL

-- Проверяем текущую версию
SELECT version_num FROM alembic_version;

-- Если нужно обновить версию вручную, выполните:
-- UPDATE alembic_version SET version_num = 'add_debt_fields_001' WHERE version_num IN ('21c200b24705', 'add_web_auth_001');

-- Или добавить новую запись (если используется несколько голов):
-- INSERT INTO alembic_version (version_num) VALUES ('add_debt_fields_001')
-- ON CONFLICT DO NOTHING;

