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
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    db = testing_session()
    admin = User(id="admin-calendar", name="Admin", email="admin-calendar@example.com", password_hash=hash_password("SenhaSegura26"), role=UserRole.ADMIN, status=UserStatus.ACTIVE)
    consultant = User(id="consultant-calendar", name="Consultor", email="consultant-calendar@example.com", password_hash=hash_password("SenhaSegura26"), role=UserRole.CONSULTANT, status=UserStatus.ACTIVE)
    client_record = Client(id="client-calendar", code="CLI-CAL", legal_name="Cliente Calendário")
    external = User(id="external-calendar", name="Cliente externo", email="external-calendar@example.com", password_hash=hash_password("SenhaSegura26"), role=UserRole.CLIENT_USER, status=UserStatus.ACTIVE, client_id=client_record.id)
    db.add_all([admin, consultant, client_record, external])
    db.commit()

    def override_get_db():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    main.app.dependency_overrides[main.get_db] = override_get_db
    headers = {"Authorization": f"Bearer {create_access_token(admin)}"}
    external_headers = {"Authorization": f"Bearer {create_access_token(external)}"}
    with TestClient(main.app) as client_instance:
        yield client_instance, headers, external_headers, consultant.id
    main.app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def test_internal_user_can_manage_calendar_holiday_and_resource(api_client):
    client, headers, _, consultant_id = api_client
    calendar_response = client.post("/calendars", headers=headers, json={"name": "Jornada reduzida", "working_days": [0, 1, 2, 3]})
    assert calendar_response.status_code == 201
    calendar = calendar_response.json()
    assert calendar["working_days"] == [0, 1, 2, 3]

    holiday_response = client.post(f"/calendars/{calendar['id']}/holidays", headers=headers, json={"date": "2026-08-05", "description": "Feriado local"})
    assert holiday_response.status_code == 201
    assert holiday_response.json()["description"] == "Feriado local"

    duplicate = client.post(f"/calendars/{calendar['id']}/holidays", headers=headers, json={"date": "2026-08-05", "description": "Duplicado"})
    assert duplicate.status_code == 409

    resource_response = client.post("/resources", headers=headers, json={"user_id": consultant_id, "calendar_id": calendar["id"], "role_title": "Consultor funcional", "internal_cost_per_hour": 100, "billing_rate_per_hour": 220, "daily_capacity_hours": 6})
    assert resource_response.status_code == 201
    resource = resource_response.json()
    assert resource["calendar_id"] == calendar["id"]
    assert resource["calendar_name"] == "Jornada reduzida"

    availability = client.get(f"/resources/{resource['id']}/availability?start_date=2026-08-03&end_date=2026-08-09", headers=headers)
    assert availability.status_code == 200
    assert availability.json()["working_dates"] == ["2026-08-03", "2026-08-04", "2026-08-06"]
    assert availability.json()["working_days_count"] == 3
    assert availability.json()["capacity_hours"] == 18

    project = client.post("/projects", headers=headers, json={"client_id": "client-calendar", "manager_id": "admin-calendar", "code": "PRJ-CAL", "name": "Projeto calendário", "status": "PLANNING", "sold_value": 0}).json()
    predecessor = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Predecessora", "wbs_code": "1.1", "planned_start_date": "2026-08-03", "planned_end_date": "2026-08-04"}).json()
    successor = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Sucessora", "wbs_code": "1.2", "planned_start_date": "2026-08-03", "planned_end_date": "2026-08-04"}).json()
    assigned = client.post(f"/tasks/{predecessor['id']}/assignments", headers=headers, json={"resource_id": resource["id"], "allocated_hours": 12})
    assert assigned.status_code == 201
    dependency = client.post(f"/tasks/{predecessor['id']}/dependencies", headers=headers, json={"successor_task_id": successor["id"], "dependency_type": "FS", "lag_days": 0})
    assert dependency.status_code == 201

    moved = client.patch(f"/tasks/{predecessor['id']}", headers=headers, json={"estimated_hours": 24})
    assert moved.status_code == 200
    assert moved.json()["cascaded_task_ids"] == [successor["id"]]
    tasks_after = client.get(f"/projects/{project['id']}/tasks", headers=headers).json()
    successor_after = next(row for row in tasks_after if row["id"] == successor["id"])
    assert successor_after["planned_start_date"] == "2026-08-11"
    assert successor_after["planned_end_date"] == "2026-08-11"


