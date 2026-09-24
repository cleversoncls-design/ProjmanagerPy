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


def test_list_users_filters_by_role_and_is_restricted_to_management(client, setup):
    consultant_headers = auth_headers(client, setup["consultant"].email)
    denied = client.get("/users", headers=consultant_headers)
    assert denied.status_code == 403

    all_users = client.get("/users", headers=setup["admin_headers"])
    assert all_users.status_code == 200
    assert setup["pm"].id in {u["id"] for u in all_users.json()}

    only_client_pm = client.get("/users", params={"role": "CLIENT_PM"}, headers=setup["admin_headers"])
    assert only_client_pm.status_code == 200
    assert [u["id"] for u in only_client_pm.json()] == [setup["client_pm_a"].id]


def test_list_resources_filters_by_user_and_allows_consultant(client, setup):
    admin_headers = setup["admin_headers"]
    created = client.post(
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
    scoped = client.get("/resources", params={"user_id": setup["consultant"].id}, headers=consultant_headers)
    assert scoped.status_code == 200
    assert [r["id"] for r in scoped.json()] == [created["id"]]

    external_headers = auth_headers(client, setup["client_pm_a"].email)
    denied = client.get("/resources", headers=external_headers)
    assert denied.status_code == 403


def test_list_calendars(client, setup):
    admin_headers = setup["admin_headers"]
    created = client.post("/calendars", json={"name": "Padrão"}, headers=admin_headers).json()

    response = client.get("/calendars", headers=admin_headers)
    assert response.status_code == 200
    assert created["id"] in {c["id"] for c in response.json()}


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


def test_audit_log_records_actions_and_is_restricted_to_internal_management(client, setup):
    """Regressão/cobertura da auditoria mínima: criar uma tarefa gera uma
    entrada de auditoria, e a listagem só é acessível a ADMIN/INTERNAL_PM."""
    admin_headers = setup["admin_headers"]
    project_id = setup["project_a"].id

    task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Tarefa", "wbs_code": "1"}, headers=admin_headers
    ).json()

    denied = client.get("/audit-log", headers=auth_headers(client, setup["consultant"].email))
    assert denied.status_code == 403

    response = client.get(
        "/audit-log", params={"entity_type": "task", "entity_id": task["id"]}, headers=admin_headers
    )
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert entries[0]["action"] == "CREATE"
    assert entries[0]["entity_type"] == "task"
    assert entries[0]["entity_id"] == task["id"]
    assert entries[0]["user_id"] == setup["admin"].id


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


