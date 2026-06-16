"""M1 - User Access Management Start
Verifies authentication, token, and password setup behavior.
M1 End"""

from datetime import timedelta

from app.models.user import UserCreate
from app.services.user_service import create_initial_admin, create_user
from app.utils.security import create_access_token, hash_password, verify_password


def test_password_hashing_does_not_return_original_password():
    password = "Secure123"

    hashed_password = hash_password(password)

    assert hashed_password != password
    assert hashed_password.startswith("pbkdf2_sha256$")


def test_password_verification_succeeds_for_correct_password():
    password = "Secure123"
    hashed_password = hash_password(password)

    assert verify_password(password, hashed_password) is True


def test_password_verification_fails_for_wrong_password():
    hashed_password = hash_password("Secure123")

    assert verify_password("Wrong123", hashed_password) is False


def test_login_succeeds_with_valid_active_user(client, standard_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "USER@example.com", "password": "User1234"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["password_change_required"] is False


def test_bootstrap_admin_login_requires_password_change(client, db_session):
    create_initial_admin(db_session, "first.login@example.com", "FirstLogin123")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "first.login@example.com", "password": "FirstLogin123"},
    )

    assert response.status_code == 200
    assert response.json()["password_change_required"] is True


def test_login_fails_with_invalid_credentials(client, standard_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "Wrong123"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["type"] == "INVALID_CREDENTIALS"


def test_login_forbidden_for_inactive_user(client, inactive_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "Inactive123"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["type"] == "INACTIVE_USER"


def test_me_returns_current_user_with_valid_token(client, standard_user):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "User1234"},
    )
    token = login_response.json()["access_token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
    assert "hashed_password" not in response.json()


def test_refresh_returns_new_token_for_active_session(client, standard_user):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "User1234"},
    )
    token = login_response.json()["access_token"]

    response = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["password_change_required"] is False

    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "user@example.com"


def test_authenticated_user_can_change_password(client, db_session):
    admin = create_initial_admin(db_session, "password.setup@example.com", "SetupAdmin123")
    token = create_access_token(admin.id)

    response = client.post(
        "/api/v1/auth/change-password",
        json={"new_password": "ChangedAdmin123"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["must_change_password"] is False

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "password.setup@example.com", "password": "ChangedAdmin123"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["password_change_required"] is False


def test_protected_endpoint_rejects_missing_token(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_protected_endpoint_rejects_invalid_token(client):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401
    assert response.json()["detail"]["type"] == "INVALID_TOKEN"


def test_protected_endpoint_rejects_expired_token(client, standard_user):
    expired_token = create_access_token(standard_user.id, expires_delta=timedelta(seconds=-1))

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})

    assert response.status_code == 401
    assert response.json()["detail"]["type"] == "INVALID_TOKEN"


def test_duplicate_email_returns_controlled_error(db_session):
    create_user(
        db_session,
        UserCreate(
            email="duplicate@example.com",
            full_name="Duplicate One",
            password="Duplicate123",
        ),
    )

    try:
        create_user(
            db_session,
            UserCreate(
                email="DUPLICATE@example.com",
                full_name="Duplicate Two",
                password="Duplicate123",
            ),
        )
    except Exception as exc:
        assert exc.status_code == 400
        assert exc.detail["type"] == "USER_ALREADY_EXISTS"
    else:
        raise AssertionError("Expected duplicate email to fail")


# M1 End