def test_external_user_cannot_read_or_manage_calendar_resources(api_client):
    client, _, external_headers, _ = api_client
    assert client.get("/calendars", headers=external_headers).status_code == 403
    assert client.post("/calendars", headers=external_headers, json={"name": "Calendário indevido", "working_days": [0, 1, 2, 3, 4]}).status_code == 403
    assert client.get("/resources", headers=external_headers).status_code == 403


def test_advanced_task_contract_generates_wbs_and_uses_resource_calendar(api_client):
    client, headers, _, consultant_id = api_client
    calendar = client.post("/calendars", headers=headers, json={"name": "Calendário EAP", "working_days": [0, 1, 2, 3, 4]}).json()
    client.post(f"/calendars/{calendar['id']}/holidays", headers=headers, json={"date": "2026-08-05", "description": "Feriado EAP"})
    resource = client.post("/resources", headers=headers, json={"user_id": consultant_id, "calendar_id": calendar["id"], "role_title": "Consultor", "internal_cost_per_hour": 100, "billing_rate_per_hour": 200, "daily_capacity_hours": 8}).json()
    project = client.post("/projects", headers=headers, json={"client_id": "client-calendar", "manager_id": "admin-calendar", "code": "PRJ-EAP", "name": "Projeto EAP", "status": "PLANNING", "sold_value": 10000}).json()

    parent = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Funcionalidade", "description": "Entrega pai", "wbs_code": "99", "estimated_hours": 24, "duration_days": 3, "priority": "HIGH", "task_type": "IMPLEMENTATION", "planned_start_date": "2026-08-03", "observation": "Marco principal"})
    assert parent.status_code == 201
    parent_data = parent.json()
    assert parent_data["wbs_code"] == "1"
    assert parent_data["planned_end_date"] == "2026-08-05"
    assert parent_data["priority"] == "HIGH"

    child = client.post("/tasks", headers=headers, json={"project_id": project["id"], "parent_task_id": parent_data["id"], "name": "Carga de dados", "wbs_code": "1.99", "estimated_hours": 16, "duration_days": 2, "task_type": "DEVELOPMENT", "planned_start_date": "2026-08-03"})
    assert child.status_code == 201
    child_data = child.json()
    assert child_data["wbs_code"] == "1.1"
    assert child_data["parent_task_id"] == parent_data["id"]
    parent_after_child = next(row for row in client.get(f"/projects/{project['id']}/tasks", headers=headers).json() if row["id"] == parent_data["id"])
    assert parent_after_child["estimated_hours"] == 16
    assert parent_after_child["duration_days"] == 2
    assert parent_after_child["planned_start_date"] == "2026-08-03"
    assert parent_after_child["planned_end_date"] == "2026-08-04"

    assignment = client.post(f"/tasks/{child_data['id']}/assignments", headers=headers, json={"resource_id": resource["id"], "allocated_hours": 16})
    assert assignment.status_code == 201
    child_after_assignment = client.get(f"/projects/{project['id']}/tasks", headers=headers).json()
    child_data = next(row for row in child_after_assignment if row["id"] == child_data["id"])
    assert child_data["planned_end_date"] == "2026-08-04"
    assert child_data["assignments"][0]["resource_id"] == resource["id"]
    assert child_data["spi"] == 0
    assert child_data["cpi"] == 1

    parent_assignment = client.post(f"/tasks/{parent_data['id']}/assignments", headers=headers, json={"resource_id": resource["id"], "allocated_hours": 24})
    assert parent_assignment.status_code == 201
    parent_after_assignment = next(row for row in client.get(f"/projects/{project['id']}/tasks", headers=headers).json() if row["id"] == parent_data["id"])
    assert parent_after_assignment["estimated_hours"] == 16
    assert parent_after_assignment["duration_days"] == 2
    assert parent_after_assignment["planned_end_date"] == "2026-08-04"

    dependency = client.post(f"/tasks/{parent_data['id']}/dependencies", headers=headers, json={"successor_task_id": child_data["id"], "dependency_type": "FS", "lag_days": 0})
    assert dependency.status_code == 201
    assert child_data["id"] in dependency.json()["cascaded_task_ids"]

    refreshed = client.get(f"/projects/{project['id']}/tasks", headers=headers).json()
    refreshed_child = next(row for row in refreshed if row["id"] == child_data["id"])
    assert refreshed_child["planned_start_date"] == "2026-08-06"
    assert refreshed_child["planned_end_date"] == "2026-08-07"


