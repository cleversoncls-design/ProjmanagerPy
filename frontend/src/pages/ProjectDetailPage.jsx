import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import * as projectsApi from '../api/projects'
import * as reportsApi from '../api/reports'
import * as tasksApi from '../api/tasks'
import * as clientsApi from '../api/clients'
import { useAuth } from '../context/AuthContext'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import StatTile from '../components/StatTile'
import Table from '../components/Table'
import Button from '../components/Button'
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import StatusPill from '../components/StatusPill'
import CategoryBars from '../components/CategoryBars'
import { FormField, TextInput, Select } from '../components/FormField'
import { formatCurrency, formatDate, formatNumber, formatPercent, parseApiDate } from '../utils/format'
import {
  APPROVAL_STATUS_LABELS,
  APPROVAL_STATUS_TONE,
  MANAGEMENT_ROLES,
  PROJECT_STATUS_LABELS,
  PROJECT_STATUS_TONE,
  TASK_STATUS_COLORS,
  TASK_STATUS_LABELS,
  TASK_STATUS_TONE,
  TASK_TYPE_COLORS,
  TASK_TYPE_LABELS,
} from '../utils/labels'

const TABS = [
  { key: 'overview', label: 'Visão geral' },
  { key: 'tasks', label: 'Tarefas' },
  { key: 'gantt', label: 'Gantt' },
]

