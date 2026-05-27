#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Универсальный скрипт для настройки сервера и деплоя приложения.
Работает на Windows, Linux, macOS.

Требования:
    pip install paramiko

Использование:
    python deploy/deploy.py            # интерактивное меню
    python deploy/deploy.py setup      # только первоначальная настройка сервера
    python deploy/deploy.py deploy     # только деплой кода
    python deploy/deploy.py full       # настройка + деплой
    python deploy/deploy.py status     # проверка состояния сервера
"""

import io
import sys
import time
import secrets
from pathlib import Path

try:
    import paramiko
except ImportError:
    print("[ERROR] paramiko не установлен. Установите: pip install paramiko")
    sys.exit(1)

# ========== КОНФИГУРАЦИЯ ==========
SERVER_IP = "186.246.10.51"
SSH_USER = "root"
SSH_PASSWORD = "jtFF759@#6bFTH"
SSH_PORT = 22

APP_DIR = "/opt/suupr"
SERVICE_NAME = "suupr-backend"
REPO_URL = "https://github.com/som1one/PromoutersWeb.git"
BRANCH = "main"
APP_USER = "suupr"
DB_NAME = "suupr"
DB_USER = "suupr"
DB_PASSWORD = "suupr_password"
# ===================================


class SSHClient:
    def __init__(self, host, user, password, port=22):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.client = None

    def connect(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print(f"[*] Подключение к {self.user}@{self.host}:{self.port}...")
        self.client.connect(
            hostname=self.host,
            port=self.port,
            username=self.user,
            password=self.password,
            timeout=15,
            banner_timeout=30,
            auth_timeout=30,
        )
        print("[OK] Подключение установлено")

    def close(self):
        if self.client:
            self.client.close()

    def run(self, command, check=True, quiet=False, timeout=600):
        """Выполнить команду на сервере. Стримит вывод."""
        if not quiet:
            short = command if len(command) < 200 else command[:200] + "..."
            print(f"[$] {short}")

        # Используем bash -lc для корректной работы set -e и переменных
        wrapped = f"bash -lc {shell_quote(command)}"
        stdin, stdout, stderr = self.client.exec_command(wrapped, timeout=timeout)

        out_lines = []
        err_lines = []

        # Стримим stdout
        for line in iter(stdout.readline, ""):
            if not line:
                break
            out_lines.append(line)
            if not quiet:
                sys.stdout.write(line)
                sys.stdout.flush()

        # Дочитаем stderr
        err = stderr.read().decode("utf-8", errors="replace")
        if err:
            err_lines.append(err)
            if not quiet:
                sys.stderr.write(err)
                sys.stderr.flush()

        exit_code = stdout.channel.recv_exit_status()

        if check and exit_code != 0:
            raise RuntimeError(
                f"Команда завершилась с кодом {exit_code}:\n{command}\n--- stderr ---\n{err}"
            )

        return exit_code, "".join(out_lines), "".join(err_lines)

    def run_quiet(self, command, check=True):
        return self.run(command, check=check, quiet=True)

    def upload_text(self, content, remote_path, mode=0o644):
        """Загрузить текстовое содержимое в файл на сервере."""
        print(f"[>] Загрузка содержимого в {remote_path}")
        sftp = self.client.open_sftp()
        try:
            with sftp.file(remote_path, "w") as f:
                f.write(content)
            sftp.chmod(remote_path, mode)
        finally:
            sftp.close()

    def upload_file(self, local_path, remote_path):
        """Загрузить локальный файл на сервер."""
        print(f"[>] {local_path} -> {remote_path}")
        sftp = self.client.open_sftp()
        try:
            sftp.put(local_path, remote_path)
        finally:
            sftp.close()


def shell_quote(s):
    """Экранировать строку для безопасной передачи в bash -lc."""
    return "'" + s.replace("'", "'\"'\"'") + "'"


# ========== ШАГИ ДЕПЛОЯ ==========

def setup_server(ssh: SSHClient):
    """Первоначальная настройка нового сервера."""
    print("\n" + "=" * 60)
    print("  ПЕРВОНАЧАЛЬНАЯ НАСТРОЙКА СЕРВЕРА")
    print("=" * 60)

    print("\n>> [1/8] Обновление пакетов и установка зависимостей")
    ssh.run("export DEBIAN_FRONTEND=noninteractive && apt-get update -y")
    # python3-venv — transitional, поэтому ставим versioned (python3.12-venv на Ubuntu 24.04)
    ssh.run(
        "export DEBIAN_FRONTEND=noninteractive && "
        "PYVER=$(python3 -c 'import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")') && "
        "apt-get install -y --no-install-recommends "
        "git curl wget ca-certificates gnupg "
        "nginx "
        "python3 python3-venv python3-pip python3-dev \"python${PYVER}-venv\" "
        "build-essential "
        "postgresql postgresql-contrib "
        "openssl"
    )

    print("\n>> [1.5/8] Установка Node.js 20.x (LTS)")
    ssh.run(
        "if ! command -v node >/dev/null 2>&1 || [ \"$(node -v | cut -c2-3)\" -lt 18 ]; then "
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && "
        "apt-get install -y nodejs; "
        "fi; node -v && npm -v"
    )

    print(f"\n>> [2/8] Создание системного пользователя {APP_USER}")
    ssh.run(
        f"id -u {APP_USER} >/dev/null 2>&1 || "
        f"useradd -m -s /bin/bash {APP_USER}"
    )

    print(f"\n>> [3/8] Настройка PostgreSQL (БД: {DB_NAME}, пользователь: {DB_USER})")
    ssh.run("systemctl enable --now postgresql")
    # Создаём пользователя и БД, если их ещё нет (идемпотентно)
    ssh.run(
        f"sudo -u postgres psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='{DB_USER}'\" "
        f"| grep -q 1 || "
        f"sudo -u postgres psql -c \"CREATE USER {DB_USER} WITH PASSWORD '{DB_PASSWORD}';\""
    )
    ssh.run(
        f"sudo -u postgres psql -tAc \"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'\" "
        f"| grep -q 1 || "
        f"sudo -u postgres psql -c \"CREATE DATABASE {DB_NAME} OWNER {DB_USER};\""
    )
    ssh.run(
        f"sudo -u postgres psql -c "
        f"\"GRANT ALL PRIVILEGES ON DATABASE {DB_NAME} TO {DB_USER};\""
    )

    print(f"\n>> [4/8] Создание директории приложения {APP_DIR}")
    ssh.run(f"mkdir -p {APP_DIR}")
    ssh.run(f"chown -R {APP_USER}:{APP_USER} {APP_DIR}")

    print("\n>> [5/8] Клонирование репозитория (если нужно)")
    code, _, _ = ssh.run_quiet(f"[ -d {APP_DIR}/.git ] && echo HAS_GIT || echo NO_GIT")
    if "NO_GIT" in _ or code != 0:
        # Делаем bare-friendly: клонируем под root, потом chown
        ssh.run(f"git config --global --add safe.directory {APP_DIR}")
        ssh.run(
            f"if [ -z \"$(ls -A {APP_DIR} 2>/dev/null)\" ]; then "
            f"  git clone --branch {BRANCH} {REPO_URL} {APP_DIR}; "
            f"else "
            f"  cd {APP_DIR} && git init -q && "
            f"  (git remote remove origin 2>/dev/null || true) && "
            f"  git remote add origin {REPO_URL} && "
            f"  git fetch origin {BRANCH} && "
            f"  git checkout -f -B {BRANCH} origin/{BRANCH}; "
            f"fi"
        )
        ssh.run(f"chown -R {APP_USER}:{APP_USER} {APP_DIR}")

    print(f"\n>> [6/8] Создание .env (если ещё нет)")
    code, exists, _ = ssh.run_quiet(f"[ -f {APP_DIR}/.env ] && echo YES || echo NO")
    if "NO" in exists:
        secret_key = secrets.token_hex(32)
        env_content = f"""# === Auto-generated by deploy.py ===
