import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import * as projectsApi from '../api/projects'
import * as reportsApi from '../api/reports'
import * as tasksApi from '../api/tasks'
import * as baselinesApi from '../api/baselines'
import * as clientsApi from '../api/clients'
import * as usersApi from '../api/users'
import * as resourcesApi from '../api/resources'
import * as calendarsApi from '../api/calendars'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import StatTile from '../components/StatTile'
import Table from '../components/Table'
import Button from '../components/Button'
import IconButton from '../components/IconButton'
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import StatusPill from '../components/StatusPill'
import StatusDot from '../components/StatusDot'
import CategoryBars from '../components/CategoryBars'
import { FormField, TextInput, Select, TextArea } from '../components/FormField'
import { ColumnsIcon, DownloadIcon, FlagIcon, HashIcon, MoveIcon, PencilIcon, PlusIcon, RefreshIcon, TrashIcon } from '../components/icons'
import { formatCurrency, formatDate, formatIndex, formatNumber, formatPercent, parseApiDate } from '../utils/format'
import {
  APPROVAL_STATUS_TONE,
  MANAGEMENT_ROLES,
  PROJECT_STATUS_TONE,
  TASK_STATUS_COLORS,
  TASK_STATUS_TONE,
  TASK_TYPE_COLORS,
} from '../utils/labels'

const TABS = [
  { key: 'overview', label: 'Visão geral' },
  { key: 'tasks', label: 'Tarefas' },
  { key: 'gantt', label: 'Gantt' },
]

export default function ProjectDetailPage() {
  const { projectId } = useParams()
  const { user } = useAuth()
  const { labels } = useLanguage()
  const canWrite = MANAGEMENT_ROLES.includes(user.role)

  const [project, setProject] = useState(null)
  const [client, setClient] = useState(null)
  const [report, setReport] = useState(null)
  const [evm, setEvm] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('overview')
  const [showEditModal, setShowEditModal] = useState(false)
  const [showStatsModal, setShowStatsModal] = useState(false)

  function loadProject() {
    setLoading(true)
    setError('')
    Promise.all([projectsApi.getProject(projectId), reportsApi.getProjectReport(projectId), reportsApi.getEvm(projectId).catch(() => null)])
      .then(([projectResult, reportResult, evmResult]) => {
        setProject(projectResult)
        setReport(reportResult)
        setEvm(evmResult)
        return clientsApi.getClient(projectResult.client_id).catch(() => null)
      })
      .then((clientResult) => setClient(clientResult))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadProject, [projectId])

  if (loading) return <Spinner />
  if (error) return <ErrorBanner message={error} />
  if (!project) return null

  return (
    <div>
      <PageHeader
        title={`${project.code} — ${project.name}`}
        subtitle={client ? client.legal_name : undefined}
        action={
          <div className="flex items-center gap-2">
            <StatusPill label={labels.PROJECT_STATUS_LABELS[project.status] || project.status} tone={PROJECT_STATUS_TONE[project.status]} />
            <Button variant="secondary" onClick={() => setShowStatsModal(true)}>
              Estatísticas
            </Button>
            {canWrite && (
              <Button variant="secondary" onClick={() => setShowEditModal(true)}>
                Editar projeto
              </Button>
            )}
          </div>
        }
      />

      <div className="mb-6 flex gap-1 border-b border-[var(--border)]">
        {TABS.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setTab(item.key)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              tab === item.key
                ? 'border-[var(--series-1)] text-[var(--series-1)]'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && <OverviewTab project={project} report={report} evm={evm} />}
      {tab === 'tasks' && <TasksTab projectId={projectId} canWrite={canWrite} onTaskCreated={loadProject} />}
      {tab === 'gantt' && <GanttTab projectId={projectId} project={project} />}

      {showEditModal && (
        <ProjectEditModal
          project={project}
          onClose={() => setShowEditModal(false)}
          onSaved={() => {
            setShowEditModal(false)
            loadProject()
          }}
        />
      )}

      {showStatsModal && (
        <ProjectStatisticsModal projectId={projectId} projectLabel={`${project.code} — ${project.name}`} onClose={() => setShowStatsModal(false)} />
      )}
    </div>
  )
}

