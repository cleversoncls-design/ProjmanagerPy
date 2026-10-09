from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import EXTERNAL_ROLES, get_current_user, require_project_access
from ..i18n import t as translate
from ..models import (
    TASK_FINISHED_STATUSES,
    AuditAction,
    Project,
    Resource,
    Task,
    TaskApprovalStatus,
    TaskAssignment,
    TaskClientAssignment,
    TaskDependency,
    TaskStatus,
    Timesheet,
    User,
    UserRole,
    UserStatus,
)
from ..schemas import (
    ClientUserRead,
    RescheduleRequest,
    TaskAssignmentCreate,
    TaskAssignmentRead,
    TaskClientApprovalUpdate,
    TaskClientAssignmentCreate,
    TaskCreate,
    TaskDependencyCreate,
    TaskDependencyRead,
    TaskGroupApplyRequest,
    TaskMoveRequest,
    TaskRead,
    TaskUpdate,
    WbsRecalculateResponse,
)
from ..services import (
    DEFAULT_CAPACITY_HOURS_PER_DAY,
    capacity_hours_per_day_for_task,
    apply_effort_driven,
    apply_task_group_to_task,
    calendar_for_project,
    calendar_from_db,
    copy_project_tasks,
    end_date_from_duration,
    move_task,
    recalculate_schedule,
    recalculate_wbs,
    reschedule_cascade,
)

router = APIRouter(tags=["tasks"])

# "Administrar tarefas" ficou só com Admin/Gerente de Projetos (revisão de
# acessos do usuário) — todo `require_project_access(..., write=True)` deste
# arquivo passa `allow_consultant_write=False`, barrando o Consultor mesmo
# via API direta (a UI já não mostra mais a tela de Projetos pra ele, ver
# PROJECTS_VISIBLE_ROLES no frontend). `review_task_client_approval` abaixo
# não entra nessa regra — usa write=False (é o fluxo de aprovação do
# cliente, não edição da tarefa).


def _get_task_or_404(db: Session, task_id: str, lang: str) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail=translate("Tarefa não encontrada", lang))
    return task


@router.post("/projects/{project_id}/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    project_id: str,
    data: TaskCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Task:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    require_project_access(project, user, write=True, allow_consultant_write=False)
    if data.parent_task_id:
        parent = db.get(Task, data.parent_task_id)
        if not parent or parent.project_id != project_id:
            raise HTTPException(status_code=422, detail=translate("parent_task_id precisa ser uma tarefa do mesmo projeto", user.language))
    if db.scalar(select(Task).where(Task.project_id == project_id, Task.wbs_code == data.wbs_code)):
        raise HTTPException(status_code=409, detail=translate("Já existe uma tarefa com este código WBS neste projeto", user.language))
    fields = data.model_dump(exclude={"duration_days", "estimated_hours"})
    if data.is_client_activity:
        # Atividade do cliente não tem nível mínimo (ver models.Task).
        fields["min_level"] = 1
    task = Task(project_id=project_id, **fields)
    # Sem nenhum recurso alocado ainda nesta hora (a tarefa acabou de ser
    # criada), então o effort-driven usa a FTE genérica de 8h/dia — ver
    # capacity_hours_per_day_for_task para quando já há alocação. Sem
    # duration_days NEM estimated_hours informados, assume 1 dia (mesmo
    # default do modelo) como ponto de partida.
    apply_effort_driven(
        task,
        duration_days=data.duration_days if data.duration_days is not None else (None if data.estimated_hours is not None else Decimal("1")),
        estimated_hours=data.estimated_hours if data.duration_days is None else None,
        capacity_hours_per_day=DEFAULT_CAPACITY_HOURS_PER_DAY,
    )
    # Fim planejado = Início + Duração (dias úteis) sempre que a tarefa já
    # nasce com Início planejado informado — sem isso, uma tarefa SEM
    # predecessora (a maioria, ver recalculate_schedule/reschedule_cascade:
    # nenhuma das duas mexe em quem não tem predecessora) nascia sem Fim
    # planejado, precisando de edição manual depois. Sobrepõe qualquer
    # planned_end_date que tenha vindo no payload — Duração é sempre a
    # fonte da verdade (mesma regra do motor de agendamento). Sem Início
    # planejado ainda não há o que calcular; fica como veio (normalmente
    # None, ou um valor explícito pra um caso como marco sem data de
    # início própria).
    if task.planned_start_date:
        cal = calendar_for_project(db, project)
        task.planned_end_date = end_date_from_duration(cal, task.planned_start_date, task.duration_days)
    db.add(task)
    db.flush()
    if task.parent_task_id and task.planned_start_date:
        # Tarefa nova dentro de um pai que é predecessora de outra: o intervalo
        # do pai muda, então as sucessoras dele precisam ser recalculadas.
        reschedule_cascade(db, task.id, calendar_for_project(db, project))
    record_audit(db, entity_type="task", entity_id=task.id, action=AuditAction.CREATE, user_id=user.id)
    db.commit()
    db.refresh(task)
    return task


@router.get("/projects/{project_id}/tasks", response_model=list[TaskRead])
def list_tasks(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Task]:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    require_project_access(project, user)
    return list(db.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.wbs_code)).all())


