"""End-to-end smoke по живому стенду СУУПР.

Запускает сценарии работы всех ролей через REST API и печатает PASS/FAIL по
каждому пункту. Цель — убедиться, что весь функционал ТЗ работает на боевом
backend без UI.

Запуск:
    python scripts/smoke_e2e.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any

BASE = "http://127.0.0.1:8003/api/v1"


def http(method: str, path: str, *, token: str | None = None, body: Any = None) -> tuple[int, dict | list | None]:
    url = f"{BASE}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            content = response.read().decode("utf-8")
            return response.getcode(), json.loads(content) if content else None
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        try:
            payload = json.loads(text)
        except Exception:
            payload = {"raw": text}
        return exc.code, payload


def login(phone: str, password: str) -> tuple[str, dict]:
    code, payload = http("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, f"login failed for {phone}: {code} {payload}"
    return payload["access_token"], payload["user"]


PASSED: list[str] = []
FAILED: list[str] = []


def assert_true(condition: bool, label: str, detail: str = "") -> None:
    marker = "PASS" if condition else "FAIL"
    print(f"  [{marker}] {label}{(' — ' + detail) if detail else ''}")
    (PASSED if condition else FAILED).append(label)


def step(title: str) -> None:
    print()
    print(f"=== {title} ===")


def main() -> int:
    step("STEP 1. Авторизация под всеми ролями")
    owner_token, owner_user = login("+79990000001", "demo12345")
    manager_token, manager_user = login("+79990000002", "demo12345")
    director_token, director_user = login("+79990000003", "demo12345")
    promoter_token, promoter_user = login("+79990000004", "demo12345")
    promoter_north_token, _ = login("+79990000006", "demo12345")
    master_token, master_user = login("+79990000007", "demo12345")
    assert_true(owner_user["role_code"] == "owner", "owner login → роль owner")
    assert_true(manager_user["role_code"] == "branch_manager", "manager login → роль branch_manager")
    assert_true(director_user["role_code"] == "ad_director", "director login → роль ad_director")
    assert_true(promoter_user["role_code"] == "promoter", "promoter login → роль promoter")
    assert_true(master_user["role_code"] == "master", "master login → роль master")

    step("STEP 2. Изоляция филиалов")
    _, owner_branches = http("GET", "/branches", token=owner_token)
    _, manager_branches = http("GET", "/branches", token=manager_token)
    assert_true(len(owner_branches) >= 2, "owner видит ≥ 2 филиалов", f"{len(owner_branches)} филиалов")
    assert_true(len(manager_branches) == 1, "руководитель видит только свой филиал", f"{len(manager_branches)} филиалов")

    step("STEP 3. Маршруты по ролям")
    _, owner_routes = http("GET", "/routes", token=owner_token)
    _, manager_routes = http("GET", "/routes", token=manager_token)
    _, promoter_routes = http("GET", "/routes", token=promoter_token)
    _, promoter_north_routes = http("GET", "/routes", token=promoter_north_token)
    print(f"  owner sees {len(owner_routes)} routes")
    print(f"  manager.center sees {len(manager_routes)} routes")
    print(f"  promoter.center sees {len(promoter_routes)} routes")
    print(f"  promoter.north sees {len(promoter_north_routes)} routes")
    assert_true(len(owner_routes) >= len(manager_routes), "owner видит маршрутов >= manager")
    assert_true(
        all(route["promoter_id"] == promoter_user["id"] for route in promoter_routes),
        "промоутер видит только назначенные ему маршруты",
    )

    step("STEP 4. Создание маршрута директором + назначение")
    center_branch_id = manager_branches[0]["id"]
    _, rates = http("GET", "/payout-rates", token=director_token)
    hourly_rate = next(rate for rate in rates if rate["rate_type"] == "hourly")
    suffix = datetime.now().strftime("%H%M%S")
    _, new_route = http(
        "POST",
        "/routes",
        token=director_token,
        body={
            "title": f"Smoke route {suffix}",
            "description": "сценарий smoke",
            "work_date": (date.today() + timedelta(days=1)).isoformat(),
            "branch_id": center_branch_id,
            "payout_rate_id": hourly_rate["id"],
            "points": [
                {"sequence": 1, "name": "Старт", "address": "Тверская", "latitude": 55.76, "longitude": 37.61, "point_type": "start"},
                {"sequence": 2, "name": "Финиш", "address": "Пушкинская", "latitude": 55.77, "longitude": 37.60, "point_type": "finish"},
            ],
        },
    )
    assert_true(new_route["status"] == "draft", "маршрут создан со статусом draft")
    code, assigned = http(
        "POST",
        f"/routes/{new_route['id']}/assign",
        token=director_token,
        body={"promoter_id": promoter_user["id"]},
    )
    assert_true(code == 200 and assigned["status"] == "assigned", "маршрут назначен промоутеру", f"status={assigned.get('status')}")

    step("STEP 5. Прикрепление map_image к маршруту (multipart skip — проверим сервис без файла)")
    # Через JSON API multipart нельзя — UI сам делает FormData. Проверим только что эндпоинт защищён 422 без файла.
    code, _ = http("POST", f"/routes/{new_route['id']}/map-image", token=director_token)
    assert_true(code in {400, 422, 415}, "map-image требует multipart/файл", f"got {code}")

    step("STEP 6. Полный жизненный цикл заявки мастеру")
    _, mr = http(
        "POST",
        "/master-requests",
        token=director_token,
        body={
            "title": f"Smoke MR {suffix}",
            "description": "smoke",
            "address": "Тестовая 1",
            "client_name": "Smoke Client",
            "client_phone": "+74950000099",
            "estimated_amount": "5000.00",
            "currency": "RUB",
            "branch_id": center_branch_id,
            "assignee_id": master_user["id"],
        },
    )
    assert_true(mr["status"] == "new", "заявка создана со статусом new")

    transitions = ["accepted", "on_the_way", "in_progress", "completed", "handed_over"]
    for status_value in transitions:
        body = {"status": status_value, "note": f"smoke→{status_value}"}
        if status_value in {"on_the_way", "in_progress"}:
            body["latitude"] = 55.7558
            body["longitude"] = 37.6173
        code, updated = http("POST", f"/master-requests/{mr['id']}/status", token=master_token, body=body)
        assert_true(code == 200 and updated["status"] == status_value, f"переход в статус {status_value}")
        if status_value in {"on_the_way", "in_progress"}:
            assert_true(updated["geo_tracking_enabled"] is True, f"гео включена в {status_value}")
        if status_value == "handed_over":
            assert_true(updated["geo_tracking_enabled"] is False, "гео выключена в handed_over")

    _, mr_final = http("GET", f"/master-requests/{mr['id']}", token=master_token)
    assert_true(mr_final["geo_ping_count"] >= 2, "≥2 GPS-точек у мастера", f"{mr_final['geo_ping_count']}")
    assert_true(len(mr_final["status_logs"]) >= 6, "журнал статусов содержит все переходы")

    step("STEP 7. Запрет перепрыгивания статусов")
    _, mr_skip = http(
        "POST",
        "/master-requests",
        token=director_token,
        body={
            "title": f"Skip {suffix}",
            "branch_id": center_branch_id,
            "assignee_id": master_user["id"],
            "currency": "RUB",
        },
    )
    code, _ = http("POST", f"/master-requests/{mr_skip['id']}/status", token=master_token, body={"status": "in_progress"})
    assert_true(code == 409, "перепрыжка new→in_progress отбита 409", f"got {code}")

    step("STEP 8. Комментарии к заявке мастера")
    code, comment = http(
        "POST",
        f"/master-requests/{mr['id']}/comments",
        token=master_token,
        body={"body": "Закрыто в smoke"},
    )
    assert_true(code == 201, "комментарий добавлен", f"got {code}")

    step("STEP 9. План расходов: создание → submit → согласование")
    today_iso = date.today().isoformat()
    period_end = (date.today() + timedelta(days=30)).isoformat()
    _, plan = http(
        "POST",
        "/expense-plans",
        token=manager_token,
        body={
            "title": f"Smoke plan {suffix}",
            "branch_id": center_branch_id,
            "period_start": today_iso,
            "period_end": period_end,
            "currency": "RUB",
            "comment": "smoke",
            "items": [
                {"name": "Аренда офиса", "category": "Аренда", "quantity": 1, "unit_price": 60000},
                {"name": "Листовки", "category": "Материалы", "quantity": 5000, "unit_price": 3.2},
            ],
        },
    )
    assert_true(plan["status"] == "draft", "план создан как draft")
    assert_true(float(plan["total_amount"]) == 76000.0, "сумма посчитана 1*60000 + 5000*3.20 = 76000")

    code, submitted = http("POST", f"/expense-plans/{plan['id']}/submit", token=manager_token)
    assert_true(code == 200 and submitted["status"] == "submitted", "план отправлен собственнику")

    code, decided = http(
        "POST",
        f"/expense-plans/{plan['id']}/decision",
        token=owner_token,
        body={"decision": "approved", "comment": "smoke ОК"},
    )
    assert_true(code == 200 and decided["status"] == "approved", "план согласован собственником")

    step("STEP 10. Промоутер не может создать план расходов")
    code, _ = http(
        "POST",
        "/expense-plans",
        token=promoter_token,
        body={
            "title": "promoter try",
            "branch_id": center_branch_id,
            "period_start": today_iso,
            "period_end": today_iso,
            "items": [],
        },
    )
    assert_true(code == 403, "промоутер заблокирован 403", f"got {code}")

    step("STEP 11. Уведомления собственнику")
    _, owner_notifs = http("GET", "/notifications", token=owner_token)
    titles = {n["title"] for n in owner_notifs}
    print(f"  owner notifications total: {len(owner_notifs)}")
    for sample in list(titles)[:8]:
        print(f"    - {sample}")
    assert_true(len(owner_notifs) > 0, "у собственника есть уведомления")
    assert_true(
        any("plan" in t.lower() or "expense" in t.lower() for t in titles)
        or any("master" in t.lower() for t in titles)
        or any("route" in t.lower() for t in titles),
        "среди уведомлений есть события по маршрутам/планам/мастер-заявкам",
    )

    step("STEP 12. Раздел Доход/Расход — детализация по промоутерам")
    _, summary = http("GET", "/payouts/summary/by-promoter", token=owner_token)
    print(f"  promoters with payouts: {len(summary)}")
    for row in summary:
        print(f"    - {row['promoter_name']}: {row['payout_count']} начислений, {row['total_amount']} {row['currency']}")
    assert_true(len(summary) > 0, "есть начисления хотя бы по одному промоутеру")
    assert_true(
        all("payouts" in row and len(row["payouts"]) == row["payout_count"] for row in summary),
        "каждая запись содержит детализацию начислений",
    )

    step("STEP 13. Аудит-журнал")
    _, audit_owner = http("GET", "/audit-logs?limit=10", token=owner_token)
    actions = {item["action"] for item in audit_owner}
    print(f"  owner audit (10 last):")
    for action in list(actions)[:8]:
        print(f"    - {action}")
    assert_true(len(audit_owner) > 0, "у собственника есть audit-записи")

    _, audit_manager = http("GET", "/audit-logs?limit=20", token=manager_token)
    branches_in_audit = {item["branch_id"] for item in audit_manager if item["branch_id"]}
    assert_true(
        len(branches_in_audit) <= 1,
        "manager видит audit только своего филиала",
        f"branches in audit: {branches_in_audit}",
    )

    step("STEP 14. Изоляция: запрет создания заявки в чужом филиале")
    other_branch = next(branch for branch in owner_branches if branch["id"] != center_branch_id)
    code, _ = http(
        "POST",
        "/master-requests",
        token=director_token,
        body={
            "title": "Cross-branch",
            "branch_id": other_branch["id"],
            "currency": "RUB",
        },
    )
    assert_true(code == 403, "директор не может создать заявку в чужом филиале", f"got {code}")

    print()
    print("=" * 60)
    print(f"ИТОГО: {len(PASSED)} PASS / {len(FAILED)} FAIL")
    if FAILED:
        print("FAILED CHECKS:")
        for label in FAILED:
            print(f"  - {label}")
        return 1
    print("Все smoke-проверки прошли успешно.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
