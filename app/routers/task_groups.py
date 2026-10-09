from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import MANAGEMENT_ROLES, require_roles
from ..i18n import t as translate
from ..models import AuditAction, TaskGroup, TaskGroupItem, User
from ..schemas import TaskGroupCreate, TaskGroupItemCreate, TaskGroupItemRead, TaskGroupRead

router = APIRouter(prefix="/task-groups", tags=["task-groups"])

# "Grupos de Tarefas" (pedido do usuário: agrupador de tarefas reutilizável,
# aplicado depois como filhas de uma tarefa de projeto — ver
# services.apply_task_group_to_task) é um cadastro interno, sem isolamento
# por cliente — mesmo critério de Calendários: gerenciar fica restrito a
# MANAGEMENT_ROLES (quem administra Projetos/Tarefas em geral).
_MANAGE_ROLES = MANAGEMENT_ROLES


def _build_item_tree(items: list[TaskGroupItem], parent_id: str | None = None) -> list[TaskGroupItemRead]:
    """Monta a árvore (parent_item_id) a partir da lista achatada de itens
    do grupo — mesmo padrão recursivo de `recalculate_wbs`/`task_dot_colors`
    em app/services.py, aqui sem precisar de memoização (a árvore de um
    grupo é pequena e não tem referência circular, montada uma vez só por
    leitura)."""
    by_parent: dict[str | None, list[TaskGroupItem]] = defaultdict(list)
    for item in items:
        by_parent[item.parent_item_id].append(item)
    for siblings in by_parent.values():
        siblings.sort(key=lambda i: i.sort_order)

    def build(pid: str | None) -> list[TaskGroupItemRead]:
        return [
            TaskGroupItemRead(
                id=item.id,
                name=item.name,
                task_type=item.task_type,
                duration_days=item.duration_days,
                estimated_hours=item.estimated_hours,
                is_milestone=item.is_milestone,
                notes=item.notes,
                min_level=item.min_level,
                modality=item.modality,
                children=build(item.id),
            )
            for item in by_parent.get(pid, [])
        ]

    return build(parent_id)


def _group_to_read(group: TaskGroup) -> TaskGroupRead:
    return TaskGroupRead(
        id=group.id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        items=_build_item_tree(list(group.items)),
    )


def _create_items_tree(
    db: Session, group_id: str, items_in: list[TaskGroupItemCreate], parent_item_id: str | None = None
) -> None:
    """Cria recursivamente os nós informados, já na ordem recebida
    (`sort_order` = posição na lista). Dá `flush()` a cada nó pra obter o id
    gerado (default do modelo só roda no flush, ver TaskGroupItem.id) antes
    de criar os filhos — eles precisam desse id em `parent_item_id`."""
    for index, item_in in enumerate(items_in):
        item = TaskGroupItem(
            group_id=group_id,
            parent_item_id=parent_item_id,
            name=item_in.name,
            task_type=item_in.task_type,
            duration_days=item_in.duration_days,
            estimated_hours=item_in.estimated_hours,
            sort_order=index,
            is_milestone=item_in.is_milestone,
            notes=item_in.notes,
            min_level=item_in.min_level,
            modality=item_in.modality,
        )
        db.add(item)
        db.flush()
        _create_items_tree(db, group_id, item_in.children, parent_item_id=item.id)


def _get_group_or_404(db: Session, group_id: str, lang: str) -> TaskGroup:
    group = db.get(TaskGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail=translate("Grupo de tarefas não encontrado", lang))
    return group


@router.post("", response_model=TaskGroupRead, status_code=status.HTTP_201_CREATED)
def create_task_group(
    data: TaskGroupCreate,
    user: User = Depends(require_roles(*_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> TaskGroupRead:
    group = TaskGroup(name=data.name, description=data.description)
    db.add(group)
    db.flush()
    _create_items_tree(db, group.id, data.items)
    record_audit(db, entity_type="task_group", entity_id=group.id, action=AuditAction.CREATE, user_id=user.id)
    db.commit()
    db.refresh(group)
    return _group_to_read(group)


@router.get("", response_model=list[TaskGroupRead])
def list_task_groups(
    _: User = Depends(require_roles(*_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> list[TaskGroupRead]:
    groups = list(db.scalars(select(TaskGroup).order_by(TaskGroup.name)).all())
    return [_group_to_read(group) for group in groups]


@router.get("/{group_id}", response_model=TaskGroupRead)
def read_task_group(
    group_id: str,
    user: User = Depends(require_roles(*_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> TaskGroupRead:
    group = _get_group_or_404(db, group_id, user.language)
    return _group_to_read(group)


@router.put("/{group_id}", response_model=TaskGroupRead)
def update_task_group(
    group_id: str,
    data: TaskGroupCreate,
    user: User = Depends(require_roles(*_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> TaskGroupRead:
    """Substitui a árvore inteira do grupo (apaga todos os itens e recria a
    partir do payload) — nenhuma outra entidade referencia um
    TaskGroupItem individualmente (só o próprio TaskGroup, via group_id),
    então não há nada pra preservar entre uma edição e outra; bem mais
    simples que fazer diff de árvore."""
    group = _get_group_or_404(db, group_id, user.language)
    group.name = data.name
    group.description = data.description
    db.execute(delete(TaskGroupItem).where(TaskGroupItem.group_id == group.id))
    db.flush()
    _create_items_tree(db, group.id, data.items)
    record_audit(db, entity_type="task_group", entity_id=group.id, action=AuditAction.UPDATE, user_id=user.id)
    db.commit()
    db.refresh(group)
    return _group_to_read(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_group(
    group_id: str,
    user: User = Depends(require_roles(*_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> None:
    group = _get_group_or_404(db, group_id, user.language)
    record_audit(db, entity_type="task_group", entity_id=group_id, action=AuditAction.DELETE, user_id=user.id)
    db.delete(group)
    db.commit()
    return None
