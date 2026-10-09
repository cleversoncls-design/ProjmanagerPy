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
    false,
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
    # Pedido do usuário: acessos equivalentes ao Administrador, exceto
    # cadastrar/editar/excluir usuário (continua exclusivo de ADMIN, ver
    # routers/users.py) — ver ADMIN_LIKE_ROLES/MANAGEMENT_ROLES/
    # INTERNAL_ROLES em app/deps.py, onde os dois entram em todo lugar que
    # hoje já é ADMIN ou ADMIN+INTERNAL_PM.
    SERVICE_MANAGER = "SERVICE_MANAGER"
    GENERAL_DIRECTOR = "GENERAL_DIRECTOR"


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


class TaskModality(StrEnum):
    """Onde a tarefa pode ser executada (pedido do usuário, "melhorias
    parte 5") — campo puramente informativo, sem validação nenhuma
    associada (não restringe quais recursos podem ser alocados nem bloqueia
    apontamento de horas). Default BOTH ("Ambos") = mais permissivo, mesmo
    critério do default de `Task.min_level`."""

    REMOTE = "REMOTE"
    ON_SITE = "ON_SITE"
    BOTH = "BOTH"


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


class AbsenceType(StrEnum):
    """Ausência da empresa (pedido do usuário: Férias/Licença Médica/
    Licença Maternidade/Ausência/Folga) — classificada igual ao "Traslado"
    (Timesheet.is_transit), só que o oposto: Traslado é SEMPRE vinculado a
    um projeto (custo do cliente); ausência é SEMPRE sem projeto nem tarefa
    (task_id e project_id nulos, igual a hora administrativa interna — custo
    interno da empresa, nunca atribuído a um cliente). Os dois são
    mutuamente exclusivos (ver _resolve_task_and_project em
    app/routers/timesheets.py). Decisões confirmadas com o usuário: qualquer
    aprovador vê o tipo exato (sem mascarar por perfil), lançamento dia a
    dia pelo mesmo formulário de apontamento normal, e mesmo fluxo de
    aprovação de sempre (PENDING -> APPROVED/REJECTED, MANAGEMENT_ROLES).
    Também bloqueia novo agendamento do recurso na Agenda de consultores
    nesse dia (ver _check_absence em app/routers/schedules.py)."""

    VACATION = "VACATION"  # Férias
    MEDICAL_LEAVE = "MEDICAL_LEAVE"  # Licença Médica
    MATERNITY_LEAVE = "MATERNITY_LEAVE"  # Licença Maternidade
    ABSENCE = "ABSENCE"  # Ausência
    DAY_OFF = "DAY_OFF"  # Folga


class WorkClassification(StrEnum):
    """Classificador Normal/Retrabalho de um apontamento vinculado a uma
    tarefa do projeto (pedido do usuário) — só faz sentido quando
    Timesheet.task_id está setado (Traslado/Ausência/hora interna não tem o
    que "retrabalhar"); omitido num apontamento de tarefa é tratado como
    NORMAL (ver _validate_rework em routers/timesheets.py). Quando REWORK,
    `Timesheet.rework_reasons` exige pelo menos um motivo da lista fixa
    (ReworkReason, logo abaixo)."""

    NORMAL = "NORMAL"
    REWORK = "REWORK"


class ReworkReason(StrEnum):
    """Motivo do retrabalho (pedido do usuário) — lista fixa e de múltipla
    escolha; `Timesheet.rework_reasons` guarda como lista JSON de valores
    deste enum (mesmo padrão de `ResourceSchedule.working_days`, uma coluna
    JSON em vez de uma tabela de ligação, já que a lista é fixa e não tem
    CRUD próprio). Pelo menos um motivo é obrigatório quando
    Timesheet.work_classification == REWORK."""

    PRODUCT_ERROR = "PRODUCT_ERROR"  # Erro de Produto
    INITIAL_CONFIG_ERROR = "INITIAL_CONFIG_ERROR"  # Erro de Configuração inicial
    DATA_LOAD_ERROR = "DATA_LOAD_ERROR"  # Erro de dados carregados
    USER_DELAY_OR_ABSENCE = "USER_DELAY_OR_ABSENCE"  # Atraso / Falta de Usuários
    ACCESS_ISSUE_SERVICE_SERVER = "ACCESS_ISSUE_SERVICE_SERVER"  # Problemas de Acesso (Serviços / Servidor)
    ACCESS_ISSUE_NETWORK = "ACCESS_ISSUE_NETWORK"  # Problemas de Acesso (Rede)
    CONSULTANT_CHANGE = "CONSULTANT_CHANGE"  # Troca de Consultor
    POWER_OUTAGE = "POWER_OUTAGE"  # Falta de Energia Elétrica


class RiskLevel(StrEnum):
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"


class RiskStatus(StrEnum):
    OPEN = "OPEN"
    MITIGATED = "MITIGATED"
    CLOSED = "CLOSED"


