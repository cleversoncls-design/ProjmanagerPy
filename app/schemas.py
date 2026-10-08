from __future__ import annotations

import datetime as _dt
from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from .color_palette import DEFAULT_PROJECT_COLOR
from .models import (
    AbsenceType,
    AuditAction,
    ChangeStatus,
    DependencyType,
    EmailSecurity,
    IntakeStatus,
    KnowledgeRequirement,
    KnowledgeStatus,
    Language,
    ProjectStatus,
    RagStatus,
    ResourceFunction,
    ReworkReason,
    RiskLevel,
    RiskStatus,
    TaskApprovalStatus,
    TaskModality,
    TaskStatus,
    TaskType,
    TimesheetStatus,
    UserRole,
    UserStatus,
    WorkClassification,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Auth / Users
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: UserRole


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    client_id: str | None = None


class UserRead(ORMModel):
    id: str
    client_id: str | None
    name: str
    email: str
    role: UserRole
    status: UserStatus
    language: Language
    must_change_password: bool = False
    created_at: datetime


class ProjectManagerOption(ORMModel):
    """Usuário elegível a gerente de projeto (GET /projects/eligible-managers)."""

    id: str
    name: str
    email: str
    role: UserRole


class UserUpdate(BaseModel):
    """Edição de usuário (só ADMIN — ver require_roles no router). Trocar
    `status` para BLOCKED impede login imediatamente (checado em
    `POST /auth/login`); a senha não é editável por aqui — ver
    `POST /users/{id}/reset-password`, que gera um hash novo sem expor a
    senha atual."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    role: UserRole | None = None
    client_id: str | None = None
    status: UserStatus | None = None
    language: Language | None = None


class UserSelfUpdate(BaseModel):
    """Autoatendimento — qualquer usuário autenticado pode trocar o próprio
    idioma (ver PATCH /users/me), sem precisar de permissão de ADMIN
    (diferente de PATCH /users/{id}, que edita QUALQUER usuário e é
    restrito). De propósito só tem este campo: evita abrir uma porta pra
    autopromoção de role/status por essa rota."""

    language: Language


class UserPasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class PasswordChange(BaseModel):
    """Troca da PRÓPRIA senha (POST /auth/change-password) — qualquer perfil.
    A confirmação da nova senha é conferida no frontend; a API exige a senha
    atual e aplica o mesmo mínimo de 8 caracteres da criação de usuário."""

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


class ClientCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    legal_name: str = Field(min_length=1, max_length=255)
    trade_name: str | None = None
    tax_id: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = Field(default=None, max_length=2)
    zip_code: str | None = None
    primary_contact_name: str | None = None
    primary_contact_email: EmailStr | None = None
    primary_contact_phone: str | None = None


class ClientUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=40)
    legal_name: str | None = Field(default=None, min_length=1, max_length=255)
    trade_name: str | None = None
    tax_id: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = Field(default=None, max_length=2)
    zip_code: str | None = None
    primary_contact_name: str | None = None
    primary_contact_email: EmailStr | None = None
    primary_contact_phone: str | None = None


class ClientRead(ORMModel):
    id: str
    code: str
    legal_name: str
    trade_name: str | None
    tax_id: str | None
    address: str | None
    city: str | None
    state: str | None
    zip_code: str | None
    primary_contact_name: str | None
    primary_contact_email: str | None
    primary_contact_phone: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Project intakes
# ---------------------------------------------------------------------------


class ProjectIntakeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    estimated_budget: Decimal | None = Field(default=None, ge=0)
    estimated_hours: Decimal | None = Field(default=None, ge=0)


class ProjectIntakeStatusUpdate(BaseModel):
    status: IntakeStatus


class ProjectIntakeRead(ORMModel):
    id: str
    client_id: str
    title: str
    description: str | None
    estimated_budget: Decimal | None
    estimated_hours: Decimal | None
    status: IntakeStatus
    created_at: datetime


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    client_id: str
    manager_id: str
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=255)
    # sold_value NÃO é mais um campo de entrada: é calculado no backend a
    # partir das horas × taxa de gestão e de consultoria (ver
    # app/routers/projects.py), para o valor vendido nunca ficar
    # dessincronizado da composição real do pacote contratado.
    management_hours: Decimal = Field(default=Decimal("0"), ge=0)
    management_rate: Decimal = Field(default=Decimal("0"), ge=0)
    consulting_hours: Decimal = Field(default=Decimal("0"), ge=0)
    consulting_rate: Decimal = Field(default=Decimal("0"), ge=0)
    # "% de Margem vendida na BID" (pedido do usuário) — valor declarado na
    # venda/proposta, digitado direto; não é calculado a partir de custo
    # (ver comentário em Project.margin_percentage, app/models.py).
    margin_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    start_date: date | None = None
    end_date: date | None = None
    calendar_id: str | None = None
    # Um hex da paleta de 256 cores em app/color_palette.py — aplicada
    # automaticamente em toda agenda (ResourceSchedule) deste projeto.
    # Validada no router (não aqui) contra a lista de hexes válidos, no
    # mesmo padrão de manager_id/calendar_id.
    color: str = DEFAULT_PROJECT_COLOR


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    manager_id: str | None = None
    status: ProjectStatus | None = None
    management_hours: Decimal | None = Field(default=None, ge=0)
    management_rate: Decimal | None = Field(default=None, ge=0)
    consulting_hours: Decimal | None = Field(default=None, ge=0)
    consulting_rate: Decimal | None = Field(default=None, ge=0)
    margin_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    start_date: date | None = None
    end_date: date | None = None
    calendar_id: str | None = None
    # "Data de status" do projeto — ver Project.status_date em app/models.py
    # e services.project_evm/task_dot_color. Enviar null explicitamente
    # volta a usar a data de hoje como data-base.
    status_date: date | None = None
    color: str | None = None


class ProjectSummary(ORMModel):
    id: str
    client_id: str
    manager_id: str
    code: str
    name: str
    status: ProjectStatus
    start_date: date | None
    end_date: date | None
    calendar_id: str | None
    status_date: date | None
    color: str
    # True = projeto finalizado (COMPLETED/CANCELLED) exibindo o padrão
    # listrado no lugar de `color` — ver Project.color_striped.
    color_striped: bool


class ProjectDetail(ProjectSummary):
    sold_value: Decimal | None = None
    management_hours: Decimal | None = None
    management_rate: Decimal | None = None
    consulting_hours: Decimal | None = None
    consulting_rate: Decimal | None = None
    margin_percentage: Decimal | None = None
    # dict[str, Decimal | None] (não só dict[str, Decimal]) desde "melhorias
    # parte 5": "real_margin_percentage" (dentro de project_financials) pode
    # vir None quando o projeto não tem valor vendido.
    financials: dict[str, Decimal | None] | None = None


# ---------------------------------------------------------------------------
# Tasks / dependencies / assignments
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    wbs_code: str = Field(min_length=1, max_length=50)
    task_type: TaskType = TaskType.CONSULTING
    parent_task_id: str | None = None
    # Effort-driven (estilo MS Project) — ver services.apply_effort_driven:
    # "Duração" é o campo primário; "Trabalho" (estimated_hours) é derivado
    # dela (duração × capacidade diária dos recursos alocados, ou 8h/dia
    # sem nenhum recurso ainda). Informar estimated_hours explicitamente
    # (sem informar duration_days) faz o cálculo inverso — deriva a duração
    # a partir do trabalho informado.
    duration_days: Decimal | None = Field(default=None, gt=0)
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    is_milestone: bool = False
    notes: str | None = None
    # "Nível mínimo" exigido pra executar a tarefa (pedido do usuário,
    # "melhorias parte 4") — ver comentário em models.Task.min_level.
    # Default 1 = "qualquer nível serve" (não exige preenchimento manual).
    min_level: int = Field(default=1, ge=1, le=4)
    # Onde a tarefa pode ser executada (pedido do usuário, "melhorias parte
    # 5") — ver models.TaskModality. Puramente informativo.
    modality: TaskModality = TaskModality.BOTH
    # "Atividade do cliente" — ver models.Task.is_client_activity. Quando
    # verdadeiro, min_level é forçado a 1 no backend.
    is_client_activity: bool = False


class TaskUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    task_type: TaskType | None = None
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    duration_days: Decimal | None = Field(default=None, gt=0)
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    progress_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    status: TaskStatus | None = None
    is_critical_path: bool | None = None
    is_milestone: bool | None = None
    notes: str | None = None
    min_level: int | None = Field(default=None, ge=1, le=4)
    modality: TaskModality | None = None
    is_client_activity: bool | None = None


class TaskClientApprovalUpdate(BaseModel):
    status: TaskApprovalStatus
    comment: str | None = None


class TaskRead(ORMModel):
    id: str
    project_id: str
    parent_task_id: str | None
    name: str
    wbs_code: str
    task_type: TaskType
    duration_days: Decimal
    estimated_hours: Decimal
    actual_hours: Decimal
    sort_order: int
    planned_start_date: date | None
    planned_end_date: date | None
    actual_start_date: date | None
    actual_end_date: date | None
    is_critical_path: bool
    is_milestone: bool
    progress_percentage: Decimal
    status: TaskStatus
    client_approval_status: TaskApprovalStatus
    notes: str | None = None
    min_level: int
    modality: TaskModality
    is_client_activity: bool = False
    # Usuários do cliente alocados (só preenchido em atividade do cliente).
    client_user_ids: list[str] = []


class TaskMoveRequest(BaseModel):
    """Move uma tarefa para outro pai e/ou outra posição entre as irmãs —
    ver services.move_task. `new_parent_id=None` explícito move para a raiz
    do projeto (mesmo nível das fases de topo). `before_task_id=None`
    (padrão) coloca a tarefa no final da lista de irmãs; para "colocar
    antes de uma tarefa já existente", informe o id dela (precisa já ser
    irmã no `new_parent_id` de destino)."""

    new_parent_id: str | None = None
    before_task_id: str | None = None


class WbsRecalculateResponse(BaseModel):
    tasks: list[TaskRead]


# ---------------------------------------------------------------------------
# Grupos de Tarefas (TaskGroup) — agrupador reutilizável de tarefas, pedido
# do usuário pra acelerar a criação de projetos parecidos. Ver
# models.TaskGroup/TaskGroupItem e routers/task_groups.py.
# ---------------------------------------------------------------------------


class TaskGroupItemCreate(BaseModel):
    """Um nó da árvore do grupo, no formato de entrada — `children` é a
    lista de sub-itens aninhados sob este nó (hierarquia aninhada, sem
    limite de profundidade). Os mesmos campos de TaskCreate que fazem
    sentido num molde de estrutura (sem datas/status/progresso: ver
    docstring de models.TaskGroupItem)."""

    name: str = Field(min_length=1, max_length=255)
    task_type: TaskType = TaskType.CONSULTING
    duration_days: Decimal = Field(default=Decimal("1"), gt=0)
    estimated_hours: Decimal = Field(default=Decimal("0"), ge=0)
    is_milestone: bool = False
    notes: str | None = None
    min_level: int = Field(default=1, ge=1, le=4)
    modality: TaskModality = TaskModality.BOTH
    children: list["TaskGroupItemCreate"] = []


TaskGroupItemCreate.model_rebuild()


class TaskGroupCreate(BaseModel):
    """Corpo de POST /task-groups e PUT /task-groups/{id} — `items` é a
    árvore completa do grupo; um PUT substitui a árvore inteira (apaga tudo
    e recria, ver update_task_group em routers/task_groups.py), não faz
    diff com o que já existia."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    items: list[TaskGroupItemCreate] = []


