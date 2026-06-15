import os
from typing import Dict, Any

from flask import Flask, request, redirect, url_for, render_template_string, flash

from db import get_session
from model import User, City
from services.commission_service import load_settings, save_settings


app = Flask(__name__)
app.secret_key = os.getenv("ADMIN_SECRET_KEY", "dev-secret-key")


BASE_TEMPLATE = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>{{ page_title or 'Админка' }} — сервис</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {
      --bg: #0f172a;
      --bg-soft: #020617;
      --surface: #020617;
      --surface-soft: #020617;
      --border-subtle: #1e293b;
      --accent: #2563eb;
      --accent-soft: rgba(37,99,235,0.12);
      --accent-border: #1d4ed8;
      --text: #e5e7eb;
      --text-soft: #9ca3af;
      --danger: #ef4444;
      --success: #22c55e;
      --radius-lg: 18px;
      --radius-md: 10px;
    }

    * { box-sizing: border-box; }
    html, body { height: 100%; margin: 0; padding: 0; }
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: radial-gradient(circle at top left, #1d4ed8 0, #020617 45%, #000 100%);
      color: var(--text);
      -webkit-font-smoothing: antialiased;
    }

    .layout {
      display: grid;
      grid-template-columns: 250px minmax(0, 1fr);
      height: 100vh;
      max-height: 100vh;
    }

    .sidebar {
      background: linear-gradient(180deg, var(--bg-soft), #020617);
      border-right: 1px solid rgba(148,163,184,0.18);
      padding: 18px 18px 16px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .brand-logo {
      width: 32px;
      height: 32px;
      border-radius: 12px;
      background: radial-gradient(circle at 30% 20%, #60a5fa 0, #1d4ed8 35%, #020617 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #e5e7eb;
      font-weight: 600;
      font-size: 17px;
      box-shadow: 0 10px 30px rgba(37,99,235,0.4);
    }
    .brand-title {
      display: flex;
      flex-direction: column;
    }
    .brand-title-main {
      font-size: 16px;
      font-weight: 600;
      letter-spacing: 0.03em;
    }
    .brand-title-sub {
      font-size: 11px;
      color: var(--text-soft);
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }

    .nav-group-title {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      color: var(--text-soft);
      margin-bottom: 6px;
    }
    .nav {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .nav a {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 7px 10px;
      border-radius: 9px;
      color: var(--text-soft);
      text-decoration: none;
      font-size: 13px;
      transition: all 0.16s ease;
    }
    .nav a span.nav-pill {
      font-size: 11px;
      padding: 2px 6px;
      border-radius: 999px;
      background: rgba(148,163,184,0.16);
      color: var(--text-soft);
    }
    .nav a:hover {
      background: rgba(15,23,42,0.9);
      color: var(--text);
      transform: translateX(1px);
    }
    .nav a.active {
      background: var(--accent-soft);
      color: #e5edff;
      border: 1px solid var(--accent-border);
      box-shadow: 0 0 0 1px rgba(37,99,235,0.35);
    }
    .nav a.active span.nav-pill {
      background: rgba(37,99,235,0.18);
      color: #dbeafe;
    }

    .sidebar-footer {
      margin-top: auto;
      font-size: 11px;
      color: var(--text-soft);
      border-top: 1px solid rgba(148,163,184,0.18);
      padding-top: 10px;
    }

    .content {
      padding: 18px 24px 20px;
      overflow: auto;
      backdrop-filter: blur(26px);
      background: radial-gradient(circle at top left, rgba(37,99,235,0.12) 0, rgba(15,23,42,0.94) 40%, rgba(15,23,42,0.98) 100%);
    }

    .content-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
    }
    .content-title-block {
      display: flex;
      flex-direction: column;
      gap: 3px;
    }
    .content-title {
      margin: 0;
      font-size: 20px;
      letter-spacing: 0.01em;
    }
    .content-subtitle {
      margin: 0;
      font-size: 12px;
      color: var(--text-soft);
    }

    .card-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.6fr) minmax(0, 1.1fr);
      gap: 18px;
    }
    .card-grid-single {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 18px;
    }

    .card {
      background: linear-gradient(145deg, rgba(15,23,42,0.98), rgba(15,23,42,0.98));
      border-radius: var(--radius-lg);
      padding: 14px 16px 14px;
      border: 1px solid rgba(148,163,184,0.22);
      box-shadow:
        0 22px 40px rgba(15,23,42,0.85),
        0 0 0 1px rgba(15,23,42,0.8);
    }
    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
    }
    .card-title {
      margin: 0;
      font-size: 15px;
    }
    .card-meta {
      font-size: 11px;
      color: var(--text-soft);
    }

    table {
      border-collapse: collapse;
      width: 100%;
      margin-top: 8px;
      background: transparent;
    }
    th, td {
      border-bottom: 1px solid rgba(30,64,175,0.25);
      padding: 6px 8px;
      font-size: 12px;
    }
    th {
      text-align: left;
      color: var(--text-soft);
      font-weight: 500;
      background: rgba(15,23,42,0.7);
      position: sticky;
      top: 0;
      z-index: 2;
    }
    tr:last-child td {
      border-bottom-color: transparent;
    }
    tbody tr:hover td {
      background: rgba(15,23,42,0.7);
    }

    input[type="number"], input[type="text"], select {
      width: 100%;
      box-sizing: border-box;
      padding: 5px 7px;
      font-size: 12px;
      border-radius: 999px;
      border: 1px solid rgba(148,163,184,0.45);
      background: rgba(15,23,42,0.9);
      color: var(--text);
      outline: none;
      transition: all 0.12s ease;
    }
    input[type="number"]:focus, input[type="text"]:focus, select:focus {
      border-color: var(--accent-border);
      box-shadow: 0 0 0 1px rgba(37,99,235,0.45);
    }

    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 6px 12px;
      border-radius: 999px;
      border: 1px solid transparent;
      cursor: pointer;
      font-size: 12px;
      background: transparent;
      color: var(--text);
      transition: all 0.14s ease;
    }
    .btn-primary {
      background: linear-gradient(135deg, #2563eb, #4f46e5);
      color: #e5edff;
      border-color: rgba(191,219,254,0.08);
      box-shadow: 0 10px 30px rgba(37,99,235,0.45);
    }
    .btn-primary:hover {
      transform: translateY(-1px);
      box-shadow: 0 16px 40px rgba(37,99,235,0.55);
    }
    .btn-secondary {
      background: rgba(15,23,42,0.9);
      border-color: rgba(148,163,184,0.4);
      color: var(--text-soft);
    }
    .btn-secondary:hover {
      background: rgba(15,23,42,1);
      color: var(--text);
    }

    .flash {
      padding: 8px 10px;
      margin-bottom: 12px;
      border-radius: 999px;
      font-size: 12px;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid transparent;
    }
    .flash-success {
      background: rgba(22,163,74,0.16);
      color: #bbf7d0;
      border-color: rgba(22,163,74,0.6);
    }
    .flash-error {
      background: rgba(239,68,68,0.16);
      color: #fecaca;
      border-color: rgba(239,68,68,0.6);
    }

    .badge-soft {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 11px;
      background: rgba(148,163,184,0.16);
      color: var(--text-soft);
    }

    .pill-row {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 4px;
    }

    .search-row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
      font-size: 12px;
    }
    .search-row input[type="text"] {
      max-width: 240px;
    }

    @media (max-width: 960px) {
      .layout { grid-template-columns: 1fr; }
      .sidebar { display: none; }
      .content { padding: 14px 14px 20px; }
      .card-grid { grid-template-columns: minmax(0, 1fr); }
    }
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-logo">VK</div>
        <div class="brand-title">
          <div class="brand-title-main">Service Admin</div>
          <div class="brand-title-sub">управление ботом</div>
        </div>
      </div>

      <div>
        <div class="nav-group-title">Навигация</div>
        <nav class="nav">
          <a href="{{ url_for('index') }}" class="{{ 'active' if active == 'index' else '' }}">🏠 Обзор</a>
          <a href="{{ url_for('commission') }}" class="{{ 'active' if active == 'commission' else '' }}">
            📊 Проценты
            <span class="nav-pill">категории</span>
          </a>
          <a href="{{ url_for('masters') }}" class="{{ 'active' if active == 'masters' else '' }}">
            👥 Команда
            <span class="nav-pill">мастера / роли</span>
          </a>
          <a href="{{ url_for('cities') }}" class="{{ 'active' if active == 'cities' else '' }}">
            🏙 Города
            <span class="nav-pill">таймзоны</span>
          </a>
        </nav>
      </div>

      <div class="sidebar-footer">
        <div>Подключено к БД бота.</div>
        <div>Изменения применяются сразу.</div>
      </div>
    </aside>

    <main class="content">
      <div class="content-header">
        <div class="content-title-block">
          <h1 class="content-title">{{ header_title or 'Админка' }}</h1>
          {% if header_subtitle %}
            <p class="content-subtitle">{{ header_subtitle }}</p>
          {% endif %}
        </div>
      </div>

      {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
          {% for category, message in messages %}
            <div class="flash flash-{{ category }}">{{ message }}</div>
          {% endfor %}
        {% endif %}
      {% endwith %}

      {% block content %}{% endblock %}
    </main>
  </div>
</body>
</html>
"""


@app.route("/")
def index():
  return render_template_string(
      BASE_TEMPLATE + """
      {% block content %}
      <div class="card-grid">
        <div class="card">
          <div class="card-header">
            <h2 class="card-title">Быстрый доступ</h2>
            <span class="badge-soft">Рекомендуемое</span>
          </div>
          <p class="card-meta">Основные сценарии, которые вы будете делать чаще всего.</p>
          <div class="pill-row">
            <a class="btn btn-primary" href="{{ url_for('commission') }}">📊 Настроить проценты по направлениям</a>
            <a class="btn btn-secondary" href="{{ url_for('masters') }}">👨‍🔧 Индивидуальные % мастеров</a>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h2 class="card-title">Справка</h2>
          </div>
          <p class="card-meta">
            Все изменения применяются сразу в боевую БД. Будьте внимательны с процентами и городами —
            это влияет на расчёт денег и статистику в боте.
          </p>
          <ul style="margin: 6px 0 0 18px; padding: 0; font-size: 12px; color: var(--text-soft);">
            <li>Проценты по направлениям — базовая сетка комиссий по категориям техники.</li>
            <li>Индивидуальный % мастера — перекрывает базовую сетку для конкретного мастера.</li>
            <li>Города — используются для фильтраций, кассы и часовых поясов в боте.</li>
          </ul>
        </div>
      </div>
      {% endblock %}
      """,
      active="index",
      header_title="Обзор админки",
      header_subtitle="Управление процентами мастеров, ролями и городами",
  )


@app.route("/commission", methods=["GET", "POST"])
def commission():
  settings: Dict[str, Dict[str, Any]] = load_settings()

  if request.method == "POST":
    # Обновляем только проценты по порогам
    new_settings = settings.copy()
    for cat, conf in settings.items():
      tiers = conf.get("tiers") or []
      new_tiers = []
      for idx, (lo, hi, pct) in enumerate(tiers):
        field_name = f"pct_{cat}_{idx}"
        val = request.form.get(field_name, "").strip()
        try:
          new_pct = float(val)
        except ValueError:
          new_pct = pct
        new_tiers.append([lo, hi, new_pct])
      new_settings[cat]["tiers"] = new_tiers
    save_settings(new_settings)
    flash("Проценты по направлениям обновлены.", "success")
    settings = new_settings

  return render_template_string(
      BASE_TEMPLATE + """
      {% block content %}
      <div class="card-grid-single">
        <div class="card">
          <div class="card-header">
            <h2 class="card-title">Проценты мастера по направлениям</h2>
            <span class="card-meta">Измените только проценты — диапазоны сумм заданы в конфиге.</span>
          </div>
          <form method="post">
            {% for key, conf in settings.items() %}
              <h3 style="font-size:13px; margin: 14px 0 4px;">
                {{ conf.title or key }}
                <span class="card-meta">({{ key }})</span>
              </h3>
              <table>
                <thead>
                  <tr>
                    <th style="width:40px;">#</th>
                    <th style="width:120px;">От, ₽</th>
                    <th style="width:120px;">До, ₽</th>
                    <th>% мастера</th>
                  </tr>
                </thead>
                <tbody>
                  {% for tier in conf.tiers %}
                    <tr>
                      <td>{{ loop.index }}</td>
                      <td>{{ tier[0] if tier[0] is not none else 0 }}</td>
                      <td>{{ tier[1] if tier[1] is not none else "∞" }}</td>
                      <td>
                        <input type="number"
                               step="0.1"
                               name="pct_{{ key }}_{{ loop.index0 }}"
                               value="{{ tier[2] }}">
                      </td>
                    </tr>
                  {% endfor %}
                </tbody>
              </table>
            {% endfor %}
            <p style="margin-top:14px; display:flex; justify-content:flex-end;">
              <button class="btn btn-primary" type="submit">💾 Сохранить проценты</button>
            </p>
          </form>
        </div>
      </div>
      {% endblock %}
      """,
      settings=settings,
      active="commission",
      header_title="Проценты по направлениям",
      header_subtitle="Базовая сетка комиссий мастера по категориям техники",
  )


@app.route("/masters", methods=["GET", "POST"])
def masters():
  session = get_session()
  try:
    if request.method == "POST":
      # Обновление индивидуальных процентов мастеров
      for user in session.query(User).filter(User.role == "master").all():
        field = f"master_pct_{user.tg_id}"
        raw = request.form.get(field, "").strip()
        if raw == "":
          user.master_percentage = None
        else:
          try:
            user.master_percentage = float(raw)
          except ValueError:
            continue
      session.commit()
      flash("Индивидуальные проценты мастеров обновлены.", "success")

    masters_q = session.query(User).filter(User.role == "master").all()
    dispatchers = session.query(User).filter(User.role == "dispatcher").all()
    directors = session.query(User).filter(User.role == "director").all()

    return render_template_string(
        BASE_TEMPLATE + """
        {% block content %}
        <div class="card-grid">
          <div class="card">
            <div class="card-header">
              <h2 class="card-title">Мастера</h2>
              <span class="card-meta">Измените индивидуальные проценты мастеров (если нужно).</span>
            </div>
            <div class="search-row">
              <span class="card-meta">Найдите мастера по имени / ID (поиск по браузеру Ctrl+F).</span>
            </div>
            <form method="post">
              <table>
                <thead>
                  <tr>
                    <th>VK ID</th>
                    <th>Имя</th>
                    <th>Город</th>
                    <th>Телефон</th>
                    <th>Индивидуальный % мастера</th>
                  </tr>
                </thead>
                <tbody>
                  {% for u in masters %}
                    <tr>
                      <td>{{ u.tg_id }}</td>
                      <td>{{ u.full_name or u.name or "" }}</td>
                      <td>{{ u.city_rel.name if u.city_rel else "" }}</td>
                      <td>{{ u.phone or "" }}</td>
                      <td>
                        <input type="number"
                               step="0.1"
                               name="master_pct_{{ u.tg_id }}"
                               placeholder="по сетке"
                               value="{{ u.master_percentage if u.master_percentage is not none else '' }}">
                      </td>
                    </tr>
                  {% endfor %}
                </tbody>
              </table>
              <p style="margin-top:12px; display:flex; justify-content:flex-end;">
                <button class="btn btn-primary" type="submit">💾 Сохранить проценты мастеров</button>
              </p>
            </form>
          </div>

          <div class="card">
            <div class="card-header">
              <h2 class="card-title">Роли: директора и диспетчеры</h2>
            </div>

            <h3 style="font-size:13px; margin: 4px 0;">Директора</h3>
            <table>
              <thead>
                <tr>
                  <th>VK ID</th>
                  <th>Имя</th>
                  <th>Город</th>
                  <th>Телефон</th>
                </tr>
              </thead>
              <tbody>
                {% for u in directors %}
                  <tr>
                    <td>{{ u.tg_id }}</td>
                    <td>{{ u.full_name or u.name or "" }}</td>
                    <td>{{ u.city_rel.name if u.city_rel else "" }}</td>
                    <td>{{ u.phone or "" }}</td>
                  </tr>
                {% endfor %}
              </tbody>
            </table>

            <h3 style="font-size:13px; margin: 14px 0 4px;">Диспетчеры</h3>
            <table>
              <thead>
                <tr>
                  <th>VK ID</th>
                  <th>Имя</th>
                  <th>Город</th>
                  <th>Телефон</th>
                </tr>
              </thead>
              <tbody>
                {% for u in dispatchers %}
                  <tr>
                    <td>{{ u.tg_id }}</td>
                    <td>{{ u.full_name or u.name or "" }}</td>
                    <td>{{ u.city_rel.name if u.city_rel else "" }}</td>
                    <td>{{ u.phone or "" }}</td>
                  </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
        </div>
        {% endblock %}
        """,
        masters=masters_q,
        directors=directors,
        dispatchers=dispatchers,
        active="masters",
        header_title="Команда и роли",
        header_subtitle="Мастера с индивидуальными процентами, а также директора и диспетчеры",
    )
  finally:
    session.close()


@app.route("/cities", methods=["GET", "POST"])
def cities():
  session = get_session()
  try:
    if request.method == "POST":
      name = (request.form.get("name") or "").strip()
      tz = (request.form.get("timezone") or "").strip() or "Europe/Moscow"
      pct_raw = (request.form.get("cash_company_percentage") or "").strip()
      if not name:
        flash("Название города не может быть пустым.", "error")
      else:
        try:
          pct = float(pct_raw) if pct_raw else 50.0
        except ValueError:
          pct = 50.0
        if session.query(City).filter(City.name == name).first():
          flash("Город с таким названием уже существует.", "error")
        else:
          city = City(name=name, timezone=tz, cash_company_percentage=pct)
          session.add(city)
          session.commit()
          flash("Город добавлен.", "success")

    cities_q = session.query(City).order_by(City.name.asc()).all()
    return render_template_string(
        BASE_TEMPLATE + """
        {% block content %}
        <div class="card-grid">
          <div class="card">
            <div class="card-header">
              <h2 class="card-title">Города</h2>
              <span class="card-meta">Список городов, связанных с заявками и пользователями.</span>
            </div>
            <table>
              <thead>
                <tr>
                  <th style="width:60px;">ID</th>
                  <th>Название</th>
                  <th>Часовой пояс</th>
                  <th>% компании по кассе</th>
                </tr>
              </thead>
              <tbody>
                {% for c in cities %}
                  <tr>
                    <td>{{ c.id }}</td>
                    <td>{{ c.name }}</td>
                    <td>{{ c.timezone }}</td>
                    <td>{{ "%.2f"|format(c.cash_company_percentage or 0) }}</td>
                  </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>

          <div class="card">
            <div class="card-header">
              <h2 class="card-title">Добавить город</h2>
              <span class="card-meta">IANA‑таймзона нужна для правильного времени смен и кассы.</span>
            </div>
            <form method="post">
              <table>
                <tr>
                  <td style="width:120px;">Название</td>
                  <td><input type="text" name="name" required placeholder="Например, Москва"></td>
                </tr>
                <tr>
                  <td>Часовой пояс</td>
                  <td><input type="text" name="timezone" placeholder="Europe/Moscow"></td>
                </tr>
                <tr>
                  <td>% компании по кассе</td>
                  <td><input type="number" step="0.1" name="cash_company_percentage" placeholder="50.0"></td>
                </tr>
              </table>
              <p style="margin-top:12px; display:flex; justify-content:flex-end;">
                <button class="btn btn-primary" type="submit">➕ Добавить город</button>
              </p>
            </form>
          </div>
        </div>
        {% endblock %}
        """,
        cities=cities_q,
        active="cities",
        header_title="Города и таймзоны",
        header_subtitle="Управление городами, часовыми поясами и долей компании по кассе",
    )
  finally:
    session.close()


def main():
  port = int(os.getenv("ADMIN_PORT", "8000"))
  app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
  main()