function OverviewTab({ project, report, evm }) {
  const { labels } = useLanguage()
  const financials = report.financials
  const byType = report.financials_by_task_type

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label="Progresso" value={formatPercent(report.percent_complete)} />
        <StatTile label="Tarefas" value={report.tasks_total} />
        <StatTile label="Tarefas restantes" value={report.tasks_remaining} />
        <StatTile label="Início — fim planejado" value={`${formatDate(project.start_date)} – ${formatDate(project.end_date)}`} />
      </div>

      {evm && (
        <Card
          title="Desempenho do cronograma (Earned Value, em horas)"
          action={<span className="text-xs text-[var(--text-muted)]">Data de status: {formatDate(evm.status_date)}</span>}
        >
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatTile label="SPI" value={formatIndex(evm.spi)} tone={evm.spi !== null && Number(evm.spi) < 1 ? 'warning' : 'default'} />
            <StatTile label="CPI" value={formatIndex(evm.cpi)} tone={evm.cpi !== null && Number(evm.cpi) < 1 ? 'warning' : 'default'} />
            <StatTile label="% previsto" value={formatPercent(evm.planned_percent_complete)} />
            <StatTile label="% realizado" value={formatPercent(evm.percent_complete)} />
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Tarefas por status">
          {report.tasks_total > 0 ? (
            <CategoryBars
              items={Object.entries(report.tasks_by_status).map(([key, value]) => ({
                key,
                value,
                label: labels.TASK_STATUS_LABELS[key] || key,
                color: TASK_STATUS_COLORS[key],
              }))}
            />
          ) : (
            <p className="text-sm text-[var(--text-muted)]">Nenhuma tarefa cadastrada ainda.</p>
          )}
        </Card>

        <Card title="Financeiro">
          {financials ? (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <StatTile label="Valor vendido" value={formatCurrency(financials.sold_value)} />
                <StatTile label="Custo real" value={formatCurrency(financials.real_cost)} />
                <StatTile
                  label="Margem"
                  value={formatCurrency(financials.profit_margin)}
                  tone={Number(financials.profit_margin) < 0 ? 'critical' : 'default'}
                />
              </div>
              {byType && (
                <Table
                  columns={[
                    { key: 'type', header: 'Tipo' },
                    { key: 'hours', header: 'Horas', align: 'right' },
                    { key: 'cost', header: 'Custo', align: 'right' },
                  ]}
                  rows={Object.entries(byType).map(([key, value]) => ({
                    id: key,
                    type: labels.TASK_TYPE_LABELS[key] || key,
                    hours: formatNumber(value.hours),
                    cost: formatCurrency(value.cost),
                  }))}
                  getRowKey={(row) => row.id}
                />
              )}
            </div>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">Seu perfil não tem acesso a dados financeiros deste projeto.</p>
          )}
        </Card>
      </div>
    </div>
  )
}

function ProjectEditModal({ project, onClose, onSaved }) {
  const { labels } = useLanguage()
  const [form, setForm] = useState({
    name: project.name,
    manager_id: project.manager_id,
    status: project.status,
    calendar_id: project.calendar_id || '',
    status_date: project.status_date || '',
    start_date: project.start_date || '',
    end_date: project.end_date || '',
    management_hours: project.management_hours ?? '0',
    management_rate: project.management_rate ?? '0',
    consulting_hours: project.consulting_hours ?? '0',
    consulting_rate: project.consulting_rate ?? '0',
  })
  const [managers, setManagers] = useState([])
  const [calendars, setCalendars] = useState([])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    usersApi
      .listUsers({ role: 'INTERNAL_PM' })
      .then((internalPms) => usersApi.listUsers({ role: 'ADMIN' }).then((admins) => setManagers([...admins, ...internalPms])))
      .catch(() => {})
    calendarsApi.listCalendars().then(setCalendars).catch(() => {})
  }, [])

  function updateField(field) {
    return (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSaving(true)
    try {
      await projectsApi.updateProject(project.id, {
        name: form.name,
        manager_id: form.manager_id,
        status: form.status,
        calendar_id: form.calendar_id || null,
        status_date: form.status_date || null,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
        management_hours: form.management_hours,
        management_rate: form.management_rate,
        consulting_hours: form.consulting_hours,
        consulting_rate: form.consulting_rate,
      })
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Editar projeto" onClose={onClose} wide>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <FormField label="Nome" required>
            <TextInput required value={form.name} onChange={updateField('name')} />
          </FormField>
          <FormField label="Gerente responsável" required hint="Precisa ser ADMIN ou gerente de projetos interno.">
            <Select required value={form.manager_id} onChange={updateField('manager_id')}>
              {managers.map((manager) => (
                <option key={manager.id} value={manager.id}>
                  {manager.name}
                </option>
              ))}
            </Select>
          </FormField>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <FormField label="Status" required>
            <Select required value={form.status} onChange={updateField('status')}>
              {Object.entries(labels.PROJECT_STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label="Calendário do projeto" hint="Usado para calcular dias úteis nas datas planejadas.">
            <Select value={form.calendar_id} onChange={updateField('calendar_id')}>
              <option value="">Padrão (segunda a sexta, sem feriados)</option>
              {calendars.map((calendar) => (
                <option key={calendar.id} value={calendar.id}>
                  {calendar.name}
                </option>
              ))}
            </Select>
          </FormField>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <FormField label="Data de status" hint="Data-base para % previsto e status das tarefas.">
            <TextInput type="date" value={form.status_date} onChange={updateField('status_date')} />
          </FormField>
          <FormField label="Início planejado">
            <TextInput type="date" value={form.start_date} onChange={updateField('start_date')} />
          </FormField>
          <FormField label="Fim planejado">
            <TextInput type="date" value={form.end_date} onChange={updateField('end_date')} />
          </FormField>
        </div>

        <div className="rounded-lg border border-[var(--border)] p-4">
          <p className="mb-3 text-xs font-medium text-[var(--text-secondary)]">Pacote vendido (horas × valor/hora)</p>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <FormField label="Horas de gestão">
              <TextInput type="number" min="0" step="0.5" value={form.management_hours} onChange={updateField('management_hours')} />
            </FormField>
            <FormField label="Valor/h gestão">
              <TextInput type="number" min="0" step="0.01" value={form.management_rate} onChange={updateField('management_rate')} />
            </FormField>
            <FormField label="Horas de consultoria">
              <TextInput type="number" min="0" step="0.5" value={form.consulting_hours} onChange={updateField('consulting_hours')} />
            </FormField>
            <FormField label="Valor/h consultoria">
              <TextInput type="number" min="0" step="0.01" value={form.consulting_rate} onChange={updateField('consulting_rate')} />
            </FormField>
          </div>
        </div>

        <ErrorBanner message={error} />

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? 'Salvando…' : 'Salvar'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function StatisticsRow({ label, field, stats }) {
  function cell(range) {
    if (!range) return '—'
    if (field === 'start_date' || field === 'finish_date') return formatDate(range[field])
    if (field === 'duration_days') return `${formatNumber(range.duration_days)} d`
    if (field === 'work_hours') return `${formatNumber(range.work_hours)} h`
    if (field === 'cost') return range.cost === null || range.cost === undefined ? '—' : formatCurrency(range.cost)
    return '—'
  }
  return (
    <tr className="border-b border-[var(--border)] last:border-0">
      <td className="px-3 py-2 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{label}</td>
      <td className="px-3 py-2 text-right tabular">{cell(stats.current)}</td>
      <td className="px-3 py-2 text-right tabular">{cell(stats.baseline)}</td>
      <td className="px-3 py-2 text-right tabular">{cell(stats.actual)}</td>
    </tr>
  )
}

function ProjectStatisticsModal({ projectId, projectLabel, onClose }) {
  const [stats, setStats] = useState(null)
  const [baselines, setBaselines] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [showBaselineForm, setShowBaselineForm] = useState(false)
  const [versionName, setVersionName] = useState('')
  const [savingBaseline, setSavingBaseline] = useState(false)
  const [baselineError, setBaselineError] = useState('')

  // Estatísticas e linhas de base são recarregadas juntas: salvar uma
  // linha de base nova muda imediatamente a coluna "Linha de base" das
  // estatísticas (project_statistics usa sempre a mais recente — ver
  // services._latest_baseline_task_map), então as duas telas precisam
  // ficar sincronizadas.
  function reload() {
    return Promise.all([reportsApi.getStatistics(projectId), baselinesApi.listBaselines(projectId)]).then(
      ([statsResult, baselinesResult]) => {
        setStats(statsResult)
        setBaselines(baselinesResult)
      },
    )
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    reload()
      .catch((err) => active && setError(err.message))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [projectId])

  async function handleSaveBaseline(event) {
    event.preventDefault()
    const name = versionName.trim()
    if (!name) return
    setSavingBaseline(true)
    setBaselineError('')
    try {
      await baselinesApi.createBaseline(projectId, name)
      await reload()
      setVersionName('')
      setShowBaselineForm(false)
    } catch (err) {
      setBaselineError(err.message)
    } finally {
      setSavingBaseline(false)
    }
  }

  const latestBaseline = baselines[baselines.length - 1]

  return (
    <Modal title={`Estatísticas do projeto — ${projectLabel}`} onClose={onClose} wide>
      {loading && <Spinner />}
      <ErrorBanner message={error} />
      {stats && (
        <div className="space-y-4">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]"></th>
                  <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">Atual</th>
                  <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">Linha de base</th>
                  <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">Real</th>
                </tr>
              </thead>
              <tbody>
                <StatisticsRow label="Início" field="start_date" stats={stats} />
                <StatisticsRow label="Término" field="finish_date" stats={stats} />
                <StatisticsRow label="Duração" field="duration_days" stats={stats} />
                <StatisticsRow label="Trabalho" field="work_hours" stats={stats} />
                <StatisticsRow label="Custo" field="cost" stats={stats} />
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between gap-3 rounded-lg border border-[var(--border)] px-3 py-2">
            <p className="text-xs text-[var(--text-muted)]">
              {latestBaseline ? (
                <>
                  Linha de base atual: <span className="font-medium text-[var(--text-primary)]">{latestBaseline.version_name}</span> (salva em{' '}
                  {formatDate(latestBaseline.created_at)})
                </>
              ) : (
                'Nenhuma linha de base salva ainda para este projeto.'
              )}
            </p>
            {!showBaselineForm && (
              <Button type="button" variant="secondary" onClick={() => setShowBaselineForm(true)}>
                Salvar linha de base
              </Button>
            )}
          </div>

          {showBaselineForm && (
            <form onSubmit={handleSaveBaseline} className="flex items-end gap-2 rounded-lg border border-[var(--border)] p-3">
              <div className="flex-1">
                <FormField label="Nome da versão" hint="Ex.: Baseline inicial, Revisão de escopo #2.">
                  <TextInput
                    value={versionName}
                    onChange={(event) => setVersionName(event.target.value)}
                    placeholder="Ex.: Baseline inicial"
                    autoFocus
                  />
                </FormField>
              </div>
              <Button type="submit" disabled={savingBaseline || !versionName.trim()}>
                {savingBaseline ? 'Salvando…' : 'Salvar'}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setShowBaselineForm(false)
                  setVersionName('')
                  setBaselineError('')
                }}
              >
                Cancelar
              </Button>
            </form>
          )}
          <ErrorBanner message={baselineError} />

          <div className="grid grid-cols-3 gap-4">
            <StatTile
              label="Variância de término"
              value={
                stats.variance_finish_days === null || stats.variance_finish_days === undefined
                  ? '—'
                  : `${Number(stats.variance_finish_days) > 0 ? '+' : ''}${formatNumber(stats.variance_finish_days)} d`
              }
            />
            <StatTile label="% concluído (Duração)" value={formatPercent(stats.percent_complete_duration)} />
            <StatTile label="% concluído (Trabalho)" value={formatPercent(stats.percent_complete_work)} />
          </div>
        </div>
      )}
    </Modal>
  )
}

/** Modal "Salvar linha de base" — grava um snapshot das datas/horas
 * planejadas ATUAIS de todas as tarefas do projeto (POST /projects/{id}/
 * baselines; ver app/routers/baselines.py) para comparação futura (colunas
 * "Linha base" da grade de Tarefas, variância de término nas Estatísticas).
 * Fica disponível direto na tela de Tarefas — onde o usuário está olhando o
 * cronograma — em vez de escondida só dentro do modal de Estatísticas. */
function BaselineModal({ projectId, onClose, onSaved }) {
  const [versionName, setVersionName] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(event) {
    event.preventDefault()
    const name = versionName.trim()
    if (!name) return
    setSaving(true)
    setError('')
    try {
      await baselinesApi.createBaseline(projectId, name)
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Salvar linha de base" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          Grava a Duração, o Trabalho e as datas planejadas de hoje de todas as tarefas como a nova linha de base do
          projeto — usada para comparar com o realizado depois (colunas "Linha base" na grade e variância de término
          nas Estatísticas).
        </p>
        <FormField label="Nome da versão" required hint='Ex.: "Baseline inicial", "Revisão de escopo #2".'>
          <TextInput value={versionName} onChange={(event) => setVersionName(event.target.value)} placeholder="Ex.: Baseline inicial" autoFocus />
        </FormField>
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={saving || !versionName.trim()}>
            {saving ? 'Salvando…' : 'Salvar linha de base'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

/** Achata a árvore de tarefas (parent_task_id) em ordem de exibição —
 * mesma regra de desempate de services.recalculate_wbs (sort_order, com
 * wbs_code como critério estável), pra grade e os seletores de
 * pai/predecessora ficarem na mesma ordem que o WBS depois de recalculado. */
function buildOrderedTasks(tasks) {
  const byParent = new Map()
  for (const t of tasks) {
    const key = t.parent_task_id || 'root'
    if (!byParent.has(key)) byParent.set(key, [])
    byParent.get(key).push(t)
  }
  for (const list of byParent.values()) {
    list.sort((a, b) => Number(a.sort_order) - Number(b.sort_order) || a.wbs_code.localeCompare(b.wbs_code, undefined, { numeric: true }))
  }
  const ordered = []
  function visit(key, depth) {
    for (const t of byParent.get(key) || []) {
      ordered.push({ ...t, depth })
      visit(t.id, depth + 1)
    }
  }
  visit('root', 0)
  return ordered
}

// Colunas "do meio" da grade de Tarefas (entre o nome da tarefa e as ações
// da linha) que o usuário pode reordenar/esconder — da mesma forma que o
// pedido descreveu: "de duração até aprovação do cliente". WBS/nome (fixas
// no início) e a coluna de ações (fixa no fim) não entram aqui.
const TASK_COLUMN_LABELS = {
  duration_days: 'Duração',
  estimated_hours: 'Trabalho',
  planned_start_date: 'Início',
  planned_end_date: 'Fim',
  resources: 'Recursos',
  predecessors: 'Predecessora(s)',
  progress_percentage: '% realizado',
  planned_percent_complete: '% previsto',
  spi: 'SPI',
  cpi: 'CPI',
  baseline: 'Linha base (início)',
  status: 'Status',
  client_approval_status: 'Aprovação do cliente',
}
const DEFAULT_TASK_COLUMN_ORDER = Object.keys(TASK_COLUMN_LABELS)
const TASK_COLUMN_PREFS_KEY = 'pmpy_task_columns_v1'

/** Preferência de colunas é só visual e por navegador (não há conceito de
 * "layout da tela" no backend, e não precisaria — é o gerente de projeto
 * ajustando a PRÓPRIA tela) — localStorage, com fallback silencioso pro
 * padrão se o navegador bloquear/limpar o storage. */
function loadTaskColumnPrefs() {
  try {
    const raw = localStorage.getItem(TASK_COLUMN_PREFS_KEY)
    if (!raw) return { order: DEFAULT_TASK_COLUMN_ORDER, hidden: [] }
    const parsed = JSON.parse(raw)
    const savedOrder = Array.isArray(parsed.order) ? parsed.order.filter((k) => TASK_COLUMN_LABELS[k]) : []
    // Colunas novas (adicionadas depois que o usuário salvou a preferência)
    // entram no fim, em vez de sumirem da tela sem explicação.
    const order = [...savedOrder, ...DEFAULT_TASK_COLUMN_ORDER.filter((k) => !savedOrder.includes(k))]
    const hidden = Array.isArray(parsed.hidden) ? parsed.hidden.filter((k) => TASK_COLUMN_LABELS[k]) : []
    return { order, hidden }
  } catch {
    return { order: DEFAULT_TASK_COLUMN_ORDER, hidden: [] }
  }
}

function saveTaskColumnPrefs(prefs) {
  try {
    localStorage.setItem(TASK_COLUMN_PREFS_KEY, JSON.stringify(prefs))
  } catch {
    // Storage bloqueado/cheio: a preferência só não sobrevive a um reload,
    // não impede o uso da tela.
  }
}

/** Modal "Colunas" — reordena (subir/descer) e mostra/esconde as colunas
 * do meio da grade de Tarefas, pra cada gerente de projeto montar a visão
 * que importa pro que está fazendo, sem depender de scroll horizontal pra
 * achar a coluna certa. */
function ColumnsModal({ order, hidden, onClose, onSave }) {
  const [draftOrder, setDraftOrder] = useState(order)
  const [draftHidden, setDraftHidden] = useState(new Set(hidden))

  function move(index, delta) {
    const target = index + delta
    if (target < 0 || target >= draftOrder.length) return
    const next = [...draftOrder]
    ;[next[index], next[target]] = [next[target], next[index]]
    setDraftOrder(next)
  }

  function toggle(key) {
    setDraftHidden((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  return (
    <Modal title="Colunas da grade de tarefas" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          Escolha quais colunas aparecem e em que ordem — WBS, nome da tarefa e as ações da linha ficam sempre
          fixas nas pontas.
        </p>
        <ul className="divide-y divide-[var(--border)] rounded-lg border border-[var(--border)]">
          {draftOrder.map((key, index) => (
            <li key={key} className="flex items-center gap-3 px-3 py-2">
              <label className="flex flex-1 items-center gap-2 text-sm text-[var(--text-primary)]">
                <input type="checkbox" checked={!draftHidden.has(key)} onChange={() => toggle(key)} />
                {TASK_COLUMN_LABELS[key]}
              </label>
              <div className="flex gap-1">
                <button
                  type="button"
                  disabled={index === 0}
                  onClick={() => move(index, -1)}
                  className="rounded px-1.5 py-0.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--page)] disabled:opacity-30"
                  title="Mover para cima"
                >
                  ↑
                </button>
                <button
                  type="button"
                  disabled={index === draftOrder.length - 1}
                  onClick={() => move(index, 1)}
                  className="rounded px-1.5 py-0.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--page)] disabled:opacity-30"
                  title="Mover para baixo"
                >
                  ↓
                </button>
              </div>
            </li>
          ))}
        </ul>
        <div className="flex justify-between gap-2 pt-1">
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setDraftOrder(DEFAULT_TASK_COLUMN_ORDER)
              setDraftHidden(new Set())
            }}
          >
            Restaurar padrão
          </Button>
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="button" onClick={() => onSave({ order: draftOrder, hidden: [...draftHidden] })}>
              Salvar
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  )
}

/** Modal de confirmação pra apagar uma tarefa — a API recusa (409) quando
 * ela tem filhas na EAP ou já tem apontamento de horas lançado (ver
 * DELETE /tasks/{id}); a mensagem de erro do backend já explica qual dos
 * dois casos é, então basta repassá-la. */
function DeleteTaskModal({ task, onClose, onDeleted }) {
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')

  async function handleDelete() {
    setDeleting(true)
    setError('')
    try {
      await tasksApi.deleteTask(task.id)
      onDeleted()
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Modal title="Apagar tarefa" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          Tem certeza que quer apagar <span className="font-medium text-[var(--text-primary)]">{task.wbs_code} {task.name}</span>?
          Essa ação não pode ser desfeita.
        </p>
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="button" variant="danger" disabled={deleting} onClick={handleDelete}>
            {deleting ? 'Apagando…' : 'Apagar'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

function TasksTab({ projectId, canWrite, onTaskCreated }) {
  const { labels } = useLanguage()
  const [schedule, setSchedule] = useState(null)
  const [resources, setResources] = useState([])
  const [users, setUsers] = useState([])
  const [assignmentsByTask, setAssignmentsByTask] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyMessage, setBusyMessage] = useState('')
  const [statusDateInput, setStatusDateInput] = useState('')

  const [showModal, setShowModal] = useState(false)
  const [editingTask, setEditingTask] = useState(null)
  const [movingTask, setMovingTask] = useState(null)
  const [deletingTask, setDeletingTask] = useState(null)
  const [showBaselineModal, setShowBaselineModal] = useState(false)
  const [showColumnsModal, setShowColumnsModal] = useState(false)
  const [columnPrefs, setColumnPrefs] = useState(loadTaskColumnPrefs)

  function loadSchedule() {
    setLoading(true)
    setError('')
    // GET /resources e GET /users são restritos a perfis internos (ver
    // require_roles em app/routers/resources.py e users.py) — perfis
    // externos (CLIENT_PM/CLIENT_USER) recebem 403 aqui, então a coluna de
    // recursos degrada para mostrar só o id em vez de quebrar a aba inteira.
    Promise.all([
      reportsApi.getSchedule(projectId),
      resourcesApi.listResources().catch(() => []),
      usersApi.listUsers().catch(() => []),
    ])
      .then(([scheduleResult, resourcesResult, usersResult]) => {
        setSchedule(scheduleResult)
        setStatusDateInput(scheduleResult.status_date || '')
        setResources(resourcesResult)
        setUsers(usersResult)
        return Promise.all(
          scheduleResult.tasks.map((t) => tasksApi.listAssignments(t.id).then((list) => [t.id, list])),
        )
      })
      .then((pairs) => setAssignmentsByTask(Object.fromEntries(pairs)))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadSchedule, [projectId])

  const orderedTasks = useMemo(() => (schedule ? buildOrderedTasks(schedule.tasks) : []), [schedule])
  const taskById = useMemo(() => Object.fromEntries((schedule?.tasks || []).map((t) => [t.id, t])), [schedule])
  const userById = useMemo(() => Object.fromEntries(users.map((u) => [u.id, u])), [users])
  const resourceById = useMemo(() => Object.fromEntries(resources.map((r) => [r.id, r])), [resources])
  const predecessorsBySuccessor = useMemo(() => {
    const map = new Map()
    for (const dep of schedule?.dependencies || []) {
      if (!map.has(dep.successor_task_id)) map.set(dep.successor_task_id, [])
      map.get(dep.successor_task_id).push(dep)
    }
    return map
  }, [schedule])

  function resourceLabel(resourceId) {
    const resource = resourceById[resourceId]
    if (!resource) return '—'
    const owner = userById[resource.user_id]
    return owner ? owner.name : resource.role_title
  }

  async function withBusy(message, action) {
    setBusyMessage(message)
    setError('')
    try {
      await action()
      loadSchedule()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyMessage('')
    }
  }

  function handleApplyStatusDate(event) {
    event.preventDefault()
    withBusy('Atualizando data de status…', () => projectsApi.updateProject(projectId, { status_date: statusDateInput || null }))
  }

  async function handleExport() {
    setBusyMessage('Gerando planilha…')
    setError('')
    try {
      await reportsApi.downloadTasksXlsx(projectId, `${projectId}_tarefas.xlsx`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyMessage('')
    }
  }

  function handleBaselineSaved() {
    setShowBaselineModal(false)
    loadSchedule()
  }

  function handleTaskDeleted() {
    setDeletingTask(null)
    loadSchedule()
  }

  function handleSaveColumnPrefs(prefs) {
    setColumnPrefs(prefs)
    saveTaskColumnPrefs(prefs)
    setShowColumnsModal(false)
  }

  function closeModal() {
    setShowModal(false)
    setEditingTask(null)
    loadSchedule()
  }

  function handleSaved() {
    setShowModal(false)
    setEditingTask(null)
    loadSchedule()
    onTaskCreated?.()
  }

  // Definições das colunas "do meio" (customizáveis — ver ColumnsModal),
  // indexadas pela mesma chave usada em TASK_COLUMN_LABELS/columnPrefs.
  // Tarefa-pai (tem filhas) não tem Duração/Trabalho/Início/Fim próprios
  // úteis — o motor de agendamento só escreve nesses campos em
  // tarefas-folha. O backend manda o agregado das descendentes em
  // rollup_* (services._task_rollups); aqui é só preferir esse valor
  // quando ele vier preenchido, caindo pro campo cru da tarefa (folha) senão.
  const middleColumnDefs = {
    duration_days: {
      key: 'duration_days',
      header: 'Duração',
      align: 'right',
      render: (row) => `${formatNumber(row.rollup_duration_days ?? row.duration_days)} d`,
    },
    estimated_hours: {
      key: 'estimated_hours',
      header: 'Trabalho',
      align: 'right',
      render: (row) => `${formatNumber(row.rollup_estimated_hours ?? row.estimated_hours)} h`,
    },
    planned_start_date: {
      key: 'planned_start_date',
      header: 'Início',
      render: (row) => formatDate(row.rollup_start_date ?? row.planned_start_date),
    },
    planned_end_date: {
      key: 'planned_end_date',
      header: 'Fim',
      render: (row) => formatDate(row.rollup_end_date ?? row.planned_end_date),
    },
    resources: {
      key: 'resources',
      header: 'Recursos',
      render: (row) => {
        const assignments = assignmentsByTask[row.id] || []
        if (assignments.length === 0) return <span className="text-[var(--text-muted)]">—</span>
        return assignments.map((a) => resourceLabel(a.resource_id)).join(', ')
      },
    },
    predecessors: {
      key: 'predecessors',
      header: 'Predecessora(s)',
      render: (row) => {
        const deps = predecessorsBySuccessor.get(row.id) || []
        if (deps.length === 0) return <span className="text-[var(--text-muted)]">Nenhuma</span>
        return deps
          .map((dep) => {
            const pred = taskById[dep.predecessor_task_id]
            const lag = dep.lag_days ? ` ${dep.lag_days > 0 ? '+' : ''}${dep.lag_days}d` : ''
            return `${pred ? pred.wbs_code : '?'} (${labels.DEPENDENCY_TYPE_SHORT[dep.dependency_type] || dep.dependency_type}${lag})`
          })
          .join(', ')
      },
    },
    progress_percentage: {
      key: 'progress_percentage',
      header: '% realizado',
      align: 'right',
      render: (row) => formatPercent(row.progress_percentage),
    },
    planned_percent_complete: {
      key: 'planned_percent_complete',
      header: '% previsto',
      align: 'right',
      render: (row) => formatPercent(row.planned_percent_complete),
    },
    spi: { key: 'spi', header: 'SPI', align: 'right', render: (row) => formatIndex(row.spi) },
    cpi: { key: 'cpi', header: 'CPI', align: 'right', render: (row) => formatIndex(row.cpi) },
    baseline: {
      key: 'baseline',
      header: 'Linha base (início)',
      // Só a data de início importa aqui (o que o usuário quer comparar é
      // "começou quando devia?") — fim e trabalho da linha base continuam
      // disponíveis no título/tooltip pra quem precisar, sem poluir a
      // coluna com um intervalo inteiro.
      render: (row) =>
        row.baseline_start_date ? (
          <span
            title={`Fim na linha base: ${formatDate(row.baseline_end_date)} · Trabalho na linha base: ${row.baseline_estimated_hours ? `${formatNumber(row.baseline_estimated_hours)}h` : '—'}`}
          >
            {formatDate(row.baseline_start_date)}
          </span>
        ) : (
          <span className="text-[var(--text-muted)]">—</span>
        ),
    },
    status: {
      key: 'status',
      header: 'Status',
      render: (row) => <StatusPill label={labels.TASK_STATUS_LABELS[row.status] || row.status} tone={TASK_STATUS_TONE[row.status]} />,
    },
    client_approval_status: {
      key: 'client_approval_status',
      header: 'Aprovação do cliente',
      render: (row) => <StatusPill label={labels.APPROVAL_STATUS_LABELS[row.client_approval_status]} tone={APPROVAL_STATUS_TONE[row.client_approval_status]} />,
    },
  }

  const columns = [
    { key: 'status_dot', header: '', render: (row) => <StatusDot color={row.status_dot} /> },
    { key: 'wbs_code', header: 'WBS' },
    {
      key: 'name',
      header: 'Nome da tarefa',
      nowrap: true,
      render: (row) => (
        <span style={{ paddingLeft: row.depth * 18 }} className="flex items-center gap-1.5">
          {row.is_milestone && <span className="inline-block h-2 w-2 shrink-0 rotate-45" style={{ backgroundColor: 'var(--text-muted)' }} />}
          {row.name}
        </span>
      ),
    },
    ...columnPrefs.order.filter((key) => !columnPrefs.hidden.includes(key)).map((key) => middleColumnDefs[key]),
  ]

  if (canWrite) {
    columns.push({
      key: 'actions',
      header: '',
      align: 'right',
      render: (row) => (
        <div className="flex justify-end gap-1.5">
          <IconButton
            icon={PencilIcon}
            label="Editar tarefa"
            onClick={() => {
              setEditingTask(row)
              setShowModal(true)
            }}
          />
          <IconButton icon={MoveIcon} label="Mover tarefa" onClick={() => setMovingTask(row)} />
          <IconButton icon={TrashIcon} label="Apagar tarefa" variant="danger" onClick={() => setDeletingTask(row)} />
        </div>
      ),
    })
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <form onSubmit={handleApplyStatusDate} className="flex items-end gap-2">
          <FormField label="Data de status" hint="Data-base para % previsto e status das tarefas.">
            <TextInput type="date" value={statusDateInput} onChange={(event) => setStatusDateInput(event.target.value)} disabled={!canWrite} />
          </FormField>
          {canWrite && (
            <Button type="submit" variant="secondary" disabled={Boolean(busyMessage)}>
              Aplicar
            </Button>
          )}
        </form>
        <div className="flex flex-wrap gap-1.5">
          <IconButton icon={ColumnsIcon} label="Colunas" onClick={() => setShowColumnsModal(true)} />
          {/* Exportar não depende de canWrite: é leitura, então também fica
              disponível para perfis externos (CLIENT_PM/CLIENT_USER). */}
          <IconButton icon={DownloadIcon} label="Exportar (Excel)" disabled={Boolean(busyMessage)} onClick={handleExport} />
          {canWrite && (
            <>
              <IconButton icon={FlagIcon} label="Salvar linha de base" disabled={Boolean(busyMessage)} onClick={() => setShowBaselineModal(true)} />
              <IconButton
                icon={HashIcon}
                label="Recalcular WBS/EAP"
                disabled={Boolean(busyMessage)}
                onClick={() => withBusy('Recalculando WBS/EAP…', () => tasksApi.recalculateWbs(projectId))}
              />
              <IconButton
                icon={RefreshIcon}
                label="Recalcular tudo"
                disabled={Boolean(busyMessage)}
                onClick={() => withBusy('Recalculando datas do projeto…', () => tasksApi.rescheduleProject(projectId))}
              />
              <IconButton
                icon={PlusIcon}
                label="Nova tarefa"
                variant="primary"
                onClick={() => {
                  setEditingTask(null)
                  setShowModal(true)
                }}
              />
            </>
          )}
        </div>
      </div>

      {busyMessage && <p className="mb-3 text-xs text-[var(--text-muted)]">{busyMessage}</p>}
      {loading && <Spinner />}
      <ErrorBanner message={error} />

      {!loading && !error && (
        <Card dense>
          <Table columns={columns} rows={orderedTasks} getRowKey={(row) => row.id} emptyMessage="Nenhuma tarefa cadastrada ainda." dense />
        </Card>
      )}

      {showBaselineModal && <BaselineModal projectId={projectId} onClose={() => setShowBaselineModal(false)} onSaved={handleBaselineSaved} />}

      {showColumnsModal && (
        <ColumnsModal
          order={columnPrefs.order}
          hidden={columnPrefs.hidden}
          onClose={() => setShowColumnsModal(false)}
          onSave={handleSaveColumnPrefs}
        />
      )}

      {deletingTask && (
        <DeleteTaskModal task={deletingTask} onClose={() => setDeletingTask(null)} onDeleted={handleTaskDeleted} />
      )}

      {showModal && (
        <TaskFormModal
          projectId={projectId}
          task={editingTask}
          allTasks={orderedTasks}
          resources={resources}
          resourceLabel={resourceLabel}
          initialDependencies={editingTask ? predecessorsBySuccessor.get(editingTask.id) || [] : []}
          initialAssignments={editingTask ? assignmentsByTask[editingTask.id] || [] : []}
          onClose={closeModal}
          onSaved={handleSaved}
        />
      )}

      {movingTask && (
        <MoveTaskModal
          task={movingTask}
          allTasks={orderedTasks}
          onClose={() => setMovingTask(null)}
          onSaved={() => {
            setMovingTask(null)
            loadSchedule()
          }}
        />
      )}
    </div>
  )
}

const EMPTY_TASK_FORM = {
  name: '',
  wbs_code: '',
  task_type: 'CONSULTING',
  parent_task_id: '',
  duration_days: '',
  estimated_hours: '',
  planned_start_date: '',
  planned_end_date: '',
  progress_percentage: '0',
  status: 'NOT_STARTED',
  is_milestone: false,
  notes: '',
}

function TaskFormModal({ projectId, task, allTasks, resources, resourceLabel, initialDependencies, initialAssignments, onClose, onSaved }) {
  const { labels } = useLanguage()
  const isEdit = Boolean(task)
  const [form, setForm] = useState(() =>
    isEdit
      ? {
          name: task.name,
          wbs_code: task.wbs_code,
          task_type: task.task_type,
          parent_task_id: task.parent_task_id || '',
          duration_days: task.duration_days,
          estimated_hours: task.estimated_hours,
          planned_start_date: task.planned_start_date || '',
          planned_end_date: task.planned_end_date || '',
          progress_percentage: task.progress_percentage,
          status: task.status,
          is_milestone: task.is_milestone,
          notes: task.notes || '',
        }
      : EMPTY_TASK_FORM,
  )
  // Qual dos dois campos do par Duração/Trabalho o usuário editou por
  // último — decide o que vai no payload (ver services.apply_effort_driven:
  // informar um recalcula o outro; os dois nunca vão juntos).
  const [effortField, setEffortField] = useState(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const [dependencies, setDependencies] = useState(initialDependencies)
  const [assignments, setAssignments] = useState(initialAssignments)
  const [depForm, setDepForm] = useState({ predecessor_task_id: '', dependency_type: 'FS', lag_days: '0' })
  const [assignForm, setAssignForm] = useState({ resource_id: '', allocated_hours: '' })
  const [depError, setDepError] = useState('')
  const [assignError, setAssignError] = useState('')

  function updateField(field) {
    return (event) => {
      const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
      setForm((prev) => ({ ...prev, [field]: value }))
      if (field === 'duration_days') setEffortField('duration')
      if (field === 'estimated_hours') setEffortField('hours')
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSaving(true)
    try {
      if (isEdit) {
        const payload = {
          name: form.name,
          task_type: form.task_type,
          planned_start_date: form.planned_start_date || null,
          planned_end_date: form.planned_end_date || null,
          progress_percentage: form.progress_percentage,
          status: form.status,
          is_milestone: form.is_milestone,
          notes: form.notes || null,
        }
        if (effortField === 'duration') payload.duration_days = form.duration_days
        if (effortField === 'hours') payload.estimated_hours = form.estimated_hours
        await tasksApi.updateTask(task.id, payload)
      } else {
        const payload = {
          name: form.name,
          wbs_code: form.wbs_code,
          task_type: form.task_type,
          is_milestone: form.is_milestone,
        }
        if (form.notes) payload.notes = form.notes
        if (form.parent_task_id) payload.parent_task_id = form.parent_task_id
        if (form.planned_start_date) payload.planned_start_date = form.planned_start_date
        if (form.planned_end_date) payload.planned_end_date = form.planned_end_date
        if (effortField === 'duration' && form.duration_days) payload.duration_days = form.duration_days
        if (effortField === 'hours' && form.estimated_hours) payload.estimated_hours = form.estimated_hours
        await tasksApi.createTask(projectId, payload)
      }
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleAddDependency(event) {
    event.preventDefault()
    setDepError('')
    if (!depForm.predecessor_task_id) {
      setDepError('Selecione a tarefa predecessora.')
      return
    }
    try {
      const created = await tasksApi.createDependency({
        predecessor_task_id: depForm.predecessor_task_id,
        successor_task_id: task.id,
        dependency_type: depForm.dependency_type,
        lag_days: Number(depForm.lag_days) || 0,
      })
      setDependencies((prev) => [...prev, created])
      setDepForm({ predecessor_task_id: '', dependency_type: 'FS', lag_days: '0' })
    } catch (err) {
      setDepError(err.message)
    }
  }

  async function handleRemoveDependency(dependencyId) {
    setDepError('')
    try {
      await tasksApi.deleteDependency(dependencyId)
      setDependencies((prev) => prev.filter((dep) => dep.id !== dependencyId))
    } catch (err) {
      setDepError(err.message)
    }
  }

  async function handleAddAssignment(event) {
    event.preventDefault()
    setAssignError('')
    if (!assignForm.resource_id || !assignForm.allocated_hours) {
      setAssignError('Selecione o recurso e informe as horas alocadas.')
      return
    }
    try {
      const created = await tasksApi.assignResource(task.id, {
        resource_id: assignForm.resource_id,
        allocated_hours: assignForm.allocated_hours,
      })
      setAssignments((prev) => [...prev, created])
      setAssignForm({ resource_id: '', allocated_hours: '' })
    } catch (err) {
      setAssignError(err.message)
    }
  }

  async function handleRemoveAssignment(assignmentId) {
    setAssignError('')
    try {
      await tasksApi.removeAssignment(task.id, assignmentId)
      setAssignments((prev) => prev.filter((a) => a.id !== assignmentId))
    } catch (err) {
      setAssignError(err.message)
    }
  }

  const predecessorOptions = allTasks.filter((t) => t.id !== task?.id)
  const assignedResourceIds = new Set(assignments.map((a) => a.resource_id))
  const resourceOptions = resources.filter((r) => !assignedResourceIds.has(r.id))

  return (
    <Modal title={isEdit ? `Editar tarefa — ${task.wbs_code} ${task.name}` : 'Nova tarefa'} onClose={onClose} wide>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <FormField label="Código WBS" required hint={isEdit ? 'Use "Recalcular WBS/EAP" para renumerar.' : 'Ex.: "1.2"'}>
            <TextInput required disabled={isEdit} value={form.wbs_code} onChange={updateField('wbs_code')} />
          </FormField>
          <FormField label="Nome" required>
            <TextInput required value={form.name} onChange={updateField('name')} />
          </FormField>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <FormField label="Tipo" required>
            <Select required value={form.task_type} onChange={updateField('task_type')}>
              <option value="CONSULTING">Consultoria</option>
              <option value="MANAGEMENT">Gestão</option>
            </Select>
          </FormField>
          {!isEdit ? (
            <FormField label="Tarefa pai" hint="Deixe em branco para uma tarefa de topo (raiz).">
              <Select value={form.parent_task_id} onChange={updateField('parent_task_id')}>
                <option value="">Nenhuma (raiz)</option>
                {allTasks.map((t) => (
                  <option key={t.id} value={t.id}>
                    {'—'.repeat(t.depth)} {t.wbs_code} {t.name}
                  </option>
                ))}
              </Select>
            </FormField>
          ) : (
            <FormField label="Status">
              <Select value={form.status} onChange={updateField('status')}>
                {Object.entries(labels.TASK_STATUS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </FormField>
          )}
        </div>
        <div className="grid grid-cols-2 gap-4">
          <FormField label="Duração (dias)" hint="Editar recalcula o Trabalho.">
            {/* step="0.5" rejeitava qualquer valor com centavos que não caísse
                na grade min + n*0.5 (ex.: 2.00 ou 1.75) — o navegador acusava
                "valor inválido" mesmo sendo um número perfeitamente válido
                para o campo. step="0.01" aceita duas casas decimais, que é a
                precisão que Duração/Trabalho já usam no backend (Decimal). */}
            <TextInput type="number" min="0.01" step="0.01" value={form.duration_days} onChange={updateField('duration_days')} placeholder="Ex.: 2" />
          </FormField>
          <FormField label="Trabalho (horas)" hint="Editar recalcula a Duração.">
            <TextInput type="number" min="0" step="0.01" value={form.estimated_hours} onChange={updateField('estimated_hours')} placeholder="Ex.: 16" />
          </FormField>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <FormField label="Início planejado" hint="Sem predecessora, esta data fica manual.">
            <TextInput type="date" value={form.planned_start_date} onChange={updateField('planned_start_date')} />
          </FormField>
          <FormField label="Fim planejado">
            <TextInput type="date" value={form.planned_end_date} onChange={updateField('planned_end_date')} />
          </FormField>
        </div>
        {isEdit && (
          <FormField label="% Realizado">
            <TextInput type="number" min="0" max="100" step="1" value={form.progress_percentage} onChange={updateField('progress_percentage')} />
          </FormField>
        )}
        <FormField label="Observações">
          <TextArea rows={2} value={form.notes} onChange={updateField('notes')} />
        </FormField>
        <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <input type="checkbox" checked={form.is_milestone} onChange={updateField('is_milestone')} />
          É um marco (milestone)
        </label>

        <ErrorBanner message={error} />

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? 'Salvando…' : 'Salvar'}
          </Button>
        </div>
      </form>

      {isEdit && (
        <div className="mt-6 space-y-5 border-t border-[var(--border)] pt-5">
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Predecessoras</h3>
            {dependencies.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">Nenhuma — a data de início desta tarefa fica manual.</p>
            ) : (
              <ul className="space-y-1.5">
                {dependencies.map((dep) => {
                  const pred = allTasks.find((t) => t.id === dep.predecessor_task_id)
                  return (
                    <li key={dep.id} className="flex items-center justify-between rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm">
                      <span>
                        {pred ? `${pred.wbs_code} — ${pred.name}` : dep.predecessor_task_id} · {labels.DEPENDENCY_TYPE_LABELS[dep.dependency_type] || dep.dependency_type}
                        {dep.lag_days ? ` · ${dep.lag_days > 0 ? '+' : ''}${dep.lag_days}d` : ''}
                      </span>
                      <button type="button" onClick={() => handleRemoveDependency(dep.id)} className="text-xs text-[var(--status-critical)] hover:underline">
                        Remover
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
            <form onSubmit={handleAddDependency} className="mt-3 flex flex-wrap items-end gap-2">
              <FormField label="Nova predecessora">
                <Select value={depForm.predecessor_task_id} onChange={(event) => setDepForm((prev) => ({ ...prev, predecessor_task_id: event.target.value }))}>
                  <option value="">Selecione…</option>
                  {predecessorOptions.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.wbs_code} — {t.name}
                    </option>
                  ))}
                </Select>
              </FormField>
              <FormField label="Tipo">
                <Select value={depForm.dependency_type} onChange={(event) => setDepForm((prev) => ({ ...prev, dependency_type: event.target.value }))}>
                  {Object.entries(labels.DEPENDENCY_TYPE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </Select>
              </FormField>
              <FormField label="Atraso (dias)">
                <TextInput
                  type="number"
                  step="1"
                  value={depForm.lag_days}
                  onChange={(event) => setDepForm((prev) => ({ ...prev, lag_days: event.target.value }))}
                  className="w-24"
                />
              </FormField>
              <Button type="submit" variant="secondary">
                Adicionar
              </Button>
            </form>
            <ErrorBanner message={depError} />
          </div>

          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Recursos alocados</h3>
            {assignments.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">Nenhum recurso alocado — o Trabalho usa uma FTE genérica de 8h/dia.</p>
            ) : (
              <ul className="space-y-1.5">
                {assignments.map((a) => (
                  <li key={a.id} className="flex items-center justify-between rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm">
                    <span>
                      {resourceLabel(a.resource_id)} · {formatNumber(a.allocated_hours)}h alocadas
                    </span>
                    <button type="button" onClick={() => handleRemoveAssignment(a.id)} className="text-xs text-[var(--status-critical)] hover:underline">
                      Remover
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <form onSubmit={handleAddAssignment} className="mt-3 flex flex-wrap items-end gap-2">
              <FormField label="Recurso">
                <Select value={assignForm.resource_id} onChange={(event) => setAssignForm((prev) => ({ ...prev, resource_id: event.target.value }))}>
                  <option value="">Selecione…</option>
                  {resourceOptions.map((r) => (
                    <option key={r.id} value={r.id}>
                      {resourceLabel(r.id)}
                    </option>
                  ))}
                </Select>
              </FormField>
              <FormField label="Horas alocadas">
                <TextInput
                  type="number"
                  min="0.5"
                  step="0.5"
                  value={assignForm.allocated_hours}
                  onChange={(event) => setAssignForm((prev) => ({ ...prev, allocated_hours: event.target.value }))}
                  className="w-28"
                />
              </FormField>
              <Button type="submit" variant="secondary">
                Adicionar
              </Button>
            </form>
            <ErrorBanner message={assignError} />
          </div>
        </div>
      )}
    </Modal>
  )
}

function MoveTaskModal({ task, allTasks, onClose, onSaved }) {
  const [newParentId, setNewParentId] = useState(task.parent_task_id || '')
  const [beforeTaskId, setBeforeTaskId] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  function isDescendant(candidateId) {
    let current = allTasks.find((t) => t.id === candidateId)
    while (current) {
      if (current.id === task.id) return true
      current = allTasks.find((t) => t.id === current.parent_task_id)
    }
    return false
  }

  const parentOptions = allTasks.filter((t) => t.id !== task.id && !isDescendant(t.id))
  const siblingOptions = allTasks.filter((t) => t.id !== task.id && (t.parent_task_id || '') === (newParentId || ''))

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSaving(true)
    try {
      await tasksApi.moveTask(task.id, { new_parent_id: newParentId || null, before_task_id: beforeTaskId || null })
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={`Mover tarefa — ${task.wbs_code} ${task.name}`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField label="Nova tarefa pai" hint="Deixe em branco para mover para a raiz do projeto.">
          <Select
            value={newParentId}
            onChange={(event) => {
              setNewParentId(event.target.value)
              setBeforeTaskId('')
            }}
          >
            <option value="">Nenhuma (raiz)</option>
            {parentOptions.map((t) => (
              <option key={t.id} value={t.id}>
                {'—'.repeat(t.depth)} {t.wbs_code} {t.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label="Colocar antes de" hint="Deixe em branco para colocar por último entre as irmãs.">
          <Select value={beforeTaskId} onChange={(event) => setBeforeTaskId(event.target.value)}>
            <option value="">Por último</option>
            {siblingOptions.map((t) => (
              <option key={t.id} value={t.id}>
                {t.wbs_code} — {t.name}
              </option>
            ))}
          </Select>
        </FormField>
        <p className="text-xs text-[var(--text-muted)]">
          Depois de mover, use "Recalcular WBS/EAP" para renumerar e "Recalcular tudo" se a tarefa tiver predecessoras.
        </p>
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? 'Movendo…' : 'Mover'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

/** Data efetiva de uma linha do Gantt: tarefa-folha usa a própria
 * planned_start_date/end_date; tarefa-pai (WBS) não tem essas colunas
 * preenchidas de forma útil — usa o agregado das descendentes que o
 * backend já manda em rollup_start_date/rollup_end_date (mesma regra da
 * grade de Tarefas, ver services._task_rollups). Sem isso, toda
 * tarefa-pai aparecia como "sem datas" no Gantt mesmo tendo filhas
 * totalmente agendadas. */
function ganttStart(task) {
  return task.rollup_start_date ?? task.planned_start_date
}
function ganttEnd(task) {
  return task.rollup_end_date ?? task.planned_end_date
}

const GANTT_LABEL_COL_PX = 220
const GANTT_DAY_PX = 34
const GANTT_ROW_PX = 30
// Segunda-feira de referência (03/01/2000) só pra achar o índice de semana
// ISO-like de qualquer data por subtração de datas — não é uma data real do
// projeto, é só uma âncora fixa de cálculo.
const GANTT_WEEK_ANCHOR_MS = Date.UTC(2000, 0, 3)
const GANTT_MONTH_YEAR_FORMATTER = new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric', timeZone: 'UTC' })

/** Largura de cada coluna de SEMANA no modo "semana" do Gantt — diminui
 * conforme o período cresce (pedido do usuário), pra régua não ficar
 * absurdamente comprida; mesmo assim o contêiner rola horizontalmente
 * quando ainda não cabe na tela. */
function ganttWeekColumnPx(weeksCount) {
  if (weeksCount <= 8) return 96
  if (weeksCount <= 16) return 72
  if (weeksCount <= 30) return 52
  if (weeksCount <= 60) return 38
  return 28
}

/** Monta a régua de datas do Gantt em PIXELS (não mais em %), pra permitir
 * rolagem horizontal e duas granularidades de zoom:
 * - período de até ~1 mês: uma coluna por DIA (sem mês/ano — isso fica na
 *   régua de cima) com faixas alternadas identificando cada semana;
 * - período maior: uma coluna por SEMANA (rótulo = data de início da
 *   semana), coluna mais estreita quanto mais semanas o período tiver.
 * A régua de mês/ano de cima é calculada à parte, em cima do mesmo
 * pxPerDay — funciona igual nos dois modos, sem precisar saber qual é. */
function buildGanttLayout(rangeStartDate, rangeEndDate, totalDays) {
  const numDays = Math.round(totalDays) + 1
  const mode = numDays <= 31 ? 'day' : 'week'

  let pxPerDay
  const units = []
  if (mode === 'day') {
    pxPerDay = GANTT_DAY_PX
    for (let i = 0; i < numDays; i += 1) {
      const time = rangeStartDate.getTime() + i * 86_400_000
      const weekIndex = Math.floor((time - GANTT_WEEK_ANCHOR_MS) / (7 * 86_400_000))
      units.push({
        key: `d${i}`,
        leftPx: i * pxPerDay,
        widthPx: pxPerDay,
        label: String(new Date(time).getUTCDate()).padStart(2, '0'),
        title: formatDate(new Date(time).toISOString().slice(0, 10)),
        shaded: weekIndex % 2 === 1,
      })
    }
  } else {
    const weeksCount = Math.ceil(numDays / 7)
    const weekPx = ganttWeekColumnPx(weeksCount)
    pxPerDay = weekPx / 7
    for (let w = 0; w < weeksCount; w += 1) {
      const startOffsetDays = w * 7
      const daysInWeek = Math.min(7, numDays - startOffsetDays)
      const weekStartTime = rangeStartDate.getTime() + startOffsetDays * 86_400_000
      const weekEndTime = weekStartTime + (daysInWeek - 1) * 86_400_000
      const weekStartStr = new Date(weekStartTime).toISOString().slice(0, 10)
      units.push({
        key: `w${w}`,
        leftPx: startOffsetDays * pxPerDay,
        widthPx: daysInWeek * pxPerDay,
        label: `${String(new Date(weekStartTime).getUTCDate()).padStart(2, '0')}/${String(new Date(weekStartTime).getUTCMonth() + 1).padStart(2, '0')}`,
        title: `${formatDate(weekStartStr)} – ${formatDate(new Date(weekEndTime).toISOString().slice(0, 10))}`,
        shaded: w % 2 === 1,
      })
    }
  }

  const totalWidthPx = numDays * pxPerDay

  // Régua de mês/ano — sempre calculada em dias, independente do modo
  // dia/semana da régua de baixo.
  const monthSpans = []
  let cursor = new Date(rangeStartDate.getTime())
  while (cursor.getTime() <= rangeEndDate.getTime()) {
    const nextMonthStart = Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth() + 1, 1)
    const segmentEndTime = Math.min(nextMonthStart - 86_400_000, rangeEndDate.getTime())
    const daysInSegment = Math.round((segmentEndTime - cursor.getTime()) / 86_400_000) + 1
    const leftPx = Math.round((cursor.getTime() - rangeStartDate.getTime()) / 86_400_000) * pxPerDay
    const label = GANTT_MONTH_YEAR_FORMATTER.format(cursor)
    monthSpans.push({
      key: cursor.toISOString().slice(0, 7),
      leftPx,
      widthPx: daysInSegment * pxPerDay,
      label: label.charAt(0).toUpperCase() + label.slice(1),
    })
    cursor = new Date(nextMonthStart)
  }

  function pxFromDate(dateStr) {
    const date = parseApiDate(dateStr)
    return Math.round((date.getTime() - rangeStartDate.getTime()) / 86_400_000) * pxPerDay
  }

  function pxWidthBetween(startStr, endStr) {
    const start = parseApiDate(startStr)
    const end = parseApiDate(endStr)
    const days = Math.max(1, Math.round((end.getTime() - start.getTime()) / 86_400_000) + 1)
    return Math.max(6, days * pxPerDay)
  }

  return { mode, pxPerDay, totalWidthPx, units, monthSpans, pxFromDate, pxWidthBetween }
}

/** Resolve "var(--nome)" pra cor de verdade (hex/rgb) lendo o tema atual —
 * necessário pro export em PNG, que desenha num <canvas> e não entende
 * variáveis CSS. O atributo de tema (data-theme) fica no próprio
 * <html> (ver ThemeContext.jsx), então getComputedStyle nele já resolve
 * claro/escuro corretamente. */
function resolveGanttColor(cssVarExpr) {
  if (typeof document === 'undefined') return cssVarExpr
  const match = /var\((--[\w-]+)\)/.exec(cssVarExpr || '')
  if (!match) return cssVarExpr
  const value = getComputedStyle(document.documentElement).getPropertyValue(match[1]).trim()
  return value || '#94a3b8'
}

function ganttRoundRect(ctx, x, y, w, h, r) {
  const radius = Math.max(0, Math.min(r, w / 2, h / 2))
  ctx.beginPath()
  ctx.moveTo(x + radius, y)
  ctx.arcTo(x + w, y, x + w, y + h, radius)
  ctx.arcTo(x + w, y + h, x, y + h, radius)
  ctx.arcTo(x, y + h, x, y, radius)
  ctx.arcTo(x, y, x + w, y, radius)
  ctx.closePath()
}

function ganttTruncateForCanvas(ctx, text, maxWidth) {
  if (ctx.measureText(text).width <= maxWidth) return text
  let truncated = text
  while (truncated.length > 1 && ctx.measureText(`${truncated}…`).width > maxWidth) {
    truncated = truncated.slice(0, -1)
  }
  return `${truncated}…`
}

function GanttTab({ projectId, project }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  // Período exibido no Gantt: por padrão é o intervalo natural (min/max das
  // datas das tarefas), mas o usuário pode alargar pra ver um período maior
  // (ex.: enxergar folga antes do início ou depois do fim do projeto).
  const [rangeOverride, setRangeOverride] = useState({ start: '', end: '' })

  useEffect(() => {
    let active = true
    // /schedule (não /gantt) porque já vem com rollup_start_date/
    // rollup_end_date agregados nas tarefas-pai — ver ganttStart/ganttEnd.
    reportsApi
      .getSchedule(projectId)
      .then((result) => active && setData(result))
      .catch((err) => active && setError(err.message))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [projectId])

  if (loading) return <Spinner />
  if (error) return <ErrorBanner message={error} />
  if (!data || data.tasks.length === 0) {
    return <p className="text-sm text-[var(--text-muted)]">Nenhuma tarefa cadastrada ainda.</p>
  }

  const scheduled = data.tasks.filter((task) => ganttStart(task) && ganttEnd(task))
  if (scheduled.length === 0) {
    return (
      <p className="text-sm text-[var(--text-muted)]">
        Nenhuma tarefa tem datas planejadas ainda — o Gantt aparece assim que houver início/fim planejados.
      </p>
    )
  }

  const rangeStartStr = scheduled.reduce((min, t) => (ganttStart(t) < min ? ganttStart(t) : min), ganttStart(scheduled[0]))
  const rangeEndStr = scheduled.reduce((max, t) => (ganttEnd(t) > max ? ganttEnd(t) : max), ganttEnd(scheduled[0]))

  // Override do usuário: só é aplicado se formar um intervalo válido
  // (início <= fim) — string ISO (YYYY-MM-DD) compara lexicograficamente
  // igual a data, então dá pra validar sem parsear. Um override inválido
  // (ex.: campo em branco por causa de digitação incompleta) cai de volta
  // pro intervalo natural em vez de quebrar o gráfico.
  const effectiveStartStr = rangeOverride.start && rangeOverride.start <= (rangeOverride.end || rangeEndStr) ? rangeOverride.start : rangeStartStr
  const effectiveEndStr = rangeOverride.end && (rangeOverride.start || rangeStartStr) <= rangeOverride.end ? rangeOverride.end : rangeEndStr
  const hasCustomRange = effectiveStartStr !== rangeStartStr || effectiveEndStr !== rangeEndStr

  const rangeStartDate = parseApiDate(effectiveStartStr)
  const rangeEndDate = parseApiDate(effectiveEndStr)
  const totalDays = Math.max(1, (rangeEndDate.getTime() - rangeStartDate.getTime()) / 86_400_000)

  const layout = buildGanttLayout(rangeStartDate, rangeEndDate, totalDays)

  const predecessorCount = {}
  for (const dependency of data.dependencies) {
    predecessorCount[dependency.successor_task_id] = (predecessorCount[dependency.successor_task_id] || 0) + 1
  }

  // Export em PNG: desenha a mesma régua/barras num <canvas> (não é uma
  // foto do DOM) reaproveitando o layout já calculado acima, então fica
  // consistente com o que está na tela em qualquer zoom (dia/semana).
  function handleExportPng() {
    const titleH = project ? 20 : 0
    const monthRowH = 18
    const unitRowH = 20
    const headerH = titleH + monthRowH + unitRowH
    const rowH = GANTT_ROW_PX
    const legendH = 30
    const padX = 16
    const padY = 12
    const width = GANTT_LABEL_COL_PX + layout.totalWidthPx + padX * 2
    const height = headerH + data.tasks.length * rowH + legendH + padY * 2

    const scale = 2 // resolução maior pra ficar nítido ao ampliar/imprimir
    const canvas = document.createElement('canvas')
    canvas.width = Math.ceil(width * scale)
    canvas.height = Math.ceil(height * scale)
    const ctx = canvas.getContext('2d')
    ctx.scale(scale, scale)

    const surface = resolveGanttColor('var(--surface)')
    const border = resolveGanttColor('var(--border)')
    const grid = resolveGanttColor('var(--grid)')
    const textSecondary = resolveGanttColor('var(--text-secondary)')
    const textMuted = resolveGanttColor('var(--text-muted)')

    ctx.fillStyle = surface
    ctx.fillRect(0, 0, width, height)
    ctx.translate(padX, padY)

    if (project) {
      ctx.fillStyle = textSecondary
      ctx.font = '600 12px sans-serif'
      ctx.textBaseline = 'middle'
      ctx.textAlign = 'left'
      ctx.fillText(
        `${project.code} — ${project.name} · Gantt (${formatDate(effectiveStartStr)} – ${formatDate(effectiveEndStr)})`,
        0,
        titleH / 2,
      )
    }

    ctx.textBaseline = 'middle'
    ctx.textAlign = 'left'
    ctx.font = '600 11px sans-serif'
    ctx.fillStyle = textSecondary
    layout.monthSpans.forEach((m) => {
      ctx.fillText(m.label, GANTT_LABEL_COL_PX + m.leftPx + 4, titleH + monthRowH / 2)
    })

    ctx.strokeStyle = border
    ctx.beginPath()
    ctx.moveTo(0, titleH + monthRowH)
    ctx.lineTo(width - padX * 2, titleH + monthRowH)
    ctx.stroke()

    ctx.font = '10px sans-serif'
    layout.units.forEach((u) => {
      const x = GANTT_LABEL_COL_PX + u.leftPx
      if (u.shaded) {
        ctx.fillStyle = grid
        ctx.fillRect(x, titleH + monthRowH, u.widthPx, unitRowH)
      }
      ctx.strokeStyle = border
      ctx.beginPath()
      ctx.moveTo(x, titleH + monthRowH)
      ctx.lineTo(x, headerH)
      ctx.stroke()
      ctx.fillStyle = textMuted
      ctx.textAlign = 'center'
      ctx.fillText(u.label, x + u.widthPx / 2, titleH + monthRowH + unitRowH / 2, u.widthPx - 2)
    })

    ctx.strokeStyle = border
    ctx.beginPath()
    ctx.moveTo(0, headerH)
    ctx.lineTo(width - padX * 2, headerH)
    ctx.stroke()

    ctx.font = '11px sans-serif'
    data.tasks.forEach((task, idx) => {
      const y = headerH + idx * rowH
      const start = ganttStart(task)
      const end = ganttEnd(task)
      const color = resolveGanttColor(TASK_TYPE_COLORS[task.task_type] || 'var(--text-muted)')

      ctx.strokeStyle = border
      layout.units.forEach((u) => {
        const x = GANTT_LABEL_COL_PX + u.leftPx
        ctx.beginPath()
        ctx.moveTo(x, y)
        ctx.lineTo(x, y + rowH)
        ctx.stroke()
      })

      ctx.fillStyle = textSecondary
      ctx.textAlign = 'left'
      const label = `${task.wbs_code} ${task.name}`
      ctx.fillText(ganttTruncateForCanvas(ctx, label, GANTT_LABEL_COL_PX - 8), 0, y + rowH / 2)

      if (start && end) {
        const left = GANTT_LABEL_COL_PX + layout.pxFromDate(start)
        ctx.fillStyle = color
        if (task.is_milestone) {
          const cy = y + rowH / 2
          const s = 5
          ctx.save()
          ctx.translate(left + layout.pxPerDay / 2, cy)
          ctx.rotate(Math.PI / 4)
          ctx.fillRect(-s, -s, s * 2, s * 2)
          ctx.restore()
        } else {
          const w = layout.pxWidthBetween(start, end)
          ganttRoundRect(ctx, left, y + rowH / 2 - 6, w, 12, 3)
          ctx.fill()
        }
      }
    })

    const legendY = headerH + data.tasks.length * rowH + legendH / 2
    ctx.font = '10px sans-serif'
    ctx.textAlign = 'left'
    let lx = 0
    ;[
      { label: 'Consultoria', color: resolveGanttColor(TASK_TYPE_COLORS.CONSULTING) },
      { label: 'Gestão', color: resolveGanttColor(TASK_TYPE_COLORS.MANAGEMENT) },
    ].forEach((item) => {
      ctx.fillStyle = item.color
      ctx.beginPath()
      ctx.arc(lx + 5, legendY, 5, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillStyle = textSecondary
      ctx.fillText(item.label, lx + 14, legendY)
      lx += 14 + ctx.measureText(item.label).width + 18
    })

    canvas.toBlob((blob) => {
      if (!blob) return
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${project?.code || projectId}_gantt.png`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    }, 'image/png')
  }

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div className="flex flex-wrap items-end gap-2">
          <FormField label="Início do período exibido">
            <TextInput
              type="date"
              value={rangeOverride.start || rangeStartStr}
              onChange={(event) => setRangeOverride((prev) => ({ ...prev, start: event.target.value }))}
            />
          </FormField>
          <FormField label="Fim do período exibido">
            <TextInput
              type="date"
              value={rangeOverride.end || rangeEndStr}
              onChange={(event) => setRangeOverride((prev) => ({ ...prev, end: event.target.value }))}
            />
          </FormField>
          {hasCustomRange && (
            <Button variant="secondary" onClick={() => setRangeOverride({ start: '', end: '' })}>
              Restaurar período do projeto
            </Button>
          )}
        </div>
        <IconButton icon={DownloadIcon} label="Exportar PNG" onClick={handleExportPng} />
      </div>

      <div className="overflow-x-auto">
        <div style={{ width: GANTT_LABEL_COL_PX + layout.totalWidthPx }}>
          {/* Régua de mês/ano */}
          <div className="flex">
            <span className="sticky left-0 z-10 shrink-0 bg-[var(--surface)]" style={{ width: GANTT_LABEL_COL_PX }} />
            <div className="relative h-5 text-xs font-semibold text-[var(--text-secondary)]" style={{ width: layout.totalWidthPx }}>
              {layout.monthSpans.map((m) => (
                <span key={m.key} className="absolute top-0 truncate whitespace-nowrap pl-1" style={{ left: m.leftPx, width: m.widthPx }}>
                  {m.label}
                </span>
              ))}
            </div>
          </div>
          {/* Régua de dias (período ≤ 1 mês) ou semanas (período maior) */}
          <div className="flex border-b border-[var(--border)] pb-1">
            <span className="sticky left-0 z-10 shrink-0 bg-[var(--surface)]" style={{ width: GANTT_LABEL_COL_PX }} />
            <div className="relative h-5 text-[10px] text-[var(--text-muted)]" style={{ width: layout.totalWidthPx }}>
              {layout.units.map((u) => (
                <span
                  key={u.key}
                  className="absolute inset-y-0 flex items-center justify-center overflow-hidden border-l border-[var(--border)]"
                  style={{ left: u.leftPx, width: u.widthPx, backgroundColor: u.shaded ? 'var(--grid)' : 'transparent' }}
                  title={u.title}
                >
                  {u.label}
                </span>
              ))}
            </div>
          </div>

          <div className="mt-1 space-y-0.5">
            {data.tasks.map((task) => {
              const start = ganttStart(task)
              const end = ganttEnd(task)
              const hasDates = Boolean(start && end)
              const color = TASK_TYPE_COLORS[task.task_type] || 'var(--text-muted)'
              const preds = predecessorCount[task.id] || 0
              return (
                <div key={task.id} className="flex items-center">
                  <span
                    className="sticky left-0 z-10 shrink-0 truncate bg-[var(--surface)] pr-2 text-xs text-[var(--text-secondary)]"
                    style={{ width: GANTT_LABEL_COL_PX }}
                    title={task.name}
                  >
                    <span className="text-[var(--text-muted)]">{task.wbs_code}</span> {task.name}
                    {preds > 0 && (
                      <span className="text-[var(--text-muted)]">
                        {' '}
                        · {preds} predecessora{preds > 1 ? 's' : ''}
                      </span>
                    )}
                  </span>
                  <div className="relative" style={{ width: layout.totalWidthPx, height: GANTT_ROW_PX }}>
                    {layout.units.map((u) => (
                      <span
                        key={u.key}
                        className="absolute inset-y-0 border-l border-[var(--border)]"
                        style={{ left: u.leftPx, width: u.widthPx, backgroundColor: u.shaded ? 'var(--grid)' : 'transparent' }}
                      />
                    ))}
                    {hasDates ? (
                      task.is_milestone ? (
                        <span
                          className="absolute top-1/2 h-3 w-3 -translate-y-1/2 -translate-x-1/2 rotate-45"
                          style={{ left: layout.pxFromDate(start) + layout.pxPerDay / 2, backgroundColor: color }}
                          title={`Marco: ${formatDate(start)}`}
                        />
                      ) : (
                        <span
                          className="absolute top-1/2 h-4 -translate-y-1/2 rounded"
                          style={{
                            left: layout.pxFromDate(start),
                            width: layout.pxWidthBetween(start, end),
                            backgroundColor: color,
                          }}
                          title={`${formatDate(start)} – ${formatDate(end)}`}
                        />
                      )
                    ) : (
                      <span className="absolute inset-y-0 left-2 flex items-center text-xs text-[var(--text-muted)]">sem datas</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <div className="mt-5 flex items-center gap-4 border-t border-[var(--border)] pt-3 text-xs text-[var(--text-secondary)]">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: TASK_TYPE_COLORS.CONSULTING }} />
          Consultoria
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: TASK_TYPE_COLORS.MANAGEMENT }} />
          Gestão
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rotate-45" style={{ backgroundColor: 'var(--text-muted)' }} />
          Marco
        </span>
      </div>
    </Card>
  )
}