class RagStatus(StrEnum):
    """Semáforo (verde/amarelo/vermelho) usado nos 5 indicadores do Status
    Report (prazo, custo, margem, escopo, risco) — pedido do usuário: "2
    modelos de status report" baseados nos mockups já validados (badges
    "No prazo"/"Atenção"/"Atrasado" etc. do canvas de design). Só 3
    valores, fixo — por isso `ProjectStatusReport` abaixo guarda estes como
    `String` simples (não enum do Postgres), mesmo critério já usado em
    `EmailLog.kind`: evita repetir o bug de enum duplicado da migração
    0024 (ver alembic/versions/0024_email_settings.py), e aqui nem seria
    necessário por não ter previsão de crescer, mas o padrão String já
    estabelecido no projeto evita qualquer risco à toa."""

    GOOD = "GOOD"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ChangeStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ProjectType(StrEnum):
    """Classificador do projeto (pedido do usuário) — lista fixa, só
    informativa/filtro (nenhuma regra de cálculo depende dele). Guardado como
    String (não enum do Postgres) em Project.project_type, como as demais
    colunas de classificação recentes: acrescentar um tipo não exige migração."""

    FIXED_PRICE = "FIXED_PRICE"  # Projeto Fechado
    OPEN_HOURS = "OPEN_HOURS"  # Projeto Horas Abertas
    HOUR_BANK = "HOUR_BANK"  # Banco de Horas
    SUPPORT = "SUPPORT"  # Sustentação
    INTERNAL = "INTERNAL"  # Internos
    COMMERCIAL = "COMMERCIAL"  # Comercial
    INVESTMENT = "INVESTMENT"  # Investimento


class TicketCriticality(StrEnum):
    """Criticidade do ticket interno (pendente) — escolhida por quem abre."""

    LOW = "LOW"  # Baixa: não impede a operação
    MEDIUM = "MEDIUM"  # Média: dificulta o processo, mas existem alternativas
    HIGH = "HIGH"  # Alta: impede o funcionamento de um processo-chave
    CRITICAL = "CRITICAL"  # Crítica: interrupção total / bloqueio geral


class TicketStatus(StrEnum):
    """Fluxo do ticket: OPEN -> ASSIGNED (gerente direciona) -> IN_PROGRESS
    <-> WAITING_REQUESTER (responsável pede informação) -> RESOLVED
    (responsável conclui) -> CLOSED (só o solicitante confirma; se
    discordar, volta a IN_PROGRESS = reaberto)."""

    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_REQUESTER = "WAITING_REQUESTER"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketInteractionKind(StrEnum):
    CREATED = "CREATED"
    COMMENT = "COMMENT"
    ASSIGNMENT = "ASSIGNMENT"
    STATUS = "STATUS"
    CRITICALITY = "CRITICALITY"
    TIME = "TIME"  # horas apontadas na tarefa a partir do ticket


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
    # Troca de senha pelo próprio usuário (pedido do usuário):
    # - `must_change_password`: True quando o ADMIN cria o usuário ou redefine
    #   a senha dele (a senha provisória só vale pra entrar e trocar a
    #   própria senha); enquanto True, a API só libera /users/me e
    #   /auth/change-password (ver deps.get_current_user). Usuários que já
    #   existiam antes desta funcionalidade nascem com False (server_default).
    # - `token_version`: entra no JWT ("tv"); trocar/redefinir a senha
    #   incrementa o valor e, com isso, invalida qualquer token emitido antes
    #   ("encerra as outras sessões"). Tokens antigos, sem "tv", valem como 0.
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
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
    # Tipo do projeto (ver ProjectType) — opcional: projetos já existentes
    # ficam sem tipo até alguém classificar.
    project_type: Mapped[str | None] = mapped_column(String(30))
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