class TaskGroupItemRead(ORMModel):
    id: str
    name: str
    task_type: TaskType
    duration_days: Decimal
    estimated_hours: Decimal
    is_milestone: bool
    notes: str | None = None
    min_level: int
    modality: TaskModality
    children: list["TaskGroupItemRead"] = []


TaskGroupItemRead.model_rebuild()


class TaskGroupRead(ORMModel):
    id: str
    name: str
    description: str | None = None
    created_at: datetime
    items: list[TaskGroupItemRead] = []


class TaskGroupApplyRequest(BaseModel):
    """Corpo de POST /tasks/{task_id}/apply-task-group — clona a árvore do
    grupo `task_group_id` como tarefas-filhas de `task_id`. Ver
    services.apply_task_group_to_task."""

    task_group_id: str


class TaskScheduleRow(TaskRead):
    """Linha enriquecida para a grade de cronograma/Gantt — os campos que
    dependem da `status_date` do projeto ou do último baseline, calculados
    sob demanda (nunca armazenados) por `services.task_schedule_rows`."""

    status_dot: str
    # Duração/Trabalho/Início/Fim agregados a partir das descendentes, só
    # para tarefas-pai (WBS) — None numa tarefa-folha, que já usa os campos
    # próprios (duration_days/estimated_hours/planned_start_date/
    # planned_end_date acima, herdados de TaskRead) para tudo. Ver
    # services._task_rollups: o pai nunca teve essas colunas próprias
    # preenchidas de forma útil, então o frontend prefere estes campos
    # quando presentes.
    rollup_start_date: date | None = None
    rollup_end_date: date | None = None
    rollup_duration_days: Decimal | None = None
    rollup_estimated_hours: Decimal | None = None
    # % Realizado agregado das folhas descendentes (ponderado por horas) —
    # só tarefa-pai; None na folha, que usa progress_percentage. Ver
    # services._task_progress_rollups.
    rollup_progress_percentage: Decimal | None = None
    baseline_start_date: date | None = None
    baseline_end_date: date | None = None
    baseline_estimated_hours: Decimal | None = None
    planned_percent_complete: Decimal
    # SPI/CPI calculados por TAREFA (mesma base de horas de EvmMetrics,
    # nunca monetária) — None quando o denominador é zero, mesma regra do
    # cálculo em nível de projeto. Ver services.task_schedule_rows.
    spi: Decimal | None = None
    cpi: Decimal | None = None


