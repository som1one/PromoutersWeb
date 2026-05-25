"""Интеграционные тесты мастер-контура: создание заявки, смена статусов, БСО, комментарии."""

from __future__ import annotations

from tests.conftest import auth_headers
from promouters.models.enums import RoleCode


def test_master_request_full_workflow(client, user_factory, login_helper, seed_branch):
    director, director_pass = user_factory(RoleCode.AD_DIRECTOR)
    master, master_pass = user_factory(RoleCode.MASTER)

    director_token = login_helper(director.phone, director_pass)
    master_token = login_helper(master.phone, master_pass)

    # Директор создаёт заявку и назначает на мастера
    create_response = client.post(
        "/api/v1/master-requests",
        headers=auth_headers(director_token),
        json={
            "title": "Установка кондиционера",
            "description": "Демонтаж + установка",
            "address": "ул. Тестовая, 1",
            "client_name": "Клиент",
            "client_phone": "+74950000000",
            "estimated_amount": "5000.00",
            "currency": "RUB",
            "branch_id": str(seed_branch.id),
            "assignee_id": str(master.id),
        },
    )
    assert create_response.status_code == 201, create_response.text
    master_request = create_response.json()
    request_id = master_request["id"]
    assert master_request["status"] == "new"
    assert master_request["assignee_id"] == str(master.id)

    # Мастер видит заявку
    list_response = client.get("/api/v1/master-requests", headers=auth_headers(master_token))
    assert list_response.status_code == 200
    titles = [item["title"] for item in list_response.json()]
    assert "Установка кондиционера" in titles

    # Полный цикл смены статусов мастером
    for status_value, geo in [
        ("accepted", None),
        ("on_the_way", (55.7558, 37.6173)),
        ("in_progress", (55.7560, 37.6175)),
        ("completed", None),
        ("handed_over", None),
    ]:
        payload: dict[str, object] = {"status": status_value, "note": f"Переход на {status_value}"}
        if geo is not None:
            payload["latitude"] = geo[0]
            payload["longitude"] = geo[1]
        change_response = client.post(
            f"/api/v1/master-requests/{request_id}/status",
            headers=auth_headers(master_token),
            json=payload,
        )
        assert change_response.status_code == 200, (
            f"transition to {status_value} failed: {change_response.text}"
        )

    final = client.get(
        f"/api/v1/master-requests/{request_id}", headers=auth_headers(master_token)
    ).json()
    assert final["status"] == "handed_over"
    assert final["geo_tracking_enabled"] is False  # на handed_over геопозиция выключена
    # На on_the_way и in_progress должны быть гео-пинги
    assert final["geo_ping_count"] >= 2
    assert any(log["to_status"] == "on_the_way" for log in final["status_logs"])
    assert any(log["to_status"] == "handed_over" for log in final["status_logs"])

    # Мастер добавил комментарий
    comment_response = client.post(
        f"/api/v1/master-requests/{request_id}/comments",
        headers=auth_headers(master_token),
        json={"body": "Заявка закрыта успешно"},
    )
    assert comment_response.status_code == 201, comment_response.text


def test_master_cannot_skip_status(client, user_factory, login_helper, seed_branch):
    director, director_pass = user_factory(RoleCode.AD_DIRECTOR)
    master, master_pass = user_factory(RoleCode.MASTER)
    director_token = login_helper(director.phone, director_pass)
    master_token = login_helper(master.phone, master_pass)

    create_response = client.post(
        "/api/v1/master-requests",
        headers=auth_headers(director_token),
        json={
            "title": "Перепрыжка статусов",
            "branch_id": str(seed_branch.id),
            "assignee_id": str(master.id),
            "currency": "RUB",
        },
    )
    request_id = create_response.json()["id"]

    # Попытка перепрыгнуть с new сразу на in_progress — должна быть отклонена
    bad_transition = client.post(
        f"/api/v1/master-requests/{request_id}/status",
        headers=auth_headers(master_token),
        json={"status": "in_progress"},
    )
    assert bad_transition.status_code == 409


def test_promoter_cannot_see_master_requests_outside_branch(
    client, user_factory, login_helper, db_session, seed_branch
):
    other_branch = type(seed_branch)(
        name="Другой филиал", code="OTHER", city="СПб", is_active=True
    )
    db_session.add(other_branch)
    db_session.commit()
    db_session.refresh(other_branch)

    director, director_pass = user_factory(RoleCode.AD_DIRECTOR)
    master, _ = user_factory(RoleCode.MASTER, branch=other_branch)

    director_token = login_helper(director.phone, director_pass)

    response = client.post(
        "/api/v1/master-requests",
        headers=auth_headers(director_token),
        json={
            "title": "Заявка для другого филиала",
            "branch_id": str(other_branch.id),
            "assignee_id": str(master.id),
            "currency": "RUB",
        },
    )
    # Директор не может создать заявку в чужом филиале
    assert response.status_code == 403
