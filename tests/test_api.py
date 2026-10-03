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


def test_only_admin_can_create_client(client, setup):
    """Revisão de acessos do usuário: "Administrar clientes" ficou só com o
    Administrador — Gerente de Projetos perdeu esse item (continua
    enxergando a lista via GET /clients, que ele ainda precisa pra montar o
    dropdown de Cliente ao criar/editar projeto)."""
    pm_headers = auth_headers(client, setup["pm"].email)
    denied = client.post("/clients", json={"code": "CLI-NEW", "legal_name": "Novo Cliente"}, headers=pm_headers)
    assert denied.status_code == 403

    still_lists = client.get("/clients", headers=pm_headers)
    assert still_lists.status_code == 200

    allowed = client.post("/clients", json={"code": "CLI-NEW", "legal_name": "Novo Cliente"}, headers=setup["admin_headers"])
    assert allowed.status_code == 201


def test_only_admin_can_update_client(client, setup):
    """Pedido do usuário ("mais melhorias"): "O cadastro de clientes não
    permite modificar dados" — adicionado PATCH /clients/{id}, com a mesma
    restrição de create_client (só Administrador)."""
    client_id = setup["client_a"].id
    pm_headers = auth_headers(client, setup["pm"].email)
    admin_headers = setup["admin_headers"]

    denied = client.patch(f"/clients/{client_id}", json={"legal_name": "Tentativa PM"}, headers=pm_headers)
    assert denied.status_code == 403

    updated = client.patch(
        f"/clients/{client_id}",
        json={
            "legal_name": "Cliente A Atualizado",
            "address": "Av. Principal 123",
            "zip_code": "7000",
            "primary_contact_phone": "+595 981 000000",
        },
        headers=admin_headers,
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["legal_name"] == "Cliente A Atualizado"
    # Campos que ClientRead não expunha antes (pedido "mais melhorias") —
    # precisam ir e voltar certinho pelo PATCH/GET sem precisar reenviar o
    # resto do cadastro (exclude_unset no TaskUpdate/ClientUpdate).
    assert body["address"] == "Av. Principal 123"
    assert body["zip_code"] == "7000"
    assert body["primary_contact_phone"] == "+595 981 000000"

    fetched = client.get(f"/clients/{client_id}", headers=admin_headers).json()
    assert fetched["address"] == "Av. Principal 123"
    assert fetched["code"] == "CLI-A"  # não mandado no PATCH — permanece intacto


def test_update_client_rejects_duplicate_code(client, setup):
    """Trocar o código de um cliente pro código já usado por outro cliente
    não pode ser permitido (mesma regra de unicidade do create_client)."""
    admin_headers = setup["admin_headers"]
    conflict = client.patch(f"/clients/{setup['client_a'].id}", json={"code": "CLI-B"}, headers=admin_headers)
    assert conflict.status_code == 409


def test_consultant_cannot_administer_project_or_tasks(client, setup):
    """Revisão de acessos do usuário: "Administrar projetos"/"Administrar
    tarefas" ficaram só com Admin/Gerente de Projetos — Consultor perdeu a
    tela de Projetos inteira, então também não pode mais escrever ali via
    API direta (allow_consultant_write=False em require_project_access).
    PM continua podendo — só o Consultor é restringido."""
    consultant_headers = auth_headers(client, setup["consultant"].email)
    pm_headers = auth_headers(client, setup["pm"].email)
    project_id = setup["project_a"].id

    denied_project = client.patch(f"/projects/{project_id}", json={"name": "Novo nome"}, headers=consultant_headers)
    assert denied_project.status_code == 403

    task_payload = {"name": "Tarefa", "wbs_code": "1", "duration_days": "1"}
    denied_task = client.post(f"/projects/{project_id}/tasks", json=task_payload, headers=consultant_headers)
    assert denied_task.status_code == 403

    allowed_task = client.post(f"/projects/{project_id}/tasks", json=task_payload, headers=pm_headers)
    assert allowed_task.status_code == 201


def test_dashboard_restricted_to_admin_like_roles(client, setup):
    """Reorganização de menus (pedido do usuário): Dashboard ficou só com
    ADMIN_LIKE_ROLES. Gerente de Projetos e Consultor já não tinham esse
    item; PM do Cliente e Usuário-chave perderam o que tinham (confirmado
    com o usuário: Painel saiu do menu do PM do Cliente, e Usuário-chave
    ficou sem nenhum acesso por enquanto) — restrito aqui também na API, não
    só escondido na UI. O mesmo dado (escopado por cliente, sem margem)
    continua disponível pro perfil externo via GET /reports/portfolio, que
    não tem essa restrição (ver test_reports_portfolio_endpoint_scopes_by_client)."""
    denied_pm = client.get("/dashboard", headers=auth_headers(client, setup["pm"].email))
    assert denied_pm.status_code == 403

    denied_consultant = client.get("/dashboard", headers=auth_headers(client, setup["consultant"].email))
    assert denied_consultant.status_code == 403

    denied_client_pm = client.get("/dashboard", headers=auth_headers(client, setup["client_pm_a"].email))
    assert denied_client_pm.status_code == 403

    denied_client_user = client.get("/dashboard", headers=auth_headers(client, setup["client_user_a"].email))
    assert denied_client_user.status_code == 403

    allowed_admin = client.get("/dashboard", headers=setup["admin_headers"])
    assert allowed_admin.status_code == 200


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


def test_service_manager_and_general_director_mirror_admin_except_user_management(client, setup, db_session):
    """Pedido do usuário: Gerente de Serviços e Diretor Geral têm acessos
    equivalentes ao Administrador, EXCETO cadastrar/editar/excluir usuário
    (que continua exclusivo de ADMIN — ver MANAGEMENT_ROLES/ADMIN_LIKE_ROLES
    em app/deps.py). Cobre os dois perfis novos com os mesmos exemplos já
    testados acima pro Administrador (create_user, create_client,
    dashboard) mais a listagem de usuários, que eles precisam pra vincular
    um Recurso mesmo não podendo cadastrar Usuário."""
    # Cores distintas e diferentes de DEFAULT_PROJECT_COLOR (já usada pelo
    # project_a ATIVO do fixture `setup`) — evita 409 de "cor já em uso
    # entre projetos ativos" (ver _ensure_color_available).
    colors = {UserRole.SERVICE_MANAGER: "#800000", UserRole.GENERAL_DIRECTOR: "#008000"}
    for role in (UserRole.SERVICE_MANAGER, UserRole.GENERAL_DIRECTOR):
        user = make_user(db_session, role=role, email=f"{role.value.lower()}@example.com")
        headers = auth_headers(client, user.email)

        # Única exceção: não pode cadastrar usuário.
        denied_user = client.post(
            "/users",
            json={"name": "Outro", "email": f"outro-{role.value.lower()}@example.com", "password": PASSWORD, "role": "CONSULTANT"},
            headers=headers,
        )
        assert denied_user.status_code == 403, role

        # Mas continua enxergando a lista de usuários (precisa pra montar o
        # formulário de "vincular recurso" — ver GET /users em routers/users.py).
        can_list_users = client.get("/users", headers=headers)
        assert can_list_users.status_code == 200, role

        # Tudo o resto que hoje é "só Administrador" ou "Admin/PM" libera
        # igual ao Administrador.
        can_create_client = client.post("/clients", json={"code": f"CLI-{role.value}", "legal_name": "Cliente Novo"}, headers=headers)
        assert can_create_client.status_code == 201, role

        can_see_dashboard = client.get("/dashboard", headers=headers)
        assert can_see_dashboard.status_code == 200, role

        can_create_project = client.post(
            "/projects",
            json={
                "client_id": setup["client_a"].id,
                "manager_id": setup["pm"].id,
                "code": f"PRJ-{role.value}",
                "name": "Projeto novo",
                "color": colors[role],
            },
            headers=headers,
        )
        assert can_create_project.status_code == 201, role


def test_list_resources_filters_by_user_and_allows_consultant(client, setup):
    admin_headers = setup["admin_headers"]
    created = client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
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


def test_external_roles_cannot_write_tasks(client, setup):
    """Regressão do bug em que a checagem de escrita nunca disparava: antes
    da correção original, CLIENT_USER também conseguia criar tarefas.

    Reorganização de menus (pedido do usuário): PM do Cliente, que antes
    podia escrever dentro do próprio escopo de cliente, também passou a ser
    sempre somente leitura — igual já era CLIENT_USER (ver
    require_project_access em app/deps.py)."""
    project_id = setup["project_a"].id

    client_user_headers = auth_headers(client, setup["client_user_a"].email)
    denied_client_user = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Tarefa 1", "wbs_code": "1"},
        headers=client_user_headers,
    )
    assert denied_client_user.status_code == 403

    client_pm_headers = auth_headers(client, setup["client_pm_a"].email)
    denied_client_pm = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Tarefa 1", "wbs_code": "1"},
        headers=client_pm_headers,
    )
    assert denied_client_pm.status_code == 403


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


def test_timesheet_requires_assignment_active_project_and_allows_same_day_duplicates(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]

    task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Implantação", "wbs_code": "1"}, headers=admin_headers
    ).json()

    resource = client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
        },
        headers=admin_headers,
    ).json()

    consultant_headers = auth_headers(client, setup["consultant"].email)
    timesheet_payload = {"task_id": task["id"], "date": "2026-08-24", "start_time": "09:00", "end_time": "13:00"}

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

    # Mais de um apontamento do mesmo recurso, na mesma tarefa, no mesmo dia
    # é permitido de propósito (ex.: dois períodos de trabalho no mesmo dia)
    # — não existe checagem de duplicado em _resolve_task_and_project.
    duplicate = client.post("/timesheets", json=timesheet_payload, headers=consultant_headers)
    assert duplicate.status_code == 201


def test_only_admin_pm_manage_project_resources_consultant_falls_back_to_it(client, setup):
    """Pedido do usuário: "vincular os usuários ao projeto principal" pra
    não alocar tarefa por tarefa em projetos pequenos — POST/DELETE
    /projects/{id}/resources é Admin/PM (mesma regra de "Administrar
    projetos", Consultor sem acesso nem via API direta), e uma tarefa SEM
    nenhuma alocação própria cai pro vínculo de projeto na hora de apontar
    horas (busca primeiro na tarefa, depois no projeto)."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    pm_headers = auth_headers(client, setup["pm"].email)

    resource = client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
        },
        headers=admin_headers,
    ).json()
    consultant_headers = auth_headers(client, setup["consultant"].email)

    task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Sem alocação", "wbs_code": "1"}, headers=admin_headers
    ).json()
    timesheet_payload = {"task_id": task["id"], "date": "2026-08-25", "start_time": "09:00", "end_time": "10:00"}

    # Sem vínculo nenhum ainda -> bloqueado.
    denied = client.post("/timesheets", json=timesheet_payload, headers=consultant_headers)
    assert denied.status_code == 403

    # Consultor não vincula recurso a projeto, nem a si mesmo.
    denied_link = client.post(f"/projects/{project_id}/resources", json={"resource_id": resource["id"]}, headers=consultant_headers)
    assert denied_link.status_code == 403

    linked = client.post(f"/projects/{project_id}/resources", json={"resource_id": resource["id"]}, headers=pm_headers)
    assert linked.status_code == 201

    listed = client.get(f"/projects/{project_id}/resources", headers=pm_headers)
    assert listed.status_code == 200
    assert [row["resource_id"] for row in listed.json()] == [resource["id"]]

    # Agora com o vínculo de projeto, a tarefa sem alocação própria libera.
    allowed = client.post("/timesheets", json=timesheet_payload, headers=consultant_headers)
    assert allowed.status_code == 201


def test_task_assignment_still_restricts_even_with_project_link(client, setup):
    """Uma tarefa que já tem alocação própria (pra outro recurso) continua
    fechada só pra quem está alocado nela — o vínculo de projeto nunca
    "abre" uma tarefa que o PM deixou restrita de propósito (pedido
    explícito do usuário: "posso ter tarefas específicas que quero
    atribuir a um consultor e não deixar abertas todas as tarefas a
    ele")."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]

    resource_a = client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
        },
        headers=admin_headers,
    ).json()
    other_user_resp = client.post(
        "/users",
        json={"name": "Outro Consultor", "email": "outro.consultor.b@example.com", "password": PASSWORD, "role": "CONSULTANT"},
        headers=admin_headers,
    ).json()
    resource_b = client.post(
        "/resources",
        json={
            "user_id": other_user_resp["id"],
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
        },
        headers=admin_headers,
    ).json()

    task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Restrita a outro", "wbs_code": "2"}, headers=admin_headers
    ).json()
    # Aloca só resource_b na tarefa.
    assign = client.post(
        f"/tasks/{task['id']}/assignments", json={"resource_id": resource_b["id"], "allocated_hours": "10"}, headers=admin_headers
    )
    assert assign.status_code == 201

    # resource_a vinculado ao PROJETO (não à tarefa).
    linked = client.post(f"/projects/{project_id}/resources", json={"resource_id": resource_a["id"]}, headers=admin_headers)
    assert linked.status_code == 201

    consultant_headers = auth_headers(client, setup["consultant"].email)
    timesheet_payload = {"task_id": task["id"], "date": "2026-08-25", "start_time": "09:00", "end_time": "10:00"}
    denied = client.post("/timesheets", json=timesheet_payload, headers=consultant_headers)
    assert denied.status_code == 403


