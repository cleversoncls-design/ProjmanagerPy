from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .color_palette import DEFAULT_PROJECT_COLOR


class Base(DeclarativeBase):
    pass


class StrEnum(str, enum.Enum):
    pass


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    INTERNAL_PM = "INTERNAL_PM"
    CONSULTANT = "CONSULTANT"
    CLIENT_PM = "CLIENT_PM"
    CLIENT_USER = "CLIENT_USER"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    BLOCKED = "BLOCKED"


class Language(StrEnum):
    """Idioma da interface e das mensagens de erro da API — hoje só
    Português (padrão) e Espanhol. Fica no cadastro do usuário (não no
    navegador) pra seguir o usuário entre dispositivos, ver
    routers/users.py PATCH /users/me."""

    PT_BR = "pt-BR"
    ES = "es"


class IntakeStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ProjectStatus(StrEnum):
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    # Projeto-modelo: só existe pra servir de base pro botão "Copiar
    # estrutura de outro projeto" (ver routers/projects.py copy_tasks_from)
    # — nunca entra em indicador/dashboard (ver _scoped_projects e roi() em
    # routers/reports.py) e, por não ser ACTIVE, apontamento de horas já
    # fica bloqueado nele pela regra existente em routers/timesheets.py.
    MODELO = "MODELO"


class DependencyType(StrEnum):
    FS = "FS"
    FF = "FF"
    SS = "SS"
    SF = "SF"


class TaskStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DELAYED = "DELAYED"
    # "Desativar tarefa" (pedido do usuário) — estado final de "cerrada",
    # diferente de COMPLETED (que segue significando "concluída dentro do
    # fluxo normal"). Uma tarefa CLOSED não aparece mais como pendente/
    # atrasada em nenhum indicador (ver TASK_FINISHED_STATUSES abaixo) e
    # para de aceitar apontamento de horas (ver timesheets._resolve_task_and_project).
    CLOSED = "CLOSED"


# Conjunto de status "finalizados" pra fins de indicador (bolinha de status,
# % restante, atrasadas) — COMPLETED e CLOSED contam igual nesses cálculos,
# mesmo sendo estados conceitualmente diferentes (concluída vs. desativada).
TASK_FINISHED_STATUSES = frozenset({TaskStatus.COMPLETED, TaskStatus.CLOSED})


class TaskType(StrEnum):
    MANAGEMENT = "MANAGEMENT"
    CONSULTING = "CONSULTING"


class TaskApprovalStatus(StrEnum):
    """Aprovação da tarefa pelo lado do cliente (gerente de projeto do
    cliente ou usuário-chave), independente do TaskStatus de execução —
    uma tarefa pode estar COMPLETED e ainda não ter sido validada pelo
    cliente."""

    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TimesheetStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"


class RiskStatus(StrEnum):
    OPEN = "OPEN"
    MITIGATED = "MITIGATED"
    CLOSED = "CLOSED"


class ChangeStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ResourceFunction(StrEnum):
    """Categoria de função do recurso (pedido do usuário, "melhorias parte
    4") — combinada com `Resource.level` (1 a 4) pra indicar a senioridade.
    Decisão confirmada: dois campos independentes (Função + Nível) em vez
    de uma lista única com as 8 combinações literais sugeridas (ex.:
    "Consultor Pleno - Nível 2"); mais flexível pra relatórios/filtros,
    mesmo que tecnicamente permita combinações que não existem na prática
    (ex.: "Gerente de Projetos" com nível 3) — risco aceito pelo usuário."""

    CONSULTANT = "CONSULTANT"
    DEVELOPER = "DEVELOPER"
    SPECIALIST = "SPECIALIST"
    PROJECT_MANAGER = "PROJECT_MANAGER"


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(255))
    tax_id: Mapped[str | None] = mapped_column(String(30), unique=True)
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(2))
    zip_code: Mapped[str | None] = mapped_column(String(15))
    primary_contact_name: Mapped[str | None] = mapped_column(String(255))
    primary_contact_email: Mapped[str | None] = mapped_column(String(255))
    primary_contact_phone: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    users: Mapped[list[User]] = relationship(back_populates="client")
    projects: Mapped[list[Project]] = relationship(back_populates="client")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(nullable=False)
    status: Mapped[UserStatus] = mapped_column(nullable=False, default=UserStatus.ACTIVE)
    # `values_callable` é necessário aqui: por padrão o SQLAlchemy grava/lê
    # colunas Enum pelo NOME do membro Python (ex.: "PT_BR"), não pelo
    # `.value` — passa despercebido em todo outro enum deste arquivo porque
    # neles nome e valor são iguais (ex.: UserStatus.ACTIVE = "ACTIVE").
    # Language é o único onde divergem (Language.PT_BR = "pt-BR"), e o tipo
    # nativo do Postgres criado pela migração 0005 usa os VALORES
    # ("pt-BR"/"es") como rótulo — sem isso, todo SELECT em User quebra com
    # "'pt-BR' is not among the defined enum values".
    language: Mapped[Language] = mapped_column(
        SqlEnum(Language, name="language", values_callable=lambda enum_cls: [member.value for member in enum_cls]),
        nullable=False,
        default=Language.PT_BR,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    client: Mapped[Client | None] = relationship(back_populates="users")
    resource: Mapped[Resource | None] = relationship(back_populates="user", uselist=False)


class ProjectIntake(Base):
    __tablename__ = "project_intakes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    estimated_budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    estimated_hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    status: Mapped[IntakeStatus] = mapped_column(nullable=False, default=IntakeStatus.SUBMITTED)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)
    manager_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(nullable=False, default=ProjectStatus.PLANNING)
    sold_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    # Quebra do valor vendido entre horas de gestão e de consultoria — cada
    # bolsa tem sua própria quantidade de horas contratadas e seu próprio
    # valor/hora. `sold_value` continua existindo como coluna (usado direto
    # por project_financials), mas passa a ser CALCULADO a partir destes 4
    # campos no momento de criar/atualizar o projeto (ver app/routers/projects.py),
    # em vez de ser digitado diretamente.
    management_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    management_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    consulting_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    consulting_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    # "% de Margem vendida na BID" (pedido do usuário) — um valor DECLARADO
    # na venda/proposta, digitado direto no formulário; nunca calculado a
    # partir de custo (não existe custo conhecido ainda nesse estágio do
    # projeto) nem reconciliado depois com a margem real (profit_margin em
    # services.project_financials, essa sim calculada a partir do custo
    # efetivo). Opcional — fica em branco até alguém preencher.
    margin_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    # Calendário aplicado ao projeto (dias úteis/feriados usados para
    # calcular datas finais e o motor de reagendamento). Opcional: sem ele,
    # o recálculo cai no calendário padrão (segunda a sexta, sem feriados) —
    # ver `services.calendar_for_project`. Pode ser comparado/validado
    # contra o calendário pessoal do consultor (Resource.calendar_id) na
    # tela de recursos.
    calendar_id: Mapped[str | None] = mapped_column(ForeignKey("calendars.id", ondelete="SET NULL"))
    # "Data de status"/data-base: a partir dela, o sistema calcula o %
    # previsto e o status (no prazo/atrasada) de cada tarefa — ver
    # `services.project_evm` e `services.task_dot_color`. None = usa a data
    # de hoje como data-base (comportamento antes de existir este campo).
    status_date: Mapped[date | None] = mapped_column(Date)
    # Cor do projeto — um hex (ex.: "#2A78D6") da paleta de 256 cores
    # nomeadas em app/color_palette.py (PROJECT_COLOR_PALETTE; validação de
    # membership fica no router, não aqui). Aplicada automaticamente em toda
    # agenda (ResourceSchedule) deste projeto na tela "Agenda de
    # consultores", sem escolha manual por agendamento.
    color: Mapped[str] = mapped_column(String(20), nullable=False, default=DEFAULT_PROJECT_COLOR)
    # Enquanto o projeto está "ativo" (status fora de COMPLETED/CANCELLED/
    # MODELO), a cor acima é exclusiva dele — nenhum outro projeto ativo
    # pode usar o mesmo hex (ver _ensure_color_available em
    # routers/projects.py). Ao virar COMPLETED ou CANCELLED, este flag liga
    # sozinho: a cor real (`color`, nunca apagada) some da tela e o
    # projeto passa a aparecer com o padrão listrado branco/vermelho fixo
    # (ver PROJECT_STRIPED_PATTERN no frontend), liberando o hex pra outro
    # projeto ativo escolher. Volta a False sozinho se o projeto for
    # reativado (status muda de volta pra fora desse grupo) — nesse
    # momento a cor original pode já ter sido tomada por outro projeto
    # nesse meio tempo, então update_project revalida a exclusividade.
    color_striped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    client: Mapped[Client] = relationship(back_populates="projects")
    calendar: Mapped[Calendar | None] = relationship()
    tasks: Mapped[list[Task]] = relationship(back_populates="project", cascade="all, delete-orphan")
    expenses: Mapped[list[ProjectExpense]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Baseline(Base):
    __tablename__ = "baselines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    version_name: Mapped[str] = mapped_column(String(100), nullable=False)
    snapshot_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    wbs_code: Mapped[str] = mapped_column(String(50), nullable=False)
    task_type: Mapped[TaskType] = mapped_column(nullable=False, default=TaskType.CONSULTING)
    # "Duração" (dias) — campo primário do agendamento effort-driven (estilo
    # MS Project): estimated_hours ("Trabalho") é derivado dela × a
    # capacidade diária dos recursos alocados (ou 8h/dia sem nenhum recurso
    # alocado ainda). Editar estimated_hours diretamente faz o cálculo
    # inverso. Ver `services.apply_effort_driven`.
    duration_days: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=1)
    estimated_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    actual_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    # Posição manual entre as tarefas-irmãs (mesmo parent_task_id) — usada
    # por "mover tarefa" (reordenar/reparentar) e por `recalculate_wbs` para
    # decidir a ordem final do WBS, já que a ordenação alfabética de
    # wbs_code não reflete mais a ordem depois de um recálculo. Não é único
    # nem denso (gaps são normais); só a ordem relativa importa.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    planned_start_date: Mapped[date | None] = mapped_column(Date)
    planned_end_date: Mapped[date | None] = mapped_column(Date)
    actual_start_date: Mapped[date | None] = mapped_column(Date)
    actual_end_date: Mapped[date | None] = mapped_column(Date)
    dependency_type: Mapped[DependencyType] = mapped_column(nullable=False, default=DependencyType.FS)
    lag_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_critical_path: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_milestone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    progress_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    status: Mapped[TaskStatus] = mapped_column(nullable=False, default=TaskStatus.NOT_STARTED)
    client_approval_status: Mapped[TaskApprovalStatus] = mapped_column(nullable=False, default=TaskApprovalStatus.NOT_REQUIRED)
    # Campo de observações livre (item 16 do pedido de revisão da tela de
    # tarefas) — texto sem estrutura, nunca usado em cálculo nenhum.
    notes: Mapped[str | None] = mapped_column(Text)
    # "Nível mínimo" exigido pra executar a tarefa (pedido do usuário,
    # "melhorias parte 4") — usado só como FILTRO no seletor de "Recurso" da
    # alocação (Recursos Alocados, ver frontend): o combo esconde recursos
    # com `Resource.level` definido e abaixo do mínimo, mas um recurso SEM
    # nível definido continua aparecendo (decisão deliberada, pra não
    # esvaziar o seletor enquanto os recursos ainda não tiverem Função/
    # Nível preenchidos) — e nada é bloqueado no backend. Obrigatório
    # (pedido explícito do usuário); default 1 = "qualquer nível serve".
    min_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    __table_args__ = (
        UniqueConstraint("project_id", "wbs_code", name="uq_task_project_wbs"),
        CheckConstraint("min_level BETWEEN 1 AND 4", name="ck_task_min_level_range"),
    )
    project: Mapped[Project] = relationship(back_populates="tasks")
    parent: Mapped[Task | None] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list[Task]] = relationship(back_populates="parent")
    assignments: Mapped[list[TaskAssignment]] = relationship(back_populates="task", cascade="all, delete-orphan")
    timesheets: Mapped[list[Timesheet]] = relationship(back_populates="task", cascade="all, delete-orphan")