class TaskDependencyCreate(BaseModel):
    predecessor_task_id: str
    successor_task_id: str
    dependency_type: DependencyType = DependencyType.FS
    lag_days: int = 0


class TaskDependencyRead(ORMModel):
    id: str
    predecessor_task_id: str
    successor_task_id: str
    dependency_type: DependencyType
    lag_days: int


class RescheduleRequest(BaseModel):
    # Opcional agora que o projeto pode ter seu próprio calendário
    # (Project.calendar_id): sem informar, usa o calendário do projeto (ou
    # o padrão segunda-sexta, se o projeto também não tiver um definido).
    calendar_id: str | None = None


class TaskAssignmentCreate(BaseModel):
    resource_id: str
    allocated_hours: Decimal = Field(gt=0)


class TaskAssignmentRead(ORMModel):
    id: str
    task_id: str
    resource_id: str
    allocated_hours: Decimal


class TaskClientAssignmentCreate(BaseModel):
    user_id: str


class ClientUserRead(ORMModel):
    """Usuário do cliente do projeto, candidato a uma "atividade do cliente"
    (GET /projects/{id}/client-users)."""

    id: str
    name: str
    email: str
    role: UserRole


# ---------------------------------------------------------------------------
# Recursos do projeto (vínculo direto recurso-projeto, sem passar por
# tarefa — ver ProjectResource em app/models.py)
# ---------------------------------------------------------------------------


class ProjectResourceCreate(BaseModel):
    resource_id: str


class ProjectResourceRead(ORMModel):
    id: str
    project_id: str
    resource_id: str


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


class ResourceCreate(BaseModel):
    user_id: str
    # Função + Nível (pedido do usuário, "melhorias parte 4") — substituem o
    # antigo `role_title` de texto livre. Ambos opcionais: ficam "Não
    # definido" até alguém preencher (decisão confirmada — sem migração
    # automática do texto livre que existia antes).
    function: ResourceFunction | None = None
    level: int | None = Field(default=None, ge=1, le=4)
    internal_cost_per_hour: Decimal = Field(gt=0)
    billing_rate_per_hour: Decimal = Field(gt=0)
    daily_capacity_hours: Decimal = Field(default=Decimal("8"), gt=0, le=24)
    calendar_id: str | None = None


class ResourceUpdate(BaseModel):
    """Todos os campos opcionais (PATCH parcial) — mesmo padrão de
    TaskUpdate/ProjectUpdate. Sem isto, o único jeito de corrigir o
    custo/hora ou a função de um recurso já cadastrado era apagar e
    recriar (perdendo o vínculo de user_id único, já que POST /resources
    recusa um segundo recurso pro mesmo usuário)."""

    function: ResourceFunction | None = None
    level: int | None = Field(default=None, ge=1, le=4)
    internal_cost_per_hour: Decimal | None = Field(default=None, gt=0)
    billing_rate_per_hour: Decimal | None = Field(default=None, gt=0)
    daily_capacity_hours: Decimal | None = Field(default=None, gt=0, le=24)
    calendar_id: str | None = None


class ResourceRead(ORMModel):
    id: str
    user_id: str
    function: ResourceFunction | None
    level: int | None
    internal_cost_per_hour: Decimal
    billing_rate_per_hour: Decimal
    daily_capacity_hours: Decimal
    calendar_id: str | None


# ---------------------------------------------------------------------------
# Agenda de consultores (ResourceSchedule)
# ---------------------------------------------------------------------------


class ResourceScheduleCreate(BaseModel):
    resource_id: str
    project_id: str
    date: date
    start_time: time
    end_time: time
    description: str | None = None
    # Tarefas do bloco (pedido do usuário: "adicionar uma ou mais tarefas,
    # sem horas, para a agenda") — precisam pertencer a `project_id` e não
    # ter tarefas-filhas (mesma regra de "só tarefa-folha" do apontamento de
    # horas, ver _resolve_task_and_project em routers/timesheets.py);
    # validado em create_schedule, routers/schedules.py.
    task_ids: list[str] = []


