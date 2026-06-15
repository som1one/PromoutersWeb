# 🔧 Исправление проблемы с миграцией timezone

## Проблема

При применении миграций возникает ошибка:
```
psycopg2.errors.DuplicateColumn: column "timezone" of relation "cities" already exists
```

Это означает, что колонка `timezone` уже существует в таблице `cities`, но миграция пытается её добавить снова.

## Решение

### Вариант 1: Пропустить проблемную миграцию (быстрое решение)

```bash
# На сервере
cd /opt/servicebot

# 1. Помечаем миграцию как примененную вручную
docker compose exec postgres psql -U serviceuser -d servicebot -c \
  "INSERT INTO alembic_version (version_num) VALUES ('47d580f2bd85') ON CONFLICT DO NOTHING;"

# 2. Продолжаем применять миграции
docker compose exec admin alembic upgrade head
```

### Вариант 2: Исправить миграцию и пересобрать образ (правильное решение)

**На вашей локальной машине:**

1. Миграция уже исправлена в файле `alembic/versions/47d580f2bd85_init.py`
2. Пересоберите и запушьте образ:

```bash
docker build -t greenteeea/vk-bot:latest .
docker push greenteeea/vk-bot:latest
```

**На сервере:**

```bash
cd /opt/servicebot

# Получить обновленный образ
docker compose pull

# Перезапустить контейнеры
docker compose restart admin bot

# Применить миграции с исправленной версией
docker compose exec admin alembic upgrade head
```

### Вариант 3: Временное исправление через SQL (если нужно срочно)

```bash
# На сервере
cd /opt/servicebot

# 1. Проверяем текущее состояние миграций
docker compose exec admin alembic current

# 2. Если миграция 47d580f2bd85 не применена, помечаем её как примененную
docker compose exec postgres psql -U serviceuser -d servicebot -c \
  "INSERT INTO alembic_version (version_num) VALUES ('47d580f2bd85') ON CONFLICT DO NOTHING;"

# 3. Продолжаем применять остальные миграции
docker compose exec admin alembic upgrade head
```

## Проверка после исправления

```bash
# Проверяем текущую версию миграций
docker compose exec admin alembic current

# Проверяем, что все таблицы созданы
docker compose exec postgres psql -U serviceuser -d servicebot -c "\dt"

# Должны быть таблицы: users, orders, cities, attendance, penalties, stats и т.д.
```

## Создание базового пользователя

После успешного применения миграций:

```bash
# Вариант 1: Через скрипт (если таблица users уже существует)
docker compose exec admin python assign_roles.py
# Выберите опцию 2

# Вариант 2: Напрямую через SQL (если таблица users существует)
docker compose exec postgres psql -U serviceuser -d servicebot -c \
  "INSERT INTO users (tg_id, name, role) VALUES (1080026562, 'Admin', 'owner') \
   ON CONFLICT (tg_id) DO UPDATE SET role = 'owner';"
```

## Если таблица users не существует

Если после применения миграций таблица `users` все еще не существует, возможно, нужно применить более ранние миграции:

```bash
# Проверяем все миграции
docker compose exec admin alembic history

# Применяем миграции с начала (осторожно!)
docker compose exec admin alembic upgrade head --sql  # Сначала посмотрите SQL
docker compose exec admin alembic upgrade head
```

## Полезные команды

```bash
# Посмотреть текущую версию миграций
docker compose exec admin alembic current

# Посмотреть историю миграций
docker compose exec admin alembic history

# Посмотреть SQL миграций без применения
docker compose exec admin alembic upgrade head --sql

# Откатить последнюю миграцию (осторожно!)
docker compose exec admin alembic downgrade -1
```