def test_project_manager_can_timesheet_any_task_without_allocation(client, setup):
    """Pedido do usuário: criou uma tarefa de Gestão no próprio projeto que
    gerencia (Project.manager_id) e levou 403 até se vincular como Recurso
    do projeto — o gerente deveria poder apontar horas em qualquer tarefa
    do próprio projeto, alocado ou não, sem precisar desse vínculo extra."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    pm = setup["pm"]
    pm_headers = auth_headers(client, pm.email)

    pm_resource = client.post(
        "/resources",
        json={"user_id": pm.id, "internal_cost_per_hour": "80", "billing_rate_per_hour": "150"},
        headers=admin_headers,
    ).json()
    task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Gestão do Projeto", "wbs_code": "5", "task_type": "MANAGEMENT"}, headers=admin_headers
    ).json()

    # Nenhum TaskAssignment nem ProjectResource pro pm_resource — só o fato
    # de ser Project.manager_id precisa bastar.
    allowed = client.post(
        "/timesheets",
        json={"task_id": task["id"], "date": "2026-08-25", "start_time": "09:00", "end_time": "10:00"},
        headers=pm_headers,
    )
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["resource_id"] == pm_resource["id"]


def test_pending_approvals_scoped_to_manager_for_internal_pm(client, db_session, setup):
    """Pedido do usuário: a fila "Aprovações pendentes" só deve trazer
    apontamentos dos projetos onde o usuário é o gerente — pra um
    INTERNAL_PM que não é o gerente de um projeto, o pendente desse
    projeto não deve aparecer. ADMIN continua vendo tudo (é quem precisa
    aprovar "fora da agenda", então não pode ficar restrito a projeto
    nenhum)."""
    admin_headers = setup["admin_headers"]
    pm = setup["pm"]
    pm_headers = auth_headers(client, pm.email)
    other_pm = make_user(db_session, role=UserRole.INTERNAL_PM, email="outro.pm.aprovacao@example.com")
    other_pm_headers = auth_headers(client, other_pm.email)
    other_project = make_project(db_session, client_id=setup["client_b"].id, manager_id=other_pm.id, code="PRJ-D")
    client.patch(f"/projects/{other_project.id}", json={"status": ProjectStatus.ACTIVE.value}, headers=admin_headers)

    consultant_resource = client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
        },
        headers=admin_headers,
    ).json()
    consultant_headers = auth_headers(client, setup["consultant"].email)
    client.post(f"/projects/{setup['project_a'].id}/resources", json={"resource_id": consultant_resource["id"]}, headers=admin_headers)
    client.post(f"/projects/{other_project.id}/resources", json={"resource_id": consultant_resource["id"]}, headers=admin_headers)

    task_a = client.post(f"/projects/{setup['project_a'].id}/tasks", json={"name": "A", "wbs_code": "6"}, headers=admin_headers).json()
    task_d = client.post(f"/projects/{other_project.id}/tasks", json={"name": "D", "wbs_code": "1"}, headers=admin_headers).json()
    for task in (task_a, task_d):
        resp = client.post(
            "/timesheets",
            json={"task_id": task["id"], "date": "2026-08-25", "start_time": "09:00", "end_time": "10:00"},
            headers=consultant_headers,
        )
        assert resp.status_code == 201

    pm_pending = client.get("/timesheets", params={"status_filter": "PENDING"}, headers=pm_headers)
    assert pm_pending.status_code == 200
    assert [row["task_id"] for row in pm_pending.json()] == [task_a["id"]]

    other_pm_pending = client.get("/timesheets", params={"status_filter": "PENDING"}, headers=other_pm_headers)
    assert other_pm_pending.status_code == 200
    assert [row["task_id"] for row in other_pm_pending.json()] == [task_d["id"]]

    admin_pending = client.get("/timesheets", params={"status_filter": "PENDING"}, headers=admin_headers)
    assert admin_pending.status_code == 200
    assert {row["task_id"] for row in admin_pending.json()} == {task_a["id"], task_d["id"]}


def test_timesheets_filter_by_date_range(client, setup):
    """Pedido do usuário: filtro por período na lista de apontamentos."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    resource = client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
        },
        headers=admin_headers,
    ).json()
    consultant_headers = auth_headers(client, setup["consultant"].email)
    client.post(f"/projects/{project_id}/resources", json={"resource_id": resource["id"]}, headers=admin_headers)
    task = client.post(f"/projects/{project_id}/tasks", json={"name": "T", "wbs_code": "3"}, headers=admin_headers).json()

    for day in ("2026-08-10", "2026-08-20"):
        resp = client.post(
            "/timesheets",
            json={"task_id": task["id"], "date": day, "start_time": "09:00", "end_time": "10:00"},
            headers=consultant_headers,
        )
        assert resp.status_code == 201

    filtered = client.get(
        "/timesheets", params={"resource_id": resource["id"], "start": "2026-08-15", "end": "2026-08-31"}, headers=admin_headers
    )
    assert filtered.status_code == 200
    dates = [row["date"] for row in filtered.json()]
    assert dates == ["2026-08-20"]


def test_timesheets_filter_by_client(client, setup):
    """Pedido do usuário: filtro por cliente em "Meus apontamentos" — não
    existe client_id em Timesheet, resolve via os projetos do cliente (ver
    comentário em list_timesheets)."""
    admin_headers = setup["admin_headers"]
    resource = client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
        },
        headers=admin_headers,
    ).json()
    consultant_headers = auth_headers(client, setup["consultant"].email)
    client.post(f"/projects/{setup['project_a'].id}/resources", json={"resource_id": resource["id"]}, headers=admin_headers)
    client.post(f"/projects/{setup['project_b'].id}/resources", json={"resource_id": resource["id"]}, headers=admin_headers)
    task_a = client.post(f"/projects/{setup['project_a'].id}/tasks", json={"name": "A", "wbs_code": "4"}, headers=admin_headers).json()
    task_b = client.post(f"/projects/{setup['project_b'].id}/tasks", json={"name": "B", "wbs_code": "4"}, headers=admin_headers).json()

    for task in (task_a, task_b):
        resp = client.post(
            "/timesheets",
            json={"task_id": task["id"], "date": "2026-08-12", "start_time": "09:00", "end_time": "10:00"},
            headers=consultant_headers,
        )
        assert resp.status_code == 201

    filtered = client.get(
        "/timesheets", params={"resource_id": resource["id"], "client_id": setup["client_a"].id}, headers=admin_headers
    )
    assert filtered.status_code == 200
    task_ids = [row["task_id"] for row in filtered.json()]
    assert task_ids == [task_a["id"]]


def test_portfolio_row_includes_manager_name(client, setup):
    """Pedido do usuário: mostrar o nome do gerente na lista de Projetos."""
    response = client.get("/reports/portfolio", headers=setup["admin_headers"])
    assert response.status_code == 200
    row = next(r for r in response.json() if r["id"] == setup["project_a"].id)
    assert row["manager_name"] == setup["pm"].name


def test_portfolio_filter_by_manager(client, db_session, setup):
    """Pedido do usuário: filtro por gerente do projeto na tela de
    Projetos — project_a/project_b (fixture `setup`) são geridos pelo
    mesmo `pm`; cria um projeto extra gerido por outro INTERNAL_PM e
    confirma que filtrar por manager_id devolve só os do gerente pedido."""
    admin_headers = setup["admin_headers"]
    other_pm = make_user(db_session, role=UserRole.INTERNAL_PM, email="outro.pm@example.com")
    other_project = make_project(db_session, client_id=setup["client_a"].id, manager_id=other_pm.id, code="PRJ-C")

    filtered = client.get("/reports/portfolio", params={"manager_id": setup["pm"].id}, headers=admin_headers)
    assert filtered.status_code == 200
    ids = {row["id"] for row in filtered.json()}
    assert ids == {setup["project_a"].id, setup["project_b"].id}
    assert other_project.id not in ids


def test_portfolio_scoped_to_manager_for_internal_pm(client, db_session, setup):
    """Pedido do usuário: "ainda posso ver com meu acesso de gerente de
    projetos, projetos de outros gerentes" — por padrão (sem filtro
    nenhum) um INTERNAL_PM só deve ver, na tela de Projetos, os projetos
    onde ele mesmo é o gerente. ADMIN continua vendo o portfólio inteiro."""
    pm_headers = auth_headers(client, setup["pm"].email)
    admin_headers = setup["admin_headers"]
    other_pm = make_user(db_session, role=UserRole.INTERNAL_PM, email="outro.pm.portfolio@example.com")
    other_project = make_project(db_session, client_id=setup["client_a"].id, manager_id=other_pm.id, code="PRJ-E")

    pm_view = client.get("/reports/portfolio", headers=pm_headers)
    assert pm_view.status_code == 200
    pm_ids = {row["id"] for row in pm_view.json()}
    assert pm_ids == {setup["project_a"].id, setup["project_b"].id}
    assert other_project.id not in pm_ids

    other_pm_headers = auth_headers(client, other_pm.email)
    other_pm_view = client.get("/reports/portfolio", headers=other_pm_headers)
    assert other_pm_view.status_code == 200
    assert {row["id"] for row in other_pm_view.json()} == {other_project.id}

    admin_view = client.get("/reports/portfolio", headers=admin_headers)
    assert admin_view.status_code == 200
    admin_ids = {row["id"] for row in admin_view.json()}
    assert {setup["project_a"].id, setup["project_b"].id, other_project.id} <= admin_ids


def test_portfolio_modelo_visible_to_any_internal_pm_regardless_of_manager(client, db_session, setup):
    """Pedido do usuário: os projetos MODELO foram todos cadastrados com o
    Admin como gerente, mas "Mostrar projetos Modelo" precisa continuar
    funcionando pra qualquer INTERNAL_PM — é um catálogo de estruturas
    compartilhado (base do "Copiar estrutura de outro projeto"), não
    trabalho de um gerente em particular. A restrição por manager_id vale
    só pros projetos normais."""
    admin_headers = setup["admin_headers"]
    pm_headers = auth_headers(client, setup["pm"].email)
    modelo = make_project(db_session, client_id=setup["client_a"].id, manager_id=setup["admin"].id, code="PRJ-MODELO")
    patched = client.patch(f"/projects/{modelo.id}", json={"status": "MODELO"}, headers=admin_headers)
    assert patched.status_code == 200

    # Sem o toggle "Mostrar projetos Modelo", continua de fora (igual
    # já era pra qualquer perfil).
    without_toggle = client.get("/reports/portfolio", headers=pm_headers)
    assert modelo.id not in {row["id"] for row in without_toggle.json()}

    with_toggle = client.get("/reports/portfolio", params={"include_modelo": True}, headers=pm_headers)
    assert with_toggle.status_code == 200
    ids = {row["id"] for row in with_toggle.json()}
    assert modelo.id in ids
    # Os projetos normais de outro gerente continuam de fora mesmo com o
    # toggle ligado — a exceção é só pro MODELO.
    assert setup["project_b"].id in ids  # é do próprio pm, deveria aparecer
    other_pm = make_user(db_session, role=UserRole.INTERNAL_PM, email="outro.pm.modelo@example.com")
    other_project = make_project(db_session, client_id=setup["client_a"].id, manager_id=other_pm.id, code="PRJ-F")
    with_toggle_again = client.get("/reports/portfolio", params={"include_modelo": True}, headers=pm_headers)
    assert other_project.id not in {row["id"] for row in with_toggle_again.json()}


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
        json={"task_id": task["id"], "date": "2026-08-24", "start_time": "09:00", "end_time": "15:00"},
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
        json={"task_id": task["id"], "date": "2026-08-24", "start_time": "09:00", "end_time": "13:00"},
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
        # Cor diferente do default (DEFAULT_PROJECT_COLOR) — o próprio
        # `project_a` do fixture `setup` já está ACTIVE com a cor default,
        # e a exclusividade de cor entre projetos ativos (ver
        # _ensure_color_available em routers/projects.py) rejeitaria (409)
        # criar outro projeto ativo com a cor repetida.
        "color": "#800000",
    }
    created = client.post("/projects", json=payload, headers=admin_headers).json()
    assert float(created["sold_value"]) == 3500.0

    updated = client.patch(
        f"/projects/{created['id']}", json={"consulting_rate": "400"}, headers=admin_headers
    ).json()
    assert float(updated["sold_value"]) == 4000.0


def test_project_color_exclusivity_and_striped_on_finalize(client, setup):
    """Item 1 do pedido do usuário: cor exclusiva entre projetos ativos, em
    todos os clientes, enquanto o projeto não for finalizado (Concluído ou
    Cancelado); ao finalizar, o flag color_striped liga sozinho (a tela usa
    o padrão listrado no lugar da cor) e o hex fica livre pra outro projeto
    ativo escolher — ver _ensure_color_available/_STRIPED_STATUSES em
    routers/projects.py."""
    admin_headers = setup["admin_headers"]
    project_a = setup["project_a"]  # já ACTIVE (ver fixture setup), cor default

    # Outro projeto ativo não pode nascer com a mesma cor de project_a.
    conflict = client.post(
        "/projects",
        json={
            "client_id": setup["client_b"].id,
            "manager_id": setup["pm"].id,
            "code": "PRJ-COLOR-1",
            "name": "Projeto cor 1",
            "color": project_a.color,
        },
        headers=admin_headers,
    )
    assert conflict.status_code == 409

    created = client.post(
        "/projects",
        json={
            "client_id": setup["client_b"].id,
            "manager_id": setup["pm"].id,
            "code": "PRJ-COLOR-2",
            "name": "Projeto cor 2",
            "color": "#870000",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    other_project_id = created.json()["id"]

    # Trocar a cor de outro projeto pra igual à de project_a também é
    # rejeitado pelo mesmo motivo (update usa a mesma checagem).
    blocked_update = client.patch(f"/projects/{other_project_id}", json={"color": project_a.color}, headers=admin_headers)
    assert blocked_update.status_code == 409

    # Finalizar project_a (Concluído) libera a cor: color_striped liga
    # sozinho e a cor original fica guardada (nunca apagada).
    finalize = client.patch(f"/projects/{project_a.id}", json={"status": "COMPLETED"}, headers=admin_headers)
    assert finalize.status_code == 200
    finalized_body = finalize.json()
    assert finalized_body["color_striped"] is True
    assert finalized_body["color"] == project_a.color

    # Agora outro projeto ativo pode usar a cor que ficou livre.
    now_allowed = client.patch(f"/projects/{other_project_id}", json={"color": project_a.color}, headers=admin_headers)
    assert now_allowed.status_code == 200
    assert now_allowed.json()["color_striped"] is False

    # Reativar project_a sem trocar de cor é rejeitado: a cor original já
    # foi tomada por other_project_id enquanto project_a estava parado.
    reactivate_conflict = client.patch(f"/projects/{project_a.id}", json={"status": "ACTIVE"}, headers=admin_headers)
    assert reactivate_conflict.status_code == 409

    # Reativando com uma cor livre funciona e o listrado desliga sozinho.
    reactivate_ok = client.patch(
        f"/projects/{project_a.id}", json={"status": "ACTIVE", "color": "#005F00"}, headers=admin_headers
    )
    assert reactivate_ok.status_code == 200
    assert reactivate_ok.json()["color_striped"] is False


def test_external_role_cannot_change_project_financials(client, setup):
    """PM do Cliente é sempre somente leitura (reorganização de menus,
    pedido do usuário) — o PATCH inteiro é barrado em require_project_access
    antes mesmo de chegar na checagem de campo financeiro por isso, o campo
    nunca muda, mesmo que o perfil tentasse editar outra coisa junto."""
    project_id = setup["project_a"].id
    external_headers = auth_headers(client, setup["client_pm_a"].email)
    response = client.patch(f"/projects/{project_id}", json={"management_rate": "999"}, headers=external_headers)
    assert response.status_code == 403

    detail = client.get(f"/projects/{project_id}", headers=setup["admin_headers"]).json()
    assert float(detail["management_rate"]) == 0.0


def test_resource_can_be_linked_to_a_calendar(client, setup):
    admin_headers = setup["admin_headers"]
    calendar = client.post("/calendars", json={"name": "Padrão"}, headers=admin_headers).json()

    resource = client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
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
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
            "calendar_id": "id-inexistente",
        },
        headers=admin_headers,
    )
    assert missing_calendar.status_code == 404


