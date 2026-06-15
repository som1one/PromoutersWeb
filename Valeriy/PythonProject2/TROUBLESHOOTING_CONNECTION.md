# 🔍 Диагностика проблемы подключения

## Проблема: ERR_CONNECTION_REFUSED

Сервер не отвечает на запросы. Проверьте следующие пункты:

## 1. Проверка статуса контейнеров

```bash
cd /opt/servicebot
docker compose ps
```

**Ожидаемый результат:**
```
NAME                  STATUS
servicebot-postgres-1   Up
servicebot-bot-1        Up
servicebot-admin-1      Up
servicebot-dispatcher-1 Up
servicebot-master-1      Up
```

**Если контейнеры не запущены:**
```bash
docker compose up -d
docker compose ps
```

## 2. Проверка логов контейнеров

```bash
# Логи админ панели (самый важный)
docker compose logs --tail=50 admin

# Логи бота
docker compose logs --tail=50 bot

# Логи всех сервисов
docker compose logs --tail=50
```

**Ищите ошибки:**
- Ошибки подключения к базе данных
- Ошибки миграций
- Порт уже занят
- Ошибки импорта модулей

## 3. Проверка файрвола

```bash
# Проверить статус файрвола
sudo ufw status

# Проверить, открыты ли порты
sudo ufw status numbered
```

**Должны быть открыты:**
- 22/tcp (SSH)
- 8000/tcp (Admin)
- 8001/tcp (Dispatcher)
- 8002/tcp (Master)

**Если порты не открыты:**
```bash
sudo ufw allow 8000/tcp
sudo ufw allow 8001/tcp
sudo ufw allow 8002/tcp
sudo ufw reload
```

## 4. Проверка, слушает ли приложение порты

```bash
# Проверить, какие порты слушаются
sudo netstat -tlnp | grep -E '8000|8001|8002'

# Или через ss
sudo ss -tlnp | grep -E '8000|8001|8002'
```

**Ожидаемый результат:**
```
tcp  0  0  0.0.0.0:8000  0.0.0.0:*  LISTEN  <PID>/python
tcp  0  0  0.0.0.0:8001  0.0.0.0:*  LISTEN  <PID>/python
tcp  0  0  0.0.0.0:8002  0.0.0.0:*  LISTEN  <PID>/python
```

**Если порты не слушаются:**
- Контейнеры не запущены или упали
- Приложение не запустилось из-за ошибок
- Проверьте логи (шаг 2)

## 5. Проверка внутри контейнера

```bash
# Проверить, что приложение запущено внутри контейнера
docker compose exec admin ps aux | grep python

# Проверить, слушает ли порт внутри контейнера
docker compose exec admin netstat -tlnp | grep 8000
```

## 6. Проверка подключения к базе данных

```bash
# Проверить, что PostgreSQL работает
docker compose exec postgres pg_isready -U serviceuser -d servicebot

# Проверить подключение из контейнера admin
docker compose exec admin python -c "
from db import get_session
session = get_session()
print('✅ Подключение к БД успешно')
session.close()
"
```

## 7. Быстрое исправление (если контейнеры упали)

```bash
cd /opt/servicebot

# Перезапустить все контейнеры
docker compose restart

# Или полный перезапуск
docker compose down
docker compose up -d

# Подождать 15 секунд
sleep 15

# Проверить статус
docker compose ps
docker compose logs --tail=20 admin
```

## 8. Проверка миграций (если проблема в БД)

```bash
# Проверить текущую версию миграций
docker compose exec admin alembic current

# Если миграции не применены, применить их
docker compose exec admin alembic upgrade head
```

## 9. Проверка переменных окружения

```bash
# Проверить, что .env файл существует и заполнен
cat .env | grep -E 'VK_BOT_TOKEN|ADMIN_IDS|DATABASE_URL'

# Проверить переменные внутри контейнера
docker compose exec admin env | grep -E 'VK_BOT_TOKEN|ADMIN_IDS|DATABASE_URL'
```

## 10. Типичные проблемы и решения

### Проблема: Контейнеры постоянно перезапускаются

**Причина:** Ошибка в коде или конфигурации

**Решение:**
```bash
# Посмотреть логи
docker compose logs admin

# Проверить, что .env файл корректен
cat .env
```

### Проблема: Порт уже занят

**Причина:** Другое приложение использует порт

**Решение:**
```bash
# Найти процесс, использующий порт
sudo lsof -i :8000

# Остановить процесс или изменить порт в docker-compose.yml
```

### Проблема: Файрвол блокирует

**Решение:**
```bash
# Временно отключить файрвол для проверки (НЕ для production!)
sudo ufw disable

# Попробовать подключиться

# Включить обратно и правильно настроить
sudo ufw enable
sudo ufw allow 8000/tcp
sudo ufw allow 8001/tcp
sudo ufw allow 8002/tcp
```

### Проблема: База данных не запустилась

**Решение:**
```bash
# Проверить логи PostgreSQL
docker compose logs postgres

# Перезапустить PostgreSQL
docker compose restart postgres

# Подождать и проверить
sleep 10
docker compose exec postgres pg_isready -U serviceuser -d servicebot
```

## 11. Полная диагностика (одна команда)

```bash
cd /opt/servicebot && \
echo "=== Статус контейнеров ===" && \
docker compose ps && \
echo -e "\n=== Последние логи admin ===" && \
docker compose logs --tail=20 admin && \
echo -e "\n=== Статус файрвола ===" && \
sudo ufw status && \
echo -e "\n=== Слушаемые порты ===" && \
sudo ss -tlnp | grep -E '8000|8001|8002' && \
echo -e "\n=== Версия миграций ===" && \
docker compose exec admin alembic current 2>/dev/null || echo "Миграции не применены"
```

## 12. Если ничего не помогло

```bash
# Полный перезапуск с нуля
cd /opt/servicebot
docker compose down
docker compose pull
docker compose up -d
sleep 20
docker compose ps
docker compose logs --tail=50
```

---

## 📞 Что проверить в первую очередь:

1. ✅ `docker compose ps` - все ли контейнеры запущены?
2. ✅ `docker compose logs admin` - есть ли ошибки?
3. ✅ `sudo ufw status` - открыты ли порты?
4. ✅ `sudo ss -tlnp | grep 8000` - слушает ли порт?

После проверки этих пунктов станет ясно, в чем проблема.