# Database
POSTGRES_DB={DB_NAME}
POSTGRES_USER={DB_USER}
POSTGRES_PASSWORD={DB_PASSWORD}
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@localhost:5432/{DB_NAME}

# Security
SECRET_KEY={secret_key}
WEB_COOKIE_SECURE=false
WEB_COOKIE_SAMESITE=lax

# Application
DEBUG=false
ENVIRONMENT=production
LOG_LEVEL=INFO
"""
        ssh.upload_text(env_content, f"{APP_DIR}/.env", mode=0o600)
        ssh.run(f"chown {APP_USER}:{APP_USER} {APP_DIR}/.env")
        print("[OK] .env создан со случайным SECRET_KEY")
    else:
        print("[OK] .env уже существует — оставляем как есть")

    print(f"\n>> [7/8] Установка systemd unit-файла {SERVICE_NAME}")
    service_content = f"""[Unit]
Description=Suupr Backend (FastAPI)
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User={APP_USER}
Group={APP_USER}
WorkingDirectory={APP_DIR}
Environment=PATH={APP_DIR}/.venv/bin:/usr/local/bin:/usr/bin:/bin
EnvironmentFile={APP_DIR}/.env
ExecStart={APP_DIR}/.venv/bin/uvicorn promouters.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    ssh.upload_text(service_content, f"/etc/systemd/system/{SERVICE_NAME}.service")
    ssh.run("systemctl daemon-reload")
    ssh.run(f"systemctl enable {SERVICE_NAME}")

    print("\n>> [8/8] Установка nginx-конфигурации")
    nginx_local = Path(__file__).parent / "nginx-suupr.conf"
    if nginx_local.exists():
        ssh.upload_file(str(nginx_local), "/etc/nginx/sites-available/suupr")
    else:
        print(f"[WARN] {nginx_local} не найден, пропускаем")
    ssh.run("ln -sf /etc/nginx/sites-available/suupr /etc/nginx/sites-enabled/suupr")
    ssh.run("rm -f /etc/nginx/sites-enabled/default")
    ssh.run("nginx -t")
    ssh.run("systemctl enable --now nginx")

    print("\n[OK] Сервер настроен.")