def test_update_resource_changes_role_and_cost(client, setup):
    admin_headers = setup["admin_headers"]
    resource = client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
        },
        headers=admin_headers,
    ).json()

    updated = client.patch(
        f"/resources/{resource['id']}",
        json={"function": "CONSULTANT", "level": 3, "internal_cost_per_hour": "65"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["function"] == "CONSULTANT"
    assert body["level"] == 3
    assert float(body["internal_cost_per_hour"]) == 65.0
    # Campos não enviados no PATCH continuam com o valor original.
    assert float(body["billing_rate_per_hour"]) == 100.0

    bad_calendar = client.patch(f"/resources/{resource['id']}", json={"calendar_id": "id-inexistente"}, headers=admin_headers)
    assert bad_calendar.status_code == 404


def test_user_can_change_own_language_without_admin_role(client, setup):
    """PATCH /users/me — autoatendimento de idioma: qualquer usuário logado
    troca o próprio idioma, sem depender de um ADMIN editar o cadastro
    (diferente de PATCH /users/{id}, restrito a ADMIN)."""
    consultant_headers = auth_headers(client, setup["consultant"].email)

    me = client.get("/users/me", headers=consultant_headers).json()
    assert me["language"] == "pt-BR"

    updated = client.patch("/users/me", json={"language": "es"}, headers=consultant_headers)
    assert updated.status_code == 200
    assert updated.json()["language"] == "es"

    me_again = client.get("/users/me", headers=consultant_headers).json()
    assert me_again["language"] == "es"

    # Mensagens de erro passam a vir em espanhol para este usuário.
    bad_project = client.post(
        "/timesheets",
        json={"task_id": "id-inexistente", "date": "2026-01-01", "start_time": "09:00", "end_time": "10:00"},
        headers=consultant_headers,
    )
    assert bad_project.status_code == 422
    assert "recurso" in bad_project.json()["detail"].lower()


def test_adhoc_timesheet_without_task_or_project(client, setup):
    """Hora administrativa interna (sem task_id nem project_id) continua
    livre, sem exigir TaskAssignment prévio. O apontamento "avulso" antigo
    (project_id sem task_id, padrão Clockify/Toggl) foi descontinuado —
    pedido do usuário: projeto selecionado sem tarefa (e sem Traslado) agora
    é rejeitado (ver test_timesheet_requires_task_or_transit_when_project_is_set)."""
    admin_headers = setup["admin_headers"]
    project_id = setup["project_a"].id

    client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
        },
        headers=admin_headers,
    )
    consultant_headers = auth_headers(client, setup["consultant"].email)

    admin_hours = client.post(
        "/timesheets", json={"date": "2026-08-24", "start_time": "09:00", "end_time": "10:00"}, headers=consultant_headers
    )
    assert admin_hours.status_code == 201
    assert admin_hours.json()["task_id"] is None
    assert admin_hours.json()["project_id"] is None

    task = client.post(f"/projects/{project_id}/tasks", json={"name": "Entrega", "wbs_code": "41"}, headers=admin_headers).json()
    project_hours = client.post(
        "/timesheets",
        json={"task_id": task["id"], "date": "2026-08-24", "start_time": "09:00", "end_time": "11:00"},
        headers=consultant_headers,
    )
    assert project_hours.status_code == 201

    listed = client.get("/timesheets", params={"project_id": project_id}, headers=admin_headers)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [project_hours.json()["id"]]


def test_timesheet_requires_task_or_transit_when_project_is_set(client, setup):
    """Pedido do usuário: ao selecionar um projeto, é obrigatório selecionar
    uma tarefa OU marcar Traslado — o apontamento "avulso" (projeto sem
    tarefa) deixou de ser permitido (ver _resolve_task_and_project,
    routers/timesheets.py)."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    )
    consultant_headers = auth_headers(client, setup["consultant"].email)

    rejected = client.post(
        "/timesheets",
        json={"project_id": project_id, "date": "2026-08-24", "start_time": "09:00", "end_time": "11:00"},
        headers=consultant_headers,
    )
    assert rejected.status_code == 422

    # Com Traslado marcado, projeto sem tarefa continua válido.
    transit_ok = client.post(
        "/timesheets",
        json={"project_id": project_id, "date": "2026-08-24", "start_time": "09:00", "end_time": "11:00", "is_transit": True},
        headers=consultant_headers,
    )
    assert transit_ok.status_code == 201

    # Com uma tarefa, também válido.
    task = client.post(f"/projects/{project_id}/tasks", json={"name": "Entrega", "wbs_code": "42"}, headers=admin_headers).json()
    task_ok = client.post(
        "/timesheets",
        json={"task_id": task["id"], "date": "2026-08-24", "start_time": "11:00", "end_time": "12:00"},
        headers=consultant_headers,
    )
    assert task_ok.status_code == 201


def test_task_client_approval_workflow(client, setup):
    """Fluxo de validação de tarefa pelo lado do cliente: um perfil interno
    submete (reorganização de menus tirou PM do Cliente dessa rota também —
    ver test_external_roles_cannot_write_tasks); só o cliente (CLIENT_PM/
    CLIENT_USER, ambos sempre somente-leitura no resto da API) aprova ou
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
    """Admin enxerga o portfólio inteiro (os dois projetos do setup), com
    margem na linha de portfólio. A checagem de escopo por cliente e de
    margem escondida pro perfil externo foi pra
    test_reports_portfolio_endpoint_scopes_by_client logo abaixo —
    reorganização de menus (pedido do usuário) tirou PM do Cliente/
    Usuário-chave do Dashboard (ver test_dashboard_restricted_to_admin_like_roles),
    então GET /dashboard não é mais chamável por perfil externo."""
    admin_view = client.get("/dashboard", headers=setup["admin_headers"]).json()
    assert admin_view["projects_total"] == 2
    admin_row = next(row for row in admin_view["portfolio"] if row["id"] == setup["project_a"].id)
    assert admin_row["margin"] is not None


def test_reports_portfolio_endpoint_scopes_by_client(client, setup):
    """Diferente de GET /dashboard (restrito a ADMIN_LIKE_ROLES), este
    endpoint continua aberto a qualquer perfil autenticado — é por aqui que
    o PM do Cliente enxerga o próprio portfólio depois da reorganização de
    menus. Escopado por client_id e sem margem (mesmo tratamento de dado
    financeiro do resto da API para perfil externo)."""
    external_headers = auth_headers(client, setup["client_pm_a"].email)
    response = client.get("/reports/portfolio", headers=external_headers)
    assert response.status_code == 200
    rows = response.json()
    assert [row["id"] for row in rows] == [setup["project_a"].id]
    assert rows[0]["margin"] is None


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


def _status_report_payload(**overrides) -> dict:
    payload = {
        "period_start": "2026-08-01",
        "period_end": "2026-08-15",
        "rag_schedule": "GOOD",
        "rag_cost": "WARNING",
        "rag_margin": "GOOD",
        "rag_scope": "GOOD",
        "rag_risk": "WARNING",
        "executive_summary": "Projeto avançando dentro do previsto, com atenção ao custo.",
        "next_steps_client": "Validar entrega da fase 2 até o fim do mês.",
        "next_steps_internal": "Negociar horas extras com o consultor X.",
    }
    payload.update(overrides)
    return payload


def test_status_report_create_restricted_to_management_roles(client, setup):
    """Pedido do usuário: "pode implementar os 2 modelos e colocar na
    opção de relatorios" — quem fecha o período é a gerência interna
    (MANAGEMENT_ROLES), nunca Consultor nem perfil externo."""
    project_id = setup["project_a"].id

    consultant_headers = auth_headers(client, setup["consultant"].email)
    denied = client.post(
        f"/projects/{project_id}/status-reports", json=_status_report_payload(), headers=consultant_headers
    )
    assert denied.status_code == 403

    external_headers = auth_headers(client, setup["client_pm_a"].email)
    denied_external = client.post(
        f"/projects/{project_id}/status-reports", json=_status_report_payload(), headers=external_headers
    )
    assert denied_external.status_code == 403

    allowed = client.post(
        f"/projects/{project_id}/status-reports", json=_status_report_payload(), headers=setup["admin_headers"]
    )
    assert allowed.status_code == 201
    body = allowed.json()
    assert body["project_id"] == project_id
    assert body["rag_cost"] == "WARNING"
    assert body["prepared_by_id"] == setup["admin"].id
    assert body["hours_consumed"] is not None
    assert body["next_steps_internal"] == "Negociar horas extras com o consultor X."


