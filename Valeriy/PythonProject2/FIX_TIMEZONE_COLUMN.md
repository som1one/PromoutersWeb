# 🔧 Исправление отсутствующей колонки timezone

## Проблема

В модели `City` есть поле `timezone`, но в базе данных колонка отсутствует. Это вызывает ошибку при запросах.

## Быстрое решение (выполнить на сервере)

```bash
cd /opt/servicebot

# Добавить колонку timezone в таблицу cities
docker compose exec postgres psql -U serviceuser -d servicebot -c \
  "ALTER TABLE cities ADD COLUMN IF NOT EXISTS timezone VARCHAR(100) DEFAULT 'Europe/Moscow';"

# Обновить существующие записи (если есть)
docker compose exec postgres psql -U serviceuser -d servicebot -c \
  "UPDATE cities SET timezone = 'Europe/Moscow' WHERE timezone IS NULL;"

# Установить значение по умолчанию
docker compose exec postgres psql -U serviceuser -d servicebot -c \
  "ALTER TABLE cities ALTER COLUMN timezone SET DEFAULT 'Europe/Moscow';"

# Перезапустить админ панель
docker compose restart admin

# Проверить логи
docker compose logs --tail=20 admin
```

## Альтернатива: Применить все миграции заново

Если колонка все еще отсутствует, можно откатить и применить миграции заново:

```bash
cd /opt/servicebot

# 1. Проверить текущую версию миграций
docker compose exec admin alembic current

# 2. Если нужно, откатить до миграции перед add_receipt_path_001
# (ОСТОРОЖНО! Это удалит данные, если миграции необратимы)
# docker compose exec admin alembic downgrade add_attendance_fix_001

# 3. Применить миграции заново
docker compose exec admin alembic upgrade head
```

## Проверка

```bash
# Проверить, что колонка существует
docker compose exec postgres psql -U serviceuser -d servicebot -c \
  "\d cities"

# Должна быть строка:
# timezone | character varying(100) | default 'Europe/Moscow'::character varying
```

## Если проблема повторяется

Возможно, миграция `add_receipt_path_001` не была применена. Проверьте:

```bash
# Посмотреть историю миграций
docker compose exec admin alembic history

# Проверить, применена ли миграция add_receipt_path_001
docker compose exec postgres psql -U serviceuser -d servicebot -c \
  "SELECT version_num FROM alembic_version;"
```

Если миграция `add_receipt_path_001` не в списке примененных, нужно применить её:

```bash
docker compose exec admin alembic upgrade add_receipt_path_001
```