class ResourceScheduleUpdate(BaseModel):
    """Todos os campos opcionais (PATCH parcial) — mesmo padrão de
    ResourceUpdate/ProjectUpdate. resource_id não é editável de propósito:
    trocar de recurso é apagar e recriar o agendamento, não "mover" um
    existente pra outra pessoa."""

    project_id: str | None = None
    # Anotado via `_dt.date` (não `date` puro) de propósito: o campo se
    # chama `date` e tem valor padrão, então a classe ganha um atributo
    # `date = None` — com `from __future__ import annotations` (anotações
    # avaliadas como string, sob demanda), o Pydantic resolve o forward ref
    # 'date | None' usando um namespace que inclui os próprios atributos da
    # classe, e o atributo `date = None` da classe esconde o tipo `date`
    # importado do módulo `datetime`, virando `None | None` e quebrando com
    # TypeError na definição da classe (import time). Referenciar via
    # `_dt.date` evita a colisão de nome sem mudar o nome do campo (contrato
    # da API) nem o desta docstring de ResourceScheduleUpdate.
    date: _dt.date | None = None
    start_time: time | None = None
    end_time: time | None = None
    description: str | None = None
    # None = não mexe na lista de tarefas; uma lista (mesmo vazia) substitui
    # a lista inteira — mesmo critério de "PATCH parcial" do resto da classe
    # (`exclude_unset`, ver update_schedule em routers/schedules.py).
    task_ids: list[str] | None = None


class ResourceScheduleRead(ORMModel):
    id: str
    resource_id: str
    project_id: str
    date: date
    start_time: time
    end_time: time
    description: str | None
    created_at: datetime
    # Lista do que o consultor precisa trabalhar neste bloco (pedido do
    # usuário) — ver ResourceSchedule.tasks (app/models.py).
    tasks: list[TaskRead] = []


# ---------------------------------------------------------------------------
# Timesheets
# ---------------------------------------------------------------------------


class TimesheetCreate(BaseModel):
    # Apontamento "avulso" (padrão Clockify/Toggl): omita task_id para um
    # lançamento sem tarefa pré-definida na EAP. project_id é opcional e só
    # faz sentido quando task_id é omitido — aloca a hora avulsa a um
    # projeto sem exigir WBS; os dois nulos = hora administrativa interna.
    task_id: str | None = None
    project_id: str | None = None
    # Bloco da Agenda que este apontamento cumpre — opcional; informar
    # ajuda a auditoria mas não é o que decide `unscheduled` (isso é sempre
    # recalculado no backend a partir de resource+projeto+data, ver
    # create_timesheet em routers/timesheets.py — nunca confiar no cliente
    # pra essa checagem, que é justamente a regra de aprovação extra).
    schedule_id: str | None = None
    date: date
    # Hora início/fim + intervalo — `hours_spent` não é mais informado
    # aqui: é sempre calculado no backend (Hora Final − Hora Inicial −
    # Intervalo), igual ao `sold_value` do projeto.
    start_time: time
    end_time: time
    break_minutes: int = Field(default=0, ge=0)
    # "Traslado" (deslocamento, pedido do usuário) — exige project_id
    # (sempre vinculado a um projeto) e não aceita task_id junto (ver
    # validação em _resolve_task_and_project, routers/timesheets.py).
    is_transit: bool = False
    # "Ausência da empresa" (Férias/Licença Médica/Licença Maternidade/
    # Ausência/Folga, pedido do usuário) — o espelho do Traslado acima: não
    # aceita task_id nem project_id junto, nem is_transit=True ao mesmo
    # tempo (ver validação em _resolve_task_and_project).
    absence_type: AbsenceType | None = None
    # "% de Avanço da Tarefa" (pedido do usuário) — só aceito junto de
    # task_id; ao salvar, espelha o valor em Task.progress_percentage (ver
    # _validate_rework/_apply_task_progress, routers/timesheets.py).
    task_progress_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    # Classificador Normal/Retrabalho (pedido do usuário) — só aceito junto
    # de task_id; omitido num apontamento de tarefa é tratado como NORMAL.
    work_classification: WorkClassification | None = None
    # Motivo(s) do retrabalho — obrigatório (>= 1) quando
    # work_classification == REWORK, deve vir vazio caso contrário.
    rework_reasons: list[ReworkReason] = []
    description: str | None = None


class TimesheetStatusUpdate(BaseModel):
    status: TimesheetStatus


class TimesheetRead(ORMModel):
    id: str
    task_id: str | None
    project_id: str | None
    resource_id: str
    schedule_id: str | None
    date: date
    start_time: time | None
    end_time: time | None
    break_minutes: int
    hours_spent: Decimal
    unscheduled: bool
    is_transit: bool
    absence_type: AbsenceType | None
    task_progress_percentage: Decimal | None
    work_classification: WorkClassification | None
    rework_reasons: list[str] | None
    description: str | None
    status: TimesheetStatus


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------


class ProjectExpenseCreate(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0)
    expense_date: date


class ProjectExpenseRead(ORMModel):
    id: str
    project_id: str
    description: str
    category: str
    amount: Decimal
    expense_date: date


# ---------------------------------------------------------------------------
# Calendars / holidays
# ---------------------------------------------------------------------------


class CalendarCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    working_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    is_default: bool = False


class CalendarUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    working_days: list[int] | None = None
    is_default: bool | None = None


class CalendarRead(ORMModel):
    id: str
    name: str
    working_days: list[int]
    is_default: bool


class HolidayCreate(BaseModel):
    date: date
    description: str = Field(min_length=1, max_length=255)


class HolidayUpdate(BaseModel):
    date: date
    description: str = Field(min_length=1, max_length=255)


