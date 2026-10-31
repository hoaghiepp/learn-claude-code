"""pytest suite for the user_service API endpoints.

Requires a running PostgreSQL database; connection is configured through
``DATABASE_URL`` or the ``PG*`` environment variables (see ``db.py``).
Each test truncates ``users`` first so the suite is hermetic.

Run from the repository root:

    PGHOST=127.0.0.1 PGPORT=15432 PGUSER=postgres \
    PGPASSWORD=testpw PGDATABASE=user_service \
    pytest practice/user_service/test_api.py
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from practice.user_service.db import apply_schema, connection_from_env
from practice.user_service.main import app


@pytest.fixture()
def client() -> TestClient:
    """Build a TestClient and reset the ``users`` table before each test."""
    with connection_from_env() as conn:
        with conn.cursor() as cursor:
            cursor.execute("TRUNCATE users RESTART IDENTITY CASCADE")
        conn.commit()

    with TestClient(app) as test_client:
        yield test_client


def _create_user(
    client: TestClient,
    name: str = "Alice",
    email: str = "alice@app.io",
    **overrides: object,
) -> dict:
    """Helper to create a user through the API and return the JSON body."""
    payload: dict[str, object] = {"name": name, "email": email, **overrides}
    response = client.post("/users", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_users_is_empty_initially(client: TestClient) -> None:
    response = client.get("/users")

    assert response.status_code == 200
    assert response.json() == []


def test_create_user_returns_defaults(client: TestClient) -> None:
    user = _create_user(client)

    assert user["name"] == "Alice"
    assert user["email"] == "alice@app.io"
    assert user["active"] is True
    assert user["password_hash"] is None
    assert user["created_at"] is not None
    assert user["updated_at"] is not None
    assert user["id"] == 1


def test_get_user_by_id(client: TestClient) -> None:
    created = _create_user(client)

    response = client.get(f"/users/{created['id']}")

    assert response.status_code == 200
    assert response.json()["email"] == "alice@app.io"


def test_get_missing_user_returns_404(client: TestClient) -> None:
    response = client.get("/users/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_duplicate_email_returns_409(client: TestClient) -> None:
    _create_user(client)

    response = client.post(
        "/users", json={"name": "Alice 2", "email": "ALICE@app.io"}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "A user with this email already exists"


def test_custom_fields_are_stored(client: TestClient) -> None:
    user = _create_user(
        client, name="Bob", email="bob@app.io", active=False,
        password_hash="hashed-value",
    )

    assert user["name"] == "Bob"
    assert user["active"] is False
    assert user["password_hash"] == "hashed-value"


def test_patch_updates_only_provided_fields(client: TestClient) -> None:
    user = _create_user(client)

    response = client.patch(f"/users/{user['id']}", json={"active": False})

    assert response.status_code == 200
    body = response.json()
    assert body["active"] is False
    assert body["name"] == "Alice"  # untouched
    assert body["email"] == "alice@app.io"  # untouched


def test_patch_with_no_fields_returns_400(client: TestClient) -> None:
    user = _create_user(client)

    response = client.patch(f"/users/{user['id']}", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "No fields to update"


def test_patch_missing_user_returns_404(client: TestClient) -> None:
    response = client.patch(
        "/users/999999", json={"name": "Nobody"}
    )

    assert response.status_code == 404


def test_patch_to_duplicate_email_returns_409(client: TestClient) -> None:
    _create_user(client, name="Alice", email="alice@app.io")
    other = _create_user(client, name="Bob", email="bob@app.io")

    response = client.patch(
        f"/users/{other['id']}", json={"email": "ALICE@app.io"}
    )

    assert response.status_code == 409


def test_list_filters_by_active(client: TestClient) -> None:
    inactive = _create_user(client, name="Bob", email="bob@app.io", active=False)
    _create_user(client, name="Carol", email="carol@app.io")

    active_response = client.get("/users", params={"active": "true"})
    inactive_response = client.get("/users", params={"active": "false"})

    assert active_response.status_code == 200
    assert [u["id"] for u in active_response.json()] == [2]
    assert [u["id"] for u in inactive_response.json()] == [inactive["id"]]


def test_list_respects_limit(client: TestClient) -> None:
    for index in range(3):
        _create_user(client, name=f"User {index}", email=f"user{index}@app.io")

    response = client.get("/users", params={"limit": 2})

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_delete_user_returns_204(client: TestClient) -> None:
    user = _create_user(client)

    response = client.delete(f"/users/{user['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/users/{user['id']}").status_code == 404


def test_validation_rejects_bad_payload(client: TestClient) -> None:
    response = client.post(
        "/users", json={"name": "", "email": "not-an-email"}
    )

    assert response.status_code == 422


def test_schema_applies_idempotently() -> None:
    """Applying the schema twice must not raise (startup is safe to rerun)."""
    with connection_from_env() as conn:
        apply_schema(conn)
        apply_schema(conn)
