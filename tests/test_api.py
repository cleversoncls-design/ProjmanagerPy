from __future__ import annotations

import pytest

from app.models import ProjectStatus, UserRole
from .conftest import PASSWORD, auth_headers, make_client_row, make_project, make_user


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_success_and_failure(client, db_session):
    make_user(db_session, role=UserRole.ADMIN, email="admin@example.com")
    ok = client.post("/auth/login", data={"username": "admin@example.com", "password": PASSWORD})
    assert ok.status_code == 200
    assert ok.json()["role"] == "ADMIN"

    wrong = client.post("/auth/login", data={"username": "admin@example.com", "password": "senha-errada"})
    assert wrong.status_code == 401


def test_unauthenticated_request_is_rejected(client):
    response = client.get("/projects")
    assert response.status_code == 401


@pytest.fixture()
def setup(client, db_session):
    """Cria um admin, dois clientes, um PM interno e um projeto ativo do
    cliente A — a base compartilhada pelos testes de autorização abaixo."""
    admin = make_user(db_session, role=UserRole.ADMIN, email="admin@example.com")
    admin_headers = auth_headers(client, admin.email)

    client_a = make_client_row(db_session, code="CLI-A")
    client_b = make_client_row(db_session, code="CLI-B")

    pm = make_user(db_session, role=UserRole.INTERNAL_PM, email="pm@example.com")
    consultant = make_user(db_session, role=UserRole.CONSULTANT, email="consultor@example.com")
    client_pm_a = make_user(db_session, role=UserRole.CLIENT_PM, client_id=client_a.id, email="pm.cliente@example.com")
    client_user_a = make_user(db_session, role=UserRole.CLIENT_USER, client_id=client_a.id, email="user.cliente@example.com")

    project_a = make_project(db_session, client_id=client_a.id, manager_id=pm.id, code="PRJ-A")
    project_b = make_project(db_session, client_id=client_b.id, manager_id=pm.id, code="PRJ-B")

    patch = client.patch(f"/projects/{project_a.id}", json={"status": ProjectStatus.ACTIVE.value}, headers=admin_headers)
    assert patch.status_code == 200

    return {
        "admin": admin,
        "admin_headers": admin_headers,
        "client_a": client_a,
        "client_b": client_b,
        "pm": pm,
        "consultant": consultant,
        "client_pm_a": client_pm_a,
        "client_user_a": client_user_a,
        "project_a": project_a,
        "project_b": project_b,
    }


def test_only_admin_can_create_user(client, setup):
    non_admin_headers = auth_headers(client, setup["pm"].email)
    response = client.post(
        "/users",
        json={"name": "Outro", "email": "outro@example.com", "password": PASSWORD, "role": "CONSULTANT"},
        headers=non_admin_headers,
    )
    assert response.status_code == 403

    response = client.post(
        "/users",
        json={"name": "Outro", "email": "outro@example.com", "password": PASSWORD, "role": "CONSULTANT"},
        headers=setup["admin_headers"],
    )
    assert response.status_code == 201


def test_cross_client_access_is_denied(client, setup):
    headers = auth_headers(client, setup["client_pm_a"].email)
    response = client.get(f"/projects/{setup['project_b'].id}", headers=headers)
    assert response.status_code == 403


def test_client_user_is_read_only_but_client_pm_can_write(client, setup):
    """Regressão do bug em que a checagem de escrita nunca disparava: antes
    desta correção, CLIENT_USER também conseguia criar tarefas."""
    project_id = setup["project_a"].id

    client_user_headers = auth_headers(client, setup["client_user_a"].email)
    denied = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Tarefa 1", "wbs_code": "1"},
        headers=client_user_headers,
    )
    assert denied.status_code == 403

    client_pm_headers = auth_headers(client, setup["client_pm_a"].email)
    allowed = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Tarefa 1", "wbs_code": "1"},
        headers=client_pm_headers,
    )
    assert allowed.status_code == 201


def test_duplicate_wbs_code_in_same_project_is_rejected(client, setup):
    project_id = setup["project_a"].id
    payload = {"name": "Tarefa 1", "wbs_code": "1"}
    first = client.post(f"/projects/{project_id}/tasks", json=payload, headers=setup["admin_headers"])
    assert first.status_code == 201
    second = client.post(f"/projects/{project_id}/tasks", json=payload, headers=setup["admin_headers"])
    assert second.status_code == 409