def test_status_report_hides_financials_and_internal_notes_for_external_role(client, setup):
    """Mesmo critério de GET /projects/{id}/report (financials=None para
    EXTERNAL_ROLES): os campos financeiros/burndown/next_steps_internal
    do Status Report viram None/[] pro gerente de projeto do cliente,
    nunca um valor zerado fajuto — e tasks_done/tasks_next/risks_snapshot
    continuam aparecendo (os dois mockups mostram essas seções)."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]

    client.patch(f"/projects/{project_id}", json={"start_date": "2026-08-01", "end_date": "2026-08-15"}, headers=admin_headers)
    client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Entrega", "wbs_code": "1", "estimated_hours": "10", "planned_end_date": "2026-08-10"},
        headers=admin_headers,
    )
    client.post(
        f"/projects/{project_id}/risks",
        json={"description": "Atraso de fornecedor", "probability": "HIGH", "impact": "HIGH"},
        headers=admin_headers,
    )

    created = client.post(
        f"/projects/{project_id}/status-reports", json=_status_report_payload(), headers=admin_headers
    )
    assert created.status_code == 201
    report_id = created.json()["id"]

    internal_list = client.get(f"/projects/{project_id}/status-reports", headers=admin_headers)
    assert internal_list.status_code == 200
    internal_body = internal_list.json()[0]
    assert internal_body["hours_consumed"] is not None or internal_body["hours_budgeted"] is not None
    assert internal_body["next_steps_internal"] == "Negociar horas extras com o consultor X."
    assert len(internal_body["risks_snapshot"]) == 1

    external_headers = auth_headers(client, setup["client_pm_a"].email)
    external_detail = client.get(f"/projects/{project_id}/status-reports/{report_id}", headers=external_headers)
    assert external_detail.status_code == 200
    external_body = external_detail.json()
    assert external_body["hours_consumed"] is None
    assert external_body["hours_budgeted"] is None
    assert external_body["cost_planned"] is None
    assert external_body["cost_actual"] is None
    assert external_body["margin_planned_pct"] is None
    assert external_body["margin_actual_pct"] is None
    assert external_body["burndown"] == []
    assert external_body["next_steps_internal"] is None
    assert external_body["next_steps_client"] == "Validar entrega da fase 2 até o fim do mês."
    assert len(external_body["risks_snapshot"]) == 1

    cross_client_headers = auth_headers(client, setup["client_pm_a"].email)
    cross_client = client.get(f"/projects/{setup['project_b'].id}/status-reports", headers=cross_client_headers)
    assert cross_client.status_code == 403


def test_status_report_detail_404_for_wrong_project(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    created = client.post(
        f"/projects/{project_id}/status-reports", json=_status_report_payload(), headers=admin_headers
    )
    report_id = created.json()["id"]

    wrong_project = client.get(f"/projects/{setup['project_b'].id}/status-reports/{report_id}", headers=admin_headers)
    assert wrong_project.status_code == 404


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


def test_export_tasks_xlsx_returns_workbook_with_task_rows(client, setup):
    """Botão "Exportar (Excel)" da tela de Tarefas — ver app/exports.py.
    Confere o content-type/anexo e que a planilha de fato tem uma linha por
    tarefa (mesmos dados de GET /schedule, incluindo o rollup de tarefa-pai)."""
    from io import BytesIO

    from openpyxl import load_workbook

    project = setup["project_a"]
    admin_headers = setup["admin_headers"]
    parent = client.post(f"/projects/{project.id}/tasks", json={"name": "Pai", "wbs_code": "1"}, headers=admin_headers).json()
    child = client.post(
        f"/projects/{project.id}/tasks",
        json={
            "name": "Filho",
            "wbs_code": "1.1",
            "parent_task_id": parent["id"],
            "planned_start_date": "2026-08-24",
            "planned_end_date": "2026-08-28",
        },
        headers=admin_headers,
    ).json()

    response = client.get(f"/projects/{project.id}/tasks/export.xlsx", headers=admin_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in response.headers["content-disposition"]
    assert project.code in response.headers["content-disposition"]

    workbook = load_workbook(BytesIO(response.content))
    sheet = workbook.active
    header = [cell.value for cell in sheet[1]]
    assert header[0] == "WBS"
    assert header[1] == "Nome da tarefa"
    rows_by_wbs = {row[0]: row for row in sheet.iter_rows(min_row=2, values_only=True)}
    assert set(rows_by_wbs.keys()) == {parent["wbs_code"], child["wbs_code"]}
    # A tarefa-pai não tem Início/Fim próprios (não é folha) — a planilha
    # usa o rollup agregado da filha, igual à grade de Tarefas na tela.
    assert rows_by_wbs[parent["wbs_code"]][4] is not None  # Início (rollup)
    assert rows_by_wbs[child["wbs_code"]][4] is not None  # Início (próprio)


def test_schedule_and_export_order_tasks_by_wbs_hierarchy(client, setup):
    """Regressão: GET /schedule (usado pelo Gantt) e a exportação p/ Excel
    vinham na ordem "crua" do banco (sem ORDER BY nenhum em
    task_schedule_rows) em vez da ordem hierárquica da EAP/WBS — criando as
    tarefas fora de ordem (como qualquer uso real do sistema faz: ninguém
    cadastra 1, 1.1, 1.1.1... em sequência perfeita) já era suficiente pra
    embaralhar o Gantt e a planilha exportada. Ver services.py
    (order_tasks_hierarchically)."""
    from io import BytesIO

    from openpyxl import load_workbook

    project = setup["project_a"]
    admin_headers = setup["admin_headers"]

    def create(wbs_code, parent_id=None):
        payload = {"name": f"Tarefa {wbs_code}", "wbs_code": wbs_code}
        if parent_id:
            payload["parent_task_id"] = parent_id
        return client.post(f"/projects/{project.id}/tasks", json=payload, headers=admin_headers).json()

    # Cadastradas fora de ordem de propósito — mesma bagunça relatada pelo
    # usuário (ver captura de tela: 1.2.1, 1.1.1.1, 1, 1.1.1.2, 1.2.1.2,
    # 1.1, 1.1.1, 1.2.1.1, 1.2).
    root = create("1")
    t11 = create("1.1", root["id"])
    t111 = create("1.1.1", t11["id"])
    t12 = create("1.2", root["id"])
    t121 = create("1.2.1", t12["id"])
    create("1.2.1.1", t121["id"])
    create("1.2.1.2", t121["id"])
    create("1.1.1.1", t111["id"])
    create("1.1.1.2", t111["id"])

    expected_order = ["1", "1.1", "1.1.1", "1.1.1.1", "1.1.1.2", "1.2", "1.2.1", "1.2.1.1", "1.2.1.2"]

    schedule = client.get(f"/projects/{project.id}/schedule", headers=admin_headers).json()
    assert [t["wbs_code"] for t in schedule["tasks"]] == expected_order

    response = client.get(f"/projects/{project.id}/tasks/export.xlsx", headers=admin_headers)
    workbook = load_workbook(BytesIO(response.content))
    sheet = workbook.active
    wbs_column = [row[0] for row in sheet.iter_rows(min_row=2, max_row=1 + len(expected_order), values_only=True)]
    assert wbs_column == expected_order


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


def test_delete_task_succeeds_without_children_or_timesheets(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    task = client.post(f"/projects/{project_id}/tasks", json={"name": "Descartável", "wbs_code": "9"}, headers=admin_headers).json()

    delete = client.delete(f"/tasks/{task['id']}", headers=admin_headers)
    assert delete.status_code == 204

    missing = client.get(f"/tasks/{task['id']}", headers=admin_headers)
    assert missing.status_code == 404


def test_delete_task_blocked_when_it_has_children(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    parent = client.post(f"/projects/{project_id}/tasks", json={"name": "Pai", "wbs_code": "9"}, headers=admin_headers).json()
    client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Filho", "wbs_code": "9.1", "parent_task_id": parent["id"]},
        headers=admin_headers,
    )

    delete = client.delete(f"/tasks/{parent['id']}", headers=admin_headers)
    assert delete.status_code == 409


def test_delete_task_blocked_when_it_has_timesheet_entries(client, setup):
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    task = client.post(f"/projects/{project_id}/tasks", json={"name": "Com apontamento", "wbs_code": "9"}, headers=admin_headers).json()
    resource = client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
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
    logged = client.post(
        "/timesheets",
        json={"task_id": task["id"], "date": "2026-08-24", "start_time": "09:00", "end_time": "13:00"},
        headers=consultant_headers,
    )
    assert logged.status_code == 201

    delete = client.delete(f"/tasks/{task['id']}", headers=admin_headers)
    assert delete.status_code == 409


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


def test_closed_task_blocks_new_timesheet(client, setup):
    """Pedido do usuário ("MELHORIAS DO PROJETO"): opção de ativar/
    desativar tarefas, com um estado "Finalizada/Cerrada" — uma tarefa
    CLOSED (desativada) passa a bloquear novo apontamento de horas, igual
    já acontecia com projeto inativo. Reativar (voltar pra NOT_STARTED)
    libera de novo."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Tarefa", "wbs_code": "9"}, headers=admin_headers
    ).json()
    resource = client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
        },
        headers=admin_headers,
    ).json()
    client.post(
        f"/tasks/{task['id']}/assignments",
        json={"resource_id": resource["id"], "allocated_hours": "10"},
        headers=admin_headers,
    )
    consultant_headers = auth_headers(client, setup["consultant"].email)

    closed = client.patch(f"/tasks/{task['id']}", json={"status": "CLOSED"}, headers=admin_headers)
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED"

    blocked = client.post(
        "/timesheets",
        json={"task_id": task["id"], "date": "2026-08-20", "start_time": "09:00", "end_time": "10:00"},
        headers=consultant_headers,
    )
    assert blocked.status_code == 422

    reactivated = client.patch(f"/tasks/{task['id']}", json={"status": "NOT_STARTED"}, headers=admin_headers)
    assert reactivated.status_code == 200
    allowed = client.post(
        "/timesheets",
        json={"task_id": task["id"], "date": "2026-08-20", "start_time": "09:00", "end_time": "10:00"},
        headers=consultant_headers,
    )
    assert allowed.status_code == 201


def test_dashboard_overdue_excludes_closed_tasks(client, setup):
    """CLOSED conta como "finalizada" igual COMPLETED pros indicadores
    (TASK_FINISHED_STATUSES) — uma tarefa desativada com prazo vencido não
    deve continuar aparecendo como atrasada no Dashboard."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    task = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Vencida", "wbs_code": "10", "planned_start_date": "2020-01-01", "planned_end_date": "2020-01-02"},
        headers=admin_headers,
    ).json()
    assert task["planned_end_date"] < "2026-01-01"

    before = client.get("/dashboard", headers=admin_headers).json()
    assert before["tasks_overdue"] >= 1

    client.patch(f"/tasks/{task['id']}", json={"status": "CLOSED"}, headers=admin_headers)
    after = client.get("/dashboard", headers=admin_headers).json()
    assert after["tasks_overdue"] == before["tasks_overdue"] - 1


def test_calendar_read_open_to_all_authenticated_roles(client, setup):
    """Pedido do usuário ("MELHORIAS DO PROJETO"): consultores/clientes
    precisam ver os feriados na própria Agenda — leitura de calendários e
    feriados deixou de ser só ADMIN/INTERNAL_PM; cadastrar/editar continua
    restrito."""
    admin_headers = setup["admin_headers"]
    consultant_headers = auth_headers(client, setup["consultant"].email)

    created = client.post("/calendars", json={"name": "Nacional PY", "working_days": [0, 1, 2, 3, 4]}, headers=admin_headers)
    assert created.status_code == 201
    calendar_id = created.json()["id"]

    denied_create = client.post("/calendars", json={"name": "Outro"}, headers=consultant_headers)
    assert denied_create.status_code == 403

    listed = client.get("/calendars", headers=consultant_headers)
    assert listed.status_code == 200
    assert any(c["id"] == calendar_id for c in listed.json())

    holiday = client.post(
        f"/calendars/{calendar_id}/holidays", json={"date": "2026-12-25", "description": "Natal"}, headers=admin_headers
    )
    assert holiday.status_code == 201

    holidays_read = client.get(f"/calendars/{calendar_id}/holidays", headers=consultant_headers)
    assert holidays_read.status_code == 200
    assert holidays_read.json()[0]["description"] == "Natal"

    denied_add_holiday = client.post(
        f"/calendars/{calendar_id}/holidays", json={"date": "2026-12-31", "description": "Ano novo"}, headers=consultant_headers
    )
    assert denied_add_holiday.status_code == 403


def test_calendar_set_default_unsets_previous(client, setup):
    """Pedido do usuário: um único calendário padrão vale pra Agenda
    inteira mostrar feriados (a tela não é de um projeto só) — marcar outro
    como padrão desliga o anterior automaticamente."""
    admin_headers = setup["admin_headers"]
    first = client.post("/calendars", json={"name": "Calendário 1", "is_default": True}, headers=admin_headers).json()
    assert first["is_default"] is True

    second = client.post("/calendars", json={"name": "Calendário 2"}, headers=admin_headers).json()
    assert second["is_default"] is False

    made_default = client.patch(f"/calendars/{second['id']}", json={"is_default": True}, headers=admin_headers)
    assert made_default.status_code == 200
    assert made_default.json()["is_default"] is True

    first_after = client.get(f"/calendars/{first['id']}", headers=admin_headers).json()
    assert first_after["is_default"] is False


def test_task_auto_completes_at_100_percent(client, setup):
    """Pedido do usuário ("mais melhorias"): quando uma tarefa chega a 100%
    de progresso, ela muda sozinha pra Concluída — sem precisar que o
    usuário também mexa no status manualmente."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Tarefa", "wbs_code": "11"}, headers=admin_headers
    ).json()
    client.patch(f"/tasks/{task['id']}", json={"status": "IN_PROGRESS"}, headers=admin_headers)

    updated = client.patch(f"/tasks/{task['id']}", json={"progress_percentage": "100"}, headers=admin_headers)
    assert updated.status_code == 200
    assert updated.json()["status"] == "COMPLETED"
    assert float(updated.json()["progress_percentage"]) == 100.0