def test_approving_timesheet_updates_task_actual_hours(client, setup):
    """Regressão: Task.actual_hours nunca era recalculado a partir dos
    timesheets aprovados (ficava sempre em 0)."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]

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
    timesheet = client.post(
        "/timesheets",
        json={"task_id": task["id"], "date": "2026-08-24", "hours_spent": "6"},
        headers=consultant_headers,
    ).json()

    before = client.get(f"/tasks/{task['id']}", headers=admin_headers).json()
    assert float(before["actual_hours"]) == 0.0

    approved = client.patch(
        f"/timesheets/{timesheet['id']}/status", json={"status": "APPROVED"}, headers=admin_headers
    )
    assert approved.status_code == 200
    after_approval = client.get(f"/tasks/{task['id']}", headers=admin_headers).json()
    assert float(after_approval["actual_hours"]) == 6.0

    rejected = client.patch(
        f"/timesheets/{timesheet['id']}/status", json={"status": "REJECTED"}, headers=admin_headers
    )
    assert rejected.status_code == 200
    after_rejection = client.get(f"/tasks/{task['id']}", headers=admin_headers).json()
    assert float(after_rejection["actual_hours"]) == 0.0


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


def test_task_type_defaults_to_consulting_and_accepts_management(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]

    default_task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Padrão", "wbs_code": "1"}, headers=admin_headers
    ).json()
    assert default_task["task_type"] == "CONSULTING"

    management_task = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Gestão", "wbs_code": "2", "task_type": "MANAGEMENT"},
        headers=admin_headers,
    ).json()
    assert management_task["task_type"] == "MANAGEMENT"


def test_project_sold_value_is_computed_from_management_and_consulting(client, setup):
    """Regressão: sold_value deixou de ser um valor digitado direto e passou
    a ser horas×taxa de gestão + horas×taxa de consultoria, calculado no
    backend — o valor de `sold_value` enviado no payload é ignorado."""
    admin_headers = setup["admin_headers"]
    payload = {
        "client_id": setup["client_a"].id,
        "manager_id": setup["pm"].id,
        "code": "PRJ-FIN",
        "name": "Projeto financeiro",
        "management_hours": "10",
        "management_rate": "200",
        "consulting_hours": "5",
        "consulting_rate": "300",
        "sold_value": "999999",
    }
    created = client.post("/projects", json=payload, headers=admin_headers).json()
    assert float(created["sold_value"]) == 3500.0

    updated = client.patch(
        f"/projects/{created['id']}", json={"consulting_rate": "400"}, headers=admin_headers
    ).json()
    assert float(updated["sold_value"]) == 4000.0


def test_external_role_cannot_change_project_financials(client, setup):
    project_id = setup["project_a"].id
    external_headers = auth_headers(client, setup["client_pm_a"].email)
    response = client.patch(f"/projects/{project_id}", json={"management_rate": "999"}, headers=external_headers)
    assert response.status_code == 200

    detail = client.get(f"/projects/{project_id}", headers=setup["admin_headers"]).json()
    assert float(detail["management_rate"]) == 0.0


def test_resource_can_be_linked_to_a_calendar(client, setup):
    admin_headers = setup["admin_headers"]
    calendar = client.post("/calendars", json={"name": "Padrão"}, headers=admin_headers).json()

    resource = client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
            "role_title": "Consultor",
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
            "calendar_id": calendar["id"],
        },
        headers=admin_headers,
    )
    assert resource.status_code == 201
    assert resource.json()["calendar_id"] == calendar["id"]

    other_user = client.post(
        "/users",
        json={"name": "Outro", "email": "outro.consultor@example.com", "password": PASSWORD, "role": "CONSULTANT"},
        headers=admin_headers,
    ).json()
    missing_calendar = client.post(
        "/resources",
        json={
            "user_id": other_user["id"],
            "role_title": "Outro",
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
            "calendar_id": "id-inexistente",
        },
        headers=admin_headers,
    )
    assert missing_calendar.status_code == 404


def test_adhoc_timesheet_without_task_or_project(client, setup):
    """Apontamento avulso (padrão Clockify/Toggl): sem task_id, sem exigir
    TaskAssignment prévio. project_id é opcional para alocar a hora avulsa
    a um projeto sem passar pela EAP."""
    admin_headers = setup["admin_headers"]
    project_id = setup["project_a"].id

    client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
            "role_title": "Consultor",
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
        },
        headers=admin_headers,
    )
    consultant_headers = auth_headers(client, setup["consultant"].email)

    admin_hours = client.post(
        "/timesheets", json={"date": "2026-08-24", "hours_spent": "1"}, headers=consultant_headers
    )
    assert admin_hours.status_code == 201
    assert admin_hours.json()["task_id"] is None
    assert admin_hours.json()["project_id"] is None

    project_hours = client.post(
        "/timesheets",
        json={"project_id": project_id, "date": "2026-08-24", "hours_spent": "2"},
        headers=consultant_headers,
    )
    assert project_hours.status_code == 201
    assert project_hours.json()["project_id"] == project_id

    listed = client.get("/timesheets", params={"project_id": project_id}, headers=admin_headers)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [project_hours.json()["id"]]


def test_task_client_approval_workflow(client, setup):
    """Fluxo de validação de tarefa pelo lado do cliente: quem tem escrita
    (interno ou CLIENT_PM) submete; só o cliente (CLIENT_PM/CLIENT_USER,
    inclusive o último, que no resto da API é somente-leitura) aprova ou
    rejeita — e só enquanto está PENDING."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    client_user_headers = auth_headers(client, setup["client_user_a"].email)

    task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Entrega", "wbs_code": "1"}, headers=admin_headers
    ).json()
    assert task["client_approval_status"] == "NOT_REQUIRED"

    denied_review = client.patch(
        f"/tasks/{task['id']}/client-approval", json={"status": "APPROVED"}, headers=admin_headers
    )
    assert denied_review.status_code == 403

    early_approval = client.patch(
        f"/tasks/{task['id']}/client-approval", json={"status": "APPROVED"}, headers=client_user_headers
    )
    assert early_approval.status_code == 409

    submitted = client.post(f"/tasks/{task['id']}/submit-for-approval", headers=admin_headers)
    assert submitted.status_code == 200
    assert submitted.json()["client_approval_status"] == "PENDING"

    resubmit_while_pending = client.post(f"/tasks/{task['id']}/submit-for-approval", headers=admin_headers)
    assert resubmit_while_pending.status_code == 409

    rejected = client.patch(
        f"/tasks/{task['id']}/client-approval",
        json={"status": "REJECTED", "comment": "Falta anexar evidência"},
        headers=client_user_headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["client_approval_status"] == "REJECTED"

    resubmitted = client.post(f"/tasks/{task['id']}/submit-for-approval", headers=admin_headers)
    assert resubmitted.status_code == 200
    assert resubmitted.json()["client_approval_status"] == "PENDING"

    approved = client.patch(
        f"/tasks/{task['id']}/client-approval", json={"status": "APPROVED"}, headers=client_user_headers
    )
    assert approved.status_code == 200
    assert approved.json()["client_approval_status"] == "APPROVED"


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

    # Criar a dependência já dispara reschedule_cascade sozinha (ver
    # create_dependency em app/routers/tasks.py) — a sucessora não fica mais
    # esperando uma chamada manual a /reschedule para herdar a data certa.
    successor_after_dependency = client.get(f"/tasks/{successor['id']}", headers=admin_headers).json()
    assert successor_after_dependency["planned_start_date"] == "2026-08-25"

    # /tasks/{id}/reschedule continua exposto para forçar o recálculo
    # manualmente (ex.: depois de editar várias tarefas em lote) — chamado
    # de novo aqui, sem nenhuma mudança pendente desde a cascata automática
    # acima, não há mais nada para a sucessora atualizar.
    result = client.post(
        f"/tasks/{predecessor['id']}/reschedule",
        json={"calendar_id": calendar["id"]},
        headers=admin_headers,
    )
    assert result.status_code == 200
    assert result.json() == []


def test_update_task_dates_cascades_to_successor(client, setup):
    """PATCH /tasks/{id} muda a data/duração da própria tarefa; se ela tiver
    sucessoras dependentes, elas precisam se mover junto, sem esperar uma
    chamada manual a /reschedule (mesma razão de create_dependency logo
    acima)."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]

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
            "planned_start_date": "2026-08-25",
            "planned_end_date": "2026-08-25",
        },
        headers=admin_headers,
    ).json()
    dep = client.post(
        "/task-dependencies",
        json={"predecessor_task_id": predecessor["id"], "successor_task_id": successor["id"]},
        headers=admin_headers,
    )
    assert dep.status_code == 201

    # Empurra a predecessora pra uma semana à frente — a sucessora (FS, sem
    # lag) precisa acompanhar, sem precisar de um /reschedule manual depois.
    moved = client.patch(
        f"/tasks/{predecessor['id']}",
        json={"planned_start_date": "2026-08-31", "planned_end_date": "2026-08-31"},
        headers=admin_headers,
    )
    assert moved.status_code == 200

    successor_after_patch = client.get(f"/tasks/{successor['id']}", headers=admin_headers).json()
    assert successor_after_patch["planned_start_date"] == "2026-09-01"


# ---------------------------------------------------------------------------
# Fase 2: relatórios / dashboard
# ---------------------------------------------------------------------------


def test_dashboard_scopes_projects_by_client_and_hides_margin_externally(client, setup):
    """Admin enxerga o portfólio inteiro (os dois projetos do setup); um
    perfil externo só enxerga o(s) projeto(s) do próprio cliente, e sem
    margem na linha de portfólio — mesmo tratamento de dado financeiro do
    resto da API."""
    admin_view = client.get("/dashboard", headers=setup["admin_headers"]).json()
    assert admin_view["projects_total"] == 2
    admin_row = next(row for row in admin_view["portfolio"] if row["id"] == setup["project_a"].id)
    assert admin_row["margin"] is not None

    external_headers = auth_headers(client, setup["client_pm_a"].email)
    external_view = client.get("/dashboard", headers=external_headers).json()
    assert external_view["projects_total"] == 1
    assert external_view["portfolio"][0]["id"] == setup["project_a"].id
    assert external_view["portfolio"][0]["margin"] is None


def test_reports_portfolio_endpoint_scopes_by_client(client, setup):
    external_headers = auth_headers(client, setup["client_pm_a"].email)
    response = client.get("/reports/portfolio", headers=external_headers)
    assert response.status_code == 200
    rows = response.json()
    assert [row["id"] for row in rows] == [setup["project_a"].id]


def test_project_report_includes_burndown_and_hides_financials_externally(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]

    client.patch(f"/projects/{project_id}", json={"start_date": "2026-08-03", "end_date": "2026-08-17"}, headers=admin_headers)
    client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Entrega", "wbs_code": "1", "estimated_hours": "10", "planned_end_date": "2026-08-10"},
        headers=admin_headers,
    )

    internal = client.get(f"/projects/{project_id}/report", headers=admin_headers)
    assert internal.status_code == 200
    internal_body = internal.json()
    assert internal_body["tasks_total"] == 1
    assert internal_body["financials"] is not None
    assert internal_body["financials_by_task_type"] is not None
    assert len(internal_body["burndown"]) >= 2
    assert internal_body["burndown"][0]["date"] == "2026-08-03"
    assert internal_body["burndown"][-1]["date"] == "2026-08-17"

    external_headers = auth_headers(client, setup["client_pm_a"].email)
    external = client.get(f"/projects/{project_id}/report", headers=external_headers)
    assert external.status_code == 200
    external_body = external.json()
    assert external_body["financials"] is None
    assert external_body["financials_by_task_type"] is None
    assert external_body["tasks_total"] == 1


def test_resources_utilization_endpoint_requires_internal_role(client, setup):
    admin_headers = setup["admin_headers"]
    client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
            "role_title": "Consultor",
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
        },
        headers=admin_headers,
    )

    external_headers = auth_headers(client, setup["client_pm_a"].email)
    denied = client.get("/resources/utilization", headers=external_headers)
    assert denied.status_code == 403

    allowed = client.get("/resources/utilization", headers=admin_headers)
    assert allowed.status_code == 200
    row = next(r for r in allowed.json() if r["user_id"] == setup["consultant"].id)
    assert {"capacity_hours", "allocated_hours", "actual_hours", "utilization_percentage"} <= row.keys()


def test_risk_matrix_endpoint_counts_project_risks(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    client.post(
        f"/projects/{project_id}/risks",
        json={"description": "Atraso de fornecedor", "probability": "HIGH", "impact": "HIGH"},
        headers=admin_headers,
    )

    response = client.get(f"/projects/{project_id}/risks/matrix", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["grid"]["HIGH"]["HIGH"] == 1
    assert len(body["high_priority"]) == 1

    external_headers = auth_headers(client, setup["client_pm_a"].email)
    cross_client = client.get(f"/projects/{setup['project_b'].id}/risks/matrix", headers=external_headers)
    assert cross_client.status_code == 403


def test_velocity_endpoint_requires_project_id_for_external_role(client, setup):
    external_headers = auth_headers(client, setup["client_pm_a"].email)
    missing_project = client.get("/reports/velocity", headers=external_headers)
    assert missing_project.status_code == 422

    scoped = client.get("/reports/velocity", params={"project_id": setup["project_a"].id}, headers=external_headers)
    assert scoped.status_code == 200

    portfolio_wide = client.get("/reports/velocity", headers=setup["admin_headers"])
    assert portfolio_wide.status_code == 200


def test_roi_endpoint_is_restricted_to_internal_roles(client, setup):
    external_headers = auth_headers(client, setup["client_pm_a"].email)
    denied = client.get("/reports/roi", headers=external_headers)
    assert denied.status_code == 403

    allowed = client.get("/reports/roi", params={"project_id": setup["project_a"].id}, headers=setup["admin_headers"])
    assert allowed.status_code == 200
    assert allowed.json()[0]["project_id"] == setup["project_a"].id


def test_gantt_endpoint_bundles_tasks_and_dependencies(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    pred = client.post(f"/projects/{project_id}/tasks", json={"name": "A", "wbs_code": "1"}, headers=admin_headers).json()
    succ = client.post(f"/projects/{project_id}/tasks", json={"name": "B", "wbs_code": "2"}, headers=admin_headers).json()
    client.post(
        "/task-dependencies",
        json={"predecessor_task_id": pred["id"], "successor_task_id": succ["id"]},
        headers=admin_headers,
    )

    response = client.get(f"/projects/{project_id}/gantt", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert {t["id"] for t in body["tasks"]} == {pred["id"], succ["id"]}
    assert len(body["dependencies"]) == 1
    assert body["dependencies"][0]["predecessor_task_id"] == pred["id"]

    external_headers = auth_headers(client, setup["client_pm_a"].email)
    cross_client = client.get(f"/projects/{setup['project_b'].id}/gantt", headers=external_headers)
    assert cross_client.status_code == 403


# ---------------------------------------------------------------------------
# Fase 4: motor de agendamento (effort-driven, WBS, mover tarefa, calendário
# de projeto/status date, estatísticas, bloqueio de usuário)
# ---------------------------------------------------------------------------


def test_create_task_defaults_to_one_day_and_effort_driven_duration_sets_work(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]

    # Nem duration_days nem estimated_hours informados -> assume 1 dia (8h,
    # FTE genérica sem recurso alocado ainda).
    default_task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Padrão", "wbs_code": "1"}, headers=admin_headers
    ).json()
    assert float(default_task["duration_days"]) == 1.0
    assert float(default_task["estimated_hours"]) == 8.0

    # Informar duration_days deriva o Trabalho (2 dias * 8h/dia = 16h).
    by_duration = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Por duração", "wbs_code": "2", "duration_days": "2"},
        headers=admin_headers,
    ).json()
    assert float(by_duration["duration_days"]) == 2.0
    assert float(by_duration["estimated_hours"]) == 16.0

    # Informar só estimated_hours deriva a Duração pelo caminho inverso.
    by_hours = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Por trabalho", "wbs_code": "3", "estimated_hours": "20"},
        headers=admin_headers,
    ).json()
    assert float(by_hours["estimated_hours"]) == 20.0
    assert float(by_hours["duration_days"]) == 2.5


def test_update_task_duration_recomputes_work_via_api(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "T", "wbs_code": "1", "duration_days": "1"}, headers=admin_headers
    ).json()
    assert float(task["estimated_hours"]) == 8.0

    updated = client.patch(f"/tasks/{task['id']}", json={"duration_days": "3"}, headers=admin_headers)
    assert updated.status_code == 200
    assert float(updated.json()["estimated_hours"]) == 24.0


def test_recalculate_wbs_endpoint_renumbers_tasks(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    parent = client.post(f"/projects/{project_id}/tasks", json={"name": "Fase", "wbs_code": "9"}, headers=admin_headers).json()
    child = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Atividade", "wbs_code": "9.1", "parent_task_id": parent["id"]},
        headers=admin_headers,
    ).json()

    result = client.post(f"/projects/{project_id}/tasks/recalculate-wbs", headers=admin_headers)
    assert result.status_code == 200
    tasks_by_id = {t["id"]: t for t in result.json()["tasks"]}
    assert tasks_by_id[parent["id"]]["wbs_code"] == "1"
    assert tasks_by_id[child["id"]]["wbs_code"] == "1.1"


def test_move_task_endpoint_reparents(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    parent_a = client.post(f"/projects/{project_id}/tasks", json={"name": "Pai A", "wbs_code": "1"}, headers=admin_headers).json()
    parent_b = client.post(f"/projects/{project_id}/tasks", json={"name": "Pai B", "wbs_code": "2"}, headers=admin_headers).json()
    child = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Filho", "wbs_code": "1.1", "parent_task_id": parent_a["id"]},
        headers=admin_headers,
    ).json()

    moved = client.post(
        f"/tasks/{child['id']}/move", json={"new_parent_id": parent_b["id"]}, headers=admin_headers
    )
    assert moved.status_code == 200
    assert moved.json()["parent_task_id"] == parent_b["id"]


def test_project_reschedule_endpoint_recalculates_all_dependent_tasks(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    pred = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "A", "wbs_code": "1", "planned_start_date": "2026-08-24", "planned_end_date": "2026-08-24"},
        headers=admin_headers,
    ).json()
    succ = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "B", "wbs_code": "2", "planned_start_date": "2026-09-15", "planned_end_date": "2026-09-16"},
        headers=admin_headers,
    ).json()
    client.post(
        "/task-dependencies",
        json={"predecessor_task_id": pred["id"], "successor_task_id": succ["id"]},
        headers=admin_headers,
    )

    # create_dependency já dispara reschedule_cascade sozinha (ver
    # app/routers/tasks.py), então a sucessora já nasce corrigida antes de
    # qualquer chamada a /reschedule.
    succ_after_dependency = client.get(f"/tasks/{succ['id']}", headers=admin_headers).json()
    assert succ_after_dependency["planned_start_date"] == "2026-08-25"

    # "Recalcular tudo" continua disponível para reconciliar o projeto
    # inteiro depois de uma edição em lote — chamado aqui sem nenhuma
    # mudança pendente, não há mais nada para atualizar.
    result = client.post(f"/projects/{project_id}/reschedule", json={}, headers=admin_headers)
    assert result.status_code == 200
    assert result.json() == []


def test_project_schedule_endpoint_returns_status_dots(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    client.patch(f"/projects/{project_id}", json={"status_date": "2026-09-01"}, headers=admin_headers)
    task = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Atrasada", "wbs_code": "1", "planned_end_date": "2026-08-01"},
        headers=admin_headers,
    ).json()
    # Bolinha branca (por iniciar) é a regra pra status NOT_STARTED
    # independente da data; marcar em andamento é o que expõe o atraso.
    client.patch(f"/tasks/{task['id']}", json={"status": "IN_PROGRESS"}, headers=admin_headers)

    result = client.get(f"/projects/{project_id}/schedule", headers=admin_headers)
    assert result.status_code == 200
    body = result.json()
    assert body["status_date"] == "2026-09-01"
    assert body["tasks"][0]["status_dot"] == "red"


def test_project_statistics_endpoint_hides_cost_for_external_role(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    client.post(f"/projects/{project_id}/tasks", json={"name": "T", "wbs_code": "1"}, headers=admin_headers)

    internal = client.get(f"/projects/{project_id}/statistics", headers=admin_headers)
    assert internal.status_code == 200

    external_headers = auth_headers(client, setup["client_pm_a"].email)
    external = client.get(f"/projects/{project_id}/statistics", headers=external_headers)
    assert external.status_code == 200
    assert external.json()["actual"]["cost"] is None


def test_project_calendar_can_be_assigned_and_invalid_id_is_rejected(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    calendar = client.post("/calendars", json={"name": "Padrão"}, headers=admin_headers).json()

    ok = client.patch(f"/projects/{project_id}", json={"calendar_id": calendar["id"]}, headers=admin_headers)
    assert ok.status_code == 200
    assert ok.json()["calendar_id"] == calendar["id"]

    bad = client.patch(f"/projects/{project_id}", json={"calendar_id": "nao-existe"}, headers=admin_headers)
    assert bad.status_code == 404


def test_admin_can_update_user_and_block_login(client, setup, db_session):
    admin_headers = setup["admin_headers"]
    consultant = setup["consultant"]

    update = client.patch(f"/users/{consultant.id}", json={"status": "BLOCKED"}, headers=admin_headers)
    assert update.status_code == 200
    assert update.json()["status"] == "BLOCKED"

    login = client.post("/auth/login", data={"username": consultant.email, "password": PASSWORD})
    assert login.status_code == 401


def test_non_admin_cannot_update_users(client, setup):
    external_headers = auth_headers(client, setup["client_pm_a"].email)
    response = client.patch(f"/users/{setup['consultant'].id}", json={"status": "BLOCKED"}, headers=external_headers)
    assert response.status_code == 403


def test_delete_dependency_removes_predecessor_link(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    pred = client.post(f"/projects/{project_id}/tasks", json={"name": "A", "wbs_code": "1"}, headers=admin_headers).json()
    succ = client.post(f"/projects/{project_id}/tasks", json={"name": "B", "wbs_code": "2"}, headers=admin_headers).json()
    dep = client.post(
        "/task-dependencies",
        json={"predecessor_task_id": pred["id"], "successor_task_id": succ["id"]},
        headers=admin_headers,
    ).json()

    delete = client.delete(f"/task-dependencies/{dep['id']}", headers=admin_headers)
    assert delete.status_code == 204

    remaining = client.get(f"/tasks/{succ['id']}/dependencies", headers=admin_headers)
    assert remaining.json() == []


def test_admin_can_reset_user_password(client, setup):
    admin_headers = setup["admin_headers"]
    consultant = setup["consultant"]

    reset = client.post(
        f"/users/{consultant.id}/reset-password", json={"new_password": "nova-senha-123"}, headers=admin_headers
    )
    assert reset.status_code == 204

    old_login = client.post("/auth/login", data={"username": consultant.email, "password": PASSWORD})
    assert old_login.status_code == 401
    new_login = client.post("/auth/login", data={"username": consultant.email, "password": "nova-senha-123"})
    assert new_login.status_code == 200
