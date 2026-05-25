"""Smoke-тесты: проверяют, что приложение поднимается и базовые эндпоинты живы."""

from __future__ import annotations


def test_root_endpoint(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_health_endpoint(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_openapi_schema_available(client) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "paths" in data
    assert "/api/v1/auth/login" in data["paths"]


def test_login_requires_credentials(client, seed_roles, seed_branch) -> None:
    response = client.post("/api/v1/auth/login", json={"phone": "+70000000000", "password": "wrong"})
    assert response.status_code == 401