class Resource(Base):
    __tablename__ = "resources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    # Função (categoria) e Nível (1 a 4, senioridade) — pedido do usuário,
    # "melhorias parte 4": substituem o antigo campo de texto livre
    # `role_title`. Ambos opcionais — nenhuma migração automática do texto
    # livre existente (decisão confirmada); cada recurso recebe a Função/
    # Nível corretos quando alguém editar o cadastro dele. `level` é um
    # inteiro simples (não um enum) de propósito: permite comparação >=
    # direta no filtro de "Nível mínimo" da tarefa (ver `Task.min_level`).
    function: Mapped[ResourceFunction | None] = mapped_column(SqlEnum(ResourceFunction, name="resource_function"))
    level: Mapped[int | None] = mapped_column(Integer)
    internal_cost_per_hour: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    billing_rate_per_hour: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    daily_capacity_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=8)
    # Calendário pessoal (dias úteis/feriados) usado para nivelar a agenda
    # deste recurso — opcional; sem ele, o recálculo de cronograma usa o
    # calendário do projeto/calendar_id informado explicitamente na chamada.
    calendar_id: Mapped[str | None] = mapped_column(ForeignKey("calendars.id", ondelete="SET NULL"))
    __table_args__ = (CheckConstraint("level IS NULL OR level BETWEEN 1 AND 4", name="ck_resource_level_range"),)
    user: Mapped[User] = relationship(back_populates="resource")
    calendar: Mapped[Calendar | None] = relationship()


