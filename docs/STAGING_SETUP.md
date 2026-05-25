# Staging Setup

1. Создать `.env` на основе `.env.staging.example`.
2. Поднять PostgreSQL и backend:
   `docker compose up -d db`
   `alembic upgrade head`
   `uvicorn promouters.main:app --host 0.0.0.0 --port 8000`
3. Наполнить базу:
   `python scripts/seed_demo_data.py`
4. Поднять frontend:
   `cd frontend && npm install && npm run dev`
5. Проверить:
   `http://localhost:8000/docs`
   `http://localhost:5173`

## Demo Users

- Login in the current UI is by `phone + password`, not by username.
- Password for all demo users: `demo12345`
- `owner.demo` / `+79990000001`
- `manager.center` / `+79990000002`
- `director.center` / `+79990000003`
- `promoter.center` / `+79990000004`
- `manager.north` / `+79990000005`
- `promoter.north` / `+79990000006`
- `master.center` / `+79990000007`

## Что должно быть в staging

- role-based dashboard для собственника, руководителя филиала, директора по рекламе и промоутера;
- списки маршрутов, отчётов, уведомлений и выплат;
- базовый audit log;
- SMS-поток авторизации в режиме `SMS_RU_TEST=true`.
