from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import MANAGEMENT_ROLES, get_current_user, get_current_user_allow_pending_password, require_roles
from ..i18n import t as translate
from ..models import AuditAction, ChangeRequest, Client, Project, Resource, TaskAssignment, Timesheet, User, UserRole
from ..schemas import UserCreate, UserPasswordReset, UserRead, UserSelfUpdate, UserUpdate
from ..security import hash_password

router = APIRouter(tags=["users"])


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    # Cadastrar usuário continua exclusivo de ADMIN, de propósito — pedido
    # do usuário: Gerente de Serviços/Diretor Geral têm acesso equivalente
    # ao Administrador em tudo, EXCETO aqui (e em update_user/delete_user/
    # reset_user_password abaixo). Nunca trocar por MANAGEMENT_ROLES/
    # ADMIN_LIKE_ROLES nestes quatro endpoints.
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> User:
    if data.role in {UserRole.CLIENT_PM, UserRole.CLIENT_USER} and not data.client_id:
        raise HTTPException(status_code=422, detail=translate("Perfis de cliente exigem client_id", admin_user.language))
    if data.client_id and not db.get(Client, data.client_id):
        raise HTTPException(status_code=404, detail=translate("Cliente não encontrado", admin_user.language))
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(status_code=409, detail=translate("Já existe um usuário com este e-mail", admin_user.language))
    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        # Senha provisória definida pelo ADMIN: o usuário é obrigado a trocar
        # no primeiro acesso (ver deps.get_current_user).
        must_change_password=True,
        role=data.role,
        client_id=data.client_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user_allow_pending_password)) -> User:
    return current_user


@router.patch("/users/me", response_model=UserRead)
def update_my_language(
    data: UserSelfUpdate,
    current_user: User = Depends(get_current_user_allow_pending_password),
    db: Session = Depends(get_db),
) -> User:
    """Autoatendimento de idioma — qualquer usuário logado pode trocar,
    sem depender de um ADMIN editar o cadastro (PATCH /users/{id})."""
    current_user.language = data.language
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/users", response_model=list[UserRead])
def list_users(
    role: UserRole | None = None,
    client_id: str | None = None,
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
    db: Session = Depends(get_db),
) -> list[User]:
    """Faltava um jeito de listar usuários — só existia `GET /users/me`. Sem
    isso, uma tela (de gestão de usuários, ou só o seletor de `manager_id`
    ao criar um projeto / `user_id` ao criar um recurso) não tem como
    popular a lista de opções. Restrito a quem já pode criar recurso
    (MANAGEMENT_ROLES — inclui Gerente de Serviços/Diretor Geral: eles
    precisam enxergar a lista de usuários pra vincular um Recurso, mesmo não
    podendo criar/editar/excluir Usuário — ver create_user/update_user/
    delete_user abaixo, que continuam travados em UserRole.ADMIN)."""
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if client_id:
        stmt = stmt.where(User.client_id == client_id)
    return list(db.scalars(stmt.order_by(User.name)).all())


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    data: UserUpdate,
    # Continua ADMIN-only — ver comentário em create_user acima.
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> User:
    """Edição de usuário — inclui bloquear/desbloquear via `status`
    (UserStatus.BLOCKED impede login em POST /auth/login, ver deps.py e
    routers/auth.py, que já checavam `status != ACTIVE`)."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=translate("Usuário não encontrado", current_user.language))
    changes = data.model_dump(exclude_unset=True)
    if "role" in changes and changes["role"] in {UserRole.CLIENT_PM, UserRole.CLIENT_USER}:
        effective_client_id = changes.get("client_id", user.client_id)
        if not effective_client_id:
            raise HTTPException(status_code=422, detail=translate("Perfis de cliente exigem client_id", current_user.language))
    if "client_id" in changes and changes["client_id"] and not db.get(Client, changes["client_id"]):
        raise HTTPException(status_code=404, detail=translate("Cliente não encontrado", current_user.language))
    for field, value in changes.items():
        setattr(user, field, value)
    if changes:
        record_audit(db, entity_type="user", entity_id=user.id, action=AuditAction.UPDATE, user_id=current_user.id, details={"fields": sorted(changes.keys())})
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    # Continua ADMIN-only — ver comentário em create_user acima.
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    """O usuário Administrador nunca pode ser excluído — mas qualquer outro
    (inclusive um perfil de cliente sem recurso vinculado, ex.: cadastrado
    por engano) pode, desde que não esteja "em uso":
    - gerente de algum projeto (Project.manager_id é ondelete=RESTRICT —
      sem esta checagem, o DELETE quebraria com um IntegrityError feio em
      vez de uma mensagem clara);
    - autor de alguma solicitação de mudança (ChangeRequest.requested_by
      também é RESTRICT, mesmo motivo);
    - dono de um recurso que já tem alocação em tarefa ou apontamento de
      horas — Resource.user_id é ondelete=CASCADE, então apagar o usuário
      apagaria o recurso (e, em cascata, esse histórico) sem perguntar;
      um recurso "limpo" (sem histórico) pode ir junto sem problema.
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=translate("Usuário não encontrado", current_user.language))
    if user.role == UserRole.ADMIN:
        raise HTTPException(status_code=409, detail=translate("O usuário Administrador não pode ser excluído", current_user.language))
    if db.scalar(select(Project).where(Project.manager_id == user_id)):
        raise HTTPException(
            status_code=409,
            detail=translate("Usuário é gerente de um ou mais projetos — troque o gerente antes de excluir", current_user.language),
        )
    if db.scalar(select(ChangeRequest).where(ChangeRequest.requested_by == user_id)):
        raise HTTPException(
            status_code=409,
            detail=translate("Usuário solicitou uma ou mais mudanças de escopo — não pode ser excluído", current_user.language),
        )
    resource = db.scalar(select(Resource).where(Resource.user_id == user_id))
    if resource:
        if db.scalar(select(TaskAssignment).where(TaskAssignment.resource_id == resource.id)):
            raise HTTPException(
                status_code=409,
                detail=translate(
                    "O recurso deste usuário está alocado em uma ou mais tarefas — remova as alocações antes de excluir",
                    current_user.language,
                ),
            )
        if db.scalar(select(Timesheet).where(Timesheet.resource_id == resource.id)):
            raise HTTPException(
                status_code=409,
                detail=translate(
                    "O recurso deste usuário tem apontamento de horas em projetos/tarefas — não pode ser excluído",
                    current_user.language,
                ),
            )
    record_audit(db, entity_type="user", entity_id=user.id, action=AuditAction.DELETE, user_id=current_user.id, details={"email": user.email})
    db.delete(user)  # cascata apaga o Resource (se houver e já passou pelas checagens acima)
    db.commit()


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password(
    user_id: str,
    data: UserPasswordReset,
    # Continua ADMIN-only — ver comentário em create_user acima.
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=translate("Usuário não encontrado", current_user.language))
    user.password_hash = hash_password(data.new_password)
    # Senha redefinida pelo ADMIN é provisória: força nova troca no próximo
    # acesso e derruba as sessões abertas com a senha antiga.
    user.must_change_password = True
    user.token_version = (user.token_version or 0) + 1
    record_audit(db, entity_type="user", entity_id=user.id, action=AuditAction.UPDATE, user_id=current_user.id, details={"action": "password_reset"})
    db.commit()
    return None