def test_task_duration_rounds_up_by_daily_capacity(api_client):
    client, headers, _, _ = api_client
    project = client.post("/projects", headers=headers, json={"client_id": "client-calendar", "manager_id": "admin-calendar", "code": "PRJ-HRS", "name": "Projeto horas", "status": "PLANNING"}).json()
    one_hour = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Uma hora", "estimated_hours": 1, "planned_start_date": "2026-08-03"})
    nine_hours = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Nove horas", "estimated_hours": 9, "planned_start_date": "2026-08-03"})
    assert one_hour.status_code == 201
    assert nine_hours.status_code == 201
    assert one_hour.json()["duration_days"] == 1
    assert one_hour.json()["planned_end_date"] == "2026-08-03"
    assert nine_hours.json()["duration_days"] == 2
    assert nine_hours.json()["planned_end_date"] == "2026-08-04"


def test_internal_can_list_and_allocate_client_user_as_resource(api_client):
    client, headers, external_headers, _ = api_client
    candidates = client.get("/users/resource-candidates", headers=headers)
    assert candidates.status_code == 200
    external = next(row for row in candidates.json() if row["id"] == "external-calendar")
    assert external["client_id"] == "client-calendar"

    calendar = client.post("/calendars", headers=headers, json={"name": "Jornada cliente", "working_days": [0, 1, 2, 3, 4]}).json()
    resource = client.post("/resources", headers=headers, json={"user_id": external["id"], "calendar_id": calendar["id"], "role_title": "Usuário-chave", "internal_cost_per_hour": 0, "billing_rate_per_hour": 0, "daily_capacity_hours": 4})
    assert resource.status_code == 201
    assert resource.json()["user_id"] == external["id"]
    assert client.get("/users/resource-candidates", headers=external_headers).status_code == 403


def test_project_currency_is_persisted_and_limited_to_usd_or_pyg(api_client):
    client, headers, _, _ = api_client
    created = client.post("/projects", headers=headers, json={"client_id": "client-calendar", "manager_id": "admin-calendar", "code": "PRJ-CUR", "name": "Projeto em Guarani", "currency": "PYG", "sold_value": 1250000})
    assert created.status_code == 201
    project = created.json()
    assert project["currency"] == "PYG"
    assert project["sold_value"] == 1250000

    read_back = client.get(f"/projects/{project['id']}", headers=headers)
    assert read_back.status_code == 200
    assert read_back.json()["currency"] == "PYG"

    updated = client.patch(f"/projects/{project['id']}", headers=headers, json={"currency": "USD"})
    assert updated.status_code == 200
    assert updated.json()["currency"] == "USD"

    invalid = client.patch(f"/projects/{project['id']}", headers=headers, json={"currency": "BRL"})
    assert invalid.status_code == 422