class ProjectStatusReport(Base):
    """Status Report por período (pedido do usuário: "pode implementar os
    2 modelos e colocar na opção de relatórios", depois dos mockups
    visuais no canvas de design — modelos "Interno"/diretoria-gerências e
    "Cliente"/gerente de projeto do cliente). Cada linha é um "fechamento"
    congelado — como uma Baseline, mas do panorama do período inteiro, não
    só das tarefas: uma vez salvo, os números não mudam mesmo que o
    projeto continue evoluindo depois (é o que permite reabrir um relatório
    antigo e ver exatamente o que foi reportado naquela data, mesmo que
    get_db/services já tenham dados mais novos).

    Campos calculados automaticamente na criação (ver
    services.build_status_report_snapshot) a partir de EVM
    (`services.project_evm`), financeiro (`services.project_financials`),
    burndown (`services.project_burndown`) e das tarefas/riscos do projeto
    — nunca recalculados depois. Campos narrativos (resumo, próximos
    passos) são digitados pelo PM ao criar.

    Dois perfis de leitura da MESMA linha, nunca duas linhas separadas:
    perfil externo (CLIENT_PM) recebe os campos financeiros
    (hours_consumed/hours_budgeted/cost_planned/cost_actual/
    margin_planned_pct/margin_actual_pct/burndown) como `None` na resposta
    da API (ver app/routers/status_reports.py, mesmo critério já usado em
    GET /projects/{id}/report para `financials`) — nunca mais um valor
    "zerado" fajuto, que seria indistinguível de um resultado real.

    `rag_*`/risks_snapshot usam `String`/`JSON` (nunca um enum do Postgres
    novo) — ver docstring de `RagStatus` acima."""

    __tablename__ = "project_status_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    prepared_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    # RAG (semáforo) — ver RagStatus acima. String simples, validado pelo
    # schema Pydantic (StatusReportCreate), não por constraint de banco.
    rag_schedule: Mapped[str] = mapped_column(String(12), nullable=False)
    rag_cost: Mapped[str] = mapped_column(String(12), nullable=False)
    rag_margin: Mapped[str] = mapped_column(String(12), nullable=False)
    rag_scope: Mapped[str] = mapped_column(String(12), nullable=False)
    rag_risk: Mapped[str] = mapped_column(String(12), nullable=False)

    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    # Compartilhado com o cliente (vai para os dois modelos/audiências).
    next_steps_client: Mapped[str] = mapped_column(Text, nullable=False)
    # "Ações internas (não compartilhadas com o cliente)" do modelo Interno
    # — nunca aparece na resposta da API para EXTERNAL_ROLES.
    next_steps_internal: Mapped[str | None] = mapped_column(Text)

    # --- Snapshot calculado (ver services.build_status_report_snapshot) ---
    schedule_actual_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    schedule_planned_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    # Campos financeiros — todos nullable (projeto pode não ter horas
    # orçadas/valor vendido ainda) E todos ocultados para EXTERNAL_ROLES na
    # resposta da API (ver docstring da classe).
    hours_consumed: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    hours_budgeted: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    cost_planned: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    cost_actual: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    margin_planned_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    margin_actual_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Listas congeladas no momento da criação (ver docstring da classe) —
    # cada item é um dict simples (chaves em string, datas/decimais como
    # string ISO), igual ao padrão já usado em Baseline.snapshot_data.
    tasks_done: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    tasks_next: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    # Gantt (nível 1+2 da EAP, congelado) — pedido do usuário: "imprima uma
    # imagem do GANTT [...] até o segundo nível [...] respeitando as cores
    # conforme definido no projeto [...] quando uma atividade estiver
    # concluída que mude de cor" (ver services._build_gantt_level2_snapshot
    # e StatusReportGanttMini.jsx, que desenha a partir deste campo).
    # Nullable (migração 0027, depois da tabela já existir em produção) —
    # relatório criado ANTES desta funcionalidade simplesmente não tem essa
    # "foto"; o frontend mostra uma mensagem no lugar do desenho. Aparece
    # pros dois perfis (interno/cliente) — é cronograma, não dado
    # financeiro, mesmo critério de tasks_done/tasks_next.
    gantt_snapshot: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True, default=None)
    risks_snapshot: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    # Burndown (ver services.project_burndown) — só preenchido pro modelo
    # Interno; oculto (None) para EXTERNAL_ROLES na resposta da API.
    burndown: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)

    project: Mapped[Project] = relationship()
    prepared_by: Mapped[User | None] = relationship()


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
    # Onde a tarefa pode ser executada (pedido do usuário, "melhorias parte
    # 5") — ver TaskModality. Só informativo (nada valida/filtra a partir
    # dele); default BOTH = "Ambos".
    modality: Mapped[TaskModality] = mapped_column(
        SqlEnum(TaskModality, name="task_modality"), nullable=False, default=TaskModality.BOTH
    )
    # "Atividade do cliente" (pedido do usuário): tarefa executada por
    # pessoas do CLIENTE, não por consultores — por isso não tem "Nível
    # mínimo" (fica sempre 1) nem alocação de Recurso (custo/valor/hora);
    # em vez disso recebe usuários do cliente do projeto direto, ver
    # TaskClientAssignment. Nenhuma hora dessas pessoas entra em custo ou
    # apontamento.
    is_client_activity: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    __table_args__ = (
        UniqueConstraint("project_id", "wbs_code", name="uq_task_project_wbs"),
        CheckConstraint("min_level BETWEEN 1 AND 4", name="ck_task_min_level_range"),
    )
    project: Mapped[Project] = relationship(back_populates="tasks")
    parent: Mapped[Task | None] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list[Task]] = relationship(back_populates="parent")
    assignments: Mapped[list[TaskAssignment]] = relationship(back_populates="task", cascade="all, delete-orphan")
    timesheets: Mapped[list[Timesheet]] = relationship(back_populates="task", cascade="all, delete-orphan")
    client_assignments: Mapped[list[TaskClientAssignment]] = relationship(back_populates="task", cascade="all, delete-orphan")

    @property
    def client_user_ids(self) -> list[str]:
        """Ids dos usuários do cliente alocados (só faz sentido quando
        `is_client_activity`) — exposto em TaskRead pra a tela de tarefas
        não precisar de uma chamada extra por tarefa."""
        return [a.user_id for a in self.client_assignments]


