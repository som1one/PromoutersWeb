#!/bin/sh
set -e

if [ -n "$WAIT_FOR_HOST" ] && [ -n "$WAIT_FOR_PORT" ]; then
  echo "🕒 Ожидание доступности ${WAIT_FOR_HOST}:${WAIT_FOR_PORT}..."
  python - <<'PY'
import os
import socket
import time
host = os.environ.get("WAIT_FOR_HOST")
port = int(os.environ.get("WAIT_FOR_PORT", "0"))
timeout = int(os.environ.get("WAIT_FOR_TIMEOUT", "60"))
deadline = time.time() + timeout
while True:
    try:
        with socket.create_connection((host, port), timeout=3):
            break
    except OSError:
        if time.time() >= deadline:
            raise SystemExit(f"Сервис {host}:{port} недоступен после {timeout} секунд")
        time.sleep(1)
PY
fi

if [ -n "$DATABASE_URL" ]; then
  echo "▶️ Применяю миграции базы данных..."
  # Используем heads для поддержки нескольких голов миграций
  # Если не получается, пробуем head, если и это не работает - пропускаем (миграции уже применены)
  alembic upgrade heads 2>/dev/null || alembic upgrade head 2>/dev/null || echo "⚠️ Миграции уже применены или требуют ручного вмешательства"
fi

echo "🚀 Запуск бота..."
exec python setup.py