def deploy_app(ssh: SSHClient):
    """Деплой приложения на уже настроенный сервер."""
    print("\n" + "=" * 60)
    print("  ДЕПЛОЙ ПРИЛОЖЕНИЯ")
    print("=" * 60)

    print(f"\n>> [1/7] Синхронизация кода в {APP_DIR}")
    ssh.run(f"mkdir -p {APP_DIR}")
    ssh.run(f"git config --global --add safe.directory {APP_DIR}")

    sync_script = f"""set -euxo pipefail
cd {APP_DIR}
if [ ! -d .git ]; then
  if [ -z "$(ls -A . 2>/dev/null)" ]; then
    git clone --branch {BRANCH} {REPO_URL} .
  else
    git init -q
    git remote remove origin 2>/dev/null || true
    git remote add origin {REPO_URL}
    git fetch origin {BRANCH}
    git checkout -f -B {BRANCH} origin/{BRANCH}
  fi
else
  if git remote get-url origin >/dev/null 2>&1; then
    git remote set-url origin {REPO_URL}
  else
    git remote add origin {REPO_URL}
  fi
  git fetch origin {BRANCH}
  git reset --hard origin/{BRANCH}
  git clean -fd \\
    -e .env \\
    -e .venv \\
    -e media \\
    -e logs \\
    -e frontend/.env.local \\
    -e frontend/node_modules \\
    -e frontend/dist
fi
echo "HEAD: $(git rev-parse --short HEAD)"
"""
    ssh.run(sync_script)

    print("\n>> [2/7] Python venv + зависимости")
    # Если .venv существует, но битый (нет работающего pip) — пересоздать
    ssh.run(
        f"if [ -d {APP_DIR}/.venv ] && ! {APP_DIR}/.venv/bin/python -m pip --version >/dev/null 2>&1; then "
        f"  echo 'Битый .venv — удаляем'; rm -rf {APP_DIR}/.venv; "
        f"fi"
    )
    ssh.run(
        f"[ -d {APP_DIR}/.venv ] || python3 -m venv {APP_DIR}/.venv"
    )
    ssh.run(f"{APP_DIR}/.venv/bin/python -m pip install --upgrade pip --quiet")
    ssh.run(f"{APP_DIR}/.venv/bin/python -m pip install -e {APP_DIR} --quiet")

    print("\n>> [3/7] Миграции БД (alembic upgrade head)")
    ssh.run(f"cd {APP_DIR} && {APP_DIR}/.venv/bin/python -m alembic upgrade head")

    print("\n>> [4/7] Сборка фронтенда")
    ssh.run(f"cd {APP_DIR}/frontend && npm install --no-audit --no-fund --prefer-offline")
    ssh.run(f"cd {APP_DIR}/frontend && npm run build")

    print(f"\n>> [5/7] Восстановление прав владельца ({APP_USER})")
    ssh.run(f"chown -R {APP_USER}:{APP_USER} {APP_DIR}")

    print(f"\n>> [6/7] Перезапуск backend ({SERVICE_NAME})")
    ssh.run(
        f"grep -q '^WEB_COOKIE_SECURE=' {APP_DIR}/.env || "
        f"echo 'WEB_COOKIE_SECURE=false' >> {APP_DIR}/.env"
    )
    ssh.run(f"chown {APP_USER}:{APP_USER} {APP_DIR}/.env")
    ssh.run(f"systemctl restart {SERVICE_NAME}")
    time.sleep(3)
    ssh.run(f"systemctl is-active {SERVICE_NAME}")

    print("\n>> [7/7] Перезагрузка nginx и smoke-проверки")
    ssh.run(
        f"install -m 644 {APP_DIR}/deploy/nginx-suupr.conf "
        f"/etc/nginx/sites-available/suupr"
    )
    ssh.run("ln -sf /etc/nginx/sites-available/suupr /etc/nginx/sites-enabled/suupr")
    ssh.run("rm -f /etc/nginx/sites-enabled/default")
    ssh.run("nginx -t")
    ssh.run("systemctl reload nginx")
    time.sleep(1)

    print("\n>> Smoke-тесты")
    ssh.run("curl -fsS -o /dev/null -w 'HEALTH=%{http_code}\\n' http://127.0.0.1/api/v1/health || true")
    ssh.run("curl -fsS -o /dev/null -w 'INDEX=%{http_code}\\n'  http://127.0.0.1/ || true")

    print("\n[OK] Деплой завершён.")
    print(f"\nПриложение:  http://{SERVER_IP}/")
    print(f"Админка:     http://{SERVER_IP}/admin")
    print(f"API health:  http://{SERVER_IP}/api/v1/health")


