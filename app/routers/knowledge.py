from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..audit import record_audit
from ..database import get_db
from ..deps import (
    INTERNAL_ROLES,
    KNOWLEDGE_CATALOG_ROLES,
    KNOWLEDGE_REVIEW_ROLES,
    KNOWLEDGE_SELF_ASSESSMENT_ROLES,
    get_current_user,
    require_roles,
)
from ..i18n import t as translate
from ..models import (
    AuditAction,
    KnowledgeFunctionality,
    KnowledgeModule,
    KnowledgeStatus,
    KnowledgeSubmission,
    KnowledgeSystem,
    Resource,
    ResourceKnowledge,
    User,
    UserRole,
)
from ..schemas import (
    KnowledgeFunctionalityCreate,
    KnowledgeFunctionalityRead,
    KnowledgeModuleCreate,
    KnowledgeModuleRead,
    KnowledgeSubmissionItemRead,
    KnowledgeSubmissionRead,
    KnowledgeSubmissionReview,
    KnowledgeSystemCreate,
    KnowledgeSystemRead,
    MyKnowledgeFunctionalityRead,
    MyKnowledgeModuleRead,
    MyKnowledgeSystemRead,
    ResourceKnowledgeUpsert,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# "NOVAS MELHORIAS" (pedido do usuário): processo de registro de
# conhecimento dos consultores — três telas, três conjuntos de acesso
# (ver app/deps.py KNOWLEDGE_CATALOG_ROLES/KNOWLEDGE_SELF_ASSESSMENT_ROLES/
# KNOWLEDGE_REVIEW_ROLES, exatamente como o usuário especificou por tela).
# O cálculo da matriz agregada e o cruzamento com nível exigido em tarefas
# ficaram de fora desta rodada (o usuário pediu como "futuramente") — ver
# claude/registro-conhecimento-consultores.md.


def _get_system_or_404(db: Session, system_id: str, lang: str) -> KnowledgeSystem:
    system = db.get(KnowledgeSystem, system_id)
    if not system:
        raise HTTPException(status_code=404, detail=translate("Sistema não encontrado", lang))
    return system


def _get_module_or_404(db: Session, module_id: str, lang: str) -> KnowledgeModule:
    module = db.get(KnowledgeModule, module_id)
    if not module:
        raise HTTPException(status_code=404, detail=translate("Módulo não encontrado", lang))
    return module


def _get_functionality_or_404(db: Session, functionality_id: str, lang: str) -> KnowledgeFunctionality:
    functionality = db.get(KnowledgeFunctionality, functionality_id)
    if not functionality:
        raise HTTPException(status_code=404, detail=translate("Funcionalidade não encontrada", lang))
    return functionality


def _get_own_resource_or_422(db: Session, user: User) -> Resource:
    """Mesmo critério/mensagem de create_timesheet (routers/timesheets.py):
    um Consultor/Gerente de Projeto sem cadastro de Recurso vinculado não
    tem como se autoavaliar."""
    resource = db.scalar(select(Resource).where(Resource.user_id == user.id))
    if not resource:
        raise HTTPException(status_code=422, detail=translate("Usuário não possui recurso habilitado", user.language))
    return resource


# ---------------------------------------------------------------------------
# Cadastro das Funcionalidades (Sistema / Módulo / Funcionalidade)
# ---------------------------------------------------------------------------


@router.get("/catalog", response_model=list[KnowledgeSystemRead])
def list_catalog(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[KnowledgeSystem]:
    """Catálogo completo — leitura aberta a qualquer perfil INTERNO (nunca
    cliente: é dado de gestão de equipe, não de projeto). Cadastrar/editar/
    excluir continua restrito a KNOWLEDGE_CATALOG_ROLES (ver abaixo)."""
    if user.role not in INTERNAL_ROLES:
        raise HTTPException(status_code=403, detail=translate("Acesso restrito a perfis internos", user.language))
    return list(
        db.scalars(
            select(KnowledgeSystem)
            .options(selectinload(KnowledgeSystem.modules).selectinload(KnowledgeModule.functionalities))
            .order_by(KnowledgeSystem.name)
        ).all()
    )


@router.post("/systems", response_model=KnowledgeSystemRead, status_code=status.HTTP_201_CREATED)
def create_system(
    data: KnowledgeSystemCreate, user: User = Depends(require_roles(*KNOWLEDGE_CATALOG_ROLES)), db: Session = Depends(get_db)
) -> KnowledgeSystem:
    system = KnowledgeSystem(
        name=data.name,
        description=data.description,
        applies_to_consultant=data.applies_to_consultant,
        applies_to_internal_pm=data.applies_to_internal_pm,
        requirement=data.requirement.value,
    )
    db.add(system)
    db.flush()
    record_audit(db, entity_type="knowledge_system", entity_id=system.id, action=AuditAction.CREATE, user_id=user.id)
    db.commit()
    db.refresh(system)
    return system


@router.patch("/systems/{system_id}", response_model=KnowledgeSystemRead)
def update_system(
    system_id: str,
    data: KnowledgeSystemCreate,
    user: User = Depends(require_roles(*KNOWLEDGE_CATALOG_ROLES)),
    db: Session = Depends(get_db),
) -> KnowledgeSystem:
    system = _get_system_or_404(db, system_id, user.language)
    system.name = data.name
    system.description = data.description
    system.applies_to_consultant = data.applies_to_consultant
    system.applies_to_internal_pm = data.applies_to_internal_pm
    system.requirement = data.requirement.value
    record_audit(db, entity_type="knowledge_system", entity_id=system.id, action=AuditAction.UPDATE, user_id=user.id)
    db.commit()
    db.refresh(system)
    return system


@router.delete("/systems/{system_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_system(
    system_id: str, user: User = Depends(require_roles(*KNOWLEDGE_CATALOG_ROLES)), db: Session = Depends(get_db)
) -> None:
    """Apaga em cascata todos os Módulos/Funcionalidades deste Sistema e
    qualquer ResourceKnowledge ligado a elas (ver `ondelete="CASCADE"` em
    app/models.py) — autoavaliações registradas nessas funcionalidades se
    perdem junto, de propósito (o Sistema deixou de existir no catálogo)."""
    system = _get_system_or_404(db, system_id, user.language)
    record_audit(db, entity_type="knowledge_system", entity_id=system_id, action=AuditAction.DELETE, user_id=user.id)
    db.delete(system)
    db.commit()
    return None


@router.post("/systems/{system_id}/modules", response_model=KnowledgeModuleRead, status_code=status.HTTP_201_CREATED)
def create_module(
    system_id: str,
    data: KnowledgeModuleCreate,
    user: User = Depends(require_roles(*KNOWLEDGE_CATALOG_ROLES)),
    db: Session = Depends(get_db),
) -> KnowledgeModule:
    _get_system_or_404(db, system_id, user.language)
    module = KnowledgeModule(
        system_id=system_id,
        name=data.name,
        description=data.description,
        applies_to_consultant=data.applies_to_consultant,
        applies_to_internal_pm=data.applies_to_internal_pm,
        requirement=data.requirement.value,
    )
    db.add(module)
    db.flush()
    record_audit(db, entity_type="knowledge_module", entity_id=module.id, action=AuditAction.CREATE, user_id=user.id)
    db.commit()
    db.refresh(module)
    return module


@router.patch("/modules/{module_id}", response_model=KnowledgeModuleRead)
def update_module(
    module_id: str,
    data: KnowledgeModuleCreate,
    user: User = Depends(require_roles(*KNOWLEDGE_CATALOG_ROLES)),
    db: Session = Depends(get_db),
) -> KnowledgeModule:
    module = _get_module_or_404(db, module_id, user.language)
    module.name = data.name
    module.description = data.description
    module.applies_to_consultant = data.applies_to_consultant
    module.applies_to_internal_pm = data.applies_to_internal_pm
    module.requirement = data.requirement.value
    record_audit(db, entity_type="knowledge_module", entity_id=module.id, action=AuditAction.UPDATE, user_id=user.id)
    db.commit()
    db.refresh(module)
    return module


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_module(
    module_id: str, user: User = Depends(require_roles(*KNOWLEDGE_CATALOG_ROLES)), db: Session = Depends(get_db)
) -> None:
    module = _get_module_or_404(db, module_id, user.language)
    record_audit(db, entity_type="knowledge_module", entity_id=module_id, action=AuditAction.DELETE, user_id=user.id)
    db.delete(module)
    db.commit()
    return None


@router.post(
    "/modules/{module_id}/functionalities", response_model=KnowledgeFunctionalityRead, status_code=status.HTTP_201_CREATED
)
def create_functionality(
    module_id: str,
    data: KnowledgeFunctionalityCreate,
    user: User = Depends(require_roles(*KNOWLEDGE_CATALOG_ROLES)),
    db: Session = Depends(get_db),
) -> KnowledgeFunctionality:
    _get_module_or_404(db, module_id, user.language)
    functionality = KnowledgeFunctionality(
        module_id=module_id, name=data.name, description=data.description, requirement=data.requirement.value
    )
    db.add(functionality)
    db.flush()
    record_audit(db, entity_type="knowledge_functionality", entity_id=functionality.id, action=AuditAction.CREATE, user_id=user.id)
    db.commit()
    db.refresh(functionality)
    return functionality


@router.patch("/functionalities/{functionality_id}", response_model=KnowledgeFunctionalityRead)
def update_functionality(
    functionality_id: str,
    data: KnowledgeFunctionalityCreate,
    user: User = Depends(require_roles(*KNOWLEDGE_CATALOG_ROLES)),
    db: Session = Depends(get_db),
) -> KnowledgeFunctionality:
    functionality = _get_functionality_or_404(db, functionality_id, user.language)
    functionality.name = data.name
    functionality.description = data.description
    functionality.requirement = data.requirement.value
    record_audit(
        db, entity_type="knowledge_functionality", entity_id=functionality.id, action=AuditAction.UPDATE, user_id=user.id
    )
    db.commit()
    db.refresh(functionality)
    return functionality


@router.delete("/functionalities/{functionality_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_functionality(
    functionality_id: str, user: User = Depends(require_roles(*KNOWLEDGE_CATALOG_ROLES)), db: Session = Depends(get_db)
) -> None:
    functionality = _get_functionality_or_404(db, functionality_id, user.language)
    record_audit(
        db, entity_type="knowledge_functionality", entity_id=functionality_id, action=AuditAction.DELETE, user_id=user.id
    )
    db.delete(functionality)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Registro de Funcionalidades por Consultor / Gerente (autoavaliação)
# ---------------------------------------------------------------------------


@router.get("/my-catalog", response_model=list[MyKnowledgeSystemRead])
def get_my_catalog(
    user: User = Depends(require_roles(*KNOWLEDGE_SELF_ASSESSMENT_ROLES)), db: Session = Depends(get_db)
) -> list[MyKnowledgeSystemRead]:
    """Catálogo filtrado pelo perfil do recurso logado (decisão confirmada
    com o usuário: o vínculo de perfil fica no Módulo) e já anotado com a
    autoavaliação existente de cada Funcionalidade, se houver. Dentro de um
    módulo liberado, TODAS as funcionalidades aparecem — o recurso avalia
    direto (0 a 4) as que fizerem parte do trabalho dele; o que não mexer
    fica `status=None` ("não avaliada"), sem precisar de um passo de
    seleção separado (decisão confirmada com o usuário)."""
    resource = _get_own_resource_or_422(db, user)
    profile_column = KnowledgeModule.applies_to_consultant if user.role == UserRole.CONSULTANT else KnowledgeModule.applies_to_internal_pm

    systems = list(
        db.scalars(
            select(KnowledgeSystem).options(selectinload(KnowledgeSystem.modules).selectinload(KnowledgeModule.functionalities)).order_by(KnowledgeSystem.name)
        ).all()
    )
    existing = {
        rk.functionality_id: rk
        for rk in db.scalars(select(ResourceKnowledge).where(ResourceKnowledge.resource_id == resource.id)).all()
    }

    result: list[MyKnowledgeSystemRead] = []
    for system in systems:
        visible_modules = [m for m in system.modules if getattr(m, profile_column.key)]
        if not visible_modules:
            continue
        modules_out = []
        for module in visible_modules:
            functionalities_out = []
            for functionality in module.functionalities:
                record = existing.get(functionality.id)
                functionalities_out.append(
                    MyKnowledgeFunctionalityRead(
                        id=functionality.id,
                        name=functionality.name,
                        description=functionality.description,
                        requirement=functionality.requirement,
                        self_level=record.self_level if record else None,
                        reviewed_level=record.reviewed_level if record else None,
                        status=record.status if record else None,
                        notes=record.notes if record else None,
                    )
                )
            modules_out.append(
                MyKnowledgeModuleRead(id=module.id, name=module.name, description=module.description, functionalities=functionalities_out)
            )
        result.append(MyKnowledgeSystemRead(id=system.id, name=system.name, description=system.description, modules=modules_out))
    return result


@router.put("/my-ratings/{functionality_id}", response_model=MyKnowledgeFunctionalityRead)
def upsert_my_rating(
    functionality_id: str,
    data: ResourceKnowledgeUpsert,
    user: User = Depends(require_roles(*KNOWLEDGE_SELF_ASSESSMENT_ROLES)),
    db: Session = Depends(get_db),
) -> MyKnowledgeFunctionalityRead:
    resource = _get_own_resource_or_422(db, user)
    functionality = _get_functionality_or_404(db, functionality_id, user.language)
    module = functionality.module
    visible = module.applies_to_consultant if user.role == UserRole.CONSULTANT else module.applies_to_internal_pm
    if not visible:
        raise HTTPException(
            status_code=403, detail=translate("Esta funcionalidade não está liberada para o seu perfil", user.language)
        )

    record = db.scalar(
        select(ResourceKnowledge).where(
            ResourceKnowledge.resource_id == resource.id, ResourceKnowledge.functionality_id == functionality_id
        )
    )
    if not record:
        record = ResourceKnowledge(resource_id=resource.id, functionality_id=functionality_id)
        db.add(record)

    record.self_level = data.self_level
    record.notes = data.notes
    # Editar depois de aprovado/rejeitado reabre um novo ciclo (decisão
    # documentada em ResourceKnowledge.__doc__): volta pra DRAFT, solto de
    # qualquer envio anterior. `reviewed_level` do ciclo anterior fica como
    # estava até uma nova aprovação sobrescrever.
    record.status = KnowledgeStatus.DRAFT.value
    record.submission_id = None
    db.commit()
    db.refresh(record)
    return MyKnowledgeFunctionalityRead(
        id=functionality.id,
        name=functionality.name,
        description=functionality.description,
        requirement=functionality.requirement,
        self_level=record.self_level,
        reviewed_level=record.reviewed_level,
        status=record.status,
        notes=record.notes,
    )


@router.post("/my-ratings/submit", response_model=KnowledgeSubmissionRead, status_code=status.HTTP_201_CREATED)
def submit_my_ratings(
    user: User = Depends(require_roles(*KNOWLEDGE_SELF_ASSESSMENT_ROLES)), db: Session = Depends(get_db)
) -> KnowledgeSubmission:
    """Envia pra revisão TODAS as autoavaliações em DRAFT do recurso logado,
    de uma vez (decisão confirmada com o usuário: aprovação é sempre do
    envio inteiro, nunca item a item)."""
    resource = _get_own_resource_or_422(db, user)
    draft_records = list(
        db.scalars(
            select(ResourceKnowledge).where(
                ResourceKnowledge.resource_id == resource.id, ResourceKnowledge.status == KnowledgeStatus.DRAFT.value
            )
        ).all()
    )
    if not draft_records:
        raise HTTPException(
            status_code=422, detail=translate("Nenhuma autoavaliação pendente para enviar", user.language)
        )

    submission = KnowledgeSubmission(resource_id=resource.id, status=KnowledgeStatus.SUBMITTED.value)
    db.add(submission)
    db.flush()
    for record in draft_records:
        record.submission_id = submission.id
        record.status = KnowledgeStatus.SUBMITTED.value
    record_audit(
        db,
        entity_type="knowledge_submission",
        entity_id=submission.id,
        action=AuditAction.CREATE,
        user_id=user.id,
        details={"items": len(draft_records)},
    )
    db.commit()
    db.refresh(submission)
    return _submission_to_read(submission)


@router.get("/my-submissions", response_model=list[KnowledgeSubmissionRead])
def list_my_submissions(
    user: User = Depends(require_roles(*KNOWLEDGE_SELF_ASSESSMENT_ROLES)), db: Session = Depends(get_db)
) -> list[KnowledgeSubmissionRead]:
    """Histórico dos próprios envios (inclui REJECTED, com `review_notes`
    explicando o motivo) — pra tela de autoavaliação poder mostrar um
    aviso tipo "seu último envio foi devolvido: <review_notes>". Note que
    um envio REJECTED aqui ainda referencia os itens (`submission_id` não
    é zerado na rejeição, ver review_submission abaixo) até o recurso
    editar algum deles de novo."""
    resource = _get_own_resource_or_422(db, user)
    submissions = list(
        db.scalars(
            select(KnowledgeSubmission)
            .where(KnowledgeSubmission.resource_id == resource.id)
            .order_by(KnowledgeSubmission.submitted_at.desc())
        ).all()
    )
    return [_submission_to_read(submission) for submission in submissions]


# ---------------------------------------------------------------------------
# Revisão e Aprovação
# ---------------------------------------------------------------------------


def _submission_to_read(submission: KnowledgeSubmission) -> KnowledgeSubmissionRead:
    items = []
    for record in submission.items:
        functionality = record.functionality
        items.append(
            KnowledgeSubmissionItemRead(
                id=record.id,
                functionality_id=functionality.id,
                system_name=functionality.module.system.name,
                module_name=functionality.module.name,
                functionality_name=functionality.name,
                requirement=functionality.requirement,
                self_level=record.self_level,
                reviewed_level=record.reviewed_level,
                notes=record.notes,
            )
        )
    return KnowledgeSubmissionRead(
        id=submission.id,
        resource_id=submission.resource_id,
        resource_name=submission.resource.user.name,
        resource_user_id=submission.resource.user_id,
        status=submission.status,
        submitted_at=submission.submitted_at,
        reviewed_by=submission.reviewed_by,
        reviewer_name=submission.reviewer.name if submission.reviewer else None,
        reviewed_at=submission.reviewed_at,
        review_notes=submission.review_notes,
        items=items,
    )


def _get_submission_or_404(db: Session, submission_id: str, lang: str) -> KnowledgeSubmission:
    submission = db.get(KnowledgeSubmission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail=translate("Envio não encontrado", lang))
    return submission


@router.get("/submissions", response_model=list[KnowledgeSubmissionRead])
def list_submissions(
    status_filter: str | None = None,
    user: User = Depends(require_roles(*KNOWLEDGE_REVIEW_ROLES)),
    db: Session = Depends(get_db),
) -> list[KnowledgeSubmissionRead]:
    """Lista de envios — por padrão só os PENDENTES (SUBMITTED), que é o que
    a tela de revisão precisa mostrar primeiro; `?status_filter=APPROVED`
    (ou REJECTED) mostra o histórico já revisado."""
    stmt = select(KnowledgeSubmission).order_by(KnowledgeSubmission.submitted_at.desc())
    stmt = stmt.where(KnowledgeSubmission.status == (status_filter or KnowledgeStatus.SUBMITTED.value))
    submissions = list(db.scalars(stmt).all())
    return [_submission_to_read(submission) for submission in submissions]


@router.get("/submissions/{submission_id}", response_model=KnowledgeSubmissionRead)
def get_submission(
    submission_id: str, user: User = Depends(require_roles(*KNOWLEDGE_REVIEW_ROLES)), db: Session = Depends(get_db)
) -> KnowledgeSubmissionRead:
    submission = _get_submission_or_404(db, submission_id, user.language)
    return _submission_to_read(submission)


@router.patch("/submissions/{submission_id}", response_model=KnowledgeSubmissionRead)
def review_submission(
    submission_id: str,
    data: KnowledgeSubmissionReview,
    user: User = Depends(require_roles(*KNOWLEDGE_REVIEW_ROLES)),
    db: Session = Depends(get_db),
) -> KnowledgeSubmissionRead:
    """Aprova ou rejeita o envio INTEIRO (decisão confirmada com o usuário:
    nunca item a item). Na aprovação, o revisor pode ajustar o nível de
    qualquer item via `data.items` (decisão confirmada: "revisor pode
    ajustar o nível") — o que não vier listado mantém
    `reviewed_level = self_level`. Na rejeição, `review_notes` é
    obrigatório (motivo) e os itens voltam pra DRAFT, soltos deste envio,
    pro recurso editar e reenviar."""
    submission = _get_submission_or_404(db, submission_id, user.language)
    if submission.status != KnowledgeStatus.SUBMITTED.value:
        raise HTTPException(status_code=409, detail=translate("Este envio já foi revisado", user.language))
    if data.status not in (KnowledgeStatus.APPROVED, KnowledgeStatus.REJECTED):
        raise HTTPException(status_code=422, detail=translate("Status inválido — use APPROVED ou REJECTED", user.language))

    # Um revisor não pode aprovar/rejeitar a própria autoavaliação — um
    # Gerente de Projetos está em KNOWLEDGE_SELF_ASSESSMENT_ROLES E em
    # KNOWLEDGE_REVIEW_ROLES ao mesmo tempo (pedido do usuário, acesso
    # literal das duas telas), então precisa de outra pessoa pra revisar a
    # própria.
    if submission.resource.user_id == user.id:
        raise HTTPException(
            status_code=403, detail=translate("Você não pode revisar sua própria autoavaliação", user.language)
        )

    if data.status == KnowledgeStatus.REJECTED and not (data.review_notes and data.review_notes.strip()):
        raise HTTPException(
            status_code=422, detail=translate("Informe o motivo da rejeição em Comentário do revisor", user.language)
        )

    overrides = {item.functionality_id: item.reviewed_level for item in data.items}

    if data.status == KnowledgeStatus.APPROVED:
        for record in submission.items:
            record.reviewed_level = overrides.get(record.functionality_id, record.self_level)
            record.status = KnowledgeStatus.APPROVED.value
    else:
        # `submission_id` É MANTIDO de propósito (não zerado aqui) — assim a
        # resposta deste PATCH (e qualquer consulta futura a este envio)
        # continua mostrando o que foi rejeitado, pra fins de histórico. Só
        # fica "solto" do envio quando o recurso editar de novo (ver
        # upsert_my_rating acima, que aí sim zera `submission_id`).
        for record in submission.items:
            record.status = KnowledgeStatus.DRAFT.value

    submission.status = data.status.value
    submission.reviewed_by = user.id
    submission.reviewed_at = datetime.now(timezone.utc)
    submission.review_notes = data.review_notes
    record_audit(
        db,
        entity_type="knowledge_submission",
        entity_id=submission.id,
        action=AuditAction.UPDATE,
        user_id=user.id,
        details={"status": data.status.value},
    )
    db.commit()
    db.refresh(submission)
    return _submission_to_read(submission)
