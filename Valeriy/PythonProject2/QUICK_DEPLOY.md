# ⚡ Быстрое развертывание на новом сервере

Краткая инструкция для опытных пользователей.

## 1. Установка Docker

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Выйти и зайти снова
```

## 2. Создание проекта

```bash
sudo mkdir -p /opt/servicebot
sudo chown $USER:$USER /opt/servicebot
cd /opt/servicebot
```

## 3. Создание docker-compose.yml

```bash
cat > docker-compose.yml << 'EOF'
services:
  postgres:
    image: postgres:15
    restart: unless-stopped
    environment:
      POSTGRES_USER: serviceuser
      POSTGRES_PASSWORD: servicepass
      POSTGRES_DB: servicebot
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U serviceuser -d servicebot"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    volumes:
      - pgdata:/var/lib/postgresql/data

  bot:
    image: greenteeea/vk-bot:latest
    restart: unless-stopped
    env_file:
      - .env
    environment:
      WAIT_FOR_HOST: postgres
      WAIT_FOR_PORT: 5432
      WAIT_FOR_TIMEOUT: 90
      DATABASE_URL: postgresql+psycopg2://serviceuser:servicepass@postgres:5432/servicebot
    volumes:
      - ./data:/app/data
    depends_on:
      - postgres

  admin:
    image: greenteeea/vk-bot:latest
    restart: unless-stopped
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+psycopg2://serviceuser:servicepass@postgres:5432/servicebot
    depends_on:
      - postgres
    volumes:
      - ./data:/app/data
    entrypoint: []
    command: ["python", "admin_fastapi.py"]
    ports:
      - "8000:8000"

  dispatcher:
    image: greenteeea/vk-bot:latest
    restart: unless-stopped
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+psycopg2://serviceuser:servicepass@postgres:5432/servicebot
    depends_on:
      - postgres
    volumes:
      - ./data:/app/data
    entrypoint: []
    command: ["python", "dispatcher_admin.py"]
    ports:
      - "8001:8001"

  master:
    image: greenteeea/vk-bot:latest
    restart: unless-stopped
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+psycopg2://serviceuser:servicepass@postgres:5432/servicebot
    depends_on:
      - postgres
    volumes:
      - ./data:/app/data
    entrypoint: []
    command: ["python", "master_admin.py"]
    ports:
      - "8002:8002"

volumes:
  pgdata:
EOF
```

## 4. Создание .env

```bash
cat > .env << 'EOF'
VK_BOT_TOKEN=vk1.a.HZeL9VKteG-P-jDXfsKt9MhffGj8O2kKEdnemvp-Hm2iqT87ub6I6w3yli0qZQE30CDKS-ucHe8yAA1m-LIO4wWBkz4Q-TONizdroh2IExID5ZLtLAYv_EeCvOHtnQnkIjAySLoc9bXZ7namvS5xj8oKjEZmm6qslfmKXWPgWzwyEFY0E0XTM0MDA8aEpKx6EKzsj9xntMwsnOfoj68ytw
VK_GROUP_ID=233621166
DATABASE_URL=postgresql+psycopg2://serviceuser:servicepass@postgres:5432/servicebot
ADMIN_IDS=1080026562
DEFAULT_TZ_NAME=Europe/Moscow
EOF
```

## 5. Запуск

```bash
mkdir -p data/bso_files data/receipts
docker compose pull
docker compose up -d
sleep 15
docker compose exec admin alembic upgrade head
docker compose exec admin python assign_roles.py
# Выберите опцию 2
```

## 6. Проверка

```bash
docker compose ps
docker compose logs --tail=20
```

## Готово! 🎉

Веб-интерфейсы:
- Admin: http://server-ip:8000
- Dispatcher: http://server-ip:8001
- Master: http://server-ip:8002