def test_task_auto_complete_does_not_override_explicit_status(client, setup):
    """O auto-complete em 100% não pode atropelar uma escolha explícita de
    status mandada no mesmo PATCH — ex.: o usuário encerra (CLOSED) uma
    tarefa já com 100% de progresso, não deve "voltar" pra COMPLETED."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Tarefa", "wbs_code": "12"}, headers=admin_headers
    ).json()
    client.patch(f"/tasks/{task['id']}", json={"status": "IN_PROGRESS"}, headers=admin_headers)

    updated = client.patch(
        f"/tasks/{task['id']}", json={"progress_percentage": "100", "status": "CLOSED"}, headers=admin_headers
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "CLOSED"


def test_task_auto_complete_with_unchanged_status_in_payload(client, setup):
    """O formulário de edição do front sempre manda "status" junto no
    payload (não é um diff) — quando o valor mandado é igual ao que a
    tarefa já tinha (ou seja, não foi uma troca explícita), o auto-complete
    em 100% continua disparando normalmente."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Tarefa", "wbs_code": "13"}, headers=admin_headers
    ).json()
    client.patch(f"/tasks/{task['id']}", json={"status": "IN_PROGRESS"}, headers=admin_headers)

    updated = client.patch(
        f"/tasks/{task['id']}",
        json={"progress_percentage": "100", "status": "IN_PROGRESS", "name": "Tarefa"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "COMPLETED"


def test_task_auto_complete_does_not_resurrect_closed_task(client, setup):
    """Uma tarefa já Encerrada (CLOSED) que ganha um PATCH elevando o
    progresso a 100% sem tocar no status continua Encerrada — o
    auto-complete não ressuscita um estado já finalizado pra COMPLETED."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Tarefa", "wbs_code": "14"}, headers=admin_headers
    ).json()
    client.patch(f"/tasks/{task['id']}", json={"status": "CLOSED"}, headers=admin_headers)

    updated = client.patch(f"/tasks/{task['id']}", json={"progress_percentage": "100"}, headers=admin_headers)
    assert updated.status_code == 200
    assert updated.json()["status"] == "CLOSED"


# ---------------------------------------------------------------------------
# "mais novas melhorias, parte 3"
# ---------------------------------------------------------------------------


def test_only_admin_can_delete_client_and_link_checks_are_enforced(client, db_session, setup):
    """Pedido do usuário: botão de excluir cliente, validando que não está
    vinculado a nenhuma tabela — Projeto (RESTRICT), Usuário (SET NULL, mas
    o pedido foi bloquear mesmo assim) e Solicitação de projeto (CASCADE)
    bloqueiam a exclusão; um cliente limpo pode ser excluído."""
    admin_headers = setup["admin_headers"]
    pm_headers = auth_headers(client, setup["pm"].email)

    client_a_id = setup["client_a"].id
    denied = client.delete(f"/clients/{client_a_id}", headers=pm_headers)
    assert denied.status_code == 403

    # client_a já tem project_a (ver fixture setup) — bloqueado por Projeto.
    blocked_by_project = client.delete(f"/clients/{client_a_id}", headers=admin_headers)
    assert blocked_by_project.status_code == 409

    # Um cliente novo, sem projeto, mas com um usuário vinculado — bloqueado
    # por Usuário.
    client_c = make_client_row(db_session, code="CLI-C")
    make_user(db_session, role=UserRole.CLIENT_USER, client_id=client_c.id, email="user.c@example.com")
    blocked_by_user = client.delete(f"/clients/{client_c.id}", headers=admin_headers)
    assert blocked_by_user.status_code == 409

    # Um cliente novo, sem projeto nem usuário, mas com uma solicitação de
    # projeto (intake) registrada — bloqueado por ProjectIntake.
    client_d = make_client_row(db_session, code="CLI-D")
    intake = client.post(f"/clients/{client_d.id}/intakes", json={"title": "Novo projeto"}, headers=admin_headers)
    assert intake.status_code == 201
    blocked_by_intake = client.delete(f"/clients/{client_d.id}", headers=admin_headers)
    assert blocked_by_intake.status_code == 409

    # Um cliente limpo (sem nenhum vínculo) pode ser excluído.
    client_e = make_client_row(db_session, code="CLI-E")
    allowed = client.delete(f"/clients/{client_e.id}", headers=admin_headers)
    assert allowed.status_code == 204
    assert client.get(f"/clients/{client_e.id}", headers=admin_headers).status_code == 404


def test_timesheet_transit_requires_project_and_rejects_task(client, setup):
    """Pedido do usuário: "Traslado" sempre vinculado a um projeto, nunca a
    uma tarefa específica (decisão confirmada)."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    task = client.post(f"/projects/{project_id}/tasks", json={"name": "Tarefa", "wbs_code": "20"}, headers=admin_headers).json()
    consultant_headers = auth_headers(client, setup["consultant"].email)
    client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    )

    no_project = client.post(
        "/timesheets",
        json={"date": "2026-08-20", "start_time": "09:00", "end_time": "10:00", "is_transit": True},
        headers=consultant_headers,
    )
    assert no_project.status_code == 422

    with_task = client.post(
        "/timesheets",
        json={"task_id": task["id"], "date": "2026-08-20", "start_time": "09:00", "end_time": "10:00", "is_transit": True},
        headers=consultant_headers,
    )
    assert with_task.status_code == 422

    ok = client.post(
        "/timesheets",
        json={"project_id": project_id, "date": "2026-08-20", "start_time": "09:00", "end_time": "10:00", "is_transit": True},
        headers=consultant_headers,
    )
    assert ok.status_code == 201
    assert ok.json()["is_transit"] is True
    assert ok.json()["task_id"] is None
    assert ok.json()["project_id"] == project_id


def test_timesheet_transit_has_its_own_bucket_in_financials_by_task_type(client, setup):
    """Pedido do usuário: Traslado aparece como categoria própria nos
    relatórios financeiros (não misturado com Avulso/ADHOC)."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    consultant_headers = auth_headers(client, setup["consultant"].email)
    client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    )
    created = client.post(
        "/timesheets",
        json={"project_id": project_id, "date": "2026-08-20", "start_time": "09:00", "end_time": "11:00", "is_transit": True},
        headers=consultant_headers,
    )
    assert created.status_code == 201

    report = client.get(f"/reports/project/{project_id}", headers=admin_headers).json()
    by_type = report["financials_by_task_type"]
    assert "TRASLADO" in by_type
    assert float(by_type["TRASLADO"]["hours"]) == 2.0


def test_absence_timesheet_rejects_project_task_and_transit(client, setup):
    """Pedido do usuário: ausência da empresa (Férias/Licença Médica/Licença
    Maternidade/Ausência/Folga) é sempre custo interno — nunca pode vir com
    task_id, project_id ou is_transit=True junto (decisão confirmada:
    Traslado é custo do cliente, ausência é custo interno, mutuamente
    exclusivos)."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    task = client.post(f"/projects/{project_id}/tasks", json={"name": "Tarefa", "wbs_code": "30"}, headers=admin_headers).json()
    client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    )
    consultant_headers = auth_headers(client, setup["consultant"].email)

    with_task = client.post(
        "/timesheets",
        json={"task_id": task["id"], "absence_type": "VACATION", "date": "2026-08-25", "start_time": "09:00", "end_time": "17:00"},
        headers=consultant_headers,
    )
    assert with_task.status_code == 422

    with_project = client.post(
        "/timesheets",
        json={"project_id": project_id, "absence_type": "VACATION", "date": "2026-08-25", "start_time": "09:00", "end_time": "17:00"},
        headers=consultant_headers,
    )
    assert with_project.status_code == 422

    with_transit = client.post(
        "/timesheets",
        json={"is_transit": True, "absence_type": "VACATION", "date": "2026-08-25", "start_time": "09:00", "end_time": "17:00"},
        headers=consultant_headers,
    )
    assert with_transit.status_code == 422

    ok = client.post(
        "/timesheets",
        json={"absence_type": "MEDICAL_LEAVE", "date": "2026-08-25", "start_time": "09:00", "end_time": "17:00"},
        headers=consultant_headers,
    )
    assert ok.status_code == 201
    assert ok.json()["absence_type"] == "MEDICAL_LEAVE"
    assert ok.json()["task_id"] is None
    assert ok.json()["project_id"] is None


def test_absence_timesheet_counts_toward_resource_utilization(client, setup):
    """Pedido do usuário: uma semana de ausência não pode parecer recurso
    ocioso — entra normalmente em `actual_hours` (resource_utilization),
    mesmo critério já usado por hora administrativa interna/Traslado."""
    admin_headers = setup["admin_headers"]
    resource = client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    ).json()
    consultant_headers = auth_headers(client, setup["consultant"].email)

    created = client.post(
        "/timesheets",
        json={"absence_type": "VACATION", "date": "2026-08-26", "start_time": "09:00", "end_time": "17:00"},
        headers=consultant_headers,
    )
    assert created.status_code == 201

    utilization = client.get(
        "/resources/utilization",
        params={"start": "2026-08-01", "end": "2026-08-31", "resource_id": resource["id"]},
        headers=admin_headers,
    )
    assert utilization.status_code == 200
    row = utilization.json()[0]
    assert float(row["actual_hours"]) == 8.0


def _assigned_task_timesheet_setup(client, setup):
    """Monta projeto + tarefa + recurso alocado, pronto pra apontar horas —
    extraído pra reusar nos testes de % de Avanço/Retrabalho abaixo."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    task = client.post(f"/projects/{project_id}/tasks", json={"name": "Configurar Módulo", "wbs_code": "40"}, headers=admin_headers).json()
    resource = client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    ).json()
    client.post(f"/tasks/{task['id']}/assignments", json={"resource_id": resource["id"], "allocated_hours": "20"}, headers=admin_headers)
    consultant_headers = auth_headers(client, setup["consultant"].email)
    return task, resource, consultant_headers


def test_timesheet_task_progress_percentage_mirrors_into_task(client, setup):
    """Pedido do usuário: "% de Avanço da Tarefa" na tela de apontamento —
    ao salvar, espelha o valor em Task.progress_percentage (o apontamento é
    o momento em que o consultor reporta o avanço)."""
    admin_headers = setup["admin_headers"]
    task, _resource, consultant_headers = _assigned_task_timesheet_setup(client, setup)

    created = client.post(
        "/timesheets",
        json={
            "task_id": task["id"],
            "date": "2026-08-27",
            "start_time": "09:00",
            "end_time": "13:00",
            "task_progress_percentage": "45",
        },
        headers=consultant_headers,
    )
    assert created.status_code == 201
    assert float(created.json()["task_progress_percentage"]) == 45.0
    assert created.json()["work_classification"] == "NORMAL"
    assert created.json()["rework_reasons"] in (None, [])

    refreshed_task = client.get(f"/tasks/{task['id']}", headers=admin_headers).json()
    assert float(refreshed_task["progress_percentage"]) == 45.0

    # Sem informar o % num apontamento seguinte, o progresso já registrado
    # na tarefa não é mexido.
    second = client.post(
        "/timesheets",
        json={"task_id": task["id"], "date": "2026-08-28", "start_time": "09:00", "end_time": "10:00"},
        headers=consultant_headers,
    )
    assert second.status_code == 201
    assert second.json()["task_progress_percentage"] is None
    still_task = client.get(f"/tasks/{task['id']}", headers=admin_headers).json()
    assert float(still_task["progress_percentage"]) == 45.0


def test_timesheet_rework_requires_at_least_one_reason(client, setup):
    """Pedido do usuário: classificar o apontamento como Retrabalho exige
    ao menos um motivo de uma lista fixa."""
    task, _resource, consultant_headers = _assigned_task_timesheet_setup(client, setup)

    no_reason = client.post(
        "/timesheets",
        json={"task_id": task["id"], "date": "2026-08-27", "start_time": "09:00", "end_time": "10:00", "work_classification": "REWORK"},
        headers=consultant_headers,
    )
    assert no_reason.status_code == 422

    with_reason = client.post(
        "/timesheets",
        json={
            "task_id": task["id"],
            "date": "2026-08-27",
            "start_time": "09:00",
            "end_time": "10:00",
            "work_classification": "REWORK",
            "rework_reasons": ["PRODUCT_ERROR", "CONSULTANT_CHANGE"],
        },
        headers=consultant_headers,
    )
    assert with_reason.status_code == 201
    assert with_reason.json()["work_classification"] == "REWORK"
    assert sorted(with_reason.json()["rework_reasons"]) == ["CONSULTANT_CHANGE", "PRODUCT_ERROR"]

    # Normal (padrão quando omitido) não aceita motivo nenhum.
    normal_with_reason = client.post(
        "/timesheets",
        json={
            "task_id": task["id"],
            "date": "2026-08-27",
            "start_time": "10:00",
            "end_time": "11:00",
            "rework_reasons": ["PRODUCT_ERROR"],
        },
        headers=consultant_headers,
    )
    assert normal_with_reason.status_code == 422


def test_timesheet_rework_and_progress_only_accepted_with_task_id(client, setup):
    """Pedido do usuário: % de Avanço e o classificador Normal/Retrabalho
    só fazem sentido num apontamento de tarefa do projeto — Traslado não
    aceita nenhum dos dois."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    )
    consultant_headers = auth_headers(client, setup["consultant"].email)

    with_progress = client.post(
        "/timesheets",
        json={"project_id": project_id, "is_transit": True, "date": "2026-08-27", "start_time": "09:00", "end_time": "10:00", "task_progress_percentage": "50"},
        headers=consultant_headers,
    )
    assert with_progress.status_code == 422

    with_classification = client.post(
        "/timesheets",
        json={"project_id": project_id, "is_transit": True, "date": "2026-08-27", "start_time": "09:00", "end_time": "10:00", "work_classification": "NORMAL"},
        headers=consultant_headers,
    )
    assert with_classification.status_code == 422

    with_reasons = client.post(
        "/timesheets",
        json={"project_id": project_id, "is_transit": True, "date": "2026-08-27", "start_time": "09:00", "end_time": "10:00", "rework_reasons": ["PRODUCT_ERROR"]},
        headers=consultant_headers,
    )
    assert with_reasons.status_code == 422


def test_service_order_activity_includes_work_classification_and_reasons(client, setup):
    """Pedido do usuário: a Ordem de Serviço imprime, por tarefa, a
    classificação Normal/Retrabalho e o(s) motivo(s) de retrabalho — ver
    ServiceOrderPrintSheet.jsx. `GET /reports/service-orders` é quem
    alimenta tanto a tabela quanto a impressão, então basta confirmar que
    `service_orders` (services.py) repassa os dois campos do Timesheet."""
    task, _resource, consultant_headers = _assigned_task_timesheet_setup(client, setup)
    admin_headers = setup["admin_headers"]

    created = client.post(
        "/timesheets",
        json={
            "task_id": task["id"],
            "date": "2026-08-27",
            "start_time": "09:00",
            "end_time": "10:00",
            "work_classification": "REWORK",
            "rework_reasons": ["DATA_LOAD_ERROR"],
        },
        headers=consultant_headers,
    )
    assert created.status_code == 201

    report = client.get(
        "/reports/service-orders",
        params={"start": "2026-08-27", "end": "2026-08-27", "project_id": setup["project_a"].id},
        headers=admin_headers,
    )
    assert report.status_code == 200
    orders = report.json()
    assert len(orders) == 1
    activities = orders[0]["activities"]
    assert len(activities) == 1
    assert activities[0]["work_classification"] == "REWORK"
    assert activities[0]["rework_reasons"] == ["DATA_LOAD_ERROR"]


