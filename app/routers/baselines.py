from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_project_access
from ..models import Baseline, Project, Task, User
from ..schemas import BaselineCreate, BaselineRead

router = APIRouter(tags=["baselines"])


def _serialize(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


@router.post("/projects/{project_id}/baselines", response_model=BaselineRead, status_code=201)
def create_baseline(
    project_id: str,
    data: BaselineCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Baseline:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    require_project_access(project, user, write=True)
    tasks = db.scalars(select(Task).where(Task.project_id == project_id)).all()
    snapshot = {
        "tasks": [
            {
                "id": t.id,
                "wbs_code": t.wbs_code,
                "name": t.name,
                "planned_start_date": _serialize(t.planned_start_date),
                "planned_end_date": _serialize(t.planned_end_date),
                "estimated_hours": _serialize(t.estimated_hours),
                "status": t.status.value,
            }
            for t in tasks
        ]
    }
    baseline = Baseline(project_id=project_id, version_name=data.version_name, snapshot_data=snapshot)
    db.add(baseline)
    db.commit()
    db.refresh(baseline)
    return baseline


@router.get("/projects/{project_id}/baselines", response_model=list[BaselineRead])
def list_baselines(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Baseline]:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    require_project_access(project, user)
    return list(db.scalars(select(Baseline).where(Baseline.project_id == project_id)).all())
