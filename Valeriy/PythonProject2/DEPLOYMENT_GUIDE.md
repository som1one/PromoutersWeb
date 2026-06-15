# 🚀 Гайд по развертыванию на новом сервере

Полная инструкция по установке и настройке системы на новом сервере.

## 📋 Требования

- Сервер с Ubuntu 20.04+ или Debian 11+ (или другой Linux дистрибутив)
- Минимум 2GB RAM, 20GB свободного места
- Доступ по SSH с правами sudo
- Доменное имя (опционально, для веб-интерфейса)

---

## Шаг 1: Подготовка сервера

### 1.1. Подключение к серверу

```bash
ssh user@your-server-ip
```

### 1.2. Обновление системы

```bash
sudo apt update
sudo apt upgrade -y
```

### 1.3. Установка необходимых пакетов

```bash
sudo apt install -y \
    curl \
    wget \
    git \
    nano \
    ufw \
    certbot \
    python3-pip
```

---

## Шаг 2: Установка Docker и Docker Compose

### 2.1. Установка Docker

```bash
# Удаляем старые версии (если есть)
sudo apt remove -y docker docker-engine docker.io containerd runc

# Устанавливаем зависимости
sudo apt install -y \
    ca-certificates \
    gnupg \
    lsb-release

# Добавляем официальный GPG ключ Docker
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Добавляем репозиторий Docker
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Устанавливаем Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Проверяем установку
docker --version
docker compose version
```

### 2.2. Настройка Docker (опционально)

```bash
# Добавляем текущего пользователя в группу docker (чтобы не использовать sudo)
sudo usermod -aG docker $USER

# Выходим и заходим снова, чтобы изменения вступили в силу
exit
# Затем снова: ssh user@your-server-ip
```

---

## Шаг 3: Настройка файрвола (UFW)

```bash
# Разрешаем SSH
sudo ufw allow 22/tcp

# Разрешаем порты для веб-интерфейсов
sudo ufw allow 8000/tcp  # Admin панель
sudo ufw allow 8001/tcp  # Dispatcher панель
sudo ufw allow 8002/tcp  # Master панель

# Включаем файрвол
sudo ufw enable

# Проверяем статус
sudo ufw status
```

---

## Шаг 4: Создание директории проекта

```bash
# Создаем директорию для проекта
sudo mkdir -p /opt/servicebot
sudo chown $USER:$USER /opt/servicebot
cd /opt/servicebot
```

---

## Шаг 5: Создание docker-compose.yml

```bash
cd /opt/servicebot

# Создаем файл docker-compose.yml
nano docker-compose.yml
```

Вставьте следующее содержимое:

```yaml
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
```

Сохраните файл: `Ctrl+O`, `Enter`, `Ctrl+X`

**Примечание:** Весь код приложения уже содержится в Docker образе `greenteeea/vk-bot:latest` из Docker Hub, поэтому копировать файлы проекта не нужно!

---

## Шаг 6: Создание файла .env

```bash
cd /opt/servicebot

# Создаем файл .env
nano .env
```

### Содержимое файла `.env`:

```env
# VK Bot
VK_BOT_TOKEN=vk1.a.HZeL9VKteG-P-jDXfsKt9MhffGj8O2kKEdnemvp-Hm2iqT87ub6I6w3yli0qZQE30CDKS-ucHe8yAA1m-LIO4wWBkz4Q-TONizdroh2IExID5ZLtLAYv_EeCvOHtnQnkIjAySLoc9bXZ7namvS5xj8oKjEZmm6qslfmKXWPgWzwyEFY0E0XTM0MDA8aEpKx6EKzsj9xntMwsnOfoj68ytw
VK_GROUP_ID=235733723

# База данных (не менять - используется в docker-compose.yml)
DATABASE_URL=postgresql+psycopg2://serviceuser:servicepass@postgres:5432/servicebot

# Администраторы (ID пользователей VK или Telegram)
ADMIN_IDS=1080026562

# Часовой пояс
DEFAULT_TZ_NAME=Europe/Moscow

# Опционально: Telegram Bot (если нужен)
# TELEGRAM_TOKEN=your_telegram_token
```

**Важно:** Замените значения на ваши реальные данные!

Сохраните файл: `Ctrl+O`, `Enter`, `Ctrl+X`

---

## Шаг 7: Создание директорий для данных

```bash
cd /opt/servicebot

# Создаем директории для данных (будут использоваться контейнерами)
mkdir -p data/bso_files
mkdir -p data/receipts
mkdir -p passport_photos

# Устанавливаем права доступа
chmod -R 755 data
```

---

## Шаг 8: Запуск контейнеров из Docker Hub

```bash
cd /opt/servicebot

# Получаем последний образ из Docker Hub
# Весь код приложения уже содержится в образе greenteeea/vk-bot:latest
docker compose pull

# Запускаем все сервисы
docker compose up -d

# Проверяем статус
docker compose ps
```

**Важно:** Все сервисы используют образ `greenteeea/vk-bot:latest` из Docker Hub. Весь код приложения уже включен в образ, поэтому копировать файлы проекта не требуется!

Вы должны увидеть:
```
NAME                STATUS
servicebot-postgres-1   Up
servicebot-bot-1        Up
servicebot-admin-1       Up
servicebot-dispatcher-1 Up
servicebot-master-1     Up
```

---

## Шаг 9: Применение миграций базы данных

```bash
# Ждем, пока PostgreSQL полностью запустится (10-15 секунд)
sleep 15

# Применяем миграции Alembic
docker compose exec admin alembic upgrade head

# Проверяем, что миграции применены
docker compose exec admin alembic current
```