@router.get("/tasks/{task_id}", response_model=TaskRead)
def read_task(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Task:
    task = _get_task_or_404(db, task_id, user.language)
    require_project_access(task.project, user)
    return task


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: str,
    data: TaskUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Task:
    task = _get_task_or_404(db, task_id, user.language)
    require_project_access(task.project, user, write=True, allow_consultant_write=False)
    changes = data.model_dump(exclude_unset=True)
    # Duração/Trabalho passam pelo motor effort-driven (mesma regra de
    # create_task): informar um recalcula o outro; informar os dois, quem
    # manda é a Duração (ver docstring de apply_effort_driven). Os demais
    # campos seguem o setattr genérico de sempre.
    duration_days = changes.pop("duration_days", None)
    estimated_hours = changes.pop("estimated_hours", None)
    # Se a própria data/duração da tarefa muda, as sucessoras dependentes
    # dela precisam ser recalculadas em cascata agora — sem isso, o usuário
    # via uma predecessora nova data mas as sucessoras só se moviam depois
    # de clicar manualmente em "Recalcular tudo" (mesmo problema de
    # create_dependency, ver comentário lá).
    schedule_fields_changed = (
        duration_days is not None
        or estimated_hours is not None
        or "planned_start_date" in changes
        or "planned_end_date" in changes
    )
    # "Atividade do cliente": ligar exige que a tarefa ainda não tenha
    # Recurso alocado (os dois modelos de alocação não se misturam); desligar
    # solta os usuários do cliente que estavam nela. Enquanto for atividade
    # do cliente, o nível mínimo fica sempre 1.
    if changes.get("is_client_activity") is None:
        changes.pop("is_client_activity", None)
    if "is_client_activity" in changes:
        turning_on = changes["is_client_activity"] and not task.is_client_activity
        turning_off = (not changes["is_client_activity"]) and task.is_client_activity
        if turning_on and db.scalar(select(TaskAssignment.id).where(TaskAssignment.task_id == task.id).limit(1)):
            raise HTTPException(
                status_code=409,
                detail=translate("Remova os recursos alocados antes de marcar a tarefa como atividade do cliente", user.language),
            )
        if turning_off:
            for link in list(task.client_assignments):
                db.delete(link)
            db.flush()
            db.refresh(task)
    if changes.get("is_client_activity", task.is_client_activity) and ("min_level" in changes or "is_client_activity" in changes):
        changes["min_level"] = 1
    previous_status = task.status
    for field, value in changes.items():
        setattr(task, field, value)
    # "Quando a tarefa for completada com 100%, muda pra finalizada" (pedido
    # do usuário) — dispara quando o progress_percentage deste PATCH chega a
    # 100. O form de edição (ProjectDetailPage.jsx) sempre manda "status"
    # junto no payload (é um form completo, não um diff), então não dá pra
    # checar só "status" in changes" pra saber se foi uma escolha explícita:
    # comparamos o valor recebido com o status que a tarefa já tinha antes
    # deste PATCH — só conta como escolha explícita (e então não mexe) se o
    # valor enviado for DIFERENTE do anterior (ex.: usuário escolheu
    # Encerrada/Não iniciada de propósito junto com os 100%). Também não
    # ressuscita uma tarefa que já estava Concluída/Encerrada. Entra em
    # "changes" pra aparecer no audit log também.
    status_explicitly_changed = "status" in changes and changes["status"] != previous_status
    if (
        "progress_percentage" in changes
        and not status_explicitly_changed
        and task.status not in TASK_FINISHED_STATUSES
        and task.progress_percentage is not None
        and Decimal(task.progress_percentage) >= 100
    ):
        task.status = TaskStatus.COMPLETED
        changes["status"] = TaskStatus.COMPLETED
    if duration_days is not None or estimated_hours is not None:
        apply_effort_driven(
            task,
            duration_days=duration_days,
            estimated_hours=estimated_hours if duration_days is None else None,
            capacity_hours_per_day=capacity_hours_per_day_for_task(db, task.id),
        )
        changes["duration_days"] = duration_days if duration_days is not None else task.duration_days
        changes["estimated_hours"] = task.estimated_hours
    if schedule_fields_changed:
        cal = calendar_for_project(db, task.project)
        # Fim planejado = Início + Duração (dias úteis) — mesma regra de
        # create_task, reaplicada aqui sempre que Início/Duração/Trabalho/
        # Fim mudam nesta edição, pra essa tarefa (a que está sendo editada
        # diretamente, não suas sucessoras — essas o reschedule_cascade
        # logo abaixo já cobre) nunca ficar com um Fim planejado
        # desatualizado ou nulo. Sobrepõe qualquer planned_end_date que
        # tenha vindo no payload, igual em create_task.
        if task.planned_start_date:
            task.planned_end_date = end_date_from_duration(cal, task.planned_start_date, task.duration_days)
        db.flush()
        try:
            reschedule_cascade(db, task.id, cal)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if changes:
        record_audit(db, entity_type="task", entity_id=task.id, action=AuditAction.UPDATE, user_id=user.id, details={"fields": sorted(changes.keys())})
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Apaga uma tarefa — recusa (409) se ela tiver tarefas-filhas na EAP
    (apagar destruiria uma parte inteira da estrutura sem aviso; mova ou
    apague as filhas primeiro) ou se já tiver algum apontamento de horas
    (Timesheet) registrado contra ela (apagar destruiria histórico real de
    trabalho lançado — o pedido explícito do usuário foi permitir apagar
    "desde que não tenha tido nenhum apontamento"). Dependências e
    alocações de recurso da própria tarefa são removidas junto (cascade no
    banco — TaskDependency/TaskAssignment não são histórico de trabalho
    feito, só vínculos estruturais)."""
    task = _get_task_or_404(db, task_id, user.language)
    require_project_access(task.project, user, write=True, allow_consultant_write=False)
    if db.scalar(select(Task.id).where(Task.parent_task_id == task_id)):
        raise HTTPException(status_code=409, detail=translate("Não é possível apagar uma tarefa que tem tarefas-filhas. Mova ou apague as filhas primeiro.", user.language))
    if db.scalar(select(Timesheet.id).where(Timesheet.task_id == task_id)):
        raise HTTPException(status_code=409, detail=translate("Não é possível apagar uma tarefa que já tem apontamento de horas registrado.", user.language))
    record_audit(
        db,
        entity_type="task",
        entity_id=task.id,
        action=AuditAction.UPDATE,
        user_id=user.id,
        details={"action": "task_deleted", "wbs_code": task.wbs_code, "name": task.name},
    )
    db.delete(task)
    db.commit()
    return None


@router.post("/tasks/{task_id}/submit-for-approval", response_model=TaskRead)
def submit_task_for_approval(
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Task:
    """Quem tem acesso de escrita na tarefa (perfil interno) marca a tarefa
    como pronta para o cliente validar. PM do Cliente deixou de poder
    chamar esta rota (reorganização de menus, pedido do usuário: os dois
    perfis externos agora são sempre somente leitura — ver
    require_project_access em app/deps.py); quem valida continua sendo só
    o lado do cliente, pelo endpoint abaixo. Pode ser chamado de novo
    depois de uma rejeição, para reenviar."""
    task = _get_task_or_404(db, task_id, user.language)
    require_project_access(task.project, user, write=True, allow_consultant_write=False)
    if task.client_approval_status == TaskApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail=translate("Tarefa já está aguardando validação do cliente", user.language))
    task.client_approval_status = TaskApprovalStatus.PENDING
    record_audit(
        db,
        entity_type="task",
        entity_id=task.id,
        action=AuditAction.UPDATE,
        user_id=user.id,
        details={"client_approval_status": TaskApprovalStatus.PENDING.value},
    )
    db.commit()
    db.refresh(task)
    return task


@router.patch("/tasks/{task_id}/client-approval", response_model=TaskRead)
def review_task_client_approval(
    task_id: str,
    data: TaskClientApprovalUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Task:
    """Validação da tarefa pelo lado do cliente (gerente de projeto do
    cliente ou usuário-chave) — inclusive CLIENT_USER, que em todo o resto
    da API é somente-leitura: aprovar/rejeitar não é editar a tarefa, é a
    própria razão de existir desse perfil."""
    task = _get_task_or_404(db, task_id, user.language)
    require_project_access(task.project, user, write=False)
    if user.role not in EXTERNAL_ROLES:
        raise HTTPException(status_code=403, detail=translate("Só o cliente valida suas próprias tarefas", user.language))
    if data.status not in (TaskApprovalStatus.APPROVED, TaskApprovalStatus.REJECTED):
        raise HTTPException(status_code=422, detail=translate("status precisa ser APPROVED ou REJECTED", user.language))
    if task.client_approval_status != TaskApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail=translate("Tarefa não está aguardando validação do cliente", user.language))
    task.client_approval_status = data.status
    record_audit(
        db,
        entity_type="task",
        entity_id=task.id,
        action=AuditAction.UPDATE,
        user_id=user.id,
        details={"client_approval_status": data.status.value, "comment": data.comment},
    )
    db.commit()
    db.refresh(task)
    return task


def _is_ancestor(db: Session, ancestor_id: str, task_id: str) -> bool:
    """True se `ancestor_id` está acima de `task_id` na hierarquia da EAP."""
    current = db.get(Task, task_id)
    guard = 0
    while current is not None and current.parent_task_id and guard < 1000:
        if current.parent_task_id == ancestor_id:
            return True
        current = db.get(Task, current.parent_task_id)
        guard += 1
    return False


@router.post("/task-dependencies", response_model=TaskDependencyRead, status_code=status.HTTP_201_CREATED)
def create_dependency(
    data: TaskDependencyCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskDependency:
    predecessor = _get_task_or_404(db, data.predecessor_task_id, user.language)
    successor = _get_task_or_404(db, data.successor_task_id, user.language)
    if predecessor.project_id != successor.project_id:
        raise HTTPException(status_code=422, detail=translate("Predecessora e sucessora precisam pertencer ao mesmo projeto", user.language))
    if predecessor.id == successor.id:
        raise HTTPException(status_code=422, detail=translate("Uma tarefa não pode depender de si mesma", user.language))
    require_project_access(predecessor.project, user, write=True, allow_consultant_write=False)
    # Tarefa-pai pode ser predecessora de outra tarefa (vale o intervalo
    # agregado das filhas), mas nunca de uma das próprias filhas/ancestrais:
    # as datas do pai dependem das filhas, então seria uma dependência circular.
    if _is_ancestor(db, predecessor.id, successor.id) or _is_ancestor(db, successor.id, predecessor.id):
        raise HTTPException(
            status_code=422,
            detail=translate("Uma tarefa não pode depender da própria tarefa-pai nem de uma tarefa-filha dela", user.language),
        )
    if db.scalar(
        select(TaskDependency).where(
            TaskDependency.predecessor_task_id == predecessor.id,
            TaskDependency.successor_task_id == successor.id,
        )
    ):
        raise HTTPException(status_code=409, detail=translate("Essa dependência já existe", user.language))
    dependency = TaskDependency(**data.model_dump())
    db.add(dependency)
    # Sem o flush, reschedule_cascade (que faz sua própria query em
    # TaskDependency logo abaixo) não enxergaria essa dependência recém-
    # criada — a sessão tem autoflush=False (app/database.py).
    db.flush()
    # A sucessora precisa herdar a data da predecessora imediatamente: antes
    # desta chamada, criar a dependência só gravava o vínculo e a sucessora
    # continuava com a data antiga até o usuário clicar manualmente em
    # "Recalcular tudo".
    try:
        cal = calendar_for_project(db, predecessor.project)
        reschedule_cascade(db, predecessor.id, cal)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(dependency)
    return dependency


@router.delete("/task-dependencies/{dependency_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dependency(
    dependency_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    dependency = db.get(TaskDependency, dependency_id)
    if not dependency:
        raise HTTPException(status_code=404, detail=translate("Dependência não encontrada", user.language))
    successor = _get_task_or_404(db, dependency.successor_task_id, user.language)
    require_project_access(successor.project, user, write=True, allow_consultant_write=False)
    db.delete(dependency)
    record_audit(
        db,
        entity_type="task",
        entity_id=successor.id,
        action=AuditAction.UPDATE,
        user_id=user.id,
        details={"dependency_removed": dependency_id, "predecessor_task_id": dependency.predecessor_task_id},
    )
    db.commit()
    return None


@router.get("/tasks/{task_id}/dependencies", response_model=list[TaskDependencyRead])
def list_dependencies(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[TaskDependency]:
    task = _get_task_or_404(db, task_id, user.language)
    require_project_access(task.project, user)
    return list(
        db.scalars(
            select(TaskDependency).where(
                or_(TaskDependency.predecessor_task_id == task_id, TaskDependency.successor_task_id == task_id)
            )
        ).all()
    )


@router.post("/tasks/{task_id}/reschedule", response_model=list[TaskRead])
def reschedule_task(
    task_id: str,
    data: RescheduleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Task]:
    """Recalcula as sucessoras da tarefa após uma mudança de datas, usando o
    motor de cascata FS/SS/FF/SF (`reschedule_cascade`) — antes desta rota,
    essa função existia em `app/services.py` mas não era acionável pela API.
    """
    task = _get_task_or_404(db, task_id, user.language)
    require_project_access(task.project, user, write=True, allow_consultant_write=False)
    try:
        cal = calendar_from_db(db, data.calendar_id) if data.calendar_id else calendar_for_project(db, task.project)
        updated = reschedule_cascade(db, task_id, cal)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    for item in updated:
        db.refresh(item)
    return updated


@router.post("/tasks/{task_id}/assignments", response_model=TaskAssignmentRead, status_code=status.HTTP_201_CREATED)
def assign_resource(
    task_id: str,
    data: TaskAssignmentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskAssignment:
    task = _get_task_or_404(db, task_id, user.language)
    require_project_access(task.project, user, write=True, allow_consultant_write=False)
    if task.is_client_activity:
        raise HTTPException(
            status_code=409,
            detail=translate("Atividade do cliente não aceita recurso alocado — use os usuários do cliente", user.language),
        )
    resource = db.get(Resource, data.resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail=translate("Recurso não encontrado", user.language))
    if db.scalar(
        select(TaskAssignment).where(TaskAssignment.task_id == task_id, TaskAssignment.resource_id == data.resource_id)
    ):
        raise HTTPException(status_code=409, detail=translate("Recurso já alocado nesta tarefa", user.language))
    assignment = TaskAssignment(task_id=task_id, **data.model_dump())
    db.add(assignment)
    db.flush()
    # Fixed Units: aloca mais um recurso mantém a Duração e recalcula só o
    # Trabalho (capacidade diária total dos recursos agora alocados) — ver
    # docstring de apply_effort_driven.
    apply_effort_driven(
        task,
        duration_days=None,
        estimated_hours=None,
        capacity_hours_per_day=capacity_hours_per_day_for_task(db, task_id),
    )
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get("/tasks/{task_id}/assignments", response_model=list[TaskAssignmentRead])
def list_assignments(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[TaskAssignment]:
    task = _get_task_or_404(db, task_id, user.language)
    require_project_access(task.project, user)
    return list(db.scalars(select(TaskAssignment).where(TaskAssignment.task_id == task_id)).all())


@router.delete("/tasks/{task_id}/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_assignment(
    task_id: str,
    assignment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    task = _get_task_or_404(db, task_id, user.language)
    require_project_access(task.project, user, write=True, allow_consultant_write=False)
    assignment = db.get(TaskAssignment, assignment_id)
    if not assignment or assignment.task_id != task_id:
        raise HTTPException(status_code=404, detail=translate("Alocação não encontrada", user.language))
    db.delete(assignment)
    db.flush()
    # Um recurso a menos: mesma regra Fixed Units, na direção oposta —
    # Duração fica igual, Trabalho cai para a nova capacidade total (ou
    # volta pra FTE genérica se este era o último recurso alocado).
    apply_effort_driven(
        task,
        duration_days=None,
        estimated_hours=None,
        capacity_hours_per_day=capacity_hours_per_day_for_task(db, task_id),
    )
    record_audit(db, entity_type="task", entity_id=task.id, action=AuditAction.UPDATE, user_id=user.id, details={"assignment_removed": assignment_id})
    db.commit()
    return None


@router.get("/projects/{project_id}/client-users", response_model=list[ClientUserRead])
def list_project_client_users(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[User]:
    """Usuários ativos do cliente do projeto (CLIENT_PM/CLIENT_USER) —
    lista usada pelo seletor de "Atividade do cliente" no cadastro de
    tarefa. GET /users é restrito a perfis internos e não filtra por
    cliente, por isso a rota própria."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    require_project_access(project, user)
    return list(
        db.scalars(
            select(User)
            .where(
                User.client_id == project.client_id,
                User.role.in_([UserRole.CLIENT_PM, UserRole.CLIENT_USER]),
                User.status == UserStatus.ACTIVE,
            )
            .order_by(User.name)
        ).all()
    )


@router.post("/tasks/{task_id}/client-users", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def assign_client_user(
    task_id: str,
    data: TaskClientAssignmentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Task:
    task = _get_task_or_404(db, task_id, user.language)
    require_project_access(task.project, user, write=True, allow_consultant_write=False)
    if not task.is_client_activity:
        raise HTTPException(status_code=409, detail=translate("A tarefa não é uma atividade do cliente", user.language))
    target = db.get(User, data.user_id)
    if not target:
        raise HTTPException(status_code=404, detail=translate("Usuário não encontrado", user.language))
    if (
        target.client_id != task.project.client_id
        or target.role not in (UserRole.CLIENT_PM, UserRole.CLIENT_USER)
        or target.status != UserStatus.ACTIVE
    ):
        raise HTTPException(
            status_code=422,
            detail=translate("O usuário precisa ser um usuário ativo do cliente deste projeto", user.language),
        )
    if data.user_id in task.client_user_ids:
        raise HTTPException(status_code=409, detail=translate("Usuário já alocado nesta tarefa", user.language))
    db.add(TaskClientAssignment(task_id=task_id, user_id=data.user_id))
    record_audit(db, entity_type="task", entity_id=task.id, action=AuditAction.UPDATE, user_id=user.id, details={"client_user_added": data.user_id})
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}/client-users/{user_id}", response_model=TaskRead)
def remove_client_user(
    task_id: str,
    user_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Task:
    task = _get_task_or_404(db, task_id, user.language)
    require_project_access(task.project, user, write=True, allow_consultant_write=False)
    link = db.scalar(select(TaskClientAssignment).where(TaskClientAssignment.task_id == task_id, TaskClientAssignment.user_id == user_id))
    if not link:
        raise HTTPException(status_code=404, detail=translate("Alocação não encontrada", user.language))
    db.delete(link)
    record_audit(db, entity_type="task", entity_id=task.id, action=AuditAction.UPDATE, user_id=user.id, details={"client_user_removed": user_id})
    db.commit()
    db.refresh(task)
    return task


@router.post("/projects/{project_id}/tasks/recalculate-wbs", response_model=WbsRecalculateResponse)
def recalculate_project_wbs(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Botão "recalcular WBS/EAP" — renumera todas as tarefas do projeto a
    partir da hierarquia e da ordem manual (sort_order). Ver
    services.recalculate_wbs."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    require_project_access(project, user, write=True, allow_consultant_write=False)
    updated = recalculate_wbs(db, project_id)
    record_audit(db, entity_type="project", entity_id=project_id, action=AuditAction.UPDATE, user_id=user.id, details={"action": "recalculate_wbs"})
    db.commit()
    for item in updated:
        db.refresh(item)
    return {"tasks": updated}


@router.post("/projects/{project_id}/copy-tasks-from/{source_project_id}", response_model=WbsRecalculateResponse, status_code=status.HTTP_201_CREATED)
def copy_tasks_from_project(
    project_id: str,
    source_project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Botão "Copiar estrutura de outro projeto" — WBS/EAP, nome, duração,
    horas, tipo, milestone, hierarquia e predecessoras (com tipo/atraso) de
    `source_project_id` pra dentro de `project_id`, sem nenhum recurso
    alocado (ver services.copy_project_tasks). `project_id` precisa estar
    vazio (sem tarefas) — o fluxo é sempre criar o projeto primeiro, depois
    usar este botão nele, nunca misturar com uma estrutura já existente. O
    projeto de origem pode ter qualquer status (inclusive MODELO, o uso
    mais comum, mas não exigido)."""
    target = db.get(Project, project_id)
    if not target:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    require_project_access(target, user, write=True, allow_consultant_write=False)
    source = db.get(Project, source_project_id)
    if not source:
        raise HTTPException(status_code=404, detail=translate("Projeto de origem não encontrado", user.language))
    require_project_access(source, user)
    if source.id == target.id:
        raise HTTPException(status_code=422, detail=translate("O projeto de origem precisa ser diferente do projeto de destino", user.language))

    cal = calendar_for_project(db, target)
    try:
        copied = copy_project_tasks(db, source_project_id, target, cal)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # Datas de quem tem predecessora foram só um chute inicial em
    # copy_project_tasks — recalcula o projeto novo inteiro agora que as
    # TaskDependency já existem, pra essas tarefas derivarem da cascata
    # (mesma regra de reschedule_project), sobrepondo o chute.
    recalculate_schedule(db, target.id, cal)
    record_audit(
        db,
        entity_type="project",
        entity_id=target.id,
        action=AuditAction.UPDATE,
        user_id=user.id,
        details={"action": "copy_tasks_from", "source_project_id": source_project_id, "tasks_copied": len(copied)},
    )
    db.commit()
    updated = list(db.scalars(select(Task).where(Task.project_id == target.id).order_by(Task.wbs_code)).all())
    return {"tasks": updated}


@router.post("/tasks/{task_id}/apply-task-group", response_model=WbsRecalculateResponse, status_code=status.HTTP_201_CREATED)
def apply_task_group(
    task_id: str,
    data: TaskGroupApplyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Botão "Aplicar grupo de tarefas" — clona a árvore de um TaskGroup
    (ver app/routers/task_groups.py) como tarefas-filhas de `task_id`, no
    mesmo projeto dela, e renumera o WBS/EAP do projeto inteiro em seguida
    (ver services.apply_task_group_to_task/recalculate_wbs). Sem
    recalculate_schedule depois: as tarefas clonadas não carregam
    predecessora nenhuma (um TaskGroup não tem dependência, ver docstring
    de apply_task_group_to_task), então não há data pra recalcular. Mesma
    restrição de quem administra tarefas em geral
    (allow_consultant_write=False)."""
    task = _get_task_or_404(db, task_id, user.language)
    require_project_access(task.project, user, write=True, allow_consultant_write=False)
    try:
        created = apply_task_group_to_task(db, data.task_group_id, task)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    updated = recalculate_wbs(db, task.project_id)
    record_audit(
        db,
        entity_type="task",
        entity_id=task.id,
        action=AuditAction.UPDATE,
        user_id=user.id,
        details={"action": "apply_task_group", "task_group_id": data.task_group_id, "tasks_created": len(created)},
    )
    db.commit()
    for item in updated:
        db.refresh(item)
    return {"tasks": updated}


@router.post("/tasks/{task_id}/move", response_model=TaskRead)
def move_task_endpoint(
    task_id: str,
    data: TaskMoveRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Task:
    """Move a tarefa para outro pai e/ou reordena entre as irmãs — ver
    services.move_task. Não recalcula WBS nem datas automaticamente:
    chame recalculate-wbs / reschedule depois, se necessário."""
    task = _get_task_or_404(db, task_id, user.language)
    require_project_access(task.project, user, write=True, allow_consultant_write=False)
    try:
        moved = move_task(db, task_id, new_parent_id=data.new_parent_id, before_task_id=data.before_task_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(
        db,
        entity_type="task",
        entity_id=task.id,
        action=AuditAction.UPDATE,
        user_id=user.id,
        details={"moved_to_parent": data.new_parent_id, "before_task_id": data.before_task_id},
    )
    db.commit()
    db.refresh(moved)
    return moved


@router.post("/projects/{project_id}/reschedule", response_model=list[TaskRead])
def reschedule_project(
    project_id: str,
    data: RescheduleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Task]:
    """Botão "recalcular tudo" — refaz as datas de todas as tarefas do
    projeto que têm predecessora, de uma vez só (ver
    services.recalculate_schedule), em vez de precisar acionar
    reschedule_cascade tarefa por tarefa depois de uma edição em lote
    (mover tarefas, trocar predecessoras, mudar durações)."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    require_project_access(project, user, write=True, allow_consultant_write=False)
    cal = calendar_from_db(db, data.calendar_id) if data.calendar_id else calendar_for_project(db, project)
    updated = recalculate_schedule(db, project_id, cal)
    record_audit(db, entity_type="project", entity_id=project_id, action=AuditAction.UPDATE, user_id=user.id, details={"action": "reschedule_all"})
    db.commit()
    for item in updated:
        db.refresh(item)
    return updated