class HolidayRead(ORMModel):
    id: str
    calendar_id: str
    date: date
    description: str


# ---------------------------------------------------------------------------
# Risks
# ---------------------------------------------------------------------------


class RiskCreate(BaseModel):
    description: str = Field(min_length=1)
    probability: RiskLevel
    impact: RiskLevel
    mitigation_plan: str | None = None


class RiskUpdate(BaseModel):
    description: str | None = None
    probability: RiskLevel | None = None
    impact: RiskLevel | None = None
    mitigation_plan: str | None = None
    status: RiskStatus | None = None


class RiskRead(ORMModel):
    id: str
    project_id: str
    description: str
    probability: RiskLevel
    impact: RiskLevel
    mitigation_plan: str | None
    status: RiskStatus


# ---------------------------------------------------------------------------
# Change requests
# ---------------------------------------------------------------------------


class ChangeRequestCreate(BaseModel):
    description: str = Field(min_length=1)
    cost_impact: Decimal = Decimal("0")
    schedule_impact_days: int = 0


class ChangeRequestStatusUpdate(BaseModel):
    status: ChangeStatus


class ChangeRequestRead(ORMModel):
    id: str
    project_id: str
    requested_by: str
    description: str
    cost_impact: Decimal
    schedule_impact_days: int
    status: ChangeStatus


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


class BaselineCreate(BaseModel):
    version_name: str = Field(min_length=1, max_length=100)


class BaselineRead(ORMModel):
    id: str
    project_id: str
    version_name: str
    snapshot_data: dict
    created_at: datetime


# ---------------------------------------------------------------------------
# Auditoria
# ---------------------------------------------------------------------------


class AuditLogRead(ORMModel):
    id: str
    entity_type: str
    entity_id: str
    action: AuditAction
    user_id: str | None
    details: dict | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Relatórios / dashboard (Fase 2)
# ---------------------------------------------------------------------------


class ProjectPortfolioRow(BaseModel):
    """Uma linha por projeto — usada tanto em GET /reports/portfolio quanto
    dentro de GET /dashboard. `margin` e vem None para perfis externos (o
    mesmo tratamento de ocultação de dado financeiro usado em
    ProjectDetail)."""

    id: str
    code: str
    name: str
    status: ProjectStatus
    manager_name: str
    percent_complete: Decimal
    tasks_total: int
    tasks_remaining: int
    margin: Decimal | None = None
    next_milestone_name: str | None = None
    next_milestone_date: date | None = None
    # Ver Project.color_striped — a tela de Projetos é onde o padrão
    # listrado de projeto finalizado precisa aparecer de fato.
    color: str
    color_striped: bool


class DashboardResponse(BaseModel):
    projects_total: int
    projects_by_status: dict[str, int]
    tasks_total: int
    tasks_by_status: dict[str, int]
    tasks_by_type: dict[str, int]
    tasks_overdue: int
    avg_progress_percentage: Decimal
    portfolio: list[ProjectPortfolioRow]


class BurndownPoint(BaseModel):
    date: date
    planned_remaining_hours: Decimal
    actual_remaining_hours: Decimal


class ProjectReportResponse(BaseModel):
    project_id: str
    percent_complete: Decimal
    tasks_total: int
    tasks_remaining: int
    tasks_by_status: dict[str, int]
    # Ver comentário em ProjectDetail.financials — mesmo motivo.
    financials: dict[str, Decimal | None] | None = None
    financials_by_task_type: dict[str, dict[str, Decimal]] | None = None
    burndown: list[BurndownPoint]


# ---------------------------------------------------------------------------
# Status Report (pedido do usuário: "pode implementar os 2 modelos e
# colocar na opção de relatórios") — ver docstring de ProjectStatusReport
# em app/models.py.
# ---------------------------------------------------------------------------


class RiskSnapshot(BaseModel):
    """Um risco "congelado" dentro de ProjectStatusReport.risks_snapshot —
    mesmos campos de RiskRead, mas copiados (não uma referência viva à
    tabela `risks`, que pode mudar depois do relatório salvo)."""

    id: str
    description: str
    probability: RiskLevel
    impact: RiskLevel
    mitigation_plan: str | None = None
    status: RiskStatus


class TaskRefSnapshot(BaseModel):
    """Referência leve a uma tarefa dentro de tasks_done/tasks_next —
    só o que a tela do Status Report precisa mostrar (ver mockup "Semana
    anterior × próxima semana")."""

    id: str
    wbs_code: str
    name: str
    planned_start_date: date | None = None
    planned_end_date: date | None = None


class GanttLevel2TaskSnapshot(BaseModel):
    """Uma linha do Gantt (nível 1+2 da EAP) congelado dentro de
    ProjectStatusReport.gantt_snapshot — ver
    services._build_gantt_level2_snapshot. `start_date`/`end_date` já vêm
    resolvidos (rollup de descendentes quando a tarefa tem filhas, ver
    `_task_rollups`) e `progress_percent` já vem ponderado pelas horas das
    folhas descendentes (`_task_progress_rollups`) — o frontend só desenha,
    não recalcula nada disso."""

    id: str
    wbs_code: str
    name: str
    depth: int
    task_type: TaskType
    is_milestone: bool
    start_date: date | None = None
    end_date: date | None = None
    progress_percent: Decimal


class StatusReportCreate(BaseModel):
    """Formulário de criação — só os campos que o PM preenche; tudo o mais
    (EVM, financeiro, burndown, tarefas, riscos) é calculado no momento da
    criação (ver services.build_status_report_snapshot) e nunca recebido
    do cliente HTTP."""

    period_start: date
    period_end: date
    rag_schedule: RagStatus
    rag_cost: RagStatus
    rag_margin: RagStatus
    rag_scope: RagStatus
    rag_risk: RagStatus
    executive_summary: str = Field(min_length=1)
    next_steps_client: str = Field(min_length=1)
    next_steps_internal: str | None = None