class TaskGroup(Base):
    """"Grupo de Tarefas" — pedido do usuário: um agrupador reutilizável de
    tarefas (não um projeto) que pode ser aplicado depois como filhas de
    qualquer tarefa de um projeto real, pra acelerar a criação de projetos
    parecidos (ex.: "Implantação módulo Fiscal" sempre tem a mesma
    sequência de tarefas). Decisão confirmada com o usuário: cadastro novo
    e dedicado (não reaproveitar Projeto Modelo/ProjectStatus.MODELO) — ali
    sempre existe um projeto de verdade por trás; aqui não existe projeto
    nenhum, só a árvore de tarefas em si. Gerenciado numa página própria do
    menu lateral (Clientes/Recursos), não dentro da tela de Projetos.

    Ver TaskGroupItem para os itens da árvore e
    services.apply_task_group_to_task para a aplicação dentro de uma tarefa
    de projeto."""

    __tablename__ = "task_groups"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    items: Mapped[list["TaskGroupItem"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class TaskGroupItem(Base):
    """Um nó da árvore de um TaskGroup — os campos de ESTRUTURA de uma
    tarefa (nome, tipo, duração/trabalho, marco, nível mínimo, modalidade,
    observações), sem nenhum campo de EXECUÇÃO (datas, status, progresso,
    recurso alocado, dependência entre tarefas): o grupo é só um molde,
    nunca roda apontamento nem é agendado por si só — tudo isso só passa a
    existir de verdade quando o grupo é aplicado dentro de uma tarefa de um
    projeto (vira Task, ver services.apply_task_group_to_task).

    `parent_item_id` suporta qualquer profundidade de aninhamento (decisão
    confirmada com o usuário: "hierarquia aninhada", não só um nível). Usa
    `ondelete="CASCADE"` — diferente de Task.parent_task_id, que usa
    SET NULL — porque um item de grupo não carrega histórico nem dado
    financeiro: apagar um nó do molde apaga de propósito toda a sub-árvore
    abaixo dele, mais simples pra quem está editando o grupo.

    Sem relacionamento ORM próprio pai→filhos de propósito (child items só
    existem via `parent_item_id`, sem `relationship()` dedicada): a árvore é
    montada em Python a partir da lista achatada (mesmo padrão já usado por
    `services.recalculate_wbs`/`task_dot_colors`), evitando a complexidade
    de um self-join — ver `_build_item_tree` em app/routers/task_groups.py."""

    __tablename__ = "task_group_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id: Mapped[str] = mapped_column(ForeignKey("task_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_item_id: Mapped[str | None] = mapped_column(ForeignKey("task_group_items.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_type: Mapped[TaskType] = mapped_column(nullable=False, default=TaskType.CONSULTING)
    duration_days: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=1)
    estimated_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_milestone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    min_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    modality: Mapped[TaskModality] = mapped_column(
        SqlEnum(TaskModality, name="task_modality"), nullable=False, default=TaskModality.BOTH
    )
    __table_args__ = (CheckConstraint("min_level BETWEEN 1 AND 4", name="ck_task_group_item_min_level_range"),)
    group: Mapped[TaskGroup] = relationship(back_populates="items")


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
    # Convite de calendário por e-mail (Agenda → Google Calendar): cada
    # consultor liga/desliga pra si mesmo (menu do avatar → "Meu Google
    # Calendar"). `calendar_invite_email` é o endereço da conta Google, quando
    # diferente do e-mail de login; vazio = usa o e-mail do usuário.
    calendar_invite_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    calendar_invite_email: Mapped[str | None] = mapped_column(String(255))
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
    # SEQUENCE do convite de calendário (.ics): sobe a cada reenvio do mesmo
    # evento (UID = id do agendamento) pra o Google atualizar em vez de
    # duplicar. Ver app/ics.py e notifications.notify_resource_schedule.
    ics_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resource: Mapped[Resource] = relationship()
    project: Mapped[Project] = relationship()
    # Tarefas vinculadas ao bloco (pedido do usuário: "adicionar uma ou mais
    # tarefas, sem horas, para a agenda" — o consultor vê, ao abrir o
    # agendamento, o que precisa trabalhar naquele horário). Sem hora
    # própria por tarefa: a hora é só a do bloco inteiro (start_time/
    # end_time acima); não confundir com TaskAssignment (aloca capacidade
    # na tarefa) nem com Timesheet.task_id (apontamento de verdade, feito
    # depois). order_by created_at preserva a ordem em que as tarefas foram
    # adicionadas (ver ResourceScheduleTask abaixo).
    schedule_tasks: Mapped[list["ResourceScheduleTask"]] = relationship(
        back_populates="schedule", cascade="all, delete-orphan", order_by="ResourceScheduleTask.created_at"
    )

    @property
    def tasks(self) -> list["Task"]:
        """Achata `schedule_tasks` (ResourceScheduleTask, a tabela de
        ligação) para list[Task] — é isso que ResourceScheduleRead.tasks
        (TaskRead) espera; o modelo de ligação em si nunca precisa vazar
        pra fora da API."""
        return [link.task for link in self.schedule_tasks]


class ResourceScheduleTask(Base):
    """Ligação agenda↔tarefa (pedido do usuário) — puramente uma lista do
    que fazer naquele bloco, sem `allocated_hours` (diferente de
    TaskAssignment): a tarefa aparece na Agenda só como item de checklist,
    nunca lança hora sozinha."""

    __tablename__ = "resource_schedule_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    schedule_id: Mapped[str] = mapped_column(ForeignKey("resource_schedules.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("schedule_id", "task_id", name="uq_schedule_task"),)
    schedule: Mapped[ResourceSchedule] = relationship(back_populates="schedule_tasks")
    task: Mapped["Task"] = relationship()


class TaskAssignment(Base):
    __tablename__ = "task_assignments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    allocated_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    __table_args__ = (UniqueConstraint("task_id", "resource_id", name="uq_task_resource"),)
    task: Mapped[Task] = relationship(back_populates="assignments")


class TaskClientAssignment(Base):
    """Usuário do CLIENTE responsável por uma "atividade do cliente"
    (Task.is_client_activity). Sem horas alocadas, custo ou nível — é só
    "quem do cliente faz isto". O usuário precisa ser CLIENT_PM/CLIENT_USER
    do mesmo cliente do projeto (validado em routers/tasks.py)."""

    __tablename__ = "task_client_assignments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    __table_args__ = (UniqueConstraint("task_id", "user_id", name="uq_task_client_user"),)
    task: Mapped[Task] = relationship(back_populates="client_assignments")


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
    # Ticket interno (pendente) que originou esta hora — opcional, só
    # informativo/de rastreio (a hora segue na tarefa do ticket, entrando em
    # custo e horas consumidas do projeto como qualquer apontamento). SET
    # NULL: apagar o ticket nunca pode arrastar um apontamento (dado
    # financeiro) junto.
    ticket_id: Mapped[str | None] = mapped_column(ForeignKey("tickets.id", ondelete="SET NULL"), index=True)
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
    # o recurso NÃO tinha nenhum ResourceSchedule — pede aprovação extra (só
    # ADMIN_LIKE_ROLES aprova, ver update_timesheet_status). Independente do
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
    # "Ausência da empresa" (pedido do usuário) — nulo na imensa maioria dos
    # apontamentos (trabalho normal). Quando setado, é o espelho do
    # "Traslado" acima: task_id e project_id ficam sempre nulos (custo
    # interno da empresa, nunca de um cliente/projeto — decisão confirmada
    # com o usuário), e a validação em _resolve_task_and_project garante que
    # nunca vem junto com is_transit=True nem com task_id/project_id
    # preenchidos. Mesmo assim entra normalmente em Resource.actual_hours
    # (resource_utilization, services.py) — uma semana de férias não aparece
    # como recurso ocioso — e fica automaticamente fora de
    # financials_by_task_type/service_orders (os dois são escopados por
    # project_id, que aqui é sempre nulo), sem precisar de nenhuma exclusão
    # manual (diferente do ProjectStatus.MODELO, que precisa).
    absence_type: Mapped[AbsenceType | None] = mapped_column(nullable=True)
    # "% de Avanço da Tarefa" (pedido do usuário) — só relevante quando
    # task_id está setado; é um retrato do avanço reportado NESTE
    # apontamento (histórico), e ao salvar também espelha o valor em
    # Task.progress_percentage (ver _apply_task_progress em
    # routers/timesheets.py) — mesma faixa 0-100 de Task.progress_percentage.
    task_progress_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    # Classificador Normal/Retrabalho (pedido do usuário) — só relevante
    # quando task_id está setado; ver WorkClassification acima e
    # _validate_rework em routers/timesheets.py.
    work_classification: Mapped[WorkClassification | None] = mapped_column(nullable=True)
    # Motivo(s) do retrabalho — lista JSON de valores de ReworkReason;
    # obrigatório (>= 1) quando work_classification == REWORK, deve ficar
    # vazio/nulo caso contrário (ver _validate_rework).
    rework_reasons: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
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


class Ticket(Base):
    """Ticket interno / pendente (pedido do usuário): um consultor registra
    um incidente ligado a uma tarefa de um projeto, o gerente direciona para
    outro consultor/desenvolvedor, e as interações ficam gravadas em
    `TicketInteraction` até o solicitante confirmar a solução. As horas
    gastas são apontadas na tarefa (Timesheet.ticket_id) — ver
    app/routers/tickets.py."""

    __tablename__ = "tickets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Número exibido (TK-2026-0012): `year` + `seq` (sequencial por ano).
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    # SET NULL: excluir a tarefa nunca apaga o histórico do ticket; a API
    # exige a tarefa na criação.
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    criticality: Mapped[str] = mapped_column(String(10), nullable=False, default=TicketCriticality.MEDIUM.value)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TicketStatus.OPEN.value, index=True)
    requester_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.utcnow())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    __table_args__ = (UniqueConstraint("year", "seq", name="uq_ticket_year_seq"),)
    project: Mapped[Project] = relationship()
    task: Mapped[Task | None] = relationship()
    requester: Mapped[User | None] = relationship(foreign_keys=[requester_id])
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    interactions: Mapped[list["TicketInteraction"]] = relationship(
        back_populates="ticket", order_by="TicketInteraction.created_at", cascade="all, delete-orphan"
    )