def test_parent_rolls_up_hours_dates_and_wbs_after_move(api_client):
    client, headers, _, _ = api_client
    project = client.post("/projects", headers=headers, json={"client_id": "client-calendar", "manager_id": "admin-calendar", "code": "PRJ-ROLL", "name": "Projeto consolidação", "status": "PLANNING"}).json()
    first_root = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Primeira frente", "wbs_code": "77", "estimated_hours": 1, "planned_start_date": "2026-08-03"}).json()
    second_root = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Segunda frente", "wbs_code": "88", "estimated_hours": 1, "planned_start_date": "2026-08-10"}).json()
    first_child = client.post("/tasks", headers=headers, json={"project_id": project["id"], "parent_task_id": first_root["id"], "name": "Atividade A", "estimated_hours": 10, "planned_start_date": "2026-08-03", "planned_end_date": "2026-08-04"}).json()
    second_child = client.post("/tasks", headers=headers, json={"project_id": project["id"], "parent_task_id": first_root["id"], "name": "Atividade B", "estimated_hours": 6, "planned_start_date": "2026-08-06", "planned_end_date": "2026-08-07"}).json()

    tasks = client.get(f"/projects/{project['id']}/tasks", headers=headers).json()
    parent = next(row for row in tasks if row["id"] == first_root["id"])
    assert [row["wbs_code"] for row in sorted(tasks, key=lambda row: row["wbs_code"])] == ["1", "1.1", "1.2", "2"]
    assert parent["estimated_hours"] == 16
    assert parent["planned_start_date"] == "2026-08-03"
    assert parent["planned_end_date"] == "2026-08-06"
    assert parent["duration_days"] == 2

    moved = client.patch(f"/tasks/{second_child['id']}", headers=headers, json={"parent_task_id": second_root["id"], "wbs_code": "99"})
    assert moved.status_code == 200
    assert moved.json()["wbs_code"] == "2.1"

    tasks_after_move = client.get(f"/projects/{project['id']}/tasks", headers=headers).json()
    first_root_after = next(row for row in tasks_after_move if row["id"] == first_root["id"])
    second_root_after = next(row for row in tasks_after_move if row["id"] == second_root["id"])
    assert first_root_after["estimated_hours"] == 10
    assert first_root_after["planned_start_date"] == "2026-08-03"
    assert first_root_after["planned_end_date"] == "2026-08-04"
    assert second_root_after["estimated_hours"] == 6
    assert second_root_after["planned_start_date"] == "2026-08-06"
    assert second_root_after["planned_end_date"] == "2026-08-06"
    assert second_root_after["duration_days"] == 1

    updated_leaf = client.patch(f"/tasks/{second_child['id']}", headers=headers, json={"estimated_hours": 8})
    assert updated_leaf.status_code == 200
    refreshed_second_root = next(row for row in client.get(f"/projects/{project['id']}/tasks", headers=headers).json() if row["id"] == second_root["id"])
    assert refreshed_second_root["estimated_hours"] == 8


def test_internal_can_edit_task_hours_resources_and_predecessor(api_client):
    client, headers, _, consultant_id = api_client
    project = client.post("/projects", headers=headers, json={"client_id": "client-calendar", "manager_id": "admin-calendar", "code": "PRJ-EDIT", "name": "Projeto edição", "status": "PLANNING"}).json()
    resource = client.post("/resources", headers=headers, json={"user_id": consultant_id, "role_title": "Consultor", "internal_cost_per_hour": 100, "billing_rate_per_hour": 200, "daily_capacity_hours": 8}).json()
    predecessor = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Predecessora", "estimated_hours": 8, "planned_start_date": "2026-08-03"}).json()
    task = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Tarefa editável", "estimated_hours": 1, "planned_start_date": "2026-08-03"}).json()

    assignment = client.post(f"/tasks/{task['id']}/assignments", headers=headers, json={"resource_id": resource["id"], "allocated_hours": 4})
    assert assignment.status_code == 201
    assignment_id = assignment.json()["id"]
    edited_assignment = client.patch(f"/tasks/{task['id']}/assignments/{assignment_id}", headers=headers, json={"allocated_hours": 9})
    assert edited_assignment.status_code == 200
    assert edited_assignment.json()["allocated_hours"] == 9

    edited_task = client.patch(f"/tasks/{task['id']}", headers=headers, json={"estimated_hours": 9, "observation": None})
    assert edited_task.status_code == 200
    assert edited_task.json()["duration_days"] == 2
    assert edited_task.json()["planned_end_date"] == "2026-08-04"
    assert edited_task.json()["observation"] is None

    dependency = client.post(f"/tasks/{predecessor['id']}/dependencies", headers=headers, json={"successor_task_id": task["id"], "dependency_type": "FS", "lag_days": 0})
    assert dependency.status_code == 201
    dependency_id = dependency.json()["id"]
    task_after_dependency = client.get(f"/projects/{project['id']}/tasks", headers=headers).json()
    editable_after_dependency = next(row for row in task_after_dependency if row["id"] == task["id"])
    assert editable_after_dependency["predecessors"][0]["id"] == dependency_id

    assert client.delete(f"/tasks/{predecessor['id']}/dependencies/{dependency_id}", headers=headers).status_code == 204
    assert client.delete(f"/tasks/{task['id']}/assignments/{assignment_id}", headers=headers).status_code == 204


