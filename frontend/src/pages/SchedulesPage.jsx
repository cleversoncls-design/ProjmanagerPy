import { useEffect, useMemo, useState } from 'react'
import * as schedulesApi from '../api/schedules'
import * as resourcesApi from '../api/resources'
import * as usersApi from '../api/users'
import * as clientsApi from '../api/clients'
import * as projectsApi from '../api/projects'
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
import { ChevronLeftIcon, ChevronRightIcon, PencilIcon, PlusIcon } from '../components/icons'
import { formatTime } from '../utils/format'
import { MANAGEMENT_ROLES } from '../utils/labels'
import { DEFAULT_PROJECT_COLOR, contrastTextColor } from '../utils/colorPalette'

const EMPTY_FILTERS = { resource_id: '', client_id: '', project_id: '', start: '', end: '' }

function toIsoDate(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
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

  const [viewDate, setViewDate] = useState(() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), 1)
  })
  const [filters, setFilters] = useState(EMPTY_FILTERS)

  const [resources, setResources] = useState([])
  const [users, setUsers] = useState([])
  const [clients, setClients] = useState([])
  const [projects, setProjects] = useState([])
  const [schedules, setSchedules] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [formTarget, setFormTarget] = useState(null) // { schedule } pra editar, ou { date } pra criar novo

  // Referência (recursos/usuários/clientes/projetos) carregada uma vez —
  // usada pros filtros e pra montar os rótulos/cores dos blocos da agenda.
  useEffect(() => {
    resourcesApi.listResources().then(setResources).catch(() => {})
    usersApi.listUsers().then(setUsers).catch(() => {})
    clientsApi.listClients().then(setClients).catch(() => {})
    projectsApi.listProjects().then(setProjects).catch(() => {})
  }, [])

  const usersById = useMemo(() => Object.fromEntries(users.map((u) => [u.id, u])), [users])
  const resourceOptions = useMemo(
    () =>
      resources.map((resource) => ({
        ...resource,
        userName: usersById[resource.user_id]?.name || resource.role_title,
      })),
    [resources, usersById],
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

  const listMode = Boolean(filters.start && filters.end)
  const projectOptions = useMemo(
    () => (filters.client_id ? projects.filter((p) => p.client_id === filters.client_id) : projects),
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

  function loadSchedules() {
    setLoading(true)
    setError('')
    const range = listMode
      ? { start: filters.start, end: filters.end }
      : { start: toIsoDate(monthCells[0]), end: toIsoDate(monthCells[monthCells.length - 1]) }
    schedulesApi
      .listSchedules({
        resource_id: filters.resource_id || undefined,
        client_id: filters.client_id || undefined,
        project_id: filters.project_id || undefined,
        ...range,
      })
      .then(setSchedules)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadSchedules, [viewDate, filters.resource_id, filters.client_id, filters.project_id, filters.start, filters.end])

  const schedulesByDate = useMemo(() => {
    const map = {}
    for (const schedule of schedules) {
      ;(map[schedule.date] ||= []).push(schedule)
    }
    for (const list of Object.values(map)) {
      list.sort((a, b) => a.start_time.localeCompare(b.start_time))
    }
    return map
  }, [schedules])

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
      <PageHeader title={t('Agenda de consultores')} subtitle={t('Agendamento de recursos por projeto, dia e horário.')} />

      <Card className="mb-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
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
        {listMode && (
          <p className="mt-3 text-xs text-[var(--text-muted)]">
            {t('Mostrando o período filtrado (Data inicial/final) em vez do calendário mensal. Limpe as datas para voltar ao mês.')}
          </p>
        )}
      </Card>

      <ErrorBanner message={error} />

      {!listMode && (
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
      )}

      {loading && <Spinner />}

      {!loading && !listMode && (
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
              return (
                <div
                  key={iso}
                  className={`min-h-[92px] rounded-lg border p-1.5 ${inMonth ? 'border-[var(--border)]' : 'border-transparent opacity-40'}`}
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span
                      className={`text-xs font-medium ${isToday ? 'flex h-5 w-5 items-center justify-center rounded-full bg-[var(--series-1)] text-white' : 'text-[var(--text-secondary)]'}`}
                    >
                      {cellDate.getDate()}
                    </span>
                    {canManage && (
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
                  <div className="space-y-0.5">
                    {daySchedules.slice(0, 3).map((schedule) => {
                      const color = projectsById[schedule.project_id]?.color || DEFAULT_PROJECT_COLOR
                      return (
                        <button
                          key={schedule.id}
                          type="button"
                          title={scheduleLabel(schedule)}
                          onClick={() => setFormTarget({ schedule })}
                          className="block w-full truncate rounded px-1 py-0.5 text-left text-[10.5px] font-medium"
                          style={{ backgroundColor: color, color: contrastTextColor(color) }}
                        >
                          {formatTime(schedule.start_time)} {resourcesById[schedule.resource_id]?.userName || '—'}
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

      {!loading && listMode && (
        <Card>
          {schedules.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)]">{t('Nenhum agendamento no período filtrado.')}</p>
          ) : (
            <div className="space-y-1.5">
              {schedules.map((schedule) => {
                const color = projectsById[schedule.project_id]?.color || DEFAULT_PROJECT_COLOR
                return (
                  <div
                    key={schedule.id}
                    className="flex items-center justify-between gap-3 rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
                  >
                    <div className="flex items-center gap-2.5">
                      <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />
                      <span className="font-medium text-[var(--text-primary)]">{schedule.date}</span>
                      <span className="text-[var(--text-secondary)]">{scheduleLabel(schedule)}</span>
                    </div>
                    {canManage && (
                      <IconButton icon={PencilIcon} label={t('Editar')} onClick={() => setFormTarget({ schedule })} />
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </Card>
      )}

      {formTarget && (
        <ScheduleFormModal
          schedule={formTarget.schedule}
          defaultDate={formTarget.date}
          resourceOptions={resourceOptions}
          projects={projects}
          onClose={() => setFormTarget(null)}
          onSaved={() => {
            setFormTarget(null)
            loadSchedules()
          }}
        />
      )}
    </div>
  )
}

/** Cria ou edita um bloco de agenda. A cor não é escolhida aqui — segue
 * automaticamente `project.color` (decisão do usuário: "Fixa por
 * projeto") — por isso não existe nenhum ColorSwatchPicker neste form. */
function ScheduleFormModal({ schedule, defaultDate, resourceOptions, projects, onClose, onSaved }) {
  const { t } = useLanguage()
  const isEdit = Boolean(schedule)
  const [form, setForm] = useState({
    resource_id: schedule?.resource_id || '',
    project_id: schedule?.project_id || '',
    date: schedule?.date || defaultDate || '',
    start_time: schedule?.start_time?.slice(0, 5) || '',
    end_time: schedule?.end_time?.slice(0, 5) || '',
    description: schedule?.description || '',
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  function updateField(field) {
    return (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
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
          <Select required disabled={isEdit} value={form.resource_id} onChange={updateField('resource_id')}>
            <option value="">{t('Selecione…')}</option>
            {resourceOptions.map((resource) => (
              <option key={resource.id} value={resource.id}>
                {resource.userName}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label={t('Projeto')} required>
          <Select required value={form.project_id} onChange={updateField('project_id')}>
            <option value="">{t('Selecione…')}</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.code} — {project.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label={t('Data')} required>
          <TextInput type="date" required value={form.date} onChange={updateField('date')} />
        </FormField>
        <div className="grid grid-cols-2 gap-4">
          <FormField label={t('Hora início')} required>
            <TextInput type="time" required value={form.start_time} onChange={updateField('start_time')} />
          </FormField>
          <FormField label={t('Hora fim')} required>
            <TextInput type="time" required value={form.end_time} onChange={updateField('end_time')} />
          </FormField>
        </div>
        <FormField label={t('Descrição')}>
          <TextArea rows={2} value={form.description} onChange={updateField('description')} />
        </FormField>

        <ErrorBanner message={error} />

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
              <Button type="submit" disabled={saving}>
                {saving ? t('Salvando…') : t('Salvar')}
              </Button>
            </div>
          )}
        </div>
      </form>
    </Modal>
  )
}