class ResourceSchedule(Base):
    """Agenda de um recurso num projeto — item novo, independente de
    TaskAssignment (que só marca QUE o recurso está alocado na tarefa, sem
    horário nenhum). Aqui é o "agendamento" de verdade: um bloco de
    horário (dia + hora início/fim) num projeto específico, usado pela
    tela "Agenda de consultores" e como referência para o apontamento
    (Timesheet) saber se o consultor tinha algo agendado naquele dia —
    ver TimesheetCreate.schedule_id no fase 2 (apontamento)."""

    __tablename__ = "resource_schedules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resource: Mapped[Resource] = relationship()
    project: Mapped[Project] = relationship()


class TaskAssignment(Base):
    __tablename__ = "task_assignments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    allocated_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    __table_args__ = (UniqueConstraint("task_id", "resource_id", name="uq_task_resource"),)
    task: Mapped[Task] = relationship(back_populates="assignments")


class ProjectResource(Base):
    """Vínculo direto recurso↔projeto (pedido do usuário: "vincular os
    usuários ao projeto principal" pra não ter que alocar tarefa por
    tarefa) — pensado pra projetos pequenos, conduzidos por 1 ou 2
    consultores no máximo. Não substitui TaskAssignment: uma tarefa que já
    tem alocação própria continua restrita só a quem está alocado nela
    (ver `_resolve_task_and_project` em routers/timesheets.py — busca
    primeiro no TaskAssignment da tarefa, só cai pra este vínculo quando a
    tarefa não tem nenhuma alocação específica). Sem `allocated_hours`
    (diferente de TaskAssignment): é só uma lista de quem pode apontar
    horas no projeto como um todo, não uma alocação de capacidade."""

    __tablename__ = "project_resources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("project_id", "resource_id", name="uq_project_resource"),)
    project: Mapped[Project] = relationship()
    resource: Mapped[Resource] = relationship()


class Timesheet(Base):
    __tablename__ = "timesheets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Apontamento "avulso" (sem tarefa pré-definida na EAP, padrão
    # Clockify/Toggl): task_id fica nulo e project_id opcionalmente aloca o
    # custo a um projeto sem exigir WBS. Os dois nulos = hora administrativa
    # interna, sem alocação a nenhum projeto.
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    # Bloco da Agenda (ResourceSchedule) que este apontamento cumpre —
    # opcional, só informativo/de referência (ver `unscheduled` abaixo, que é
    # quem de fato decide a regra de aprovação extra). SET NULL: apagar o
    # agendamento não pode arrastar um apontamento (dado financeiro) junto.
    schedule_id: Mapped[str | None] = mapped_column(ForeignKey("resource_schedules.id", ondelete="SET NULL"))
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # Hora início/fim + intervalo (Fase 2 do apontamento) — `hours_spent`
    # nunca é digitado diretamente: é sempre calculado a partir destes três
    # (mesmo padrão de `Project.sold_value`, ver _recompute_hours_spent no
    # router). Nulos em registros antigos (criados antes desta fase, quando
    # só existia `hours_spent` solto) — nunca em um apontamento novo.
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hours_spent: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    # "Avulso" no sentido novo (Fase 2): apontamento num projeto/data em que
    # o recurso NÃO tinha nenhum ResourceSchedule — pede aprovação extra
    # (só ADMIN aprova, ver update_timesheet_status). Independente do
    # "avulso" antigo (task_id nulo, comentário acima) — os dois conceitos
    # coexistem: dá pra ter uma tarefa da EAP apontada fora da agenda, ou um
    # apontamento sem tarefa mas dentro de um horário agendado no projeto.
    # Sempre False para hora administrativa interna (sem task_id nem
    # project_id) — não há agenda de projeto pra checar nesse caso.
    unscheduled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # "Traslado" (deslocamento, pedido do usuário) — apontamento sempre
    # vinculado a um projeto (project_id setado) mas sem task_id, igual ao
    # "avulso" de cima; a diferença é só de rótulo/categoria de relatório
    # (ver TASK_TYPE_LABELS.TRASLADO no frontend e o bucket "TRASLADO" em
    # financials_by_task_type, services.py) — não entra em Task.actual_hours
    # de nenhuma tarefa (não tem task_id) mas soma normalmente no total de
    # horas do projeto, exatamente como um apontamento avulso já fazia.
    is_transit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TimesheetStatus] = mapped_column(nullable=False, default=TimesheetStatus.PENDING)
    task: Mapped[Task | None] = relationship(back_populates="timesheets")
    project: Mapped[Project | None] = relationship()
    schedule: Mapped[ResourceSchedule | None] = relationship()


