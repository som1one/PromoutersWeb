"""Интеграционные тесты плана расходов и согласования с собственником."""

from __future__ import annotations

from datetime import date, timedelta

from tests.conftest import auth_headers
from promouters.models.enums import RoleCode


def test_expense_plan_full_approval_workflow(client, user_factory, login_helper, seed_branch):
    owner, owner_pass = user_factory(RoleCode.OWNER)
    manager, manager_pass = user_factory(RoleCode.BRANCH_MANAGER)

    owner_token = login_helper(owner.phone, owner_pass)
    manager_token = login_helper(manager.phone, manager_pass)

    today = date.today()
    create_response = client.post(
        "/api/v1/expense-plans",
        headers=auth_headers(manager_token),
        json={
            "title": "План на месяц",
            "branch_id": str(seed_branch.id),
            "period_start": today.isoformat(),
            "period_end": (today + timedelta(days=30)).isoformat(),
            "currency": "RUB",
            "comment": "Стандартный месячный бюджет",
            "items": [
                {"name": "Аренда офиса", "category": "Аренда", "quantity": 1, "unit_price": 60000},
                {"name": "Листовки", "category": "Материалы", "quantity": 5000, "unit_price": 3.2},
            ],
        },
    )
    assert create_response.status_code == 201, create_response.text
    plan = create_response.json()
    plan_id = plan["id"]
    assert plan["status"] == "draft"
    # 1*60000 + 5000*3.2 = 76000
    assert float(plan["total_amount"]) == 76000.0
    assert len(plan["items"]) == 2

    # Собственник видит план
    owner_list = client.get("/api/v1/expense-plans", headers=auth_headers(owner_token)).json()
    assert any(item["id"] == plan_id for item in owner_list)

    # Руководитель отправляет на согласование
    submit_response = client.post(
        f"/api/v1/expense-plans/{plan_id}/submit",
        headers=auth_headers(manager_token),
    )
    assert submit_response.status_code == 200, submit_response.text
    assert submit_response.json()["status"] == "submitted"

    # Собственник согласовывает
    decision_response = client.post(
        f"/api/v1/expense-plans/{plan_id}/decision",
        headers=auth_headers(owner_token),
        json={"decision": "approved", "comment": "Согласовано"},
    )
    assert decision_response.status_code == 200, decision_response.text
    plan_after = decision_response.json()
    assert plan_after["status"] == "approved"
    assert plan_after["approved_at"] is not None
    assert any(approval["decision"] == "approved" for approval in plan_after["approvals"])


def test_expense_plan_rejection_returns_to_draft(
    client, user_factory, login_helper, seed_branch
):
    owner, owner_pass = user_factory(RoleCode.OWNER)
    manager, manager_pass = user_factory(RoleCode.BRANCH_MANAGER)
    owner_token = login_helper(owner.phone, owner_pass)
    manager_token = login_helper(manager.phone, manager_pass)

    today = date.today()
    plan = client.post(
        "/api/v1/expense-plans",
        headers=auth_headers(manager_token),
        json={
            "title": "Спорный план",
            "branch_id": str(seed_branch.id),
            "period_start": today.isoformat(),
            "period_end": (today + timedelta(days=10)).isoformat(),
            "items": [{"name": "Расход", "quantity": 1, "unit_price": 100}],
        },
    ).json()
    plan_id = plan["id"]

    client.post(
        f"/api/v1/expense-plans/{plan_id}/submit", headers=auth_headers(manager_token)
    )
    decision = client.post(
        f"/api/v1/expense-plans/{plan_id}/decision",
        headers=auth_headers(owner_token),
        json={"decision": "needs_revision", "comment": "Уточните позиции"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "draft"


def test_promoter_cannot_create_expense_plan(
    client, user_factory, login_helper, seed_branch
):
    promoter, password = user_factory(RoleCode.PROMOTER)
    token = login_helper(promoter.phone, password)

    response = client.post(
        "/api/v1/expense-plans",
        headers=auth_headers(token),
        json={
            "title": "Бунт",
            "branch_id": str(seed_branch.id),
            "period_start": date.today().isoformat(),
            "period_end": date.today().isoformat(),
            "items": [],
        },
    )
    assert response.status_code == 403
