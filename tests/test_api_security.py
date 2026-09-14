from app.main import create_access_token, decode_access_token
from app.models import User, UserRole


def test_jwt_round_trip_preserves_scope():
    user = User(id="user-1", name="PM", email="pm@example.com", password_hash="unused", role=UserRole.CLIENT_PM, client_id="client-1")
    token = create_access_token(user)
    claims = decode_access_token(token)
    assert claims["sub"] == "user-1"
    assert claims["role"] == "CLIENT_PM"
    assert claims["client_id"] == "client-1"


def test_jwt_rejects_tampering():
    user = User(id="user-1", name="PM", email="pm@example.com", password_hash="unused", role=UserRole.INTERNAL_PM)
    token = create_access_token(user)
    header, payload, _ = token.split(".")
    tampered = f"{header}.{payload}.invalid"
    try:
        decode_access_token(tampered)
    except Exception as error:
        assert getattr(error, "status_code", None) == 401
    else:
        raise AssertionError("token tampered deveria ser rejeitado")


def test_external_user_cannot_access_another_client_project():
    from fastapi import HTTPException
    from app.main import require_project_access
    from app.models import Project, ProjectStatus

    user = User(id="user-1", name="Cliente", email="client@example.com", password_hash="unused", role=UserRole.CLIENT_USER, client_id="client-1")
    project = Project(id="project-1", client_id="client-2", manager_id="manager-1", code="PRJ-1", name="Outro cliente", status=ProjectStatus.ACTIVE)
    try:
        require_project_access(project, user)
    except HTTPException as error:
        assert error.status_code == 403
    else:
        raise AssertionError("acesso cross-client deveria ser bloqueado")