class TicketInteraction(Base):
    """Linha do tempo do ticket — só recebe registros novos (nunca editada
    nem apagada): comentário, mudança de status, direcionamento ou troca de
    criticidade, cada um com autor e data/hora."""

    __tablename__ = "ticket_interactions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    # Para STATUS/ASSIGNMENT/CRITICALITY: valor anterior e novo (texto curto;
    # em ASSIGNMENT guardam o NOME do usuário, pra o histórico continuar
    # legível mesmo que o cadastro mude depois).
    from_value: Mapped[str | None] = mapped_column(String(255))
    to_value: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.utcnow())
    ticket: Mapped[Ticket] = relationship(back_populates="interactions")
    author: Mapped[User | None] = relationship()


class TicketAttachment(Base):
    """Arquivo anexado a um ticket (print, log, planilha...) — ligado a uma
    interação do histórico (a abertura ou um comentário). O arquivo fica em
    disco (volume do Docker, ver app/routers/tickets.py `_upload_dir`) com
    nome gerado (`stored_name`); `filename` é o nome original, só para
    exibição/download. Nunca é apagado nem editado (histórico imutável)."""

    __tablename__ = "ticket_attachments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    interaction_id: Mapped[str | None] = mapped_column(ForeignKey("ticket_interactions.id", ondelete="SET NULL"), index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(80), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.utcnow())


