from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_project_access
from ..models import Project, Resource, Task, TaskAssignment, TaskDependency, User
from ..schemas import (
    RescheduleRequest,
    TaskAssignmentCreate,
    TaskAssignmentRead,
    TaskCreate,
    TaskDependencyCreate,
    TaskDependencyRead,
    TaskRead,
    TaskUpdate,
)
from ..services import calendar_from_db, reschedule_cascade

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
    task = Task(project_id=project_id, **data.model_dump())
    db.add(task)
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
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
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
    db.commit()
    db.refresh(dependency)
    return dependency


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
        cal = calendar_from_db(db, data.calendar_id)
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
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get("/tasks/{task_id}/assignments", response_model=list[TaskAssignmentRead])
def list_assignments(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[TaskAssignment]:
    task = _get_task_or_404(db, task_id)
    require_project_access(task.project, user)
    return list(db.scalars(select(TaskAssignment).where(TaskAssignment.task_id == task_id)).all())