export default function ProjectDetailPage() {
  const { projectId } = useParams()
  const { user } = useAuth()
  const canWrite = MANAGEMENT_ROLES.includes(user.role)

  const [project, setProject] = useState(null)
  const [client, setClient] = useState(null)
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('overview')

  function loadProject() {
    setLoading(true)
    setError('')
    Promise.all([projectsApi.getProject(projectId), reportsApi.getProjectReport(projectId)])
      .then(([projectResult, reportResult]) => {
        setProject(projectResult)
        setReport(reportResult)
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
        action={<StatusPill label={PROJECT_STATUS_LABELS[project.status] || project.status} tone={PROJECT_STATUS_TONE[project.status]} />}
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

      {tab === 'overview' && <OverviewTab project={project} report={report} />}
      {tab === 'tasks' && <TasksTab projectId={projectId} canWrite={canWrite} onTaskCreated={loadProject} />}
      {tab === 'gantt' && <GanttTab projectId={projectId} />}
    </div>
  )
}

function OverviewTab({ project, report }) {
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

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Tarefas por status">
          {report.tasks_total > 0 ? (
            <CategoryBars
              items={Object.entries(report.tasks_by_status).map(([key, value]) => ({
                key,
                value,
                label: TASK_STATUS_LABELS[key] || key,
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
                    type: TASK_TYPE_LABELS[key] || key,
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

const EMPTY_TASK_FORM = {
  name: '',
  wbs_code: '',
  task_type: 'CONSULTING',
  estimated_hours: '0',
  planned_start_date: '',
  planned_end_date: '',
  is_milestone: false,
}

function TasksTab({ projectId, canWrite, onTaskCreated }) {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState(EMPTY_TASK_FORM)
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function loadTasks() {
    setLoading(true)
    tasksApi
      .listTasks(projectId)
      .then(setTasks)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadTasks, [projectId])

  function updateField(field) {
    return (event) => {
      const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
      setForm((prev) => ({ ...prev, [field]: value }))
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError('')
    setSubmitting(true)
    try {
      const payload = { ...form }
      if (!payload.planned_start_date) delete payload.planned_start_date
      if (!payload.planned_end_date) delete payload.planned_end_date
      await tasksApi.createTask(projectId, payload)
      setShowModal(false)
      setForm(EMPTY_TASK_FORM)
      loadTasks()
      onTaskCreated?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <div className="mb-4 flex justify-end">
        {canWrite && <Button onClick={() => setShowModal(true)}>Nova tarefa</Button>}
      </div>

      {loading && <Spinner />}
      <ErrorBanner message={error} />

      {!loading && !error && (
        <Card>
          <Table
            columns={[
              { key: 'wbs_code', header: 'WBS' },
              { key: 'name', header: 'Nome' },
              { key: 'task_type', header: 'Tipo', render: (row) => TASK_TYPE_LABELS[row.task_type] || row.task_type },
              {
                key: 'status',
                header: 'Status',
                render: (row) => <StatusPill label={TASK_STATUS_LABELS[row.status] || row.status} tone={TASK_STATUS_TONE[row.status]} />,
              },
              { key: 'progress_percentage', header: 'Progresso', align: 'right', render: (row) => formatPercent(row.progress_percentage) },
              {
                key: 'dates',
                header: 'Datas planejadas',
                render: (row) => `${formatDate(row.planned_start_date)} – ${formatDate(row.planned_end_date)}`,
              },
              {
                key: 'client_approval_status',
                header: 'Aprovação do cliente',
                render: (row) => <StatusPill label={APPROVAL_STATUS_LABELS[row.client_approval_status]} tone={APPROVAL_STATUS_TONE[row.client_approval_status]} />,
              },
            ]}
            rows={tasks}
            getRowKey={(row) => row.id}
            emptyMessage="Nenhuma tarefa cadastrada ainda."
          />
        </Card>
      )}

      {showModal && (
        <Modal title="Nova tarefa" onClose={() => setShowModal(false)} wide>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Código WBS" required hint='Ex.: "1.2"'>
                <TextInput required value={form.wbs_code} onChange={updateField('wbs_code')} />
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
              <FormField label="Horas estimadas">
                <TextInput type="number" min="0" step="0.5" value={form.estimated_hours} onChange={updateField('estimated_hours')} />
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Início planejado">
                <TextInput type="date" value={form.planned_start_date} onChange={updateField('planned_start_date')} />
              </FormField>
              <FormField label="Fim planejado">
                <TextInput type="date" value={form.planned_end_date} onChange={updateField('planned_end_date')} />
              </FormField>
            </div>
            <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <input type="checkbox" checked={form.is_milestone} onChange={updateField('is_milestone')} />
              É um marco (milestone)
            </label>

            <ErrorBanner message={formError} />

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="secondary" onClick={() => setShowModal(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? 'Salvando…' : 'Salvar'}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}

function GanttTab({ projectId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    reportsApi
      .getGantt(projectId)
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

  const scheduled = data.tasks.filter((task) => task.planned_start_date && task.planned_end_date)
  if (scheduled.length === 0) {
    return (
      <p className="text-sm text-[var(--text-muted)]">
        Nenhuma tarefa tem datas planejadas ainda — o Gantt aparece assim que houver início/fim planejados.
      </p>
    )
  }

  const rangeStartStr = scheduled.reduce((min, t) => (t.planned_start_date < min ? t.planned_start_date : min), scheduled[0].planned_start_date)
  const rangeEndStr = scheduled.reduce((max, t) => (t.planned_end_date > max ? t.planned_end_date : max), scheduled[0].planned_end_date)
  const rangeStartDate = parseApiDate(rangeStartStr)
  const rangeEndDate = parseApiDate(rangeEndStr)
  const totalDays = Math.max(1, (rangeEndDate.getTime() - rangeStartDate.getTime()) / 86_400_000)

  function leftPercent(dateStr) {
    const date = parseApiDate(dateStr)
    return Math.min(100, Math.max(0, ((date.getTime() - rangeStartDate.getTime()) / 86_400_000 / totalDays) * 100))
  }

  function widthPercent(startStr, endStr) {
    const start = parseApiDate(startStr)
    const end = parseApiDate(endStr)
    const days = Math.max(1, (end.getTime() - start.getTime()) / 86_400_000 + 1)
    return Math.max(1.5, (days / totalDays) * 100)
  }

  const predecessorCount = {}
  for (const dependency of data.dependencies) {
    predecessorCount[dependency.successor_task_id] = (predecessorCount[dependency.successor_task_id] || 0) + 1
  }

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between text-xs text-[var(--text-muted)]">
        <span>{formatDate(rangeStartStr)}</span>
        <span>{formatDate(rangeEndStr)}</span>
      </div>
      <div className="space-y-2.5">
        {data.tasks.map((task) => {
          const hasDates = Boolean(task.planned_start_date && task.planned_end_date)
          const color = TASK_TYPE_COLORS[task.task_type] || 'var(--text-muted)'
          const preds = predecessorCount[task.id] || 0
          return (
            <div key={task.id} className="flex items-center gap-3">
              <span className="w-56 shrink-0 truncate text-xs text-[var(--text-secondary)]" title={task.name}>
                <span className="text-[var(--text-muted)]">{task.wbs_code}</span> {task.name}
                {preds > 0 && (
                  <span className="text-[var(--text-muted)]">
                    {' '}
                    · {preds} predecessora{preds > 1 ? 's' : ''}
                  </span>
                )}
              </span>
              <div className="relative h-6 flex-1 rounded-md bg-[var(--grid)]/50">
                {hasDates ? (
                  task.is_milestone ? (
                    <span
                      className="absolute top-1/2 h-3 w-3 -translate-y-1/2 -translate-x-1/2 rotate-45"
                      style={{ left: `${leftPercent(task.planned_start_date)}%`, backgroundColor: color }}
                      title={`Marco: ${formatDate(task.planned_start_date)}`}
                    />
                  ) : (
                    <span
                      className="absolute top-1/2 h-4 -translate-y-1/2 rounded"
                      style={{
                        left: `${leftPercent(task.planned_start_date)}%`,
                        width: `${widthPercent(task.planned_start_date, task.planned_end_date)}%`,
                        backgroundColor: color,
                      }}
                      title={`${formatDate(task.planned_start_date)} – ${formatDate(task.planned_end_date)}`}
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