class TicketWorkSession(Base):
    """Cronômetro de atendimento do ticket: o responsável aperta "Iniciar
    atendimento" (cria a sessão, `ended_at` vazio) e "Finalizar atendimento"
    (fecha a sessão e gera o apontamento de horas na tarefa do ticket, com a
    hora final do momento). Fica no servidor — não se perde se a tela
    fechar. Um usuário só tem UMA sessão aberta por vez (em qualquer
    ticket)."""

    __tablename__ = "ticket_work_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.utcnow())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    timesheet_id: Mapped[str | None] = mapped_column(ForeignKey("timesheets.id", ondelete="SET NULL"))


class ProjectLegacyConsumption(Base):
    """Consumo já apropriado no SISTEMA ANTERIOR (pedido do usuário: projetos
    migrados chegam com horas já consumidas, a um custo médio por hora). Cada
    lançamento é um bloco (data de referência, horas, custo médio/hora): o
    custo é `hours * cost_per_hour`. Entra no custo real/margem do projeto e
    nas horas consumidas (EVM/Status Report) — mas NÃO é um apontamento
    (Timesheet): não passa por aprovação, Ordem de Serviço nem agenda."""

    __tablename__ = "project_legacy_consumption"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    cost_per_hour: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


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


class EmailSecurity(StrEnum):
    NONE = "NONE"
    STARTTLS = "STARTTLS"
    SSL = "SSL"


class EmailSettings(Base):
    """Configuração de SMTP usada para o envio de e-mails do sistema
    (pedido do usuário: "será necessário criar um configurador de dados
    para envio de email? para indicar servidor, usuario, senha, tipos de
    autentitcação, email de origem, etc."). Decisão confirmada com o
    usuário: fica numa tela de Configurações (não em variável de
    ambiente), pra um Admin poder trocar sem precisar de acesso ao
    servidor nem redeploy.

    Linha única — a API sempre lê/atualiza a primeira (e única) linha da
    tabela (ver app/routers/email_settings.py); não existe endpoint pra
    criar uma segunda. `smtp_password_encrypted` nunca fica em texto puro
    (ver app/crypto.py — mesma técnica de criptografia simétrica reversível
    planejada para os tokens OAuth do Google Calendar, Fernet/`cryptography`)
    e nunca é devolvida pela API depois de salva — `EmailSettingsRead` só
    expõe `password_configured: bool`. `last_test_*` guarda o resultado do
    botão "Enviar e-mail de teste" da tela: o ambiente onde este código é
    desenvolvido não tem rede até um servidor SMTP de verdade, então a
    validação de que os dados batem só acontece no servidor real do
    usuário — mesma limitação já registrada na integração com Google
    Calendar."""

    __tablename__ = "email_settings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    security: Mapped[EmailSecurity] = mapped_column(nullable=False, default=EmailSecurity.STARTTLS)
    smtp_username: Mapped[str | None] = mapped_column(String(255))
    smtp_password_encrypted: Mapped[str | None] = mapped_column(Text)
    from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(255))
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_test_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    updated_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class EmailLog(Base):
    """Registro de toda TENTATIVA de envio de e-mail (sucesso ou falha) —
    pedido do usuário: "poderia criar um botão para abrir uma tela com o
    log dos emails enviados? esse log precisa ser gravado [...] na base
    de dados e que tenha a opção de limpar o log". Escrito de dentro de
    `send_raw_email` (app/email_service.py), então cobre tanto o botão
    "Enviar e-mail de teste" quanto todo aviso "de negócio" (agendamento,
    resumo de aprovações, e os que vierem depois).

    `kind` é string livre (não enum) DE PROPÓSITO: a lista de tipos de
    aviso ainda vai crescer ("estes são alguns casos, que vão ser
    incrementados", pedido original do usuário) e um enum do Postgres
    exige nova migração a cada tipo novo — foi exatamente esse tipo de
    migração (o enum `email_security` da tabela email_settings) que
    quebrou em produção por causa de um create_table tentando recriar o
    tipo; aqui, string simples evita repetir esse problema. Não tem
    `updated_at`/edição — é só um log de apêndice, apagado por inteiro
    pelo endpoint DELETE quando o usuário pedir "limpar o log"."""

    __tablename__ = "email_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, default="outro")
    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    to_name: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)


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


# ---------------------------------------------------------------------------
# Conhecimento (pedido do usuário, "NOVAS MELHORIAS": "criar um processo de
# registro de conhecimento dos consultores") — cadastro em 3 níveis
# (Sistema > Módulo > Funcionalidade), autoavaliação de nível de
# conhecimento por recurso (Consultor/Gerente de Projeto) e revisão/
# aprovação por um gestor. Decisões confirmadas com o usuário (perguntas
# diretas): aprovação é POR ENVIO COMPLETO (todo o lote enviado pelo
# recurso é aprovado ou rejeitado de uma vez, nunca item a item); o revisor
# PODE AJUSTAR o nível de cada item antes de aprovar (o nível final
# gravado é o do revisor, que pode diferir do autoavaliado); o vínculo de
# "quem pode se autoavaliar num módulo" (perfil Consultor e/ou Gerente de
# Projeto) fica no MÓDULO (não no Sistema nem na Funcionalidade); dentro de
# um módulo liberado pro seu perfil, o recurso avalia DIRETO (0 a 4) as
# funcionalidades que fazem parte do trabalho dele, sem um passo de
# "seleção" separado — o que ele não mexer fica como "não avaliado"
# (diferente de "Nível 0 - Não conhece", que é uma resposta explícita).
#
# O cálculo da "matriz de conhecimento" agregada e o cruzamento com nível
# exigido em tarefas/projetos (mencionados pelo usuário como "futuramente")
# NÃO fazem parte desta rodada — só o cadastro, a autoavaliação e a
# aprovação. Ver claude/registro-conhecimento-consultores.md.
# ---------------------------------------------------------------------------