class StatusReportUpdate(BaseModel):
    """Edição de um Status Report já salvo (pedido do usuário: "ter opção
    de modificar") — só os campos editoriais/semáforo. `period_start`/
    `period_end` e tudo que é "fechamento" congelado (EVM, financeiro,
    burndown, tarefas, riscos — ver docstring de ProjectStatusReport em
    app/models.py) continuam IMUTÁVEIS depois de criado; mudar o período
    exigiria recalcular tudo de novo, o que descaracterizaria a ideia de
    "fechamento" (ver claude/status-report-por-periodo.md). Todos os
    campos são opcionais (`exclude_unset` no router) — PATCH parcial."""

    rag_schedule: RagStatus | None = None
    rag_cost: RagStatus | None = None
    rag_margin: RagStatus | None = None
    rag_scope: RagStatus | None = None
    rag_risk: RagStatus | None = None
    executive_summary: str | None = Field(default=None, min_length=1)
    next_steps_client: str | None = Field(default=None, min_length=1)
    next_steps_internal: str | None = None


class StatusReportRagSuggestion(BaseModel):
    """Resposta de GET /projects/{id}/status-reports/suggested-rag — ver
    services.suggest_status_report_rag. Só uma sugestão pra pré-preencher
    o formulário; o gerente sempre pode trocar antes de salvar."""

    rag_schedule: RagStatus
    rag_cost: RagStatus
    rag_margin: RagStatus
    rag_scope: RagStatus
    rag_risk: RagStatus


class StatusReportRead(ORMModel):
    """Resposta de um Status Report. Os campos financeiros/burndown são
    `None` (nunca um valor zerado fajuto) quando o perfil de quem pediu é
    EXTERNAL_ROLES — ver app/routers/status_reports.py, mesmo critério já
    usado em ProjectReportResponse.financials."""

    id: str
    project_id: str
    period_start: date
    period_end: date
    prepared_by_id: str | None
    created_at: datetime
    rag_schedule: RagStatus
    rag_cost: RagStatus
    rag_margin: RagStatus
    rag_scope: RagStatus
    rag_risk: RagStatus
    executive_summary: str
    next_steps_client: str
    # Oculto (None) para EXTERNAL_ROLES — "não compartilhadas com o cliente".
    next_steps_internal: str | None
    schedule_actual_pct: Decimal
    schedule_planned_pct: Decimal
    # Financeiro — oculto (None) para EXTERNAL_ROLES.
    hours_consumed: Decimal | None
    hours_budgeted: Decimal | None
    cost_planned: Decimal | None
    cost_actual: Decimal | None
    margin_planned_pct: Decimal | None
    margin_actual_pct: Decimal | None
    tasks_done: list[TaskRefSnapshot]
    tasks_next: list[TaskRefSnapshot]
    # Gantt nível 1+2, congelado (ver docstring de ProjectStatusReport em
    # app/models.py) — `None` em relatórios criados antes desta
    # funcionalidade existir (migração 0027). Aparece pros dois perfis —
    # cronograma, não dado financeiro, mesmo critério de tasks_done/tasks_next.
    gantt_snapshot: list[GanttLevel2TaskSnapshot] | None = None
    risks_snapshot: list[RiskSnapshot]
    # Burndown — oculto ([]) para EXTERNAL_ROLES.
    burndown: list[BurndownPoint]


class CalendarInviteSettingsRead(BaseModel):
    """Estado do convite de calendário do PRÓPRIO consultor (menu do avatar →
    "Meu Google Calendar"). `email` é o endereço salvo (None = usa o e-mail
    de login, `default_email`); `email_service_ready` avisa a tela quando o
    envio de e-mails do sistema (Configurações > E-mail) está desligado."""

    enabled: bool
    email: str | None
    default_email: str
    email_service_ready: bool


class CalendarInviteSettingsUpdate(BaseModel):
    enabled: bool
    email: EmailStr | None = None


class ResourceUtilizationRow(BaseModel):
    resource_id: str
    user_id: str
    function: ResourceFunction | None
    level: int | None
    period_start: date
    period_end: date
    capacity_hours: Decimal
    allocated_hours: Decimal
    actual_hours: Decimal
    utilization_percentage: Decimal | None


class RiskMatrixResponse(BaseModel):
    project_id: str
    grid: dict[str, dict[str, int]]
    high_priority: list[RiskRead]


class VelocityPoint(BaseModel):
    period_start: date
    hours_delivered: Decimal


class RoiRow(BaseModel):
    project_id: str
    code: str
    sold_value: Decimal
    real_cost: Decimal
    roi_percentage: Decimal | None


class ServiceOrderActivity(BaseModel):
    """Uma linha da Ordem de Serviço — um apontamento (Timesheet). Sem
    `task_id` (apontamento avulso no projeto), `wbs_code`/`task_name`
    ficam nulos e o frontend mostra "Avulso" no lugar. `id`/`status`/
    `unscheduled` existem pra a tela oferecer Editar/Excluir/Aprovar/
    Rejeitar direto na Ordem de Serviço (ver ServiceOrdersPage.jsx) — as
    mesmas rotas/regras de app/routers/timesheets.py, nunca duplicadas
    aqui; REJECTED nunca aparece (excluído por `service_orders` em
    services.py), então só PENDING/APPROVED chegam no frontend."""

    id: str
    task_id: str | None
    wbs_code: str | None
    task_name: str | None
    start_time: time
    end_time: time
    break_minutes: int
    hours: Decimal
    description: str | None
    status: TimesheetStatus
    unscheduled: bool
    is_transit: bool
    # Classificador Normal/Retrabalho + motivo(s) (pedido do usuário: também
    # impressos na Ordem de Serviço, por tarefa) — só vêm preenchidos junto
    # de task_id, mesma regra de Timesheet (ver _validate_rework,
    # routers/timesheets.py).
    work_classification: WorkClassification | None
    rework_reasons: list[str] | None


