from __future__ import annotations

from sqlalchemy.orm import Session

from .models import AuditAction, AuditLog


def record_audit(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    action: AuditAction,
    user_id: str | None,
    details: dict | None = None,
) -> None:
    """Registra uma entrada de auditoria (quem fez o quê, em qual registro).

    Não chama `db.commit()` de propósito: o chamador já está dentro da
    mesma transação da mudança de negócio (criar/atualizar o registro), e
    `db.add` aqui garante que a entrada de auditoria seja persistida junto
    no mesmo commit — nunca uma sem a outra.
    """
    db.add(
        AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            details=details,
        )
    )
