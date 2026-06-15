# 🔧 Срочное исправление на сервере

## Проблема
На сервере используется старая версия миграции без исправления. Нужно обновить образ и исправить базу данных.

## Решение (выполнить на сервере)

```bash
cd /opt/servicebot

# 1. ОСТАНОВИТЬ все контейнеры
docker compose down

# 2. Получить обновленный образ с исправленной миграцией
docker compose pull

# 3. Запустить контейнеры заново
docker compose up -d

# 4. Подождать, пока PostgreSQL запустится (10-15 секунд)
sleep 15

# 5. Проверить, существует ли таблица cities и колонка timezone
docker compose exec postgres psql -U serviceuser -d servicebot -c \
  "SELECT column_name FROM information_schema.columns WHERE table_name='cities' AND column_name='timezone';"

# 6. Если колонка существует, удалить её (чтобы исправленная миграция могла её создать с проверкой)
docker compose exec postgres psql -U serviceuser -d servicebot -c \
  "ALTER TABLE cities DROP COLUMN IF EXISTS timezone;"

# 7. Применить миграции заново (теперь с исправленной версией)
docker compose exec admin alembic upgrade head

# 8. Проверить, что таблицы созданы
docker compose exec postgres psql -U serviceuser -d servicebot -c "\dt"

# 9. Создать базового пользователя
docker compose exec postgres psql -U serviceuser -d servicebot -c \
  "INSERT INTO users (tg_id, name, role) VALUES (1080026562, 'Admin', 'owner') \
   ON CONFLICT (tg_id) DO UPDATE SET role = 'owner';"
```

## Альтернативный вариант (если первый не работает)

Если миграции все еще падают, можно применить их вручную:

```bash
# 1. Удалить проблемную колонку
docker compose exec postgres psql -U serviceuser -d servicebot -c \
  "ALTER TABLE cities DROP COLUMN IF EXISTS timezone;"

# 2. Пометить миграцию как примененную (если таблица alembic_version существует)
docker compose exec postgres psql -U serviceuser -d servicebot -c \
  "INSERT INTO alembic_version (version_num) VALUES ('47d580f2bd85') ON CONFLICT DO NOTHING;"

# 3. Продолжить применение миграций
docker compose exec admin alembic upgrade head
```

## Проверка результата

```bash
# Проверить текущую версию миграций
docker compose exec admin alembic current

# Проверить список таблиц
docker compose exec postgres psql -U serviceuser -d servicebot -c "\dt"

# Проверить пользователя
docker compose exec postgres psql -U serviceuser -d servicebot -c \
  "SELECT tg_id, name, role FROM users WHERE tg_id = 1080026562;"
```