class ServiceOrderRow(BaseModel):
    """Uma Ordem de Serviço: 1 por dia + projeto + consultor (ver
    `service_orders` em services.py). `order_number`/`emitted_at` são o
    Nro. O.S./Emissão oficiais do documento impresso — atribuídos e
    gravados na primeira vez que o grupo aparece aqui (ServiceOrderNumber
    em models.py), nunca recalculados depois."""

    date: date
    client_id: str | None
    client_code: str
    client_name: str
    project_id: str
    project_code: str
    project_name: str
    resource_id: str
    resource_name: str
    total_hours: Decimal
    order_number: str
    emitted_at: datetime
    activities: list[ServiceOrderActivity]


class HoursBreakdownTotals(BaseModel):
    """Quatro categorias de horas (pedido do usuário, menu "Relatórios"):
    PROJETO (cliente), TRASLADO, INTERNO (hora administrativa, sem
    ausência) e AUSÊNCIA — esta última desagregada por tipo
    (`absence_hours`, chaves = valores de AbsenceType). Mesmo formato tanto
    para o total da empresa quanto para cada linha de `by_resource` (ver
    hours_breakdown_report em services.py)."""

    project_hours: Decimal
    transit_hours: Decimal
    internal_hours: Decimal
    absence_hours: dict[str, Decimal]


class HoursBreakdownByResourceRow(HoursBreakdownTotals):
    resource_id: str
    resource_name: str


class HoursBreakdownByProjectRow(BaseModel):
    """Detalhe de `project_hours` por cliente/projeto — sem isso a
    categoria "Projeto" seria só um número opaco, diferente de Traslado/
    Ausência que já são auto-explicativos."""

    project_id: str
    project_code: str
    project_name: str
    client_name: str
    hours: Decimal


class HoursBreakdownReport(BaseModel):
    period_start: date
    period_end: date
    totals: HoursBreakdownTotals
    by_resource: list[HoursBreakdownByResourceRow]
    by_project: list[HoursBreakdownByProjectRow]


class GanttResponse(BaseModel):
    tasks: list[TaskRead]
    dependencies: list[TaskDependencyRead]


class ProjectScheduleResponse(BaseModel):
    """Cronograma enriquecido para a grade de tarefas (bolinha de status,
    linha base, % previsto) — usado pela tela de tarefas/Gantt do
    frontend. Separado de GanttResponse (que fica só com os campos "crus"
    de Task/TaskDependency, sem depender de status_date/baseline)."""

    status_date: date
    tasks: list[TaskScheduleRow]
    dependencies: list[TaskDependencyRead]


class EvmMetrics(BaseModel):
    """Earned Value em base de HORAS (estimated_hours), não monetária — ver
    decisão registrada em services.project_evm. planned_value/earned_value/
    actual_hours são somas de horas de tarefa; os índices SPI/CPI ficam
    None quando o denominador é zero (projeto sem horas planejadas até a
    status_date, ou sem nenhuma hora ainda apontada)."""

    status_date: date
    planned_value_hours: Decimal
    earned_value_hours: Decimal
    actual_hours: Decimal
    spi: Decimal | None
    cpi: Decimal | None
    planned_percent_complete: Decimal
    percent_complete: Decimal


class ProjectStatisticsRange(BaseModel):
    start_date: date | None
    finish_date: date | None
    duration_days: Decimal
    work_hours: Decimal
    cost: Decimal | None


class ProjectStatisticsResponse(BaseModel):
    """Espelha a caixa "Project Statistics" do MS Project (Current/Baseline/
    Actual/Variance × Start/Finish/Duration/Work/Cost + % complete) — ver
    services.project_statistics."""

    current: ProjectStatisticsRange
    baseline: ProjectStatisticsRange | None
    actual: ProjectStatisticsRange
    variance_finish_days: Decimal | None
    percent_complete_duration: Decimal
    percent_complete_work: Decimal


# ---------------------------------------------------------------------------
# Configuração de e-mail (pedido do usuário: "processo de envio de emails")
# ---------------------------------------------------------------------------


class EmailSettingsUpdate(BaseModel):
    """Corpo de `PUT /email-settings` — sempre o formulário INTEIRO (tela
    de configuração única, não uma lista de registros), exceto a senha:
    omitida (ou `None`), mantém a já salva; `""` explícito apaga a senha
    salva. Nunca devolvida de volta pela API (ver EmailSettingsRead)."""

    enabled: bool = False
    smtp_host: str = Field(min_length=1, max_length=255)
    smtp_port: int = Field(ge=1, le=65535)
    security: EmailSecurity = EmailSecurity.STARTTLS
    smtp_username: str | None = None
    smtp_password: str | None = None
    from_email: EmailStr
    from_name: str | None = None


class EmailSettingsRead(BaseModel):
    """`id`/`updated_at` nulos = configuração ainda nunca foi salva (tela
    em branco). `password_configured` substitui a senha de verdade, que
    nunca é devolvida pela API depois de salva."""

    id: str | None = None
    enabled: bool
    smtp_host: str
    smtp_port: int
    security: EmailSecurity
    smtp_username: str | None
    password_configured: bool
    from_email: str
    from_name: str | None
    last_test_at: datetime | None
    last_test_ok: bool | None
    last_test_error: str | None
    updated_at: datetime | None


class EmailTestRequest(BaseModel):
    to_email: EmailStr