def test_schedule_blocked_on_resource_absence_day(client, setup):
    """Pedido do usuário ("Sim, já incluir nesta etapa"): a Agenda de
    consultores não pode agendar um recurso num dia em que ele tem ausência
    registrada — bloqueio por RECURSO, não o dia inteiro pra todo mundo."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    resource = client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    ).json()
    consultant_headers = auth_headers(client, setup["consultant"].email)

    absence = client.post(
        "/timesheets",
        json={"absence_type": "DAY_OFF", "date": "2026-08-27", "start_time": "09:00", "end_time": "17:00"},
        headers=consultant_headers,
    )
    assert absence.status_code == 201

    blocked = client.post(
        "/resource-schedules",
        json={"resource_id": resource["id"], "project_id": project_id, "date": "2026-08-27", "start_time": "09:00", "end_time": "12:00"},
        headers=admin_headers,
    )
    assert blocked.status_code == 409

    # Noutro dia, sem ausência, o mesmo recurso agenda normalmente.
    ok = client.post(
        "/resource-schedules",
        json={"resource_id": resource["id"], "project_id": project_id, "date": "2026-08-28", "start_time": "09:00", "end_time": "12:00"},
        headers=admin_headers,
    )
    assert ok.status_code == 201

    # Mover (PATCH date) esse agendamento pro dia da ausência também é
    # bloqueado — mesma checagem de criação.
    moved = client.patch(f"/resource-schedules/{ok.json()['id']}", json={"date": "2026-08-27"}, headers=admin_headers)
    assert moved.status_code == 409

    # Rejeitar a ausência libera o dia de novo — REJECTED não conta (mesmo
    # critério de financials_by_task_type/project_burndown).
    status_update = client.patch(f"/timesheets/{absence.json()['id']}/status", json={"status": "REJECTED"}, headers=admin_headers)
    assert status_update.status_code == 200
    now_ok = client.post(
        "/resource-schedules",
        json={"resource_id": resource["id"], "project_id": project_id, "date": "2026-08-27", "start_time": "13:00", "end_time": "15:00"},
        headers=admin_headers,
    )
    assert now_ok.status_code == 201


def test_schedule_tasks_checklist(client, setup):
    """Pedido do usuário: um bloco da Agenda pode levar uma ou mais tarefas
    — sem hora própria, só uma lista do que o consultor precisa trabalhar
    naquele horário (ver ResourceScheduleTask, app/models.py). Precisam
    pertencer ao mesmo projeto do agendamento e não ter tarefas-filhas
    (mesma regra do apontamento de horas)."""
    project_a_id = setup["project_a"].id
    project_b_id = setup["project_b"].id
    admin_headers = setup["admin_headers"]
    resource = client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    ).json()

    parent = client.post(f"/projects/{project_a_id}/tasks", json={"name": "Compras", "wbs_code": "50"}, headers=admin_headers).json()
    child = client.post(
        f"/projects/{project_a_id}/tasks",
        json={"name": "Configurar Cotação", "wbs_code": "50.1", "parent_task_id": parent["id"]},
        headers=admin_headers,
    ).json()
    other_task = client.post(
        f"/projects/{project_a_id}/tasks", json={"name": "Configurar Pedido de Compras", "wbs_code": "51"}, headers=admin_headers
    ).json()
    task_other_project = client.post(
        f"/projects/{project_b_id}/tasks", json={"name": "Tarefa de outro projeto", "wbs_code": "1"}, headers=admin_headers
    ).json()

    # Tarefa de outro projeto é recusada.
    wrong_project = client.post(
        "/resource-schedules",
        json={
            "resource_id": resource["id"],
            "project_id": project_a_id,
            "date": "2026-08-29",
            "start_time": "08:00",
            "end_time": "18:00",
            "task_ids": [task_other_project["id"]],
        },
        headers=admin_headers,
    )
    assert wrong_project.status_code == 422

    # Tarefa "pai" (tem tarefa-filha) é recusada — só tarefa-folha.
    is_parent = client.post(
        "/resource-schedules",
        json={
            "resource_id": resource["id"],
            "project_id": project_a_id,
            "date": "2026-08-29",
            "start_time": "08:00",
            "end_time": "18:00",
            "task_ids": [parent["id"]],
        },
        headers=admin_headers,
    )
    assert is_parent.status_code == 422

    # Duas tarefas-folha do mesmo projeto: ok, aparecem na leitura.
    created = client.post(
        "/resource-schedules",
        json={
            "resource_id": resource["id"],
            "project_id": project_a_id,
            "date": "2026-08-29",
            "start_time": "08:00",
            "end_time": "18:00",
            "task_ids": [child["id"], other_task["id"]],
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    created_body = created.json()
    assert {t["id"] for t in created_body["tasks"]} == {child["id"], other_task["id"]}

    # PATCH substitui a lista inteira (não soma) — e sem informar task_ids,
    # a lista existente permanece intacta (mesmo critério de PATCH parcial
    # do resto do endpoint).
    untouched = client.patch(f"/resource-schedules/{created_body['id']}", json={"description": "ajuste"}, headers=admin_headers)
    assert untouched.status_code == 200
    assert {t["id"] for t in untouched.json()["tasks"]} == {child["id"], other_task["id"]}

    replaced = client.patch(
        f"/resource-schedules/{created_body['id']}", json={"task_ids": [other_task["id"]]}, headers=admin_headers
    )
    assert replaced.status_code == 200
    assert [t["id"] for t in replaced.json()["tasks"]] == [other_task["id"]]

    cleared = client.patch(f"/resource-schedules/{created_body['id']}", json={"task_ids": []}, headers=admin_headers)
    assert cleared.status_code == 200


def test_schedule_blocks_when_resource_level_below_task_min_level(client, setup):
    """Pedido do usuário: cruza o Nível do recurso com o Nível mínimo da
    tarefa — nível menor bloqueia o agendamento inteiro e a mensagem lista
    qual(is) tarefa(s) travaram. Nível igual ou maior passa normalmente, e
    um recurso sem nível definido nunca é bloqueado (mesmo critério do
    seletor de recursos da aba Tarefas)."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]

    level_1_resource = client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "level": 1, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    ).json()
    no_level_resource = client.post(
        "/resources",
        json={"user_id": setup["client_pm_a"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    ).json()
    assert no_level_resource["level"] is None

    task_level_2 = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Entrevista com o cliente", "wbs_code": "60", "min_level": 2}, headers=admin_headers
    ).json()
    task_level_1 = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Checklist simples", "wbs_code": "61", "min_level": 1}, headers=admin_headers
    ).json()

    # Nível 1 x mínimo 2: bloqueia, e a mensagem aponta a tarefa que travou.
    blocked = client.post(
        "/resource-schedules",
        json={
            "resource_id": level_1_resource["id"],
            "project_id": project_id,
            "date": "2026-08-29",
            "start_time": "08:00",
            "end_time": "18:00",
            "task_ids": [task_level_1["id"], task_level_2["id"]],
        },
        headers=admin_headers,
    )
    assert blocked.status_code == 422
    assert "60" in blocked.json()["detail"]
    assert "61" not in blocked.json()["detail"]

    # Mesmo recurso, só a tarefa de nível 1: passa normalmente.
    allowed = client.post(
        "/resource-schedules",
        json={
            "resource_id": level_1_resource["id"],
            "project_id": project_id,
            "date": "2026-08-29",
            "start_time": "08:00",
            "end_time": "18:00",
            "task_ids": [task_level_1["id"]],
        },
        headers=admin_headers,
    )
    assert allowed.status_code == 201

    # Recurso sem nível definido: nunca bloqueia, mesmo na tarefa de nível 2.
    allowed_no_level = client.post(
        "/resource-schedules",
        json={
            "resource_id": no_level_resource["id"],
            "project_id": project_id,
            "date": "2026-08-29",
            "start_time": "08:00",
            "end_time": "18:00",
            "task_ids": [task_level_2["id"]],
        },
        headers=admin_headers,
    )
    assert allowed_no_level.status_code == 201

    # PATCH também revalida — trocar pra uma lista com a tarefa de nível 2
    # continua bloqueado pro recurso nível 1 (o resource_id do agendamento já
    # criado não muda, PATCH não aceita esse campo).
    patched = client.patch(
        f"/resource-schedules/{allowed.json()['id']}", json={"task_ids": [task_level_2["id"]]}, headers=admin_headers
    )
    assert patched.status_code == 422
    assert "60" in patched.json()["detail"]
    assert cleared.json()["tasks"] == []

    # Trocar o projeto do agendamento sem informar task_ids limpa as tarefas
    # vinculadas — elas eram do projeto antigo e não fazem mais sentido.
    with_task = client.patch(
        f"/resource-schedules/{created_body['id']}", json={"task_ids": [other_task["id"]]}, headers=admin_headers
    )
    assert with_task.status_code == 200
    project_changed = client.patch(
        f"/resource-schedules/{created_body['id']}", json={"project_id": project_b_id}, headers=admin_headers
    )
    assert project_changed.status_code == 200
    assert project_changed.json()["tasks"] == []


def test_hours_breakdown_report_aggregates_project_transit_and_absence_hours(client, setup):
    """Pedido do usuário: um relatório que acompanhe, no mesmo lugar, horas
    de projeto, Traslado e ausência — totais da empresa e por consultor
    ("os dois níveis", decisão confirmada). Ver hours_breakdown_report em
    app/services.py e GET /reports/hours-breakdown."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    resource = client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    ).json()
    # Pedido do usuário: projeto sem tarefa (nem Traslado) não é mais um
    # apontamento válido — precisa de uma tarefa de verdade pra gerar
    # project_hours (ver _resolve_task_and_project, routers/timesheets.py).
    task = client.post(f"/projects/{project_id}/tasks", json={"name": "Entrega", "wbs_code": "40"}, headers=admin_headers).json()
    consultant_headers = auth_headers(client, setup["consultant"].email)

    # 2h de projeto (na tarefa).
    client.post(
        "/timesheets",
        json={"task_id": task["id"], "date": "2026-08-20", "start_time": "09:00", "end_time": "11:00"},
        headers=consultant_headers,
    )
    # 3h de Traslado (sempre vinculado a projeto, sem tarefa).
    client.post(
        "/timesheets",
        json={"project_id": project_id, "date": "2026-08-20", "start_time": "11:00", "end_time": "14:00", "is_transit": True},
        headers=consultant_headers,
    )
    # 8h de ausência (Férias).
    client.post(
        "/timesheets",
        json={"absence_type": "VACATION", "date": "2026-08-21", "start_time": "09:00", "end_time": "17:00"},
        headers=consultant_headers,
    )
    # 1h administrativa interna (sem projeto/tarefa/traslado/ausência).
    client.post(
        "/timesheets",
        json={"date": "2026-08-22", "start_time": "09:00", "end_time": "10:00"},
        headers=consultant_headers,
    )
    # Fora do período filtrado abaixo — não deve entrar nos totais.
    client.post(
        "/timesheets",
        json={"task_id": task["id"], "date": "2026-09-05", "start_time": "09:00", "end_time": "11:00"},
        headers=consultant_headers,
    )

    report = client.get(
        "/reports/hours-breakdown",
        params={"start": "2026-08-01", "end": "2026-08-31"},
        headers=admin_headers,
    )
    assert report.status_code == 200
    body = report.json()

    totals = body["totals"]
    assert float(totals["project_hours"]) == 2.0
    assert float(totals["transit_hours"]) == 3.0
    assert float(totals["internal_hours"]) == 1.0
    assert float(totals["absence_hours"]["VACATION"]) == 8.0
    assert float(totals["absence_hours"]["MEDICAL_LEAVE"]) == 0.0

    assert len(body["by_resource"]) == 1
    by_resource = body["by_resource"][0]
    assert by_resource["resource_id"] == resource["id"]
    assert float(by_resource["project_hours"]) == 2.0
    assert float(by_resource["transit_hours"]) == 3.0
    assert float(by_resource["internal_hours"]) == 1.0
    assert float(by_resource["absence_hours"]["VACATION"]) == 8.0

    assert len(body["by_project"]) == 1
    by_project = body["by_project"][0]
    assert by_project["project_id"] == project_id
    assert float(by_project["hours"]) == 2.0


def test_hours_breakdown_report_allowed_for_internal_pm_but_not_consultant(client, setup):
    """Reorganização de menus (pedido do usuário): Relatórios passou a
    aparecer também pro Gerente de Projetos, com o relatório completo
    liberado (mesmo que ele exponha ausência/horas de TODOS os recursos da
    empresa, não só dos projetos que o INTERNAL_PM gerencia) — decisão
    confirmada com o usuário, que pretende tratar relatórios por projeto
    separadamente no futuro. Continua restrito a MANAGEMENT_ROLES — o
    Consultor, que nunca teve Relatórios no menu, segue barrado."""
    pm_headers = auth_headers(client, setup["pm"].email)
    allowed = client.get(
        "/reports/hours-breakdown",
        params={"start": "2026-08-01", "end": "2026-08-31"},
        headers=pm_headers,
    )
    assert allowed.status_code == 200

    consultant_headers = auth_headers(client, setup["consultant"].email)
    denied = client.get(
        "/reports/hours-breakdown",
        params={"start": "2026-08-01", "end": "2026-08-31"},
        headers=consultant_headers,
    )
    assert denied.status_code == 403


def test_cannot_timesheet_parent_task_only_child(client, setup):
    """Pedido do usuário: não permitir apontamento em tarefa "pai" (que tem
    tarefas-filhas) — só nas tarefas-filha."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    parent = client.post(f"/projects/{project_id}/tasks", json={"name": "Pai", "wbs_code": "21"}, headers=admin_headers).json()
    child = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Filha", "wbs_code": "21.1", "parent_task_id": parent["id"]},
        headers=admin_headers,
    ).json()
    resource = client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    ).json()
    client.post(f"/tasks/{parent['id']}/assignments", json={"resource_id": resource["id"], "allocated_hours": "5"}, headers=admin_headers)
    client.post(f"/tasks/{child['id']}/assignments", json={"resource_id": resource["id"], "allocated_hours": "5"}, headers=admin_headers)
    consultant_headers = auth_headers(client, setup["consultant"].email)

    on_parent = client.post(
        "/timesheets",
        json={"task_id": parent["id"], "date": "2026-08-20", "start_time": "09:00", "end_time": "10:00"},
        headers=consultant_headers,
    )
    assert on_parent.status_code == 422

    on_child = client.post(
        "/timesheets",
        json={"task_id": child["id"], "date": "2026-08-20", "start_time": "09:00", "end_time": "10:00"},
        headers=consultant_headers,
    )
    assert on_child.status_code == 201


