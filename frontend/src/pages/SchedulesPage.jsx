import { useEffect, useMemo, useState } from 'react'
import * as schedulesApi from '../api/schedules'
import * as timesheetsApi from '../api/timesheets'
import * as resourcesApi from '../api/resources'
import * as usersApi from '../api/users'
import * as clientsApi from '../api/clients'
import * as projectsApi from '../api/projects'
import * as tasksApi from '../api/tasks'
import * as calendarsApi from '../api/calendars'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Button from '../components/Button'
import IconButton from '../components/IconButton'
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import { FormField, TextInput, Select, TextArea } from '../components/FormField'
import { ChevronLeftIcon, ChevronRightIcon, PlusIcon } from '../components/icons'
import { formatTime } from '../utils/format'
import { MANAGEMENT_ROLES, resourceFunctionLevelLabel } from '../utils/labels'
import { DEFAULT_PROJECT_COLOR, contrastTextColor } from '../utils/colorPalette'

const EMPTY_FILTERS = { resource_id: '', client_id: '', project_id: '', start: '', end: '' }

function toIsoDate(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

/** Ausência da empresa (Timesheet.absence_type, pedido do usuário: "Sim, já
 * incluir nesta etapa") do recurso numa data — consultada pelos dois
 * modais abaixo (criar/editar agendamento e confirmar mover por
 * arrastar-e-soltar) só pra AVISAR antes de salvar; quem de fato impede é
 * sempre o backend (_check_absence em routers/schedules.py — nunca confiar
 * só nesta checagem do lado do cliente). REJECTED não conta, mesmo
 * critério usado lá. Por recurso (não por dia inteiro pra todo mundo,
 * diferente do feriado do calendário padrão abaixo) — só bloqueia o
 * consultor que está realmente ausente. */
async function findResourceAbsence(resourceId, isoDate) {
  if (!resourceId || !isoDate) return null
  const rows = await timesheetsApi.listTimesheets({ resource_id: resourceId, start: isoDate, end: isoDate, has_absence: true })
  return rows.find((row) => row.absence_type && row.status !== 'REJECTED') || null
}

/** Início da semana (domingo) que contém `date` — usado só pra montar a
 * grade visual do mês (domingo a sábado, mais fácil de visualizar — pedido
 * do usuário), nunca pra cálculo de negócio: dias úteis/feriados continuam
 * em `WEEKDAY_LABELS`/`working_days` com a convenção ISO do backend
 * (segunda=0..domingo=6, ver services.py e CalendarsPage.jsx), que não
 * muda por causa disso. */
function startOfWeek(date) {
  const day = date.getDay() // 0=Dom..6=Sáb
  const result = new Date(date)
  result.setDate(result.getDate() - day)
  return result
}

/** Monta as células da grade do mês: sempre semanas completas (múltiplo de
 * 7), começando no domingo da semana que contém o dia 1 e terminando na
 * semana que contém o último dia do mês — inclui alguns dias do mês
 * anterior/seguinte pra não deixar semana incompleta na grade. */
function buildMonthCells(viewDate) {
  const firstOfMonth = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1)
  const lastOfMonth = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 0)
  const gridStart = startOfWeek(firstOfMonth)
  const cells = []
  const cursor = new Date(gridStart)
  while (cursor <= lastOfMonth || cursor.getDay() !== 0) {
    cells.push(new Date(cursor))
    cursor.setDate(cursor.getDate() + 1)
    if (cells.length > 42) break
  }
  return cells
}

