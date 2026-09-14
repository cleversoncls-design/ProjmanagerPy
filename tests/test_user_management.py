import pytest
from fastapi import HTTPException

from app.main import UserCreate, hash_password, require_admin, verify_password
from app.models import User, UserRole, UserStatus


def test_hash_password_is_verifiable_and_not_plaintext():
    encoded = hash_password("SenhaSegura26")
    assert encoded.startswith("pbkdf2_sha256$310000$")
    assert encoded != "SenhaSegura26"
    assert verify_password("SenhaSegura26", encoded)
    assert not verify_password("senha-incorreta", encoded)


def test_external_user_requires_client_id():
    payload = UserCreate(name="Usuário Cliente", email="cliente@example.com", password="SenhaSegura26", role=UserRole.CLIENT_USER)
    assert payload.client_id is None
    assert payload.role == UserRole.CLIENT_USER


def test_user_serializer_does_not_expose_password_hash():
    from app.main import serialize_user

    user = User(id="user-1", name="Gerente", email="gerente@example.com", password_hash="secret-hash", role=UserRole.INTERNAL_PM, status=UserStatus.ACTIVE)
    serialized = serialize_user(user)
    assert serialized == {"id": "user-1", "name": "Gerente", "email": "gerente@example.com", "role": "INTERNAL_PM", "status": "ACTIVE", "client_id": None}
    assert "password_hash" not in serialized


def test_only_admin_can_manage_users():
    user = User(id="user-1", name="PM", email="pm@example.com", password_hash="unused", role=UserRole.INTERNAL_PM, status=UserStatus.ACTIVE)
    with pytest.raises(HTTPException) as error:
        require_admin(user)
    assert error.value.status_code == 403