def test_project_margin_percentage_is_declared_and_hidden_from_external_roles(client, setup):
    """Pedido do usuário: "% de Margem vendida" no cadastro do projeto — um
    valor digitado direto (não calculado), escondido de perfil externo
    igual aos outros campos financeiros."""
    admin_headers = setup["admin_headers"]
    created = client.post(
        "/projects",
        json={
            "client_id": setup["client_a"].id,
            "manager_id": setup["pm"].id,
            "code": "PRJ-MARGEM",
            "name": "Projeto com margem",
            "management_hours": "10",
            "management_rate": "100",
            "margin_percentage": "35.5",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    assert float(created.json()["margin_percentage"]) == 35.5
    project_id = created.json()["id"]

    client_pm_headers = auth_headers(client, setup["client_pm_a"].email)
    external_read = client.get(f"/projects/{project_id}", headers=client_pm_headers)
    # client_pm_a é do client_a, mas este projeto é do client_a também —
    # ainda assim os campos financeiros (incluindo margin_percentage) devem
    # vir ocultos pra perfil externo.
    assert external_read.status_code == 200
    assert external_read.json()["margin_percentage"] is None

    cleared = client.patch(f"/projects/{project_id}", json={"margin_percentage": None}, headers=admin_headers)
    assert cleared.status_code == 200
    assert cleared.json()["margin_percentage"] is None


# ---------------------------------------------------------------------------
# "melhorias, parte 4"
# ---------------------------------------------------------------------------


def test_resource_function_and_level_are_optional_and_structured(client, setup):
    """Pedido do usuário: Função (categoria) e Nível (1 a 4) substituem o
    antigo campo de texto livre "role_title" — dois campos independentes,
    ambos opcionais (decisão confirmada: sem migração automática do texto
    livre, cada recurso recebe os valores quando alguém editar)."""
    admin_headers = setup["admin_headers"]

    no_function_no_level = client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    )
    assert no_function_no_level.status_code == 201
    assert no_function_no_level.json()["function"] is None
    assert no_function_no_level.json()["level"] is None

    with_both = client.patch(
        f"/resources/{no_function_no_level.json()['id']}",
        json={"function": "DEVELOPER", "level": 4},
        headers=admin_headers,
    )
    assert with_both.status_code == 200
    assert with_both.json()["function"] == "DEVELOPER"
    assert with_both.json()["level"] == 4


def test_resource_level_must_be_between_1_and_4(client, setup):
    admin_headers = setup["admin_headers"]
    out_of_range = client.post(
        "/resources",
        json={
            "user_id": setup["consultant"].id,
            "function": "CONSULTANT",
            "level": 5,
            "internal_cost_per_hour": "50",
            "billing_rate_per_hour": "100",
        },
        headers=admin_headers,
    )
    assert out_of_range.status_code == 422


def test_task_min_level_defaults_to_1_and_is_validated(client, setup):
    """Pedido do usuário: "Nível mínimo" da tarefa — obrigatório (decisão
    confirmada), default 1 ("qualquer nível serve") pra não travar criação
    de tarefas que não se importam com nível."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]

    default_level = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Sem nível informado", "wbs_code": "30"}, headers=admin_headers
    )
    assert default_level.status_code == 201
    assert default_level.json()["min_level"] == 1

    explicit_level = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Nível 3", "wbs_code": "31", "min_level": 3},
        headers=admin_headers,
    )
    assert explicit_level.status_code == 201
    assert explicit_level.json()["min_level"] == 3

    out_of_range = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Nível inválido", "wbs_code": "32", "min_level": 5},
        headers=admin_headers,
    )
    assert out_of_range.status_code == 422

    updated = client.patch(f"/tasks/{explicit_level.json()['id']}", json={"min_level": 2}, headers=admin_headers)
    assert updated.status_code == 200
    assert updated.json()["min_level"] == 2


# ---------------------------------------------------------------------------
# "melhorias, parte 5"
# ---------------------------------------------------------------------------


def test_task_modality_defaults_to_both_and_can_be_set(client, setup):
    """Pedido do usuário: campo indicando se a tarefa pode ser feita
    Remotamente/Presencial/Ambos — puramente informativo, default BOTH
    ("qualquer modalidade serve", mesmo espírito do default de min_level)."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]

    default_modality = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Sem modalidade informada", "wbs_code": "40"}, headers=admin_headers
    )
    assert default_modality.status_code == 201
    assert default_modality.json()["modality"] == "BOTH"

    remote_task = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Remota", "wbs_code": "41", "modality": "REMOTE"},
        headers=admin_headers,
    )
    assert remote_task.status_code == 201
    assert remote_task.json()["modality"] == "REMOTE"

    updated = client.patch(f"/tasks/{remote_task.json()['id']}", json={"modality": "ON_SITE"}, headers=admin_headers)
    assert updated.status_code == 200
    assert updated.json()["modality"] == "ON_SITE"

    invalid = client.post(
        f"/projects/{project_id}/tasks",
        json={"name": "Modalidade inválida", "wbs_code": "42", "modality": "HYBRID"},
        headers=admin_headers,
    )
    assert invalid.status_code == 422


def test_project_financeiro_shows_planned_and_real_margin(client, setup):
    """Pedido do usuário: % Margem Planejada (declarada na venda) e % Margem
    Real (calculada a partir do custo efetivo) lado a lado no Financeiro do
    projeto."""
    admin_headers = setup["admin_headers"]
    project_id = setup["project_a"].id

    with_margin = client.patch(f"/projects/{project_id}", json={"margin_percentage": "25.50"}, headers=admin_headers)
    assert with_margin.status_code == 200
    assert float(with_margin.json()["margin_percentage"]) == 25.5

    detail = client.get(f"/projects/{project_id}", headers=admin_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert float(body["margin_percentage"]) == 25.5
    assert "real_margin_percentage" in body["financials"]


# ---------------------------------------------------------------------------
# Grupos de Tarefas (TaskGroup) — agrupador reutilizável de tarefas, pedido
# do usuário pra acelerar a criação de projetos parecidos: um molde de
# estrutura (sem projeto por trás) aplicado depois como tarefas-filhas de
# uma tarefa de um projeto real.
# ---------------------------------------------------------------------------


def _sample_task_group_payload():
    """Grupo com dois níveis de aninhamento: uma "fase" de topo com duas
    sub-tarefas, e uma segunda "fase" de topo sem filhas — cobre hierarquia
    aninhada de verdade (não só uma lista achatada)."""
    return {
        "name": "Implantação módulo Fiscal",
        "description": "Sequência padrão de tarefas pra implantar o módulo Fiscal.",
        "items": [
            {
                "name": "Levantamento",
                "task_type": "CONSULTING",
                "duration_days": "2",
                "estimated_hours": "16",
                "children": [
                    {"name": "Entrevista com o cliente", "duration_days": "1", "estimated_hours": "8"},
                    {"name": "Documentar requisitos", "duration_days": "1", "estimated_hours": "4"},
                ],
            },
            {
                "name": "Configuração inicial",
                "duration_days": "3",
                "estimated_hours": "24",
                "is_milestone": True,
                "min_level": 3,
            },
        ],
    }


def test_task_group_crud_preserves_nested_hierarchy(client, setup):
    admin_headers = setup["admin_headers"]

    created = client.post("/task-groups", json=_sample_task_group_payload(), headers=admin_headers)
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Implantação módulo Fiscal"
    assert len(body["items"]) == 2
    levantamento = body["items"][0]
    assert levantamento["name"] == "Levantamento"
    assert len(levantamento["children"]) == 2
    assert {child["name"] for child in levantamento["children"]} == {"Entrevista com o cliente", "Documentar requisitos"}
    assert body["items"][1]["is_milestone"] is True
    # Nível mínimo (pedido do usuário: "ter o campo de Nivel mínimo igual
    # nas tarefas dos projetos") — informado no item persiste, e um item sem
    # o campo (os filhos de "Levantamento") cai no default (1), mesmo
    # critério de Task.min_level.
    assert body["items"][1]["min_level"] == 3
    assert levantamento["min_level"] == 1
    assert all(child["min_level"] == 1 for child in levantamento["children"])

    listed = client.get("/task-groups", headers=admin_headers)
    assert listed.status_code == 200
    assert any(g["id"] == body["id"] for g in listed.json())

    fetched = client.get(f"/task-groups/{body['id']}", headers=admin_headers)
    assert fetched.status_code == 200
    assert len(fetched.json()["items"][0]["children"]) == 2

    # PUT substitui a árvore inteira (apaga tudo e recria) — uma edição que
    # remove uma sub-tarefa e renomeia o grupo precisa refletir exatamente
    # isso, sem sobra da árvore anterior.
    replaced_payload = _sample_task_group_payload()
    replaced_payload["name"] = "Implantação módulo Fiscal (revisado)"
    replaced_payload["items"][0]["children"] = [{"name": "Entrevista com o cliente", "duration_days": "1"}]
    updated = client.put(f"/task-groups/{body['id']}", json=replaced_payload, headers=admin_headers)
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["name"] == "Implantação módulo Fiscal (revisado)"
    assert len(updated_body["items"][0]["children"]) == 1

    deleted = client.delete(f"/task-groups/{body['id']}", headers=admin_headers)
    assert deleted.status_code == 204
    assert client.get(f"/task-groups/{body['id']}", headers=admin_headers).status_code == 404


def test_task_group_management_restricted_to_management_roles(client, setup):
    """Mesmo critério de quem administra Projetos/Tarefas em geral
    (MANAGEMENT_ROLES) — Consultor não pode gerenciar Grupos de Tarefas."""
    consultant_headers = auth_headers(client, setup["consultant"].email)
    denied = client.post("/task-groups", json=_sample_task_group_payload(), headers=consultant_headers)
    assert denied.status_code == 403

    denied_list = client.get("/task-groups", headers=consultant_headers)
    assert denied_list.status_code == 403


def test_apply_task_group_clones_tree_as_children_and_recalculates_wbs(client, setup):
    admin_headers = setup["admin_headers"]
    project_id = setup["project_a"].id

    group = client.post("/task-groups", json=_sample_task_group_payload(), headers=admin_headers).json()
    parent_task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Fase Fiscal", "wbs_code": "1"}, headers=admin_headers
    ).json()

    applied = client.post(
        f"/tasks/{parent_task['id']}/apply-task-group", json={"task_group_id": group["id"]}, headers=admin_headers
    )
    assert applied.status_code == 201

    schedule = client.get(f"/projects/{project_id}/schedule", headers=admin_headers).json()
    tasks_by_name = {t["name"]: t for t in schedule["tasks"]}
    # A tarefa "envelope" com o NOME do grupo é criada primeiro, como filha
    # de "Fase Fiscal" — pedido do usuário depois de ver a primeira versão
    # (que jogava os itens direto como filhas da tarefa pai, sem indicar de
    # qual grupo cada um vinha): "o Agrupador precisa ser uma tarefa
    # também, e as subtarefas dele vêm como filhas do [grupo]".
    assert "Implantação módulo Fiscal" in tasks_by_name
    assert "Levantamento" in tasks_by_name
    assert "Configuração inicial" in tasks_by_name
    assert "Entrevista com o cliente" in tasks_by_name
    assert "Documentar requisitos" in tasks_by_name

    # WBS/EAP renumerado: a tarefa envelope entra como filha da tarefa "1"
    # (Fase Fiscal), e os itens do grupo entram como filhas DELA — não mais
    # direto em "Fase Fiscal". Nenhum "_tmp_" (placeholder provisório de
    # apply_task_group_to_task) deve sobrar depois do recalculate_wbs que o
    # endpoint roda em seguida.
    group_wrapper = tasks_by_name["Implantação módulo Fiscal"]
    assert group_wrapper["parent_task_id"] == parent_task["id"]
    assert group_wrapper["wbs_code"].startswith("1.")
    assert tasks_by_name["Levantamento"]["parent_task_id"] == group_wrapper["id"]
    assert tasks_by_name["Configuração inicial"]["parent_task_id"] == group_wrapper["id"]
    assert tasks_by_name["Levantamento"]["wbs_code"].startswith(f"{group_wrapper['wbs_code']}.")
    assert tasks_by_name["Entrevista com o cliente"]["parent_task_id"] == tasks_by_name["Levantamento"]["id"]
    assert tasks_by_name["Entrevista com o cliente"]["wbs_code"].startswith(f"{tasks_by_name['Levantamento']['wbs_code']}.")
    assert not any(t["wbs_code"].startswith("_tmp_") for t in schedule["tasks"])

    # Nenhuma tarefa clonada carrega data planejada nem alocação — o grupo
    # não traz nenhum dos dois (ver docstring de apply_task_group_to_task).
    assert tasks_by_name["Configuração inicial"]["planned_start_date"] is None

    # Duração e Trabalho (horas) são copiados direto do item do grupo, sem
    # passar pelo motor effort-driven (o usuário pediu pra informar a
    # quantidade de horas de cada tarefa já no próprio molde).
    assert float(tasks_by_name["Configuração inicial"]["estimated_hours"]) == 24
    assert float(tasks_by_name["Entrevista com o cliente"]["estimated_hours"]) == 8

    # Nível mínimo do item do grupo vira o Nível mínimo da tarefa clonada —
    # é o que permite já chegar com essa informação pronta (sem precisar
    # reconfigurar tarefa por tarefa depois de aplicar o grupo), inclusive
    # entrando na validação de agenda (ver _resolve_schedule_tasks).
    assert tasks_by_name["Configuração inicial"]["min_level"] == 3
    assert tasks_by_name["Levantamento"]["min_level"] == 1


