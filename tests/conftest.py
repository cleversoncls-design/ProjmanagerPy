from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")

import pytest
from fastapi.testclient import TestClient

from app.database import get_session_factory, init_db, reset_database_state
from app.main import app
from app.models import Client, Project, User, UserRole, UserStatus
from app.security import hash_password


@pytest.fixture()
def db_session():
    """Cada teste ganha um SQLite em memória isolado (poolclass=StaticPool)."""
    reset_database_state()
    init_db()
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
        reset_database_state()


@pytest.fixture()
def client(db_session):
    with TestClient(app) as test_client:
        yield test_client


PASSWORD = "senha-forte-123"


def make_user(db_session, *, role: UserRole, client_id: str | None = None, email: str | None = None) -> User:
    user = User(
        name=role.value.title(),
        email=email or f"{role.value.lower()}@example.com",
        password_hash=hash_password(PASSWORD),
        role=role,
        status=UserStatus.ACTIVE,
        client_id=client_id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def make_client_row(db_session, *, code: str = "CLI-1") -> Client:
    client_row = Client(code=code, legal_name=f"Cliente {code}")
    db_session.add(client_row)
    db_session.commit()
    db_session.refresh(client_row)
    return client_row


def make_project(db_session, *, client_id: str, manager_id: str, code: str = "PRJ-1") -> Project:
    project = Project(client_id=client_id, manager_id=manager_id, code=code, name=f"Projeto {code}")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def token_for(client, email: str) -> str:
    response = client.post("/auth/login", data={"username": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(client, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for(client, email)}"}
