from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import EXTERNAL_ROLES, get_current_user, require_project_access
from ..models import AuditAction, Project, Resource, Task, TaskApprovalStatus, TaskAssignment, TaskDependency, Timesheet, User
from ..schemas import (
    RescheduleRequest,
    TaskAssignmentCreate,
    TaskAssignmentRead,
    TaskClientApprovalUpdate,
    TaskCreate,
    TaskDependencyCreate,
    TaskDependencyRead,
    TaskMoveRequest,
    TaskRead,
    TaskUpdate,
    WbsRecalculateResponse,
)
from ..services import (
    DEFAULT_CAPACITY_HOURS_PER_DAY,
    capacity_hours_per_day_for_task,
    apply_effort_driven,
    calendar_for_project,
    calendar_from_db,
    move_task,
    recalculate_schedule,
    recalculate_wbs,
    reschedule_cascade,
)

router = APIRouter(tags=["tasks"])


def _get_task_or_404(db: Session, task_id: str) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
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
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    require_project_access(project, user, write=True)
    if data.parent_task_id:
        parent = db.get(Task, data.parent_task_id)
        if not parent or parent.project_id != project_id:
            raise HTTPException(status_code=422, detail="parent_task_id precisa ser uma tarefa do mesmo projeto")
    if db.scalar(select(Task).where(Task.project_id == project_id, Task.wbs_code == data.wbs_code)):
        raise HTTPException(status_code=409, detail="Já existe uma tarefa com este código WBS neste projeto")
    fields = data.model_dump(exclude={"duration_days", "estimated_hours"})
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
    db.add(task)
    db.flush()
    record_audit(db, entity_type="task", entity_id=task.id, action=AuditAction.CREATE, user_id=user.id)
    db.commit()
    db.refresh(task)
    return task


@router.get("/projects/{project_id}/tasks", response_model=list[TaskRead])
def list_tasks(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Task]:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    require_project_access(project, user)
    return list(db.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.wbs_code)).all())


@router.get("/tasks/{task_id}", response_model=TaskRead)
def read_task(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Task:
    task = _get_task_or_404(db, task_id)
    require_project_access(task.project, user)
    return task


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: str,
    data: TaskUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Task:
    task = _get_task_or_404(db, task_id)
    require_project_access(task.project, user, write=True)
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
    for field, value in changes.items():
        setattr(task, field, value)
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
        db.flush()
        try:
            cal = calendar_for_project(db, task.project)
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
    task = _get_task_or_404(db, task_id)
    require_project_access(task.project, user, write=True)
    if db.scalar(select(Task.id).where(Task.parent_task_id == task_id)):
        raise HTTPException(status_code=409, detail="Não é possível apagar uma tarefa que tem tarefas-filhas. Mova ou apague as filhas primeiro.")
    if db.scalar(select(Timesheet.id).where(Timesheet.task_id == task_id)):
        raise HTTPException(status_code=409, detail="Não é possível apagar uma tarefa que já tem apontamento de horas registrado.")
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
    """Quem tem acesso de escrita na tarefa (interno, ou CLIENT_PM no escopo
    do próprio cliente) marca a tarefa como pronta para o usuário-chave do
    cliente validar. Pode ser chamado de novo depois de uma rejeição, para
    reenviar."""
    task = _get_task_or_404(db, task_id)
    require_project_access(task.project, user, write=True)
    if task.client_approval_status == TaskApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail="Tarefa já está aguardando validação do cliente")
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
    task = _get_task_or_404(db, task_id)
    require_project_access(task.project, user, write=False)
    if user.role not in EXTERNAL_ROLES:
        raise HTTPException(status_code=403, detail="Só o cliente valida suas próprias tarefas")
    if data.status not in (TaskApprovalStatus.APPROVED, TaskApprovalStatus.REJECTED):
        raise HTTPException(status_code=422, detail="status precisa ser APPROVED ou REJECTED")
    if task.client_approval_status != TaskApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail="Tarefa não está aguardando validação do cliente")
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


@router.post("/task-dependencies", response_model=TaskDependencyRead, status_code=status.HTTP_201_CREATED)
def create_dependency(
    data: TaskDependencyCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskDependency:
    predecessor = _get_task_or_404(db, data.predecessor_task_id)
    successor = _get_task_or_404(db, data.successor_task_id)
    if predecessor.project_id != successor.project_id:
        raise HTTPException(status_code=422, detail="Predecessora e sucessora precisam pertencer ao mesmo projeto")
    if predecessor.id == successor.id:
        raise HTTPException(status_code=422, detail="Uma tarefa não pode depender de si mesma")
    require_project_access(predecessor.project, user, write=True)
    if db.scalar(
        select(TaskDependency).where(
            TaskDependency.predecessor_task_id == predecessor.id,
            TaskDependency.successor_task_id == successor.id,
        )
    ):
        raise HTTPException(status_code=409, detail="Essa dependência já existe")
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
        raise HTTPException(status_code=404, detail="Dependência não encontrada")
    successor = _get_task_or_404(db, dependency.successor_task_id)
    require_project_access(successor.project, user, write=True)
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
    task = _get_task_or_404(db, task_id)
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
    task = _get_task_or_404(db, task_id)
    require_project_access(task.project, user, write=True)
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
    task = _get_task_or_404(db, task_id)
    require_project_access(task.project, user, write=True)
    resource = db.get(Resource, data.resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    if db.scalar(
        select(TaskAssignment).where(TaskAssignment.task_id == task_id, TaskAssignment.resource_id == data.resource_id)
    ):
        raise HTTPException(status_code=409, detail="Recurso já alocado nesta tarefa")
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
    task = _get_task_or_404(db, task_id)
    require_project_access(task.project, user)
    return list(db.scalars(select(TaskAssignment).where(TaskAssignment.task_id == task_id)).all())


@router.delete("/tasks/{task_id}/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_assignment(
    task_id: str,
    assignment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    task = _get_task_or_404(db, task_id)
    require_project_access(task.project, user, write=True)
    assignment = db.get(TaskAssignment, assignment_id)
    if not assignment or assignment.task_id != task_id:
        raise HTTPException(status_code=404, detail="Alocação não encontrada")
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
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    require_project_access(project, user, write=True)
    updated = recalculate_wbs(db, project_id)
    record_audit(db, entity_type="project", entity_id=project_id, action=AuditAction.UPDATE, user_id=user.id, details={"action": "recalculate_wbs"})
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
    task = _get_task_or_404(db, task_id)
    require_project_access(task.project, user, write=True)
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
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    require_project_access(project, user, write=True)
    cal = calendar_from_db(db, data.calendar_id) if data.calendar_id else calendar_for_project(db, project)
    updated = recalculate_schedule(db, project_id, cal)
    record_audit(db, entity_type="project", entity_id=project_id, action=AuditAction.UPDATE, user_id=user.id, details={"action": "reschedule_all"})
    db.commit()
    for item in updated:
        db.refresh(item)
    return updated