export default function SchedulesPage() {
  const { user } = useAuth()
  const { labels, t, language } = useLanguage()
  const canManage = MANAGEMENT_ROLES.includes(user.role)
  // "Minha agenda" (pedido do usuário): para o Consultor esta tela é a página
  // inicial — mostra só os agendamentos do próprio usuário (sem filtro de
  // Consultor), mais feriados e as ausências dele, somente leitura.
  const mine = !canManage

  const [viewDate, setViewDate] = useState(() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), 1)
  })
  const [filters, setFilters] = useState(EMPTY_FILTERS)

  const [resources, setResources] = useState([])
  const [users, setUsers] = useState([])
  const [clients, setClients] = useState([])
  const [projects, setProjects] = useState([])
  const [allTasks, setAllTasks] = useState([])
  const [schedules, setSchedules] = useState([])
  const [loading, setLoading] = useState(true)
  const [resourcesLoaded, setResourcesLoaded] = useState(false)
  const [error, setError] = useState('')
  // Ausências (Férias, Atestado...) do consultor selecionado no mês, por
  // data -> tipo — só informativo na grade; quem bloqueia agendar em dia de
  // ausência é o backend.
  const [absencesByDate, setAbsencesByDate] = useState({})
  // Feriados do calendário padrão (pedido do usuário: mostrar na Agenda
  // como indisponíveis) — a Agenda não é de um projeto só (pode ter
  // agendamentos de vários projetos/recursos, cada um com seu próprio
  // Calendário), então em vez de resolver um calendário por agendamento,
  // um único calendário marcado como padrão (Calendar.is_default, ver
  // CalendarsPage.jsx) vale pra tela inteira. map iso -> descrição.
  const [holidaysByDate, setHolidaysByDate] = useState({})

  const [formTarget, setFormTarget] = useState(null) // { schedule } pra editar, ou { date } pra criar novo

  // Arrastar-e-soltar um bloco da agenda pra outro dia (pedido do usuário)
  // — draggedSchedule guarda o agendamento sendo arrastado (só setado por
  // quem tem canManage, já que Consultor só visualiza); dragOverDate só
  // controla o realce visual da célula sob o cursor; moveTarget abre o
  // modal de confirmação antes de efetivar a troca de data — nada é salvo
  // só por soltar o bloco.
  const [draggedSchedule, setDraggedSchedule] = useState(null)
  const [dragOverDate, setDragOverDate] = useState('')
  const [moveTarget, setMoveTarget] = useState(null) // { schedule, newDate }

  // Referência (recursos/usuários/clientes/projetos) carregada uma vez —
  // usada pros filtros e pra montar os rótulos/cores dos blocos da agenda.
  // Tarefas de todos os projetos (mesmo padrão de TimesheetsPage.jsx)
  // alimentam o checklist "Tarefas" do agendamento (pedido do usuário).
  useEffect(() => {
    resourcesApi
      .listResources()
      .then(setResources)
      .catch(() => {})
      .finally(() => setResourcesLoaded(true))
    // Lista de usuários é só de gestão (GET /users); o Consultor usa o
    // próprio nome (ver resourceOptions abaixo).
    if (canManage) usersApi.listUsers().then(setUsers).catch(() => {})
    clientsApi.listClients().then(setClients).catch(() => {})
    projectsApi
      .listProjects()
      .then((rows) => {
        setProjects(rows)
        Promise.all(rows.map((p) => tasksApi.listTasks(p.id).catch(() => []))).then((lists) => setAllTasks(lists.flat()))
      })
      .catch(() => {})
  }, [])

  // Carrega os feriados do calendário padrão uma única vez (lista de
  // feriados de um calendário é pequena, sem paginação/filtro por período
  // no backend — ver GET /calendars/{id}/holidays). Falha silenciosa: sem
  // calendário padrão cadastrado, a Agenda simplesmente não marca nenhum
  // dia como feriado, em vez de quebrar a tela toda.
  useEffect(() => {
    calendarsApi
      .listCalendars()
      .then((calendars) => calendars.find((c) => c.is_default))
      .then((defaultCalendar) => (defaultCalendar ? calendarsApi.listHolidays(defaultCalendar.id) : []))
      .then((holidays) => setHolidaysByDate(Object.fromEntries(holidays.map((h) => [h.date, h.description]))))
      .catch(() => {})
  }, [])

  const usersById = useMemo(() => Object.fromEntries(users.map((u) => [u.id, u])), [users])
  const resourceOptions = useMemo(
    () =>
      resources.map((resource) => ({
        ...resource,
        userName:
          (resource.user_id === user.id ? user.name : null) ||
          usersById[resource.user_id]?.name ||
          resourceFunctionLevelLabel(resource, labels) ||
          resource.id,
      })),
    [resources, usersById, labels, user],
  )
  const resourcesById = useMemo(() => Object.fromEntries(resourceOptions.map((r) => [r.id, r])), [resourceOptions])
  const projectsById = useMemo(() => Object.fromEntries(projects.map((p) => [p.id, p])), [projects])

  // Um consultor abre a própria agenda por padrão (o recurso vinculado ao
  // próprio usuário) — pode limpar o filtro pra ver outros, já que a
  // leitura é liberada pros três perfis internos (ver _READ_ROLES na API).
  useEffect(() => {
    if (canManage || filters.resource_id || resourceOptions.length === 0) return
    const own = resourceOptions.find((r) => r.user_id === user.id)
    if (own) setFilters((prev) => ({ ...prev, resource_id: own.id }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resourceOptions, canManage])

  // Filtro "Projeto" da Agenda só lista projetos ativos (pedido do
  // usuário) — mesmo critério já usado no combo de projeto do apontamento
  // de horas (TimesheetFieldsForm).
  const projectOptions = useMemo(
    () => projects.filter((p) => p.status === 'ACTIVE' && (!filters.client_id || p.client_id === filters.client_id)),
    [projects, filters.client_id],
  )
  const monthCells = useMemo(() => buildMonthCells(viewDate), [viewDate])
  // Cabeçalho da grade do mês, domingo a sábado — reordena só a exibição
  // (WEEKDAY_LABELS em si continua segunda=0..domingo=6, convenção do
  // backend usada em CalendarsPage/working_days; ver comentário em
  // startOfWeek acima).
  const weekdayLabelsSundayFirst = useMemo(
    () => [labels.WEEKDAY_LABELS[6], ...labels.WEEKDAY_LABELS.slice(0, 6)],
    [labels.WEEKDAY_LABELS],
  )

  // Sempre carrega o mês inteiro visível na grade — o calendário nunca
  // "desmonta" pra virar lista, nem quando Data inicial/final estão
  // preenchidas (pedido do usuário). O recorte por período fica só do lado
  // do cliente, em `schedulesByDate` abaixo: os blocos fora do intervalo
  // simplesmente não aparecem nos dias do mês, sem trocar o formato da
  // tela.
  function loadSchedules() {
    // Consultor: só carrega depois de descobrir o próprio recurso, para não
    // piscar a agenda de todo mundo antes do filtro entrar.
    if (mine && !filters.resource_id) {
      setSchedules([])
      setLoading(!resourcesLoaded)
      return
    }
    setLoading(true)
    setError('')
    schedulesApi
      .listSchedules({
        resource_id: filters.resource_id || undefined,
        client_id: filters.client_id || undefined,
        project_id: filters.project_id || undefined,
        start: toIsoDate(monthCells[0]),
        end: toIsoDate(monthCells[monthCells.length - 1]),
      })
      .then(setSchedules)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadSchedules, [viewDate, filters.resource_id, filters.client_id, filters.project_id, resourcesLoaded])

  // Ausências do consultor selecionado no período visível da grade.
  useEffect(() => {
    if (!filters.resource_id) {
      setAbsencesByDate({})
      return
    }
    timesheetsApi
      .listTimesheets({
        resource_id: filters.resource_id,
        start: toIsoDate(monthCells[0]),
        end: toIsoDate(monthCells[monthCells.length - 1]),
        has_absence: true,
      })
      .then((rows) =>
        setAbsencesByDate(
          Object.fromEntries(rows.filter((row) => row.absence_type && row.status !== 'REJECTED').map((row) => [row.date, row.absence_type])),
        ),
      )
      .catch(() => setAbsencesByDate({}))
  }, [viewDate, filters.resource_id])

  const schedulesByDate = useMemo(() => {
    const map = {}
    for (const schedule of schedules) {
      if (filters.start && schedule.date < filters.start) continue
      if (filters.end && schedule.date > filters.end) continue
      ;(map[schedule.date] ||= []).push(schedule)
    }
    for (const list of Object.values(map)) {
      list.sort((a, b) => a.start_time.localeCompare(b.start_time))
    }
    return map
  }, [schedules, filters.start, filters.end])

  function updateFilter(field) {
    return (event) => setFilters((prev) => ({ ...prev, [field]: event.target.value }))
  }

  function scheduleLabel(schedule) {
    const resourceName = resourcesById[schedule.resource_id]?.userName || '—'
    const projectCode = projectsById[schedule.project_id]?.code || '—'
    return `${formatTime(schedule.start_time)}–${formatTime(schedule.end_time)} · ${resourceName} · ${projectCode}`
  }

  const monthLabel = viewDate.toLocaleDateString(language === 'es' ? 'es-ES' : 'pt-BR', { month: 'long', year: 'numeric' })

  return (
    <div>
      <PageHeader
        title={mine ? t('Minha agenda') : t('Agenda de consultores')}
        subtitle={
          mine
            ? t('O que está agendado para você, com feriados e ausências.')
            : t('Agendamento de recursos por projeto, dia e horário.')
        }
      />

      <Card className="mb-4">
        <div className={`grid grid-cols-2 gap-3 ${mine ? 'md:grid-cols-4' : 'md:grid-cols-5'}`}>
          {!mine && (
            <FormField label={t('Consultor')}>
              <Select value={filters.resource_id} onChange={updateFilter('resource_id')}>
                <option value="">{t('Todos')}</option>
                {resourceOptions.map((resource) => (
                  <option key={resource.id} value={resource.id}>
                    {resource.userName}
                  </option>
                ))}
              </Select>
            </FormField>
          )}
          <FormField label={t('Cliente')}>
            <Select value={filters.client_id} onChange={updateFilter('client_id')}>
              <option value="">{t('Todos')}</option>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.legal_name}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label={t('Projeto')}>
            <Select value={filters.project_id} onChange={updateFilter('project_id')}>
              <option value="">{t('Todos')}</option>
              {projectOptions.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.code} — {project.name}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label={t('Data inicial')}>
            <TextInput type="date" value={filters.start} onChange={updateFilter('start')} />
          </FormField>
          <FormField label={t('Data final')}>
            <TextInput type="date" value={filters.end} onChange={updateFilter('end')} />
          </FormField>
        </div>
        {(filters.start || filters.end) && (
          <p className="mt-3 text-xs text-[var(--text-muted)]">
            {t('Mostrando o mês normalmente — os agendamentos fora do período informado ficam ocultos nos dias do calendário.')}
          </p>
        )}
      </Card>

      <ErrorBanner message={error} />

      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-1">
          <IconButton
            icon={ChevronLeftIcon}
            label={t('Mês anterior')}
            onClick={() => setViewDate((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1))}
          />
          <IconButton
            icon={ChevronRightIcon}
            label={t('Próximo mês')}
            onClick={() => setViewDate((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1))}
          />
          <Button
            variant="secondary"
            onClick={() => setViewDate(() => { const now = new Date(); return new Date(now.getFullYear(), now.getMonth(), 1) })}
          >
            {t('Hoje')}
          </Button>
        </div>
        <p className="text-sm font-semibold capitalize text-[var(--text-primary)]">{monthLabel}</p>
        {canManage ? (
          <Button onClick={() => setFormTarget({ date: toIsoDate(new Date()) })}>
            <PlusIcon size={16} /> {t('Novo agendamento')}
          </Button>
        ) : (
          <span />
        )}
      </div>

      {loading && <Spinner />}

      {!loading && (
        <Card dense>
          <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-[var(--text-secondary)]">
            {weekdayLabelsSundayFirst.map((day, index) => (
              <div key={`${day}-${index}`} className="py-1">
                {day}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {monthCells.map((cellDate) => {
              const iso = toIsoDate(cellDate)
              const inMonth = cellDate.getMonth() === viewDate.getMonth()
              const daySchedules = schedulesByDate[iso] || []
              const isToday = iso === toIsoDate(new Date())
              const holidayDescription = holidaysByDate[iso]
              const isHoliday = Boolean(holidayDescription)
              const absenceType = absencesByDate[iso]
              // Feriado conta como indisponível pra agendar (pedido do
              // usuário) — some o "+" de criação rápida e não aceita
              // soltar um bloco arrastado nele, sem impedir visualizar os
              // agendamentos que já existiam ali (ex.: feriado cadastrado
              // depois do agendamento já criado).
              const isDragOver = canManage && !isHoliday && dragOverDate === iso && draggedSchedule && draggedSchedule.date !== iso
              return (
                <div
                  key={iso}
                  onDragOver={
                    canManage && !isHoliday
                      ? (event) => {
                          event.preventDefault()
                          setDragOverDate(iso)
                        }
                      : undefined
                  }
                  onDragLeave={canManage ? () => setDragOverDate((prev) => (prev === iso ? '' : prev)) : undefined}
                  onDrop={
                    canManage && !isHoliday
                      ? (event) => {
                          event.preventDefault()
                          setDragOverDate('')
                          const schedule = draggedSchedule
                          setDraggedSchedule(null)
                          if (!schedule || schedule.date === iso) return
                          setMoveTarget({ schedule, newDate: iso })
                        }
                      : undefined
                  }
                  title={holidayDescription || undefined}
                  className={`min-h-[92px] rounded-lg border p-1.5 transition-colors ${
                    inMonth ? 'border-[var(--border)]' : 'border-transparent opacity-40'
                  } ${isHoliday ? 'border-[var(--status-critical)]/30 bg-[var(--status-critical)]/5' : ''} ${
                    isDragOver ? 'border-[var(--series-1)] bg-[var(--page)] ring-1 ring-[var(--series-1)]' : ''
                  }`}
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span
                      className={`text-xs font-medium ${isToday ? 'flex h-5 w-5 items-center justify-center rounded-full bg-[var(--series-1)] text-white' : 'text-[var(--text-secondary)]'}`}
                    >
                      {cellDate.getDate()}
                    </span>
                    {canManage && !isHoliday && (
                      <button
                        type="button"
                        title={t('Novo agendamento')}
                        onClick={() => setFormTarget({ date: iso })}
                        className="rounded px-1 text-xs text-[var(--text-muted)] hover:bg-[var(--page)] hover:text-[var(--text-primary)]"
                      >
                        +
                      </button>
                    )}
                  </div>
                  {isHoliday && (
                    <p className="truncate text-[10px] font-medium text-[var(--status-critical)]">{holidayDescription}</p>
                  )}
                  {absenceType && (
                    <p className="truncate text-[10px] font-medium text-[var(--status-warning)]">
                      {labels.ABSENCE_TYPE_LABELS[absenceType] || absenceType}
                    </p>
                  )}
                  <div className="space-y-0.5">
                    {daySchedules.slice(0, 3).map((schedule) => {
                      const color = projectsById[schedule.project_id]?.color || DEFAULT_PROJECT_COLOR
                      return (
                        <button
                          key={schedule.id}
                          type="button"
                          draggable={canManage}
                          title={scheduleLabel(schedule)}
                          onClick={() => setFormTarget({ schedule })}
                          onDragStart={
                            canManage
                              ? (event) => {
                                  setDraggedSchedule(schedule)
                                  event.dataTransfer.effectAllowed = 'move'
                                }
                              : undefined
                          }
                          onDragEnd={canManage ? () => { setDraggedSchedule(null); setDragOverDate('') } : undefined}
                          className={`block w-full truncate rounded px-1 py-0.5 text-left text-[10.5px] font-medium ${canManage ? 'cursor-grab active:cursor-grabbing' : ''}`}
                          style={{ backgroundColor: color, color: contrastTextColor(color) }}
                        >
                          {formatTime(schedule.start_time)}{' '}
                          {mine ? projectsById[schedule.project_id]?.code || '—' : resourcesById[schedule.resource_id]?.userName || '—'}
                        </button>
                      )
                    })}
                    {daySchedules.length > 3 && (
                      <p className="px-1 text-[10px] text-[var(--text-muted)]">{t('+{n} mais', { n: daySchedules.length - 3 })}</p>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      )}

      {formTarget && (
        <ScheduleFormModal
          schedule={formTarget.schedule}
          defaultDate={formTarget.date}
          resourceOptions={resourceOptions}
          projects={projects}
          allTasks={allTasks}
          canManage={canManage}
          onClose={() => setFormTarget(null)}
          onSaved={() => {
            setFormTarget(null)
            loadSchedules()
          }}
        />
      )}

      {moveTarget && (
        <MoveScheduleConfirmModal
          schedule={moveTarget.schedule}
          newDate={moveTarget.newDate}
          resourceName={resourcesById[moveTarget.schedule.resource_id]?.userName || '—'}
          projectLabel={
            projectsById[moveTarget.schedule.project_id]
              ? `${projectsById[moveTarget.schedule.project_id].code} — ${projectsById[moveTarget.schedule.project_id].name}`
              : '—'
          }
          onClose={() => setMoveTarget(null)}
          onMoved={() => {
            setMoveTarget(null)
            loadSchedules()
          }}
        />
      )}
    </div>
  )
}

/** Confirmação antes de efetivar o arrastar-e-soltar de um bloco da agenda
 * pra outro dia — só troca `date` (PATCH parcial), preservando
 * horário/projeto/descrição; o backend revalida sobreposição de horário do
 * recurso no dia de destino (_check_overlap em routers/schedules.py) e
 * devolve 409 se já houver outro agendamento dele no mesmo horário — o erro
 * aparece aqui em vez de mover silenciosamente pra um horário conflitante. */
function MoveScheduleConfirmModal({ schedule, newDate, resourceName, projectLabel, onClose, onMoved }) {
  const { t, labels } = useLanguage()
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  // Aviso prévio de ausência (ver findResourceAbsence acima) — só avisa;
  // quem de fato bloqueia é o backend (_check_absence), acionado no
  // handleConfirm abaixo igual a qualquer outro erro de validação.
  const [absenceWarning, setAbsenceWarning] = useState('')

  useEffect(() => {
    let active = true
    findResourceAbsence(schedule.resource_id, newDate)
      .then((absence) => {
        if (active) setAbsenceWarning(absence ? labels.ABSENCE_TYPE_LABELS[absence.absence_type] || absence.absence_type : '')
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [schedule.resource_id, newDate, labels])

  async function handleConfirm() {
    setSaving(true)
    setError('')
    try {
      await schedulesApi.updateSchedule(schedule.id, { date: newDate })
      onMoved()
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  return (
    <Modal title={t('Mover agendamento?')} onClose={onClose}>
      <div className="space-y-4">
        <div className="rounded-lg border border-[var(--border)] p-3 text-sm">
          <p className="font-medium text-[var(--text-primary)]">
            {resourceName} · {projectLabel}
          </p>
          <p className="mt-0.5 text-[var(--text-secondary)]">
            {formatTime(schedule.start_time)}–{formatTime(schedule.end_time)}
          </p>
        </div>
        <p className="text-sm text-[var(--text-secondary)]">
          {t('Mover de {from} para {to}?', { from: schedule.date, to: newDate })}
        </p>

        {absenceWarning && (
          <p className="rounded-lg border border-[var(--status-critical)]/30 bg-[var(--status-critical)]/5 px-3 py-2 text-xs text-[var(--status-critical)]">
            {t('{resource} está ausente ({type}) em {date} — não é possível agendar nesta data.', {
              resource: resourceName,
              type: absenceWarning,
              date: newDate,
            })}
          </p>
        )}

        <ErrorBanner message={error} />

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="button" disabled={saving || Boolean(absenceWarning)} onClick={handleConfirm}>
            {saving ? t('Movendo…') : t('Confirmar')}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

/** Cria ou edita um bloco de agenda. A cor não é escolhida aqui — segue
 * automaticamente `project.color` (decisão do usuário: "Fixa por
 * projeto") — por isso não existe nenhum ColorSwatchPicker neste form.
 *
 * Quem não está em MANAGEMENT_ROLES (Consultor) só pode VISUALIZAR: o
 * clique no bloco do calendário mensal abre este modal pra qualquer
 * perfil interno (pra dar consulta aos detalhes — dia, horário,
 * descrição — que não cabem no bloco), mas com `canManage=false` os
 * campos ficam desabilitados e os botões Salvar/Excluir somem, sobrando
 * só "Fechar". Reforça na UI o que a API já impõe (_MANAGE_ROLES em
 * routers/schedules.py). */
function ScheduleFormModal({ schedule, defaultDate, resourceOptions, projects, allTasks, canManage, onClose, onSaved }) {
  const { t, labels } = useLanguage()
  const isEdit = Boolean(schedule)
  const readOnly = !canManage
  const [form, setForm] = useState({
    resource_id: schedule?.resource_id || '',
    project_id: schedule?.project_id || '',
    date: schedule?.date || defaultDate || '',
    start_time: schedule?.start_time?.slice(0, 5) || '',
    end_time: schedule?.end_time?.slice(0, 5) || '',
    description: schedule?.description || '',
    // Tarefas do bloco (pedido do usuário: "adicionar uma ou mais tarefas,
    // sem horas, para a agenda") — ver ResourceScheduleTask, app/models.py.
    task_ids: schedule?.tasks?.map((task) => task.id) || [],
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [absenceWarning, setAbsenceWarning] = useState('')
  // A API (routers/schedules.py) só recusa por ausência quando a DATA está
  // sendo atribuída de novo — criar, ou editar mudando a data (mesmo
  // critério de _check_absence: editar só horário/descrição num
  // agendamento que já existia não revalida isso). O aviso do lado do
  // cliente segue o mesmo critério, pra não assustar o usuário com um erro
  // que a API nem vai dar.
  const dateChanged = !isEdit || form.date !== (schedule?.date || '')

  useEffect(() => {
    if (readOnly || !dateChanged || !form.resource_id || !form.date) {
      setAbsenceWarning('')
      return undefined
    }
    let active = true
    findResourceAbsence(form.resource_id, form.date)
      .then((absence) => {
        if (active) setAbsenceWarning(absence ? labels.ABSENCE_TYPE_LABELS[absence.absence_type] || absence.absence_type : '')
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [form.resource_id, form.date, dateChanged, readOnly, labels])

  function updateField(field) {
    return (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  // Trocar o projeto limpa as tarefas já marcadas — elas pertencem ao
  // projeto anterior e deixam de fazer sentido aqui (mesmo critério
  // aplicado no backend quando project_id muda sem informar task_ids, ver
  // update_schedule em routers/schedules.py).
  function updateProjectId(event) {
    const value = event.target.value
    setForm((prev) => ({ ...prev, project_id: value, task_ids: [] }))
  }

  function toggleTask(taskId) {
    setForm((prev) => ({
      ...prev,
      task_ids: prev.task_ids.includes(taskId) ? prev.task_ids.filter((id) => id !== taskId) : [...prev.task_ids, taskId],
    }))
  }

  // Tarefas-folha do projeto selecionado, pra montar o checklist — mesmo
  // critério de taskOptions/parentTaskIds já usado em TimesheetsPage.jsx
  // (tarefa "pai" aparece na lista só como referência, desabilitada; o
  // apontamento/agendamento só aceita tarefa-folha).
  const projectTasks = useMemo(() => allTasks.filter((task) => task.project_id === form.project_id), [allTasks, form.project_id])
  const parentTaskIds = useMemo(() => new Set(allTasks.map((task) => task.parent_task_id).filter(Boolean)), [allTasks])

  // Pedido do usuário: cruza o Nível do consultor com o Nível mínimo de
  // cada tarefa marcada — recurso sem nível definido nunca bloqueia (mesmo
  // critério do seletor de recursos na aba Tarefas, ver ProjectDetailPage.jsx).
  // Aviso só do lado do cliente, pra não deixar nem tentar salvar — a API
  // (routers/schedules.py, _resolve_schedule_tasks) recusa o mesmo jeito,
  // inclusive numa edição onde esta tela não tivesse a info mais recente.
  const selectedResource = useMemo(() => resourceOptions.find((resource) => resource.id === form.resource_id), [resourceOptions, form.resource_id])
  const levelBlockedTasks = useMemo(() => {
    if (!selectedResource || selectedResource.level == null) return []
    return projectTasks.filter((task) => form.task_ids.includes(task.id) && selectedResource.level < task.min_level)
  }, [selectedResource, projectTasks, form.task_ids])

  async function handleSubmit(event) {
    event.preventDefault()
    if (readOnly) return
    setError('')
    setSaving(true)
    try {
      if (isEdit) {
        // ResourceScheduleUpdate não tem resource_id — trocar o consultor de
        // um agendamento já feito não é suportado (rule de negócio: cria um
        // novo agendamento pro outro consultor em vez de "mover" este).
        const { resource_id, ...payload } = form
        await schedulesApi.updateSchedule(schedule.id, payload)
      } else {
        await schedulesApi.createSchedule(form)
      }
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (readOnly) return
    setDeleting(true)
    setError('')
    try {
      await schedulesApi.deleteSchedule(schedule.id)
      onSaved()
    } catch (err) {
      setError(err.message)
      setDeleting(false)
    }
  }

  return (
    <Modal title={isEdit ? t('Editar agendamento') : t('Novo agendamento')} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField
          label={t('Consultor')}
          required
          hint={isEdit ? t('Não é possível trocar o consultor de um agendamento já criado — exclua e crie um novo.') : undefined}
        >
          <Select required disabled={isEdit || readOnly} value={form.resource_id} onChange={updateField('resource_id')}>
            <option value="">{t('Selecione…')}</option>
            {resourceOptions.map((resource) => (
              <option key={resource.id} value={resource.id}>
                {resource.userName}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label={t('Projeto')} required>
          <Select required disabled={readOnly} value={form.project_id} onChange={updateProjectId}>
            <option value="">{t('Selecione…')}</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.code} — {project.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label={t('Data')} required>
          <TextInput type="date" required disabled={readOnly} value={form.date} onChange={updateField('date')} />
        </FormField>
        <div className="grid grid-cols-2 gap-4">
          <FormField label={t('Hora início')} required>
            <TextInput type="time" required disabled={readOnly} value={form.start_time} onChange={updateField('start_time')} />
          </FormField>
          <FormField label={t('Hora fim')} required>
            <TextInput type="time" required disabled={readOnly} value={form.end_time} onChange={updateField('end_time')} />
          </FormField>
        </div>

        {/* Tarefas do bloco (pedido do usuário) — no modo consulta
            (Consultor), vira uma lista enxuta só do que já está vinculado
            ("o que ele precisa trabalhar"); quem gerencia vê o checklist
            inteiro do projeto pra marcar/desmarcar. */}
        {readOnly ? (
          schedule?.tasks?.length > 0 && (
            <FormField label={t('Tarefas')}>
              <ul className="list-disc list-inside space-y-1 rounded-lg border border-[var(--border)] px-3 py-2 text-sm text-[var(--text-primary)]">
                {schedule.tasks.map((task) => (
                  <li key={task.id}>
                    {task.wbs_code} — {task.name}
                  </li>
                ))}
              </ul>
            </FormField>
          )
        ) : (
          <FormField
            label={t('Tarefas')}
            hint={
              !form.project_id
                ? t('Selecione um projeto para escolher as tarefas.')
                : projectTasks.length === 0
                  ? t('Este projeto ainda não tem tarefas cadastradas.')
                  : t('Opcional — o que o consultor precisa trabalhar neste bloco.')
            }
          >
            <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-[var(--border)] p-2">
              {projectTasks.map((task) => {
                const isParent = parentTaskIds.has(task.id)
                // Pedido do usuário: marca na própria lista qual tarefa está
                // travando (não só no aviso de baixo, que já resume todas).
                const isLevelBlocked =
                  !isParent && selectedResource && selectedResource.level != null && selectedResource.level < task.min_level && form.task_ids.includes(task.id)
                return (
                  <label
                    key={task.id}
                    className={`flex items-center gap-2 rounded px-1 py-0.5 text-xs ${
                      isLevelBlocked ? 'text-[var(--status-critical)]' : isParent ? 'text-[var(--text-muted)]' : 'text-[var(--text-secondary)]'
                    }`}
                  >
                    <input type="checkbox" checked={form.task_ids.includes(task.id)} disabled={isParent} onChange={() => toggleTask(task.id)} />
                    {task.wbs_code} — {task.name}
                    {isParent ? ` (${t('tarefa-pai, selecione uma tarefa-filha')})` : ''}
                    {isLevelBlocked ? ` (${t('nível mínimo {level}', { level: task.min_level })})` : ''}
                  </label>
                )
              })}
            </div>
          </FormField>
        )}

        <FormField label={t('Descrição')}>
          <TextArea rows={2} disabled={readOnly} value={form.description} onChange={updateField('description')} />
        </FormField>

        {absenceWarning && (
          <p className="rounded-lg border border-[var(--status-critical)]/30 bg-[var(--status-critical)]/5 px-3 py-2 text-xs text-[var(--status-critical)]">
            {t('Este consultor está ausente ({type}) nesta data — não é possível agendar.', { type: absenceWarning })}
          </p>
        )}

        {levelBlockedTasks.length > 0 && (
          <p className="rounded-lg border border-[var(--status-critical)]/30 bg-[var(--status-critical)]/5 px-3 py-2 text-xs text-[var(--status-critical)]">
            {t('Nível do consultor (nível {level}) é menor que o nível mínimo exigido pelas tarefas a seguir: {tasks}', {
              level: selectedResource?.level,
              tasks: levelBlockedTasks.map((task) => `${task.wbs_code} — ${task.name} (mín. ${task.min_level})`).join('; '),
            })}
          </p>
        )}

        <ErrorBanner message={error} />

        {readOnly ? (
          <div className="flex items-center justify-end gap-2 pt-1">
            <Button type="button" variant="secondary" onClick={onClose}>
              {t('Fechar')}
            </Button>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-2 pt-1">
            <div>
              {isEdit && !confirmingDelete && (
                <Button type="button" variant="ghost" style={{ color: 'var(--status-critical)' }} onClick={() => setConfirmingDelete(true)}>
                  {t('Excluir')}
                </Button>
              )}
              {isEdit && confirmingDelete && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-[var(--text-secondary)]">{t('Confirmar exclusão?')}</span>
                  <Button type="button" variant="danger" disabled={deleting} onClick={handleDelete}>
                    {deleting ? t('Excluindo…') : t('Confirmar')}
                  </Button>
                  <Button type="button" variant="secondary" onClick={() => setConfirmingDelete(false)}>
                    {t('Cancelar')}
                  </Button>
                </div>
              )}
            </div>
            {!confirmingDelete && (
              <div className="flex gap-2">
                <Button type="button" variant="secondary" onClick={onClose}>
                  {t('Cancelar')}
                </Button>
                <Button type="submit" disabled={saving || Boolean(absenceWarning) || levelBlockedTasks.length > 0}>
                  {saving ? t('Salvando…') : t('Salvar')}
                </Button>
              </div>
            )}
          </div>
        )}
      </form>
    </Modal>
  )
}