def status(ssh: SSHClient):
    """Проверка состояния сервера."""
    print("\n" + "=" * 60)
    print("  СОСТОЯНИЕ СЕРВЕРА")
    print("=" * 60)
    ssh.run("uname -a")
    ssh.run("uptime")
    print("\n--- suupr-backend ---")
    ssh.run(f"systemctl is-active {SERVICE_NAME} || true")
    ssh.run(f"systemctl status {SERVICE_NAME} --no-pager -l | head -15 || true", check=False)
    print("\n--- nginx ---")
    ssh.run("systemctl is-active nginx || true")
    print("\n--- postgresql ---")
    ssh.run("systemctl is-active postgresql || true")
    print("\n--- Открытые порты (80, 8000, 5432) ---")
    ssh.run("ss -tulpn | grep -E ':(80|8000|5432) ' || echo 'нет совпадений'", check=False)
    print("\n--- Дисковое пространство ---")
    ssh.run("df -h /opt /var")
    print("\n--- Последние 30 строк лога backend ---")
    ssh.run(f"journalctl -u {SERVICE_NAME} -n 30 --no-pager || true", check=False)


# ========== ТОЧКА ВХОДА ==========

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else None

    if action is None:
        print("=" * 60)
        print("  ДЕПЛОЙ НА НОВЫЙ СЕРВЕР")
        print("=" * 60)
        print(f"  Сервер: {SERVER_IP}")
        print(f"  Пользователь: {SSH_USER}")
        print("=" * 60)
        print("  1. Первоначальная настройка сервера (setup)")
        print("  2. Деплой приложения (deploy)")
        print("  3. Полная настройка + деплой (full)")
        print("  4. Проверить состояние сервера (status)")
        print("  5. Выход")
        print("=" * 60)
        choice = input("Выберите [1-5]: ").strip()
        action_map = {"1": "setup", "2": "deploy", "3": "full", "4": "status", "5": "exit"}
        action = action_map.get(choice, "exit")

    if action == "exit":
        print("Выход.")
        return 0

    if action not in ("setup", "deploy", "full", "status"):
        print(f"[ERROR] Неизвестное действие: {action}")
        print("Допустимо: setup, deploy, full, status")
        return 1

    ssh = SSHClient(SERVER_IP, SSH_USER, SSH_PASSWORD, SSH_PORT)
    try:
        ssh.connect()

        if action == "setup":
            setup_server(ssh)
        elif action == "deploy":
            deploy_app(ssh)
        elif action == "full":
            setup_server(ssh)
            print("\n[*] Пауза 5 секунд перед деплоем...")
            time.sleep(5)
            deploy_app(ssh)
        elif action == "status":
            status(ssh)

        print("\n" + "=" * 60)
        print("  ГОТОВО")
        print("=" * 60)
        print(f"  Приложение:  http://{SERVER_IP}/")
        print(f"  Админка:     http://{SERVER_IP}/admin")
        print(f"  API health:  http://{SERVER_IP}/api/v1/health")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n[FATAL] {e}", file=sys.stderr)
        return 1
    finally:
        ssh.close()


if __name__ == "__main__":
    sys.exit(main())