class KnowledgeRequirement(StrEnum):
    """Pedido do usuário: "definir se o conhecimento é necessário ou
    desejável" — atributo da Funcionalidade (não do Módulo/Sistema nem da
    autoavaliação), decidido por quem cadastra o catálogo."""

    REQUIRED = "REQUIRED"
    DESIRABLE = "DESIRABLE"


class KnowledgeStatus(StrEnum):
    """Estado de um item de conhecimento (ResourceKnowledge) e, reaproveitado
    igual, do envio que o agrupa (KnowledgeSubmission — nunca fica DRAFT,
    só é criado já SUBMITTED). DRAFT: o recurso está editando, ainda não
    enviou. SUBMITTED: enviado, aguardando revisão (todo o lote junto — ver
    docstring da seção acima). APPROVED: revisor aprovou (o nível "oficial"
    passa a ser `reviewed_level`, que pode ter sido ajustado pelo revisor).
    REJECTED: revisor devolveu (com `review_notes` explicando o motivo,
    gravado no envio) — os itens voltam pra DRAFT, soltos do envio
    rejeitado, pro recurso editar e reenviar."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class KnowledgeSystem(Base):
    """Nível 1 do catálogo (ex.: "ERP Protheus", "Totvs RM"). Cadastro
    restrito a MANAGEMENT_ROLES (ver app/deps.py KNOWLEDGE_CATALOG_ROLES);
    qualquer perfil interno (não-cliente) pode LER, pra poder se
    autoavaliar. Excluir um Sistema apaga em cascata seus Módulos,
    Funcionalidades e qualquer ResourceKnowledge ligado a elas — ver
    docstring de KnowledgeModule/KnowledgeFunctionality.

    `applies_to_consultant`/`applies_to_internal_pm`/`requirement` (pedido
    do usuário, olhando a tela pronta: "a obrigatoriedade que hoje está
    para consultor e gerente de projetos, gostaria de configurar no
    sistema/módulo, incluindo se é necessário ou desejável") — decisão
    confirmada com o usuário: são campos **só de classificação/
    organização** neste nível. Diferente do mesmo par em KnowledgeModule,
    o perfil AQUI não filtra nada em GET /knowledge/my-catalog, e
    `requirement` AQUI não é o que aparece como badge na autoavaliação/
    revisão (isso continua vindo só de KnowledgeFunctionality.requirement,
    sem mudança nenhuma — "manter pela funcionalidade a mesma regra").
    Pelo menos um perfil marcado (CheckConstraint), mesmo critério visual
    do Módulo, mas aqui é só pra evitar um cadastro que pareça "não serve
    pra ninguém"."""

    __tablename__ = "knowledge_systems"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    applies_to_consultant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    applies_to_internal_pm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # String simples, não enum do Postgres — mesmo critério de
    # KnowledgeFunctionality.requirement (ver comentário lá).
    requirement: Mapped[str] = mapped_column(String(12), nullable=False, default=KnowledgeRequirement.REQUIRED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        CheckConstraint("applies_to_consultant OR applies_to_internal_pm", name="ck_knowledge_system_has_profile"),
    )
    modules: Mapped[list["KnowledgeModule"]] = relationship(back_populates="system", cascade="all, delete-orphan", order_by="KnowledgeModule.name")


class KnowledgeModule(Base):
    """Nível 2 do catálogo (ex.: "Fiscal", "Financeiro") — ponto onde fica o
    vínculo de perfil (decisão confirmada com o usuário, ver docstring da
    seção acima): `applies_to_consultant`/`applies_to_internal_pm`
    controlam quem enxerga este módulo (e suas Funcionalidades) na tela de
    autoavaliação ("Registro de Funcionalidades por Consultor/Gerente") —
    esse efeito NÃO mudou com a adição do mesmo campo em KnowledgeSystem
    (lá é só classificação; aqui continua sendo o que de fato filtra,
    exatamente como antes). Pelo menos um dos dois precisa ficar marcado
    (CheckConstraint) — um módulo sem nenhum perfil nunca apareceria pra
    ninguém se autoavaliar, o que não faria sentido.

    `requirement` (pedido do usuário, mesma rodada do parágrafo acima) é
    só classificação/organização neste nível, igual em KnowledgeSystem —
    o badge "Necessário/Desejável" mostrado na autoavaliação/revisão
    continua vindo só de KnowledgeFunctionality.requirement."""

    __tablename__ = "knowledge_modules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    system_id: Mapped[str] = mapped_column(ForeignKey("knowledge_systems.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    applies_to_consultant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    applies_to_internal_pm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # String simples — mesmo critério de KnowledgeSystem.requirement acima.
    requirement: Mapped[str] = mapped_column(String(12), nullable=False, default=KnowledgeRequirement.REQUIRED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        CheckConstraint("applies_to_consultant OR applies_to_internal_pm", name="ck_knowledge_module_has_profile"),
    )
    system: Mapped[KnowledgeSystem] = relationship(back_populates="modules")
    functionalities: Mapped[list["KnowledgeFunctionality"]] = relationship(
        back_populates="module", cascade="all, delete-orphan", order_by="KnowledgeFunctionality.name"
    )


class KnowledgeFunctionality(Base):
    """Nível 3 (folha) do catálogo. `description` é o campo pedido pelo
    usuário: "um campo descritivo que indique quais detalhes de cada
    funcionalidade do processo são necessários ou fazem parte daquele
    processo". `requirement` é o outro pedido: "definir se o conhecimento
    é necessário ou desejável"."""

    __tablename__ = "knowledge_functionalities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    module_id: Mapped[str] = mapped_column(ForeignKey("knowledge_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # String simples, não enum do Postgres — mesmo critério de
    # ProjectStatusReport.rag_* (ver docstring de RagStatus): poucos
    # valores fixos, política do projeto desde o bug de enum duplicado da
    # migração 0024, mesmo quando (como aqui) não haveria risco técnico
    # real por ser coluna única na tabela.
    requirement: Mapped[str] = mapped_column(String(12), nullable=False, default=KnowledgeRequirement.REQUIRED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    module: Mapped[KnowledgeModule] = relationship(back_populates="functionalities")


class KnowledgeSubmission(Base):
    """O "envio" de um recurso pro revisor — agrupa, de uma vez, todos os
    itens (ResourceKnowledge) que estavam DRAFT no momento do envio (ver
    docstring da seção acima: aprovação é SEMPRE do lote inteiro, nunca
    item a item). Fica como registro histórico mesmo depois de
    aprovado/rejeitado. Numa rejeição, os itens (`ResourceKnowledge.status`)
    voltam pra DRAFT (editáveis de novo), mas CONTINUAM apontando pra este
    envio (`submission_id` não é zerado na rejeição, ver
    routers/knowledge.py review_submission) — é assim que
    GET /knowledge/my-submissions consegue mostrar ao recurso o que foi
    rejeitado e por quê (`review_notes`). Só quando o recurso edita algum
    desses itens de novo (PUT /knowledge/my-ratings/{id}) é que o item solta
    `submission_id`, começando um novo ciclo."""

    __tablename__ = "knowledge_submissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True)
    # String simples — mesmo critério de KnowledgeFunctionality.requirement
    # acima (ver comentário lá).
    status: Mapped[str] = mapped_column(String(12), nullable=False, default=KnowledgeStatus.SUBMITTED.value)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_notes: Mapped[str | None] = mapped_column(Text)
    resource: Mapped[Resource] = relationship()
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewed_by])
    items: Mapped[list["ResourceKnowledge"]] = relationship(back_populates="submission")


