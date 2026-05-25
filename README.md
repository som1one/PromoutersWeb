# СУУПР

Система управления доступом и учёта работы промоутеров. Бэкенд + мобильный фронтенд кабинета промоутера.

## Stack

### Backend

- FastAPI
- SQLAlchemy 2.0
- PostgreSQL
- Alembic
- Pydantic Settings
- JWT auth with optional SMS verification
- payout calculation and in-app notifications

### Admin UI

Активный пользовательский интерфейс — серверный Jinja2-админ под `/admin`
(объединённая панель owner / director / dispatcher / branch_manager / ad_director / master).
Стили — `src/promouters/static/css/admin.css` (тёмная тема) и `master.css` (светлая).

### Frontend (archived)

React-кабинет в `frontend/` оставлен на диске как архив и больше не собирается
и не отдаётся сервером. Все live-страницы переехали в Jinja2-админ `/admin`.

- React 19
- TypeScript
- Vite
- React Router

## Local Start

### Backend

1. Create an env file:

   ```bash
   copy .env.example .env
   ```

2. Install dependencies:

   ```bash
   pip install -e .[dev]
   ```

3. Start PostgreSQL:

   ```bash
   docker compose up -d db
   ```

4. Apply migrations:

   ```bash
   alembic upgrade head
   ```

5. Run the API:

   ```bash
   uvicorn promouters.main:app --reload
   ```

Backend docs: `http://localhost:8000/docs`

Админ-панель: `http://localhost:8000/admin/login`

### Frontend (archived, no longer served)

React-приложение в `frontend/` остаётся в репозитории как архив. Оно **не**
монтируется FastAPI-приложением; активный UI — `/admin`. Если нужно
посмотреть старый React-кабинет — `cd frontend && npm install && npm run dev`,
но это вне основного потока разработки.

## Staging And UAT

- staging env template: `.env.staging.example`
- demo data seed: `python scripts/seed_demo_data.py`
- staging guide: `docs/STAGING_SETUP.md`
- UAT checklist: `docs/UAT_CHECKLIST.md`
- post-MVP backlog: `docs/POST_MVP_BACKLOG.md`

## Frontend Foundation

- routing with public and protected zones
- `PromoterLayout` with desktop sidebar and mobile bottom navigation
- `AuthGuard` and `GuestGuard`
- basic UI-kit for cards, buttons, badges, form inputs, and section headers
- screens for login, overview, shifts, tasks, and profile

## Project Layout

- `src/promouters` - backend application package
- `migrations` - Alembic setup and versions
- `config/logging.yaml` - logging config
- `frontend` - promoter cabinet frontend app
- `.env*.example` - environment templates