def test_timesheet_requires_assignment_active_project_and_rejects_duplicates(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]

    task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Implantação", "wbs_code": "1"}, headers=admin_headers
    ).json()

    resource = client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
            "role_title": "Consultor",
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
        },
        headers=admin_headers,
    ).json()

    consultant_headers = auth_headers(client, setup["consultant"].email)
    timesheet_payload = {"task_id": task["id"], "date": "2026-08-24", "hours_spent": "4"}

    # Ainda sem alocação (TaskAssignment) -> bloqueado.
    not_assigned = client.post("/timesheets", json=timesheet_payload, headers=consultant_headers)
    assert not_assigned.status_code == 403

    assign = client.post(
        f"/tasks/{task['id']}/assignments",
        json={"resource_id": resource["id"], "allocated_hours": "20"},
        headers=admin_headers,
    )
    assert assign.status_code == 201

    created = client.post("/timesheets", json=timesheet_payload, headers=consultant_headers)
    assert created.status_code == 201

    duplicate = client.post("/timesheets", json=timesheet_payload, headers=consultant_headers)
    assert duplicate.status_code == 409


def test_timesheet_blocked_when_project_not_active(client, setup):
    admin_headers = setup["admin_headers"]
    # project_b ainda está em PLANNING (nunca foi ativado no fixture setup).
    project_id = setup["project_b"].id
    task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Tarefa", "wbs_code": "1"}, headers=admin_headers
    ).json()
    resource = client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
            "role_title": "Consultor",
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
        },
        headers=admin_headers,
    ).json()
    client.post(
        f"/tasks/{task['id']}/assignments",
        json={"resource_id": resource["id"], "allocated_hours": "20"},
        headers=admin_headers,
    )
    consultant_headers = auth_headers(client, setup["consultant"].email)
    response = client.post(
        "/timesheets",
        json={"task_id": task["id"], "date": "2026-08-24", "hours_spent": "4"},
        headers=consultant_headers,
    )
    assert response.status_code == 422


def test_project_detail_hides_financials_for_external_roles(client, setup):
    project_id = setup["project_a"].id
    internal_view = client.get(f"/projects/{project_id}", headers=setup["admin_headers"]).json()
    assert internal_view["financials"] is not None

    external_headers = auth_headers(client, setup["client_pm_a"].email)
    external_view = client.get(f"/projects/{project_id}", headers=external_headers).json()
    assert external_view["financials"] is None
    assert external_view["sold_value"] is None


def test_reschedule_endpoint_moves_successor(client, setup):
    admin_headers = setup["admin_headers"]
    project_id = setup["project_a"].id

    calendar = client.post("/calendars", json={"name": "Padrão"}, headers=admin_headers).json()

    predecessor = client.post(
        f"/projects/{project_id}/tasks",
        json={
            "name": "Predecessora",
            "wbs_code": "1",
            "planned_start_date": "2026-08-24",
            "planned_end_date": "2026-08-24",
        },
        headers=admin_headers,
    ).json()
    successor = client.post(
        f"/projects/{project_id}/tasks",
        json={
            "name": "Sucessora",
            "wbs_code": "2",
            # Datas propositalmente "erradas" para comprovar que o endpoint
            # de fato move a sucessora ao recalcular a partir da predecessora.
            "planned_start_date": "2026-09-15",
            "planned_end_date": "2026-09-16",
        },
        headers=admin_headers,
    ).json()
    dep = client.post(
        "/task-dependencies",
        json={"predecessor_task_id": predecessor["id"], "successor_task_id": successor["id"]},
        headers=admin_headers,
    )
    assert dep.status_code == 201

    result = client.post(
        f"/tasks/{predecessor['id']}/reschedule",
        json={"calendar_id": calendar["id"]},
        headers=admin_headers,
    )
    assert result.status_code == 200
    updated = result.json()
    assert len(updated) == 1
    assert updated[0]["id"] == successor["id"]
    assert updated[0]["planned_start_date"] == "2026-08-25"
