# Автодеплой через GitHub Actions

Workflow: `.github/workflows/deploy.yml`

Триггеры:
- push в ветку `main`
- ручной запуск (Actions → Deploy to production → Run workflow)

## Что делает workflow

Подключается по SSH к серверу под root, на сервере под пользователем `suupr`:

1. `git fetch + reset --hard origin/main` в `/opt/suupr` (первый раз — clone)
2. Обновляет venv: `pip install -e .`
3. `alembic upgrade head`
4. Собирает фронт: `npm install && npm run build`
5. `systemctl restart suupr-backend`
6. `nginx -t && systemctl reload nginx`
7. Smoke-проверка `http://127.0.0.1/api/v1/health` и `/`

При любом ненулевом exit code всех шагов workflow падает (`set -euo pipefail`, `script_stop: true`).

## Однократная настройка

### 1. GitHub Secrets

Settings → Secrets and variables → Actions → New repository secret. Заведите:

| Имя           | Значение                       |
|---------------|--------------------------------|
| `SSH_HOST`    | `72.56.38.35`                  |
| `SSH_USER`    | `root`                         |
| `SSH_PASSWORD`| пароль root                    |
| `SSH_PORT`    | `22` (опционально, по умолчанию 22) |

Через CLI:

```bash
gh secret set SSH_HOST     --body "72.56.38.35"
gh secret set SSH_USER     --body "root"
gh secret set SSH_PASSWORD --body '<root_password>'
```

Пароль root **никогда** не появляется в коде или в логах workflow — он передаётся только в SSH-сессию.

### 2. Сервер: один раз провизионируем

Если `/opt/suupr` пуст или ещё не существует, выполните локально через ваш `scripts/deploy_full.py` (который уже умеет ставить пакеты, БД, systemd, nginx). Или вручную одной командой по SSH:

```bash
ssh root@72.56.38.35 'bash -s' <<'EOF'
set -e
APP_DIR=/opt/suupr
APP_USER=suupr
id $APP_USER 2>/dev/null || useradd --system --create-home --shell /bin/bash $APP_USER
mkdir -p $APP_DIR
chown -R $APP_USER:$APP_USER $APP_DIR
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  curl ca-certificates gnupg python3 python3-venv python3-pip \
  postgresql postgresql-contrib nginx git build-essential
command -v node >/dev/null || (curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y -qq nodejs)
sudo -u $APP_USER git clone --branch main https://github.com/som1one/PromoutersWeb.git $APP_DIR
sudo -u $APP_USER python3 -m venv $APP_DIR/.venv
sudo -u $APP_USER $APP_DIR/.venv/bin/pip install --upgrade pip
sudo -u $APP_USER $APP_DIR/.venv/bin/pip install -e $APP_DIR
EOF
```

После этого:

1. Создайте `/opt/suupr/.env` (формат — `.env.example`, проставьте реальные пароли БД и JWT).
2. Создайте Postgres БД и пользователя по этим же значениям.
3. Накатите миграции и сидер:
   ```bash
   sudo -u suupr bash -c 'cd /opt/suupr && .venv/bin/python -m alembic upgrade head'
   sudo -u suupr bash -c 'cd /opt/suupr && .venv/bin/python scripts/seed_demo_data.py'
   ```
4. Положите systemd-юнит `/etc/systemd/system/suupr-backend.service`:
   ```ini
   [Unit]
   Description=SUUPR FastAPI backend
   After=network.target postgresql.service
   Wants=postgresql.service

   [Service]
   Type=simple
   User=suupr
   Group=suupr
   WorkingDirectory=/opt/suupr
   EnvironmentFile=/opt/suupr/.env
   ExecStart=/opt/suupr/.venv/bin/uvicorn promouters.main:app --host 127.0.0.1 --port 8000 --no-access-log
   Restart=always
   RestartSec=3

   [Install]
   WantedBy=multi-user.target
   ```
   ```bash
   systemctl daemon-reload && systemctl enable --now suupr-backend
   ```
5. Положите nginx-конфиг `/etc/nginx/sites-available/suupr` (как в `scripts/deploy_full.py` константа `NGINX_SITE`, замените `/opt/suupr` на `/opt/suupr`), и:
   ```bash
   ln -sf /etc/nginx/sites-available/suupr /etc/nginx/sites-enabled/suupr
   rm -f /etc/nginx/sites-enabled/default
   nginx -t && systemctl reload nginx
   ```
6. Дайте `suupr` право рестартовать backend и reload nginx без пароля. В файле `/etc/sudoers.d/suupr-deploy`:
   ```
   suupr ALL=(root) NOPASSWD: /bin/systemctl restart suupr-backend, /bin/systemctl is-active suupr-backend, /usr/sbin/nginx -t, /bin/systemctl reload nginx
   ```
   Это нужно только если решите сменить SSH-пользователя в CI с `root` на `suupr`. Пока CI ходит под root — пункт пропустить.

### 3. Проверка

- Сделайте любую правку, push в `main` → откройте GitHub → Actions → должен запуститься workflow `Deploy to production`.
- В случае проблем — лог шага «Deploy via SSH» покажет, на каком из 7 шагов упало.

## Откат

Workflow всегда деплоит `origin/main`. Откат через `git revert` или явный `reset --hard <sha>`:

```bash
gh workflow run deploy.yml          # перезапуск последнего main
# или вручную, минуя CI:
ssh root@72.56.38.35 'sudo -u suupr git -C /opt/suupr reset --hard <sha> && systemctl restart suupr-backend'
```

## Безопасность

- Пароль root в репозитории не хранится — только в GitHub Secrets.
- При компрометации — поменяйте пароль root на сервере, обновите `SSH_PASSWORD` в Secrets.
- По возможности замените SSH-пароль на ключ:
  - на локальной машине `ssh-keygen -t ed25519 -f ~/.ssh/suupr_deploy -N ""`
  - публичный ключ → `~/.ssh/authorized_keys` пользователя на сервере
  - приватный → секрет `SSH_KEY` в GitHub
  - в workflow заменить `password: ${{ secrets.SSH_PASSWORD }}` на `key: ${{ secrets.SSH_KEY }}`