class ResourceKnowledge(Base):
    """Uma linha da "matriz de conhecimento": nível autoavaliado por um
    Recurso (Consultor/Gerente de Projeto) numa Funcionalidade.
    `self_level`/`reviewed_level` são inteiros 0-4 (ver KNOWLEDGE_LEVEL_LABELS
    em frontend/src/utils/labels.js: 0-Não conhece, 1-Conhece o conceito,
    2-Implanta com apoio, 3-Implanta sem apoio, 4-Especialista). `reviewed_level` só é
    preenchido/atualizado na aprovação (decisão confirmada com o usuário:
    revisor pode ajustar) — é o nível "oficial" pra uso futuro (matriz
    agregada/cruzamento com projetos, fora do escopo desta rodada).

    Editar `self_level` depois de aprovado/rejeitado volta o item pra DRAFT
    (novo ciclo) e solta `submission_id` — `reviewed_level` do ciclo
    anterior fica como estava até uma nova aprovação sobrescrever."""

    __tablename__ = "resource_knowledge"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True)
    functionality_id: Mapped[str] = mapped_column(ForeignKey("knowledge_functionalities.id", ondelete="CASCADE"), nullable=False, index=True)
    self_level: Mapped[int | None] = mapped_column(Integer)
    reviewed_level: Mapped[int | None] = mapped_column(Integer)
    # String simples — mesmo critério acima.
    status: Mapped[str] = mapped_column(String(12), nullable=False, default=KnowledgeStatus.DRAFT.value)
    notes: Mapped[str | None] = mapped_column(Text)
    submission_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_submissions.id", ondelete="SET NULL"), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("resource_id", "functionality_id", name="uq_resource_knowledge_resource_functionality"),
        CheckConstraint("self_level IS NULL OR self_level BETWEEN 0 AND 4", name="ck_resource_knowledge_self_level_range"),
        CheckConstraint("reviewed_level IS NULL OR reviewed_level BETWEEN 0 AND 4", name="ck_resource_knowledge_reviewed_level_range"),
    )
    resource: Mapped[Resource] = relationship()
    functionality: Mapped[KnowledgeFunctionality] = relationship()
    submission: Mapped[KnowledgeSubmission | None] = relationship(back_populates="items")
