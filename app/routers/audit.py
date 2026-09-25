from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..models import AuditLog, User, UserRole
from ..schemas import AuditLogRead

router = APIRouter(tags=["audit"])


@router.get("/audit-log", response_model=list[AuditLogRead])
def list_audit_log(
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = 100,
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM)),
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    """Lista as entradas de auditoria mais recentes primeiro.

    Restrito a perfis internos com poder de gestão (ADMIN, INTERNAL_PM):
    quem alterou o quê é informação operacional interna, não algo que faça
    sentido expor a CONSULTANT ou aos perfis de cliente.
    """
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    stmt = stmt.limit(min(max(limit, 1), 500))
    return list(db.scalars(stmt).all())