---

## Шаг 10: Настройка базового пользователя (owner)

```bash
# Запускаем скрипт для назначения роли owner администраторам
docker compose exec admin python assign_roles.py

# Выберите опцию 2 (Назначить owner из ADMIN_IDS)
# Введите: 2
```

Или вручную через SQL:

```bash
docker compose exec postgres psql -U serviceuser -d servicebot -c \
  "INSERT INTO users (tg_id, name, role) VALUES (1080026562, 'Admin', 'owner') \
   ON CONFLICT (tg_id) DO UPDATE SET role = 'owner';"
```

---

## Шаг 11: Проверка работоспособности

### 11.1. Проверка логов

```bash
# Логи всех сервисов
docker compose logs --tail=50

# Логи конкретного сервиса
docker compose logs --tail=50 bot
docker compose logs --tail=50 admin
docker compose logs --tail=50 postgres
```

### 11.2. Проверка веб-интерфейсов

Откройте в браузере:

- **Admin панель:** `http://your-server-ip:8000`
- **Dispatcher панель:** `http://your-server-ip:8001`
- **Master панель:** `http://your-server-ip:8002`

### 11.3. Проверка бота

```bash
# Проверяем, что бот запущен и работает
docker compose logs bot | grep "Инициализация\|готов\|ready"
```

---

## Шаг 12: Настройка Nginx (опционально, для домена)

Если у вас есть домен, настройте Nginx для проксирования:

### 12.1. Установка Nginx

```bash
sudo apt install -y nginx
```

### 12.2. Создание конфигурации

```bash
sudo nano /etc/nginx/sites-available/servicebot
```

Содержимое:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Admin панель
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Dispatcher панель
    location /dispatcher {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Master панель
    location /master {
        proxy_pass http://localhost:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 12.3. Активация конфигурации

```bash
sudo ln -s /etc/nginx/sites-available/servicebot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 12.4. Настройка SSL (Let's Encrypt)

```bash
sudo certbot --nginx -d your-domain.com
```

---

## Шаг 13: Настройка автозапуска (systemd)

Создаем сервис для автозапуска Docker Compose:

```bash
sudo nano /etc/systemd/system/servicebot.service
```

Содержимое:

```ini
[Unit]
Description=ServiceBot Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/servicebot
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Активируем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable servicebot
sudo systemctl start servicebot
```

---

## 📝 Полезные команды

### Управление контейнерами

```bash
# Остановить все
docker compose down

# Запустить все
docker compose up -d

# Перезапустить конкретный сервис
docker compose restart bot
docker compose restart admin

# Посмотреть логи
docker compose logs -f bot
docker compose logs -f admin

# Посмотреть использование ресурсов
docker stats
```

### Работа с базой данных

```bash
# Подключиться к PostgreSQL
docker compose exec postgres psql -U serviceuser -d servicebot

# Создать бэкап
docker compose exec postgres pg_dump -U serviceuser servicebot > backup.sql

# Восстановить из бэкапа
docker compose exec -T postgres psql -U serviceuser -d servicebot < backup.sql
```

### Обновление проекта

```bash
cd /opt/servicebot

# Получить новый образ
docker compose pull

# Перезапустить с новым образом
docker compose up -d

# Применить новые миграции (если есть)
docker compose exec admin alembic upgrade head
```

### Очистка

```bash
# Удалить неиспользуемые образы
docker image prune -a

# Удалить неиспользуемые volumes
docker volume prune

# Полная очистка (осторожно!)
docker system prune -a --volumes
```

---

## 🔧 Решение проблем

### Проблема: Контейнеры не запускаются

```bash
# Проверьте логи
docker compose logs

# Проверьте статус
docker compose ps

# Проверьте файл .env
cat .env
```

### Проблема: Ошибки подключения к базе данных

```bash
# Проверьте, что PostgreSQL запущен
docker compose ps postgres

# Проверьте логи PostgreSQL
docker compose logs postgres

# Попробуйте перезапустить
docker compose restart postgres
sleep 10
docker compose restart admin bot
```

### Проблема: Бот не отвечает

```bash
# Проверьте токен VK
docker compose exec bot env | grep VK_BOT_TOKEN

# Проверьте логи бота
docker compose logs -f bot

# Перезапустите бота
docker compose restart bot
```

### Проблема: Веб-интерфейс не открывается

```bash
# Проверьте, что порты открыты
sudo ufw status

# Проверьте, что контейнеры запущены
docker compose ps

# Проверьте логи
docker compose logs admin
```

---

## 📞 Контакты и поддержка

При возникновении проблем проверьте:
1. Логи контейнеров: `docker compose logs`
2. Статус контейнеров: `docker compose ps`
3. Файл `.env` на наличие всех необходимых переменных
4. Доступность портов: `sudo ufw status`

---

## ✅ Чеклист развертывания

- [ ] Docker и Docker Compose установлены
- [ ] Файрвол настроен
- [ ] Файл `docker-compose.yml` создан
- [ ] Файл `.env` создан и заполнен
- [ ] Директории для данных созданы
- [ ] Контейнеры запущены (`docker compose ps`)
- [ ] Миграции применены (`alembic upgrade head`)
- [ ] Базовый пользователь создан (owner)
- [ ] Веб-интерфейсы доступны
- [ ] Бот отвечает на сообщения
- [ ] Nginx настроен (если используется домен)
- [ ] SSL сертификат установлен (если используется домен)
- [ ] Автозапуск настроен (systemd)

---

**Готово! 🎉 Система развернута и готова к работе.**