class EmailLogRead(BaseModel):
    """Uma linha da tela "Log de e-mails enviados" (ver EmailLog em
    app/models.py). `kind` é texto livre — a tela mapeia os valores
    conhecidos ("teste", "agendamento", "resumo_aprovacoes") para um
    rótulo amigável e mostra o valor cru para qualquer tipo novo que
    vier a ser adicionado depois."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    kind: str
    to_email: str
    to_name: str | None
    subject: str
    success: bool
    error_message: str | None


# ---------------------------------------------------------------------------
# Conhecimento (ver docstrings dos modelos em app/models.py para o
# detalhe das decisões confirmadas com o usuário)
# ---------------------------------------------------------------------------


class KnowledgeFunctionalityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    requirement: KnowledgeRequirement = KnowledgeRequirement.REQUIRED


class KnowledgeFunctionalityRead(ORMModel):
    id: str
    module_id: str
    name: str
    description: str | None = None
    requirement: KnowledgeRequirement


class KnowledgeModuleCreate(BaseModel):
    """`applies_to_consultant`/`applies_to_internal_pm`: pelo menos um
    precisa ficar marcado (mesma regra do `CheckConstraint` em
    KnowledgeModule — validada aqui também pra devolver um 422 amigável
    em vez de um erro de banco). `requirement` (pedido do usuário, 2ª
    rodada) é só classificação neste nível — ver docstring de
    KnowledgeModule em app/models.py."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    applies_to_consultant: bool = True
    applies_to_internal_pm: bool = True
    requirement: KnowledgeRequirement = KnowledgeRequirement.REQUIRED

    @model_validator(mode="after")
    def _at_least_one_profile(self) -> "KnowledgeModuleCreate":
        if not self.applies_to_consultant and not self.applies_to_internal_pm:
            raise ValueError("Selecione ao menos um perfil (Consultor e/ou Gerente de Projeto)")
        return self


class KnowledgeModuleRead(ORMModel):
    id: str
    system_id: str
    name: str
    description: str | None = None
    applies_to_consultant: bool
    applies_to_internal_pm: bool
    requirement: KnowledgeRequirement
    functionalities: list[KnowledgeFunctionalityRead] = []


class KnowledgeSystemCreate(BaseModel):
    """`applies_to_consultant`/`applies_to_internal_pm`/`requirement`
    (pedido do usuário, 2ª rodada: "a obrigatoriedade que hoje está para
    consultor e gerente de projetos, gostaria de configurar no
    sistema/módulo, incluindo se é necessário ou desejável") — só
    classificação/organização neste nível, sem nenhum efeito em quem vê
    o quê na autoavaliação nem no badge mostrado na revisão (isso continua
    vindo só do Módulo/Funcionalidade, respectivamente — ver docstring de
    KnowledgeSystem em app/models.py). Mesma validação "pelo menos um
    perfil" do Módulo, por consistência visual."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    applies_to_consultant: bool = True
    applies_to_internal_pm: bool = True
    requirement: KnowledgeRequirement = KnowledgeRequirement.REQUIRED

    @model_validator(mode="after")
    def _at_least_one_profile(self) -> "KnowledgeSystemCreate":
        if not self.applies_to_consultant and not self.applies_to_internal_pm:
            raise ValueError("Selecione ao menos um perfil (Consultor e/ou Gerente de Projeto)")
        return self


class KnowledgeSystemRead(ORMModel):
    id: str
    name: str
    description: str | None = None
    applies_to_consultant: bool
    applies_to_internal_pm: bool
    requirement: KnowledgeRequirement
    modules: list[KnowledgeModuleRead] = []


# --- Autoavaliação ("Registro de Funcionalidades por Consultor/Gerente") ---


class MyKnowledgeFunctionalityRead(BaseModel):
    """Uma folha do catálogo já anotada com a autoavaliação do recurso
    logado, se houver (`status=None` = nunca avaliada — diferente de
    `status=DRAFT` com `self_level=0`, que é uma resposta explícita de
    "Não conhece")."""

    id: str
    name: str
    description: str | None = None
    requirement: KnowledgeRequirement
    self_level: int | None = None
    reviewed_level: int | None = None
    status: KnowledgeStatus | None = None
    notes: str | None = None


class MyKnowledgeModuleRead(BaseModel):
    id: str
    name: str
    description: str | None = None
    functionalities: list[MyKnowledgeFunctionalityRead] = []


class MyKnowledgeSystemRead(BaseModel):
    id: str
    name: str
    description: str | None = None
    modules: list[MyKnowledgeModuleRead] = []


class ResourceKnowledgeUpsert(BaseModel):
    self_level: int = Field(ge=0, le=4)
    notes: str | None = None


# --- Revisão e Aprovação ---


class KnowledgeSubmissionItemRead(BaseModel):
    """Um item dentro do envio, já com o caminho completo do catálogo
    (Sistema / Módulo / Funcionalidade) — a tela de revisão não precisa
    montar isso na mão nem fazer chamadas extras."""

    id: str
    functionality_id: str
    system_name: str
    module_name: str
    functionality_name: str
    requirement: KnowledgeRequirement
    self_level: int | None = None
    reviewed_level: int | None = None
    notes: str | None = None


class KnowledgeSubmissionRead(BaseModel):
    id: str
    resource_id: str
    resource_name: str
    # Pedido do frontend (KnowledgeReviewPage.jsx): comparar com o usuário
    # logado pra esconder os botões Aprovar/Rejeitar na própria
    # autoavaliação — o backend já bloqueia isso com 403 (ver
    # review_submission em routers/knowledge.py), este campo só evita que o
    # revisor precise clicar pra descobrir.
    resource_user_id: str
    status: KnowledgeStatus
    submitted_at: datetime
    reviewed_by: str | None = None
    reviewer_name: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
    items: list[KnowledgeSubmissionItemRead] = []


class KnowledgeSubmissionReviewItem(BaseModel):
    functionality_id: str
    reviewed_level: int = Field(ge=0, le=4)


class KnowledgeSubmissionReview(BaseModel):
    """Corpo de PATCH /knowledge/submissions/{id} — decisão confirmada com
    o usuário: aprovação é SEMPRE do envio inteiro (nunca item a item), e
    o revisor PODE ajustar o nível de cada item antes de aprovar (`items`
    abaixo; qualquer funcionalidade do envio não listada aqui mantém
    `reviewed_level = self_level`, ver review_submission em
    routers/knowledge.py). Em uma rejeição, `review_notes` é obrigatório
    (validado no router, não aqui, porque depende do `status`)."""

    status: KnowledgeStatus
    review_notes: str | None = None
    items: list[KnowledgeSubmissionReviewItem] = []
