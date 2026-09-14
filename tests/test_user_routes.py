import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.main import create_access_token, hash_password
from app.models import Base, Client, User, UserRole, UserStatus


@pytest.fixture()
def api_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    db = TestingSession()
    admin = User(id="admin-1", name="Admin", email="admin@example.com", password_hash=hash_password("SenhaSegura26"), role=UserRole.ADMIN, status=UserStatus.ACTIVE)
    client = Client(id="client-1", code="CLI-001", legal_name="Empresa Teste", trade_name="Empresa")
    external = User(id="external-1", name="Cliente", email="cliente@example.com", password_hash=hash_password("SenhaSegura26"), role=UserRole.CLIENT_USER, status=UserStatus.ACTIVE, client_id=client.id)
    db.add_all([admin, client, external])
    db.commit()

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    main.app.dependency_overrides[main.get_db] = override_get_db
    headers = {"Authorization": f"Bearer {create_access_token(admin)}"}
    external_headers = {"Authorization": f"Bearer {create_access_token(external)}"}
    with TestClient(main.app) as client_instance:
        yield client_instance, headers, external_headers
    main.app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def test_admin_can_create_manager_and_use_it_on_project(api_client):
    client, headers, _ = api_client
    response = client.post("/users", headers=headers, json={"name": "Gerente Real", "email": "gerente@example.com", "password": "SenhaSegura26", "role": "INTERNAL_PM", "status": "ACTIVE"})
    assert response.status_code == 201
    manager = response.json()
    assert manager["role"] == "INTERNAL_PM"
    assert "password_hash" not in manager

    managers = client.get("/users/managers", headers=headers)
    assert managers.status_code == 200
    assert any(row["id"] == manager["id"] for row in managers.json())

    project = client.post("/projects", headers=headers, json={"client_id": "client-1", "manager_id": manager["id"], "code": "PRJ-001", "name": "Projeto com gerente", "status": "PLANNING", "sold_value": 0})
    assert project.status_code == 201
    assert project.json()["manager_id"] == manager["id"]


def test_admin_can_change_project_manager_and_reject_invalid_manager(api_client):
    client, headers, external_headers = api_client
    first = client.post("/users", headers=headers, json={"name": "Gerente Um", "email": "gerente1@example.com", "password": "SenhaSegura26", "role": "INTERNAL_PM", "status": "ACTIVE"}).json()
    second = client.post("/users", headers=headers, json={"name": "Gerente Dois", "email": "gerente2@example.com", "password": "SenhaSegura26", "role": "INTERNAL_PM", "status": "ACTIVE"}).json()
    project = client.post("/projects", headers=headers, json={"client_id": "client-1", "manager_id": first["id"], "code": "PRJ-003", "name": "Projeto para troca", "status": "PLANNING", "sold_value": 0})
    assert project.status_code == 201

    changed = client.patch(f"/projects/{project.json()['id']}", headers=headers, json={"manager_id": second["id"]})
    assert changed.status_code == 200
    assert changed.json()["manager_id"] == second["id"]
    assert changed.json()["manager_name"] == "Gerente Dois"

    inactive = client.post("/users", headers=headers, json={"name": "Gerente Bloqueado", "email": "gerente3@example.com", "password": "SenhaSegura26", "role": "INTERNAL_PM", "status": "INACTIVE"}).json()
    rejected = client.patch(f"/projects/{project.json()['id']}", headers=headers, json={"manager_id": inactive["id"]})
    assert rejected.status_code == 422
    assert "ativo" in rejected.json()["detail"].lower()

    forbidden = client.patch(f"/projects/{project.json()['id']}", headers=external_headers, json={"manager_id": second["id"]})
    assert forbidden.status_code == 403


def test_external_profile_cannot_manage_users_or_managers(api_client):
    client, _, external_headers = api_client
    assert client.get("/users", headers=external_headers).status_code == 403
    assert client.get("/users/managers", headers=external_headers).status_code == 403


def test_external_user_requires_client_scope(api_client):
    client, headers, _ = api_client
    response = client.post("/users", headers=headers, json={"name": "Perfil externo", "email": "novo-cliente@example.com", "password": "SenhaSegura26", "role": "CLIENT_USER", "status": "ACTIVE"})
    assert response.status_code == 422
    assert "cliente" in response.json()["detail"].lower()


def test_inactive_user_cannot_be_project_manager(api_client):
    client, headers, _ = api_client
    response = client.post("/users", headers=headers, json={"name": "Gerente Inativo", "email": "inativo@example.com", "password": "SenhaSegura26", "role": "INTERNAL_PM", "status": "INACTIVE"})
    assert response.status_code == 201
    project = client.post("/projects", headers=headers, json={"client_id": "client-1", "manager_id": response.json()["id"], "code": "PRJ-002", "name": "Projeto bloqueado", "status": "PLANNING", "sold_value": 0})
    assert project.status_code == 422
    assert "ativo" in project.json()["detail"].lower()
