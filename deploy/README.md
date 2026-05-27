# Деплой на сервер 186.246.10.51

Старый сервер был удалён. Это руководство разворачивает приложение на новой машине с нуля
и настраивает GitHub Actions для последующих автодеплоев.

## Серверные данные

| параметр | значение |
|---|---|
| host | `186.246.10.51` |
| user | `root` |
| password | `jtFF759@#6bFTH` |
| port | `22` |
| директория приложения | `/opt/suupr` |
| systemd unit | `suupr-backend` |
| БД | PostgreSQL, `suupr/suupr` |

---

## Способ 1 (рекомендуется): GitHub Actions

Один и тот же workflow и поднимает чистый сервер с нуля, и катит обновления.
Установка пакетов, создание пользователя/БД, systemd-юнит, nginx и .env создаются
идемпотентно — повторный запуск ничего не ломает.

### 1. Добавить секреты в репозиторий

GitHub → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`:

| Имя | Значение |
|---|---|
| `SSH_HOST` | `186.246.10.51` |
| `SSH_USER` | `root` |
| `SSH_PASSWORD` | `jtFF759@#6bFTH` |
| `SSH_PORT` | `22` *(опционально)* |

### 2. Запустить деплой

Любым из двух способов:

- `Actions` → `Deploy to production` → `Run workflow` → ветка `main`.
- `git push origin main` — workflow стартует автоматически.

### 3. Проверить

- http://186.246.10.51/
- http://186.246.10.51/admin
- http://186.246.10.51/api/v1/health
- http://186.246.10.51/docs

Демо-логин: `+79990000001` / `demo12345`.

---

## Способ 2: локальный запуск (Python)

Полезно, когда нужно прокатить один раз руками без коммита в main.

### Требования
- Python 3.10+ (на Windows стандартный из Microsoft Store подойдёт).
- `pip install paramiko`

### Запуск
```powershell
# из корня репозитория
python deploy\deploy.py full      # настройка чистого сервера + деплой
python deploy\deploy.py deploy    # только деплой (если сервер уже настроен)
python deploy\deploy.py status    # проверить состояние сервисов
python deploy\deploy.py           # интерактивное меню
```

Скрипт делает то же самое, что workflow: ставит пакеты, поднимает PostgreSQL,
создаёт пользователя `suupr`, кладёт systemd-юнит, разворачивает .env со
случайным `SECRET_KEY`, обновляет nginx-конфиг и перезапускает сервисы.

### Если SSH ругается на «Error reading SSH protocol banner»

Сервер закрывает соединение сразу после TCP-handshake — это `fail2ban`/`sshguard`
забанили ваш IP после нескольких неудачных попыток входа. Варианты:

1. Подождать 15–30 минут, бан снимется автоматически.
2. Сменить выход в интернет (другой VPN-узел, мобильный hotspot).
3. Запустить деплой через GitHub Actions — раннеры выходят с других IP.

---

## Что разворачивается на сервере

```
/opt/suupr/
├── .env               # креды БД, SECRET_KEY (генерится один раз)
├── .venv/             # python venv с зависимостями проекта
├── frontend/dist/     # собранный SPA, отдаётся nginx-ом
├── deploy/nginx-suupr.conf
└── …                  # код из репозитория

/etc/systemd/system/suupr-backend.service   # FastAPI на :8000
/etc/nginx/sites-enabled/suupr              # reverse-proxy на :80
```

Маршрутизация nginx (`deploy/nginx-suupr.conf`):
- `/api/*`, `/docs`, `/openapi.json`, `/admin/*` → `127.0.0.1:8000` (uvicorn)
- `/media/*` → `/opt/suupr/media/`
- остальное → SPA `frontend/dist/index.html`

---

## Диагностика

```powershell
python deploy\deploy.py status
```

Или вручную:
```bash
ssh root@186.246.10.51 systemctl status suupr-backend
ssh root@186.246.10.51 journalctl -u suupr-backend -n 100 --no-pager
ssh root@186.246.10.51 nginx -t
ssh root@186.246.10.51 systemctl status postgresql
```

Логи nginx:
```bash
ssh root@186.246.10.51 tail -f /var/log/nginx/error.log
```

---

## Дальше (по желанию)

- Привязать домен → поправить `server_name` в `deploy/nginx-suupr.conf`.
- HTTPS через Let's Encrypt: `apt install certbot python3-certbot-nginx && certbot --nginx`.
- Сменить дефолтный пароль PostgreSQL и `SECRET_KEY` на уникальные.
- Включить автоматические бэкапы БД.