def test_apply_task_group_rejects_unknown_group(client, setup):
    admin_headers = setup["admin_headers"]
    project_id = setup["project_a"].id
    parent_task = client.post(
        f"/projects/{project_id}/tasks", json={"name": "Fase", "wbs_code": "1"}, headers=admin_headers
    ).json()

    response = client.post(
        f"/tasks/{parent_task['id']}/apply-task-group", json={"task_group_id": "id-inexistente"}, headers=admin_headers
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Processo de envio de e-mails (configurador de SMTP + avisos automáticos)
# ---------------------------------------------------------------------------


def test_email_settings_crud_restricted_to_admin_like_roles(client, setup):
    """Pedido do usuário: configurador de dados de SMTP numa tela de
    Configurações, ADMIN_LIKE_ROLES (mesmo critério de Usuários/Clientes —
    dado sensível). Sem nada salvo ainda, GET devolve um "formulário em
    branco" em vez de 404 (a tela sempre tem o que mostrar)."""
    admin_headers = setup["admin_headers"]
    pm_headers = auth_headers(client, setup["pm"].email)

    blank = client.get("/email-settings", headers=admin_headers)
    assert blank.status_code == 200
    blank_body = blank.json()
    assert blank_body["id"] is None
    assert blank_body["enabled"] is False
    assert blank_body["password_configured"] is False
    assert blank_body["updated_at"] is None

    denied_get = client.get("/email-settings", headers=pm_headers)
    assert denied_get.status_code == 403
    denied_put = client.put(
        "/email-settings",
        json={"enabled": True, "smtp_host": "smtp.exemplo.com", "smtp_port": 587, "from_email": "nao-responda@exemplo.com"},
        headers=pm_headers,
    )
    assert denied_put.status_code == 403

    saved = client.put(
        "/email-settings",
        json={
            "enabled": True,
            "smtp_host": "smtp.exemplo.com",
            "smtp_port": 587,
            "security": "STARTTLS",
            "smtp_username": "no-reply@exemplo.com",
            "smtp_password": "senha-smtp-super-secreta",
            "from_email": "no-reply@exemplo.com",
            "from_name": "ProjmanagerPy",
        },
        headers=admin_headers,
    )
    assert saved.status_code == 200
    saved_body = saved.json()
    assert saved_body["id"] is not None
    assert saved_body["password_configured"] is True
    # A senha nunca volta na resposta, de jeito nenhum — nem como campo
    # dedicado nem escondida em outro lugar do payload.
    assert "senha-smtp-super-secreta" not in saved.text
    assert "smtp_password" not in saved_body

    fetched_again = client.get("/email-settings", headers=admin_headers)
    assert fetched_again.json()["smtp_host"] == "smtp.exemplo.com"


def test_email_settings_update_keeps_password_or_clears_explicitly(client, setup):
    """Omitir `smtp_password` num PUT seguinte mantém a senha já salva
    (não precisa redigitar a senha toda vez que só quer trocar o host,
    por exemplo); `smtp_password: ""` explícito apaga a senha salva."""
    admin_headers = setup["admin_headers"]
    client.put(
        "/email-settings",
        json={"enabled": False, "smtp_host": "smtp.a.com", "smtp_port": 587, "smtp_password": "senha-1", "from_email": "a@a.com"},
        headers=admin_headers,
    )

    updated = client.put(
        "/email-settings",
        json={"enabled": False, "smtp_host": "smtp.b.com", "smtp_port": 465, "security": "SSL", "from_email": "a@a.com"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["password_configured"] is True
    assert updated.json()["smtp_host"] == "smtp.b.com"

    cleared = client.put(
        "/email-settings",
        json={
            "enabled": False,
            "smtp_host": "smtp.b.com",
            "smtp_port": 465,
            "security": "SSL",
            "smtp_password": "",
            "from_email": "a@a.com",
        },
        headers=admin_headers,
    )
    assert cleared.status_code == 200
    assert cleared.json()["password_configured"] is False


class _FakeSmtpConnection:
    """Dublê de `smtplib.SMTP`/`SMTP_SSL` — grava o que seria mandado de
    verdade, sem nenhuma conexão de rede (este ambiente de desenvolvimento
    não tem rede até um servidor SMTP real, ver docstring de EmailSettings
    em app/models.py)."""

    instances: list["_FakeSmtpConnection"] = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.tls_started = False
        self.logged_in = None
        self.sent = None
        _FakeSmtpConnection.instances.append(self)

    def starttls(self):
        self.tls_started = True

    def login(self, username, password):
        self.logged_in = (username, password)

    def sendmail(self, from_addr, to_addrs, msg):
        self.sent = (from_addr, to_addrs, msg)

    def quit(self):
        pass


def test_email_settings_test_email_sends_via_configured_smtp(client, setup, monkeypatch):
    """Botão "Enviar e-mail de teste" — manda de verdade pros dados JÁ
    SALVOS, mesmo com "Ativo" ainda desligado (precisa poder validar as
    credenciais antes de ligar pra valer), e grava o resultado em
    `last_test_*` sem alterar o `enabled` salvo."""
    admin_headers = setup["admin_headers"]
    client.put(
        "/email-settings",
        json={
            "enabled": False,
            "smtp_host": "smtp.exemplo.com",
            "smtp_port": 587,
            "security": "STARTTLS",
            "smtp_username": "no-reply@exemplo.com",
            "smtp_password": "senha-smtp",
            "from_email": "no-reply@exemplo.com",
        },
        headers=admin_headers,
    )

    _FakeSmtpConnection.instances = []
    monkeypatch.setattr("app.email_service.smtplib.SMTP", _FakeSmtpConnection)

    tested = client.post("/email-settings/test-email", json={"to_email": "destino@exemplo.com"}, headers=admin_headers)
    assert tested.status_code == 200
    body = tested.json()
    assert body["last_test_ok"] is True
    assert body["last_test_error"] is None
    assert body["last_test_at"] is not None
    assert body["enabled"] is False  # não liga sozinho

    assert len(_FakeSmtpConnection.instances) == 1
    sent_instance = _FakeSmtpConnection.instances[0]
    assert sent_instance.logged_in == ("no-reply@exemplo.com", "senha-smtp")
    assert sent_instance.sent[1] == ["destino@exemplo.com"]


def test_email_settings_test_email_records_failure_without_raising(client, setup, monkeypatch):
    admin_headers = setup["admin_headers"]
    client.put(
        "/email-settings",
        json={"enabled": False, "smtp_host": "smtp.exemplo.com", "smtp_port": 587, "from_email": "no-reply@exemplo.com"},
        headers=admin_headers,
    )

    def boom(*args, **kwargs):
        raise OSError("Connection refused")

    monkeypatch.setattr("app.email_service.smtplib.SMTP", boom)

    tested = client.post("/email-settings/test-email", json={"to_email": "destino@exemplo.com"}, headers=admin_headers)
    assert tested.status_code == 200
    body = tested.json()
    assert body["last_test_ok"] is False
    assert "Connection refused" in body["last_test_error"]


def test_email_settings_test_email_requires_saved_config(client, setup):
    admin_headers = setup["admin_headers"]
    response = client.post("/email-settings/test-email", json={"to_email": "destino@exemplo.com"}, headers=admin_headers)
    assert response.status_code == 422


def test_email_log_records_entry_on_success_and_failure(client, setup, monkeypatch):
    """Pedido do usuário: "poderia criar um botão para abrir uma tela com o
    log dos emails enviados? esse log precisa ser gravado [...] na base de
    dados". Cada tentativa de `send_raw_email` (aqui disparada pelo botão
    "Enviar e-mail de teste") grava uma linha em EmailLog, sucesso ou
    falha — é o mesmo `send_raw_email` usado por todo o resto do processo
    de envio, então cobrir aqui cobre o choke point de verdade."""
    admin_headers = setup["admin_headers"]
    client.put(
        "/email-settings",
        json={"enabled": False, "smtp_host": "smtp.exemplo.com", "smtp_port": 587, "from_email": "no-reply@exemplo.com"},
        headers=admin_headers,
    )

    _FakeSmtpConnection.instances = []
    monkeypatch.setattr("app.email_service.smtplib.SMTP", _FakeSmtpConnection)
    ok = client.post("/email-settings/test-email", json={"to_email": "sucesso@exemplo.com"}, headers=admin_headers)
    assert ok.status_code == 200

    def boom(*args, **kwargs):
        raise OSError("Connection refused")

    monkeypatch.setattr("app.email_service.smtplib.SMTP", boom)
    failed = client.post("/email-settings/test-email", json={"to_email": "falha@exemplo.com"}, headers=admin_headers)
    assert failed.status_code == 200

    log = client.get("/email-settings/log", headers=admin_headers)
    assert log.status_code == 200
    rows = log.json()
    assert len(rows) == 2
    # Mais recentes primeiro.
    assert rows[0]["to_email"] == "falha@exemplo.com"
    assert rows[0]["success"] is False
    assert "Connection refused" in rows[0]["error_message"]
    assert rows[0]["kind"] == "teste"
    assert rows[1]["to_email"] == "sucesso@exemplo.com"
    assert rows[1]["success"] is True
    assert rows[1]["error_message"] is None


def test_email_log_list_and_clear_restricted_to_admin_like_roles(client, setup, monkeypatch):
    admin_headers = setup["admin_headers"]
    pm_headers = auth_headers(client, setup["pm"].email)
    client.put(
        "/email-settings",
        json={"enabled": False, "smtp_host": "smtp.exemplo.com", "smtp_port": 587, "from_email": "no-reply@exemplo.com"},
        headers=admin_headers,
    )
    monkeypatch.setattr("app.email_service.smtplib.SMTP", _FakeSmtpConnection)
    client.post("/email-settings/test-email", json={"to_email": "destino@exemplo.com"}, headers=admin_headers)

    assert client.get("/email-settings/log", headers=pm_headers).status_code == 403
    assert client.delete("/email-settings/log", headers=pm_headers).status_code == 403

    assert len(client.get("/email-settings/log", headers=admin_headers).json()) == 1

    # "opção de limpar o log" (pedido do usuário) — apaga tudo.
    cleared = client.delete("/email-settings/log", headers=admin_headers)
    assert cleared.status_code == 204
    assert client.get("/email-settings/log", headers=admin_headers).json() == []


def test_schedule_creation_and_update_trigger_email_notification(client, setup, monkeypatch):
    """Pedido do usuário (caso 1 do "processo de envio de emails": "Agendas
    definidas para consultores"). Monkeypatcha `app.notifications.
    send_email` (não a configuração de SMTP de verdade) pra isolar "o
    agendamento dispara o aviso certo" da camada de envio em si, já
    coberta pelos testes de email_settings acima."""
    sent = []

    # kind=None de propósito: este teste isola "o agendamento dispara o
    # aviso certo", não quem chama com qual `kind` — ver
    # test_send_raw_email_records_log_entry_on_success_and_failure, que
    # cobre o `kind` repassado de verdade.
    def fake_send_email(db, *, to_email, to_name, subject, html_body, text_body=None, kind=None):
        sent.append({"to_email": to_email, "to_name": to_name, "subject": subject})
        return True, None

    monkeypatch.setattr("app.notifications.send_email", fake_send_email)

    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    resource = client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    ).json()
    task = client.post(f"/projects/{project_id}/tasks", json={"name": "Tarefa X", "wbs_code": "70"}, headers=admin_headers).json()

    created = client.post(
        "/resource-schedules",
        json={
            "resource_id": resource["id"],
            "project_id": project_id,
            "date": "2026-09-01",
            "start_time": "08:00",
            "end_time": "12:00",
            "task_ids": [task["id"]],
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    assert len(sent) == 1
    assert sent[0]["to_email"] == setup["consultant"].email
    assert sent[0]["to_name"] == setup["consultant"].name

    schedule_id = created.json()["id"]
    sent.clear()

    # Editar só a descrição não dispara um novo aviso (nada que importe
    # pro consultor mudou de verdade).
    only_description = client.patch(
        f"/resource-schedules/{schedule_id}", json={"description": "Observação qualquer"}, headers=admin_headers
    )
    assert only_description.status_code == 200
    assert sent == []

    # Trocar o horário dispara um novo aviso ("Agendamento atualizado").
    rescheduled = client.patch(
        f"/resource-schedules/{schedule_id}", json={"start_time": "09:00", "end_time": "13:00"}, headers=admin_headers
    )
    assert rescheduled.status_code == 200
    assert len(sent) == 1


def test_schedule_notification_is_noop_without_email_settings_configured(client, setup):
    """Sem EmailSettings salva (ambiente recém-instalado), criar um
    agendamento continua funcionando normalmente — o aviso por e-mail é só
    "não há o que fazer" (ver send_email), nunca uma falha que derruba a
    operação principal (mesma regra da integração com Google Calendar)."""
    project_id = setup["project_a"].id
    admin_headers = setup["admin_headers"]
    resource = client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    ).json()

    created = client.post(
        "/resource-schedules",
        json={
            "resource_id": resource["id"],
            "project_id": project_id,
            "date": "2026-09-02",
            "start_time": "08:00",
            "end_time": "12:00",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201


def test_send_pending_approval_digests_groups_by_project_manager(client, setup, db_session, monkeypatch):
    """Pedido do usuário (caso 2: "Aviso de Registro de Horas/Tarefas para
    aprovar... para o gerente do projeto" — "Resumo periódico" confirmado,
    não um e-mail por apontamento). Agrupa por `Project.manager_id`: dois
    projetos de gerentes diferentes geram dois e-mails, cada um só com os
    apontamentos pendentes dos projetos daquele gerente."""
    admin_headers = setup["admin_headers"]
    project_a = setup["project_a"]  # gerenciado por setup["pm"]
    pm = setup["pm"]

    other_manager = make_user(db_session, role=UserRole.INTERNAL_PM, email="outro.gerente@example.com")
    other_project = make_project(db_session, client_id=setup["client_a"].id, manager_id=other_manager.id, code="PRJ-C")
    activated = client.patch(f"/projects/{other_project.id}", json={"status": ProjectStatus.ACTIVE.value}, headers=admin_headers)
    assert activated.status_code == 200

    resource = client.post(
        "/resources",
        json={"user_id": setup["consultant"].id, "internal_cost_per_hour": "50", "billing_rate_per_hour": "100"},
        headers=admin_headers,
    ).json()
    consultant_headers = auth_headers(client, setup["consultant"].email)

    # _resolve_task_and_project (routers/timesheets.py) exige o recurso
    # alocado na tarefa OU vinculado ao projeto (ProjectResource) pra
    # apontar horas — sem isso o consultor levaria 403 em vez do 201
    # esperado aqui.
    for project_id in (project_a.id, other_project.id):
        link = client.post(f"/projects/{project_id}/resources", json={"resource_id": resource["id"]}, headers=admin_headers)
        assert link.status_code == 201

    task_a = client.post(f"/projects/{project_a.id}/tasks", json={"name": "Tarefa A", "wbs_code": "80"}, headers=admin_headers).json()
    task_c = client.post(
        f"/projects/{other_project.id}/tasks", json={"name": "Tarefa C", "wbs_code": "81"}, headers=admin_headers
    ).json()

    entry_a = client.post(
        "/timesheets",
        json={"task_id": task_a["id"], "date": "2026-09-03", "start_time": "08:00", "end_time": "12:00"},
        headers=consultant_headers,
    )
    assert entry_a.status_code == 201
    entry_c = client.post(
        "/timesheets",
        json={"task_id": task_c["id"], "date": "2026-09-03", "start_time": "13:00", "end_time": "17:00"},
        headers=consultant_headers,
    )
    assert entry_c.status_code == 201

    sent = []

    def fake_send_email(db, *, to_email, to_name, subject, html_body, text_body=None, kind=None):
        sent.append({"to_email": to_email, "to_name": to_name})
        return True, None

    monkeypatch.setattr("app.notifications.send_email", fake_send_email)

    from app.notifications import send_pending_approval_digests

    summaries = send_pending_approval_digests(db_session, dry_run=False)

    by_email = {s["manager_email"]: s for s in summaries}
    assert pm.email in by_email
    assert other_manager.email in by_email
    assert by_email[pm.email]["count"] == 1
    assert by_email[other_manager.email]["count"] == 1
    assert float(by_email[pm.email]["total_hours"]) == 4
    assert float(by_email[other_manager.email]["total_hours"]) == 4

    assert len(sent) == 2
    assert {row["to_email"] for row in sent} == {pm.email, other_manager.email}

    # --dry-run não manda nenhum e-mail de verdade, só devolve o resumo.
    sent.clear()
    dry_summaries = send_pending_approval_digests(db_session, dry_run=True)
    assert len(dry_summaries) == 2
    assert sent == []