class ServiceOrderNumber(Base):
    """Número sequencial oficial (Nro. O.S.) e data de Emissão de uma
    Ordem de Serviço impressa (ver `service_orders` em services.py).

    A Ordem de Serviço em si não é uma entidade gravada (é montada na hora
    agrupando Timesheet por dia+projeto+consultor) — só o NÚMERO e a data
    de emissão precisam ser fixos pra sempre depois de emitidos (documento
    com linha de assinatura do cliente). Por isso esta tabela guarda só
    isso, uma linha por grupo (dia, projeto, consultor), atribuída na
    primeira vez que o grupo aparece na tela/relatório de Ordens de
    Serviço — nunca muda depois disso, mesmo que os apontamentos daquele
    dia sejam editados depois (só o CONTEÚDO da OS impressa muda).

    `number` é o próprio id autoincrement — evita uma corrida de
    "MAX()+1" calculada na mão entre requisições concorrentes."""

    __tablename__ = "service_order_numbers"
    number: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    emitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.utcnow())
    __table_args__ = (UniqueConstraint("date", "project_id", "resource_id", name="uq_service_order_number_group"),)


class ProjectExpense(Base):
    __tablename__ = "project_expenses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    project: Mapped[Project] = relationship(back_populates="expenses")


class Calendar(Base):
    __tablename__ = "calendars"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    working_days: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=lambda: [0, 1, 2, 3, 4])
    # Calendário usado pra mostrar feriados como indisponíveis na Agenda
    # (tela não é de um projeto só, então em vez de resolver o calendário de
    # cada projeto/recurso visível no mês, um único calendário "padrão" vale
    # pra todo mundo ali — pedido do usuário). Só um calendário por vez pode
    # ser o padrão — ver _set_as_default em routers/calendars.py, que
    # desliga o anterior sempre que um novo é marcado.
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    holidays: Mapped[list[Holiday]] = relationship(back_populates="calendar", cascade="all, delete-orphan")


class Holiday(Base):
    __tablename__ = "holidays"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    calendar_id: Mapped[str] = mapped_column(ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    __table_args__ = (UniqueConstraint("calendar_id", "date", name="uq_calendar_holiday"),)
    calendar: Mapped[Calendar] = relationship(back_populates="holidays")


class Risk(Base):
    __tablename__ = "risks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    probability: Mapped[RiskLevel] = mapped_column(nullable=False)
    impact: Mapped[RiskLevel] = mapped_column(nullable=False)
    mitigation_plan: Mapped[str | None] = mapped_column(Text)
    status: Mapped[RiskStatus] = mapped_column(nullable=False, default=RiskStatus.OPEN)
    project: Mapped[Project] = relationship()


class ChangeRequest(Base):
    __tablename__ = "change_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cost_impact: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    schedule_impact_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    project: Mapped[Project] = relationship()
    status: Mapped[ChangeStatus] = mapped_column(nullable=False, default=ChangeStatus.PENDING)


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    predecessor_task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    successor_task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    dependency_type: Mapped[DependencyType] = mapped_column(nullable=False, default=DependencyType.FS)
    lag_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    __table_args__ = (UniqueConstraint("predecessor_task_id", "successor_task_id", name="uq_dependency_pair"),)


class AuditAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class AuditLog(Base):
    """Registro mínimo de auditoria: quem criou/alterou qual registro e
    quando. Não é um log de todas as leituras nem um diff campo-a-campo
    completo — apenas o suficiente para responder "quem mexeu nisso e
    quando" nas entidades de negócio mais sensíveis (projetos, tarefas,
    timesheets, mudanças)."""

    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[AuditAction] = mapped_column(nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
