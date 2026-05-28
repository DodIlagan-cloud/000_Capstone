"""M1 - User Access Management Start
Verifies Identity Access user administration behavior.
M1 End"""

from app.models.user import User
from app.services.user_service import create_initial_admin


def _login(client, email: str, password: str) -> str:
    """Return a bearer token for test credentials."""
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_user_model_imports_successfully():
    assert User.__tablename__ == "users"


def test_initial_admin_can_be_created_before_other_users(db_session):
    admin = create_initial_admin(
        db_session,
        "first.admin@example.com",
        "FirstAdmin123",
        "First Admin",
    )

    assert admin.email == "first.admin@example.com"
    assert admin.full_name == "First Admin"
    assert admin.role == "admin"
    assert admin.must_change_password is True


def test_initial_admin_creation_is_blocked_after_user_exists(db_session, standard_user):
    try:
        create_initial_admin(db_session, "late.admin@example.com", "LateAdmin123")
    except Exception as exc:
        assert exc.status_code == 403
        assert exc.detail["type"] == "FORBIDDEN"
    else:
        raise AssertionError("Expected initial admin creation to be blocked")


def test_initial_admin_can_log_in_and_add_user(client, db_session):
    create_initial_admin(
        db_session,
        "initial.admin@example.com",
        "InitialAdmin123",
        "Initial Admin",
    )
    token = _login(client, "initial.admin@example.com", "InitialAdmin123")

    blocked_response = client.post(
        "/api/v1/users",
        json={
            "email": "added.user@example.com",
            "full_name": "Added User",
            "password": "AddedUser123",
            "role": "user",
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert blocked_response.status_code == 403
    assert blocked_response.json()["detail"]["type"] == "FORBIDDEN"

    password_response = client.post(
        "/api/v1/auth/change-password",
        json={"new_password": "ChangedAdmin123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert password_response.status_code == 200

    response = client.post(
        "/api/v1/users",
        json={
            "email": "added.user@example.com",
            "full_name": "Added User",
            "password": "AddedUser123",
            "role": "user",
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["email"] == "added.user@example.com"
    assert response.json()["role"] == "user"


def test_admin_can_create_user(client, admin_user):
    token = _login(client, "admin@example.com", "Admin123")

    response = client.post(
        "/api/v1/users",
        json={
            "email": "new.user@example.com",
            "full_name": "New User",
            "password": "NewUser123",
            "role": "user",
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.user@example.com"
    assert body["role"] == "user"
    assert body["must_change_password"] is True
    assert "hashed_password" not in body


def test_admin_can_list_users(client, admin_user, standard_user):
    token = _login(client, "admin@example.com", "Admin123")

    response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert [user["email"] for user in response.json()] == ["admin@example.com", "user@example.com"]


def test_standard_user_cannot_list_users(client, standard_user):
    token = _login(client, "user@example.com", "User1234")

    response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["detail"]["type"] == "FORBIDDEN"


def test_standard_user_can_get_own_profile_from_users_route(client, standard_user):
    token = _login(client, "user@example.com", "User1234")

    response = client.get(
        f"/api/v1/users/{standard_user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_standard_user_cannot_get_another_user_profile(client, admin_user, standard_user):
    token = _login(client, "user@example.com", "User1234")

    response = client.get(
        f"/api/v1/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["type"] == "FORBIDDEN"


def test_admin_cannot_deactivate_last_active_admin(client, admin_user):
    token = _login(client, "admin@example.com", "Admin123")

    response = client.patch(
        f"/api/v1/users/{admin_user.id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["type"] == "FORBIDDEN"


def test_admin_cannot_demote_last_active_admin(client, admin_user):
    token = _login(client, "admin@example.com", "Admin123")

    response = client.patch(
        f"/api/v1/users/{admin_user.id}",
        json={"role": "user"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["type"] == "FORBIDDEN"


# M1 End