def test_task_creation_calculates_minimum_duration_and_predecessor_dates(api_client):
    client, headers, _, _ = api_client
    project = client.post("/projects", headers=headers, json={"client_id": "client-calendar", "manager_id": "admin-calendar", "code": "PRJ-SCH", "name": "Projeto agenda", "status": "PLANNING"}).json()
    predecessor = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Predecessora", "estimated_hours": 8, "planned_start_date": "2026-08-03"}).json()

    one_hour = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Uma hora", "estimated_hours": 1})
    assert one_hour.status_code == 201
    assert one_hour.json()["duration_days"] == 1

    successor = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Sucessora", "estimated_hours": 9, "planned_start_date": "2026-08-03", "predecessor_task_id": predecessor["id"], "dependency_type": "FS", "lag_days": 0})
    assert successor.status_code == 201
    successor_data = successor.json()
    assert successor_data["duration_days"] == 2
    assert successor_data["planned_start_date"] == "2026-08-04"
    assert successor_data["planned_end_date"] == "2026-08-05"
    assert successor_data["predecessors"][0]["task_id"] == predecessor["id"]
    assert successor_data["predecessors"][0]["dependency_type"] == "FS"


def test_patch_predecessor_recalculates_start_and_delete_is_protected(api_client):
    client, headers, _, _ = api_client
    project = client.post("/projects", headers=headers, json={"client_id": "client-calendar", "manager_id": "admin-calendar", "code": "PRJ-DEP", "name": "Projeto dependências", "status": "PLANNING"}).json()
    resource = client.post("/resources", headers=headers, json={"user_id": "admin-calendar", "role_title": "Administrador", "internal_cost_per_hour": 100, "billing_rate_per_hour": 200, "daily_capacity_hours": 8}).json()
    predecessor = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Predecessora", "estimated_hours": 8, "planned_start_date": "2026-08-03"}).json()
    successor = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Sucessora", "estimated_hours": 1, "planned_start_date": "2026-08-03"}).json()

    linked = client.patch(f"/tasks/{successor['id']}", headers=headers, json={"predecessor_task_id": predecessor["id"], "dependency_type": "FS", "lag_days": 0})
    assert linked.status_code == 200
    assert linked.json()["planned_start_date"] == "2026-08-04"
    assert linked.json()["planned_end_date"] == "2026-08-04"
    assert linked.json()["predecessors"][0]["task_id"] == predecessor["id"]

    deletable = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Excluir sem apontamento", "estimated_hours": 1, "planned_start_date": "2026-08-03"}).json()
    assert deletable["timesheet_count"] == 0
    assert client.delete(f"/tasks/{deletable['id']}", headers=headers).status_code == 204

    with_timesheet = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Com apontamento", "estimated_hours": 1, "planned_start_date": "2026-08-03"}).json()
    assert client.post(f"/tasks/{with_timesheet['id']}/assignments", headers=headers, json={"resource_id": resource["id"], "allocated_hours": 1}).status_code == 201
    assert client.post("/timesheets", headers=headers, json={"task_id": with_timesheet["id"], "date": "2026-08-03", "hours_spent": 1, "description": "Apontamento de teste"}).status_code == 201
    assert client.delete(f"/tasks/{with_timesheet['id']}", headers=headers).status_code == 409


def test_patch_predecessor_can_be_removed_and_task_response_exposes_timesheet_count(api_client):
    client, headers, _, _ = api_client
    project = client.post("/projects", headers=headers, json={"client_id": "client-calendar", "manager_id": "admin-calendar", "code": "PRJ-DEP2", "name": "Projeto remover dependência", "status": "PLANNING"}).json()
    predecessor = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Predecessora", "estimated_hours": 8, "planned_start_date": "2026-08-03"}).json()
    successor = client.post("/tasks", headers=headers, json={"project_id": project["id"], "name": "Sucessora", "estimated_hours": 1, "planned_start_date": "2026-08-03", "predecessor_task_id": predecessor["id"]}).json()
    assert successor["planned_start_date"] == "2026-08-04"
    removed = client.patch(f"/tasks/{successor['id']}", headers=headers, json={"predecessor_task_id": None, "dependency_type": None, "lag_days": None})
    assert removed.status_code == 200
    assert removed.json()["predecessors"] == []
    assert removed.json()["timesheet_count"] == 0
