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
import * as taskGroupsApi from '../api/taskGroups'
import * as legacyApi from '../api/legacyConsumption'
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
import ColorListPicker from '../components/ColorListPicker'
import { DEFAULT_PROJECT_COLOR } from '../utils/colorPalette'
import {
  CheckIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ClockIcon,
  ColumnsIcon,
  CopyIcon,
  DownloadIcon,
  FlagIcon,
  HashIcon,
  LayersIcon,
  MoveIcon,
  PencilIcon,
  PlusIcon,
  RefreshIcon,
  TrashIcon,
  XIcon,
} from '../components/icons'
import { formatCurrency, formatDate, formatIndex, formatNumber, formatPercent, parseApiDate } from '../utils/format'
import {
  APPROVAL_STATUS_TONE,
  MANAGEMENT_ROLES,
  PROJECT_STATUS_TONE,
  TASK_STATUS_COLORS,
  TASK_STATUS_TONE,
  TASK_TYPE_COLORS,
  resourceFunctionLevelLabel,
} from '../utils/labels'

const TABS = [
  { key: 'overview', label: 'Visão geral' },
  { key: 'tasks', label: 'Tarefas' },
  { key: 'gantt', label: 'Gantt' },
  { key: 'resources', label: 'Recursos' },
  // Consumo já apropriado no sistema anterior — dado financeiro, só gestão.
  { key: 'legacy', label: 'Consumo anterior', managementOnly: true },
]

export default function ProjectDetailPage() {
  const { projectId } = useParams()
  const { user } = useAuth()
  const { labels, t } = useLanguage()
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

  // Recarrega só os números (sem o Spinner de tela cheia) depois de mexer
  // nos lançamentos de consumo anterior — o custo real/horas mudam.
  function refreshNumbers() {
    Promise.all([projectsApi.getProject(projectId), reportsApi.getProjectReport(projectId), reportsApi.getEvm(projectId).catch(() => null)])
      .then(([projectResult, reportResult, evmResult]) => {
        setProject(projectResult)
        setReport(reportResult)
        setEvm(evmResult)
      })
      .catch(() => {})
  }

  if (loading) return <Spinner />
  if (error) return <ErrorBanner message={error} />
  if (!project) return null

  return (
    <div>
      <PageHeader
        title={`${project.code} — ${project.name}`}
        subtitle={
          [client ? client.legal_name : null, project.project_type ? labels.PROJECT_TYPE_LABELS[project.project_type] : null].filter(Boolean).join(' · ') ||
          undefined
        }
        action={
          <div className="flex items-center gap-2">
            <StatusPill label={labels.PROJECT_STATUS_LABELS[project.status] || project.status} tone={PROJECT_STATUS_TONE[project.status]} />
            <Button variant="secondary" onClick={() => setShowStatsModal(true)}>
              {t('Estatísticas')}
            </Button>
            {canWrite && (
              <Button variant="secondary" onClick={() => setShowEditModal(true)}>
                {t('Editar projeto')}
              </Button>
            )}
          </div>
        }
      />

      <div className="mb-6 flex gap-1 border-b border-[var(--border)]">
        {TABS.filter((item) => !item.managementOnly || canWrite).map((item) => (
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
            {t(item.label)}
          </button>
        ))}
      </div>

      {tab === 'overview' && <OverviewTab project={project} report={report} evm={evm} />}
      {tab === 'tasks' && <TasksTab projectId={projectId} canWrite={canWrite} onTaskCreated={loadProject} />}
      {tab === 'gantt' && <GanttTab projectId={projectId} project={project} />}
      {tab === 'resources' && <ProjectResourcesTab projectId={projectId} canWrite={canWrite} />}
      {tab === 'legacy' && canWrite && <LegacyConsumptionTab projectId={projectId} onChanged={refreshNumbers} />}

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
  const { labels, t } = useLanguage()
  const financials = report.financials
  const byType = report.financials_by_task_type

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label={t('Progresso')} value={formatPercent(report.percent_complete)} />
        <StatTile label={t('Tarefas')} value={report.tasks_total} />
        <StatTile label={t('Tarefas restantes')} value={report.tasks_remaining} />
        <StatTile label={t('Início — fim planejado')} value={`${formatDate(project.start_date)} – ${formatDate(project.end_date)}`} />
      </div>

      {evm && (
        <Card
          title={t('Desempenho do cronograma (Earned Value, em horas)')}
          action={<span className="text-xs text-[var(--text-muted)]">{t('Data de status:')} {formatDate(evm.status_date)}</span>}
        >
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatTile label="SPI" value={formatIndex(evm.spi)} tone={evm.spi !== null && Number(evm.spi) < 1 ? 'warning' : 'default'} />
            <StatTile label="CPI" value={formatIndex(evm.cpi)} tone={evm.cpi !== null && Number(evm.cpi) < 1 ? 'warning' : 'default'} />
            <StatTile label={t('% previsto')} value={formatPercent(evm.planned_percent_complete)} />
            <StatTile label={t('% realizado')} value={formatPercent(evm.percent_complete)} />
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title={t('Tarefas por status')}>
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
            <p className="text-sm text-[var(--text-muted)]">{t('Nenhuma tarefa cadastrada ainda.')}</p>
          )}
        </Card>

        <Card title={t('Financeiro')}>
          {financials ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-5">
                <StatTile label={t('Valor vendido')} value={formatCurrency(financials.sold_value)} compact />
                <StatTile label={t('Custo real')} value={formatCurrency(financials.real_cost)} compact />
                <StatTile
                  label={t('Margem')}
                  value={formatCurrency(financials.profit_margin)}
                  tone={Number(financials.profit_margin) < 0 ? 'critical' : 'default'}
                  compact
                />
                {/* "% Margem Planejada" (pedido do usuário, "melhorias
                    parte 5") — mesmo valor DECLARADO na venda/BID
                    (Project.margin_percentage, "% Margem vendida" no
                    cadastro do projeto), só renomeado aqui pra ficar lado a
                    lado com "% Margem Real" pra comparação. Sempre visível
                    (antes só aparecia quando preenchido) — "—" quando o
                    projeto ainda não declarou uma margem. */}
                <StatTile label={t('% Margem Planejada')} value={formatPercent(project.margin_percentage)} compact />
                {/* "% Margem Real" — calculada a partir do custo efetivo
                    (financials.profit_margin / financials.sold_value), ver
                    project_financials em app/services.py. "—" sem valor
                    vendido (nada pra comparar). */}
                <StatTile
                  label={t('% Margem Real')}
                  value={formatPercent(financials.real_margin_percentage)}
                  tone={financials.real_margin_percentage !== null && Number(financials.real_margin_percentage) < 0 ? 'critical' : 'default'}
                  compact
                />
              </div>
              {byType && (
                <Table
                  columns={[
                    { key: 'type', header: t('Tipo') },
                    { key: 'hours', header: t('Horas'), align: 'right' },
                    { key: 'cost', header: t('Custo'), align: 'right' },
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
            <p className="text-sm text-[var(--text-muted)]">{t('Seu perfil não tem acesso a dados financeiros deste projeto.')}</p>
          )}
        </Card>
      </div>
    </div>
  )
}

/** Aba "Recursos" — vincula recursos diretamente ao projeto (pedido do
 * usuário: "não ter que vincular o usuário tarefa por tarefa" em
 * projetos pequenos, conduzidos por 1-2 consultores). Ao apontar horas
 * numa tarefa sem alocação própria, o backend cai pro vínculo daqui (ver
 * `_resolve_task_and_project` em app/routers/timesheets.py) — uma tarefa
 * que já tem alocação específica continua restrita só a quem está nela,
 * mesmo que outro recurso esteja vinculado ao projeto aqui. */
function ProjectResourcesTab({ projectId, canWrite }) {
  const { t, labels } = useLanguage()
  const [links, setLinks] = useState([])
  const [resources, setResources] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [resourceId, setResourceId] = useState('')
  const [adding, setAdding] = useState(false)
  const [removingId, setRemovingId] = useState(null)

  function load() {
    setLoading(true)
    setError('')
    // GET /resources e GET /users são restritos a perfis internos (mesma
    // observação de TasksTab) — perfil externo (CLIENT_PM/CLIENT_USER)
    // recebe 403 aqui; a aba degrada mostrando só a lista de vínculos.
    Promise.all([projectsApi.listProjectResources(projectId), resourcesApi.listResources().catch(() => []), usersApi.listUsers().catch(() => [])])
      .then(([linksResult, resourcesResult, usersResult]) => {
        setLinks(linksResult)
        setResources(resourcesResult)
        setUsers(usersResult)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [projectId])

  const usersById = useMemo(() => Object.fromEntries(users.map((u) => [u.id, u])), [users])
  const resourcesById = useMemo(() => Object.fromEntries(resources.map((r) => [r.id, r])), [resources])
  function resourceLabel(id) {
    const resource = resourcesById[id]
    if (!resource) return id
    return usersById[resource.user_id]?.name || resourceFunctionLevelLabel(resource, labels) || id
  }
  const linkedIds = useMemo(() => new Set(links.map((link) => link.resource_id)), [links])
  const availableResources = useMemo(() => resources.filter((r) => !linkedIds.has(r.id)), [resources, linkedIds])

  async function handleAdd(event) {
    event.preventDefault()
    if (!resourceId) return
    setAdding(true)
    setError('')
    try {
      await projectsApi.addProjectResource(projectId, { resource_id: resourceId })
      setResourceId('')
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setAdding(false)
    }
  }

  async function handleRemove(resourceIdToRemove) {
    setRemovingId(resourceIdToRemove)
    setError('')
    try {
      await projectsApi.removeProjectResource(projectId, resourceIdToRemove)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setRemovingId(null)
    }
  }

  if (loading) return <Spinner />

  return (
    <Card
      title={t('Recursos do projeto')}
      action={
        <span className="text-xs text-[var(--text-muted)]">
          {t('Quem está aqui pode apontar horas em qualquer tarefa deste projeto sem alocação própria.')}
        </span>
      }
    >
      <ErrorBanner message={error} />
      {links.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{t('Nenhum recurso vinculado ao projeto ainda — apontamento continua exigindo alocação por tarefa.')}</p>
      ) : (
        <ul className="space-y-1.5">
          {links.map((link) => (
            <li key={link.id} className="flex items-center justify-between rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm">
              <span>{resourceLabel(link.resource_id)}</span>
              {canWrite && (
                <button
                  type="button"
                  disabled={removingId === link.resource_id}
                  onClick={() => handleRemove(link.resource_id)}
                  className="text-xs text-[var(--status-critical)] hover:underline disabled:opacity-50"
                >
                  {t('Remover')}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canWrite && (
        <form onSubmit={handleAdd} className="mt-3 flex flex-wrap items-end gap-2">
          <FormField label={t('Recurso')}>
            <Select value={resourceId} onChange={(event) => setResourceId(event.target.value)}>
              <option value="">{t('Selecione…')}</option>
              {availableResources.map((r) => (
                <option key={r.id} value={r.id}>
                  {resourceLabel(r.id)}
                </option>
              ))}
            </Select>
          </FormField>
          <Button type="submit" variant="secondary" disabled={adding || !resourceId}>
            {t('Adicionar')}
          </Button>
        </form>
      )}
    </Card>
  )
}

/** Aba "Consumo anterior" — horas já consumidas no SISTEMA ANTERIOR, a um
 * custo médio por hora (pedido do usuário). Vários lançamentos por projeto;
 * entram no custo real/margem e nas horas consumidas, mas NÃO são
 * apontamentos (sem aprovação, Ordem de Serviço nem agenda). Também dá pra
 * carregar vários projetos de uma vez por planilha (.xlsx). */
function LegacyConsumptionTab({ projectId, onChanged }) {
  const { t } = useLanguage()
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [editing, setEditing] = useState(null) // null | 'new' | entry
  const [importing, setImporting] = useState(false)
  const [deletingId, setDeletingId] = useState(null)

  function load() {
    setError('')
    legacyApi
      .listLegacyConsumption(projectId)
      .then(setEntries)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [projectId])

  const totals = useMemo(() => {
    let hours = 0
    let cost = 0
    for (const entry of entries) {
      hours += Number(entry.hours)
      cost += Number(entry.total_cost)
    }
    return { hours, cost, average: hours > 0 ? cost / hours : 0 }
  }, [entries])

  async function handleDelete(entry) {
    if (!window.confirm(t('Excluir este lançamento de consumo anterior?'))) return
    setDeletingId(entry.id)
    setError('')
    setNotice('')
    try {
      await legacyApi.deleteLegacyConsumption(projectId, entry.id)
      load()
      onChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setDeletingId(null)
    }
  }

  async function handleImport(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setImporting(true)
    setError('')
    setNotice('')
    try {
      const result = await legacyApi.importLegacyConsumption(file)
      setNotice(
        t('Importação concluída: {n} lançamento(s) em {p} projeto(s), {h} h e {c}.', {
          n: result.created,
          p: result.projects,
          h: formatNumber(result.total_hours),
          c: formatCurrency(result.total_cost),
        }),
      )
      load()
      onChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setImporting(false)
    }
  }

  async function handleTemplate() {
    setError('')
    try {
      await legacyApi.downloadLegacyTemplate()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) return <Spinner />

  return (
    <div className="space-y-4">
      <Card
        title={t('Consumo anterior (sistema legado)')}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" onClick={handleTemplate}>
              {t('Baixar modelo')}
            </Button>
            <label
              className={`inline-flex cursor-pointer items-center rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--page)] ${
                importing ? 'pointer-events-none opacity-50' : ''
              }`}
            >
              {importing ? t('Importando…') : t('Importar planilha')}
              <input
                type="file"
                accept=".xlsx"
                className="hidden"
                onChange={handleImport}
                disabled={importing}
              />
            </label>
            <Button onClick={() => setEditing('new')}>
              <PlusIcon size={15} /> {t('Novo lançamento')}
            </Button>
          </div>
        }
      >
        <p className="mb-3 text-xs text-[var(--text-muted)]">
          {t(
            'Horas já consumidas no sistema anterior, a um custo médio por hora. Entram no custo real, na margem e nas horas consumidas do projeto, mas não são apontamentos (sem aprovação nem Ordem de Serviço). A planilha pode trazer vários projetos de uma vez; se alguma linha tiver erro, nada é gravado.',
          )}
        </p>
        <ErrorBanner message={error} />
        {notice && <p className="mb-3 rounded-lg border border-[var(--border)] bg-[var(--page)] px-3 py-2 text-sm text-[var(--text-primary)]">{notice}</p>}

        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3">
          <StatTile label={t('Horas consumidas (anterior)')} value={`${formatNumber(totals.hours)} h`} compact />
          <StatTile label={t('Custo apropriado')} value={formatCurrency(totals.cost)} compact />
          <StatTile label={t('Custo médio/hora')} value={formatCurrency(totals.average)} compact />
        </div>

        <Table
          emptyMessage={t('Nenhum consumo anterior lançado neste projeto.')}
          columns={[
            { key: 'reference_date', header: t('Data'), render: (row) => formatDate(row.reference_date) },
            { key: 'hours', header: t('Horas'), align: 'right', render: (row) => formatNumber(row.hours) },
            { key: 'cost_per_hour', header: t('Custo médio/hora'), align: 'right', render: (row) => formatCurrency(row.cost_per_hour) },
            { key: 'total_cost', header: t('Custo total'), align: 'right', render: (row) => formatCurrency(row.total_cost) },
            { key: 'description', header: t('Descrição'), render: (row) => row.description || '—' },
            {
              key: 'actions',
              header: '',
              align: 'right',
              render: (row) => (
                <div className="flex justify-end gap-1">
                  <IconButton icon={PencilIcon} label={t('Editar')} onClick={() => setEditing(row)} />
                  <IconButton icon={TrashIcon} variant="danger" label={t('Excluir')} disabled={deletingId === row.id} onClick={() => handleDelete(row)} />
                </div>
              ),
            },
          ]}
          rows={entries}
          getRowKey={(row) => row.id}
        />
      </Card>

      {editing && (
        <LegacyConsumptionModal
          projectId={projectId}
          entry={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            setNotice('')
            load()
            onChanged()
          }}
        />
      )}
    </div>
  )
}

function LegacyConsumptionModal({ projectId, entry, onClose, onSaved }) {
  const { t } = useLanguage()
  const [form, setForm] = useState({
    reference_date: entry?.reference_date || '',
    hours: entry?.hours ?? '',
    cost_per_hour: entry?.cost_per_hour ?? '',
    description: entry?.description || '',
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  function updateField(field) {
    return (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  const total = Number(form.hours || 0) * Number(form.cost_per_hour || 0)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSaving(true)
    const payload = {
      reference_date: form.reference_date,
      hours: form.hours,
      cost_per_hour: form.cost_per_hour,
      description: form.description.trim() || null,
    }
    try {
      if (entry) await legacyApi.updateLegacyConsumption(projectId, entry.id, payload)
      else await legacyApi.createLegacyConsumption(projectId, payload)
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={entry ? t('Editar lançamento de consumo anterior') : t('Novo lançamento de consumo anterior')} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField label={t('Data de referência')} required hint={t('Ex.: último dia do mês apropriado no sistema anterior.')}>
          <TextInput type="date" required value={form.reference_date} onChange={updateField('reference_date')} />
        </FormField>
        <div className="grid grid-cols-2 gap-4">
          <FormField label={t('Horas')} required>
            <TextInput type="number" required min="0.01" step="0.01" value={form.hours} onChange={updateField('hours')} />
          </FormField>
          <FormField label={t('Custo médio/hora')} required>
            <TextInput type="number" required min="0" step="0.01" value={form.cost_per_hour} onChange={updateField('cost_per_hour')} />
          </FormField>
        </div>
        <p className="text-xs text-[var(--text-secondary)]">
          {t('Custo total')}: <strong>{formatCurrency(total)}</strong>
        </p>
        <FormField label={t('Descrição')}>
          <TextInput maxLength={255} value={form.description} onChange={updateField('description')} />
        </FormField>
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? t('Salvando…') : t('Salvar')}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

// Status que liberam a cor (some da disputa de exclusividade e vira
// listrado — ver Project.color_striped no backend). Mesmo grupo de
// _COLOR_POOL_EXCLUDED_STATUSES em app/routers/projects.py, menos MODELO
// (projeto nunca chega a esta tela nesse status).
const FINALIZED_PROJECT_STATUSES = new Set(['COMPLETED', 'CANCELLED'])

function ProjectEditModal({ project, onClose, onSaved }) {
  const { labels, t } = useLanguage()
  const [form, setForm] = useState({
    name: project.name,
    manager_id: project.manager_id,
    status: project.status,
    calendar_id: project.calendar_id || '',
    color: project.color || DEFAULT_PROJECT_COLOR,
    status_date: project.status_date || '',
    start_date: project.start_date || '',
    end_date: project.end_date || '',
    management_hours: project.management_hours ?? '0',
    management_rate: project.management_rate ?? '0',
    consulting_hours: project.consulting_hours ?? '0',
    consulting_rate: project.consulting_rate ?? '0',
    margin_percentage: project.margin_percentage ?? '',
    project_type: project.project_type || '',
  })
  const [managers, setManagers] = useState([])
  const [calendars, setCalendars] = useState([])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  // Mesma ideia de ProjectsPage: Map<hex, "código — nome"> dos projetos
  // que hoje disputam a exclusividade de cor, pra desabilitar essas opções
  // no ColorListPicker — busca todos os projetos do escopo (não só os já
  // carregados nesta tela) e exclui o próprio projeto sendo editado.
  const [usedColors, setUsedColors] = useState(new Map())

  useEffect(() => {
    projectsApi
      .listEligibleManagers()
      .then(setManagers)
      .catch(() => {})
    calendarsApi.listCalendars().then(setCalendars).catch(() => {})
    projectsApi
      .listProjects()
      .then((allProjects) => {
        const map = new Map()
        for (const other of allProjects) {
          if (other.id === project.id) continue
          if (['COMPLETED', 'CANCELLED', 'MODELO'].includes(other.status)) continue
          map.set((other.color || '').toUpperCase(), `${other.code} — ${other.name}`)
        }
        setUsedColors(map)
      })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Status escolhido no próprio formulário (o usuário pode estar
  // finalizando ou reativando o projeto agora, antes de salvar) — decide
  // se o seletor de cor aparece travado/listrado já nesta tela, sem
  // esperar o round-trip pro backend.
  const willBeFinalized = FINALIZED_PROJECT_STATUSES.has(form.status)

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
        color: form.color,
        status_date: form.status_date || null,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
        management_hours: form.management_hours,
        management_rate: form.management_rate,
        consulting_hours: form.consulting_hours,
        consulting_rate: form.consulting_rate,
        margin_percentage: form.margin_percentage === '' ? null : form.margin_percentage,
        project_type: form.project_type || null,
      })
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={t('Editar projeto')} onClose={onClose} wide>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <FormField label={t('Nome')} required>
            <TextInput required value={form.name} onChange={updateField('name')} />
          </FormField>
          <FormField label={t('Gerente responsável')} required hint={t('Precisa ser ADMIN ou gerente de projetos interno.')}>
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
          <FormField label={t('Status')} required>
            <Select required value={form.status} onChange={updateField('status')}>
              {Object.entries(labels.PROJECT_STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label={t('Tipo de projeto')}>
            <Select value={form.project_type} onChange={updateField('project_type')}>
              <option value="">{t('Sem tipo definido')}</option>
              {Object.entries(labels.PROJECT_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </FormField>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <FormField label={t('Calendário do projeto')} hint={t('Usado para calcular dias úteis nas datas planejadas.')}>
            <Select value={form.calendar_id} onChange={updateField('calendar_id')}>
              <option value="">{t('Padrão (segunda a sexta, sem feriados)')}</option>
              {calendars.map((calendar) => (
                <option key={calendar.id} value={calendar.id}>
                  {calendar.name}
                </option>
              ))}
            </Select>
          </FormField>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <FormField label={t('Data de status')} hint={t('Data-base para % previsto e status das tarefas.')}>
            <TextInput type="date" value={form.status_date} onChange={updateField('status_date')} />
          </FormField>
          <FormField label={t('Início planejado')}>
            <TextInput type="date" value={form.start_date} onChange={updateField('start_date')} />
          </FormField>
          <FormField label={t('Fim planejado')}>
            <TextInput type="date" value={form.end_date} onChange={updateField('end_date')} />
          </FormField>
        </div>

        <FormField
          label={t('Cor do projeto')}
          hint={
            willBeFinalized
              ? t('Projeto finalizado (Concluído/Cancelado) exibe o padrão listrado — a cor original fica guardada e volta se o projeto for reativado.')
              : t('Usada na Agenda de consultores para identificar este projeto.')
          }
        >
          <ColorListPicker
            value={form.color}
            onChange={(color) => setForm((prev) => ({ ...prev, color }))}
            usedColors={usedColors}
            disabled={willBeFinalized}
            striped={willBeFinalized}
          />
        </FormField>

        <div className="rounded-lg border border-[var(--border)] p-4">
          <p className="mb-3 text-xs font-medium text-[var(--text-secondary)]">{t('Pacote vendido (horas × valor/hora)')}</p>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <FormField label={t('Horas de gestão')}>
              <TextInput type="number" min="0" step="0.5" value={form.management_hours} onChange={updateField('management_hours')} />
            </FormField>
            <FormField label={t('Valor/h gestão')}>
              <TextInput type="number" min="0" step="0.01" value={form.management_rate} onChange={updateField('management_rate')} />
            </FormField>
            <FormField label={t('Horas de consultoria')}>
              <TextInput type="number" min="0" step="0.5" value={form.consulting_hours} onChange={updateField('consulting_hours')} />
            </FormField>
            <FormField label={t('Valor/h consultoria')}>
              <TextInput type="number" min="0" step="0.01" value={form.consulting_rate} onChange={updateField('consulting_rate')} />
            </FormField>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-4">
            <FormField label={t('% Margem vendida')} hint={t('Valor declarado na venda — não é calculado a partir de custo.')}>
              {/* step="0.1" rejeitava valores com 2 casas decimais — ver
                  mesmo comentário em ProjectsPage.jsx. */}
              <TextInput type="number" min="0" max="100" step="0.01" value={form.margin_percentage} onChange={updateField('margin_percentage')} />
            </FormField>
          </div>
        </div>

        <ErrorBanner message={error} />

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? t('Salvando…') : t('Salvar')}
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
  const { t } = useLanguage()
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
    <Modal title={`${t('Estatísticas do projeto')} — ${projectLabel}`} onClose={onClose} wide>
      {loading && <Spinner />}
      <ErrorBanner message={error} />
      {stats && (
        <div className="space-y-4">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]"></th>
                  <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{t('Atual')}</th>
                  <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{t('Linha de base')}</th>
                  <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{t('Real')}</th>
                </tr>
              </thead>
              <tbody>
                <StatisticsRow label={t('Início')} field="start_date" stats={stats} />
                <StatisticsRow label={t('Término')} field="finish_date" stats={stats} />
                <StatisticsRow label={t('Duração')} field="duration_days" stats={stats} />
                <StatisticsRow label={t('Trabalho')} field="work_hours" stats={stats} />
                <StatisticsRow label={t('Custo')} field="cost" stats={stats} />
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between gap-3 rounded-lg border border-[var(--border)] px-3 py-2">
            <p className="text-xs text-[var(--text-muted)]">
              {latestBaseline ? (
                <>
                  {t('Linha de base atual:')} <span className="font-medium text-[var(--text-primary)]">{latestBaseline.version_name}</span> ({t('salva em')}{' '}
                  {formatDate(latestBaseline.created_at)})
                </>
              ) : (
                t('Nenhuma linha de base salva ainda para este projeto.')
              )}
            </p>
            {!showBaselineForm && (
              <Button type="button" variant="secondary" onClick={() => setShowBaselineForm(true)}>
                {t('Salvar linha de base')}
              </Button>
            )}
          </div>

          {showBaselineForm && (
            <form onSubmit={handleSaveBaseline} className="flex items-end gap-2 rounded-lg border border-[var(--border)] p-3">
              <div className="flex-1">
                <FormField label={t('Nome da versão')} hint={t('Ex.: Baseline inicial, Revisão de escopo #2.')}>
                  <TextInput
                    value={versionName}
                    onChange={(event) => setVersionName(event.target.value)}
                    placeholder={t('Ex.: Baseline inicial')}
                    autoFocus
                  />
                </FormField>
              </div>
              <Button type="submit" disabled={savingBaseline || !versionName.trim()}>
                {savingBaseline ? t('Salvando…') : t('Salvar')}
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
                {t('Cancelar')}
              </Button>
            </form>
          )}
          <ErrorBanner message={baselineError} />

          <div className="grid grid-cols-3 gap-4">
            <StatTile
              label={t('Variância de término')}
              value={
                stats.variance_finish_days === null || stats.variance_finish_days === undefined
                  ? '—'
                  : `${Number(stats.variance_finish_days) > 0 ? '+' : ''}${formatNumber(stats.variance_finish_days)} d`
              }
            />
            <StatTile label={t('% concluído (Duração)')} value={formatPercent(stats.percent_complete_duration)} />
            <StatTile label={t('% concluído (Trabalho)')} value={formatPercent(stats.percent_complete_work)} />
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
  const { t } = useLanguage()
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
    <Modal title={t('Salvar linha de base')} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          {t(
            'Grava a Duração, o Trabalho e as datas planejadas de hoje de todas as tarefas como a nova linha de base do projeto — usada para comparar com o realizado depois (colunas "Linha base" na grade e variância de término nas Estatísticas).',
          )}
        </p>
        <FormField label={t('Nome da versão')} required hint={t('Ex.: "Baseline inicial", "Revisão de escopo #2".')}>
          <TextInput value={versionName} onChange={(event) => setVersionName(event.target.value)} placeholder={t('Ex.: Baseline inicial')} autoFocus />
        </FormField>
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="submit" disabled={saving || !versionName.trim()}>
            {saving ? t('Salvando…') : t('Salvar linha de base')}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

/** "Copiar estrutura de outro projeto" (botão só aparece com o projeto
 * ainda vazio, ver TasksTab) — origem pode ser qualquer projeto (não só
 * status Modelo), a lista não filtra por status de propósito. Ver
 * services.copy_project_tasks no backend pro que exatamente é copiado
 * (sem recurso alocado) e como as datas planejadas são recalculadas. */
function CopyTasksModal({ projectId, onClose, onCopied }) {
  const { t } = useLanguage()
  const [projects, setProjects] = useState([])
  const [sourceProjectId, setSourceProjectId] = useState('')
  const [loadingProjects, setLoadingProjects] = useState(true)
  const [copying, setCopying] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    projectsApi
      .listProjects()
      .then((rows) => setProjects(rows.filter((p) => p.id !== projectId)))
      .catch((err) => setError(err.message))
      .finally(() => setLoadingProjects(false))
  }, [projectId])

  async function handleSubmit(event) {
    event.preventDefault()
    if (!sourceProjectId) return
    setCopying(true)
    setError('')
    try {
      await tasksApi.copyTasksFrom(projectId, sourceProjectId)
      onCopied()
    } catch (err) {
      setError(err.message)
    } finally {
      setCopying(false)
    }
  }

  return (
    <Modal title={t('Copiar estrutura de outro projeto')} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          {t(
            'Copia WBS/EAP, descrição, duração, horas, tipo, predecessoras (com tipo de atraso) e marcos de todas as tarefas do projeto escolhido — sem nenhum recurso alocado. As datas planejadas são recalculadas a partir do início deste projeto.',
          )}
        </p>
        <FormField label={t('Projeto de origem')} required>
          <Select required value={sourceProjectId} onChange={(event) => setSourceProjectId(event.target.value)} disabled={loadingProjects}>
            <option value="">{t('Selecione…')}</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.code} — {project.name}
              </option>
            ))}
          </Select>
        </FormField>
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="submit" disabled={copying || !sourceProjectId}>
            {copying ? t('Copiando…') : t('Copiar estrutura')}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

/** "Aplicar grupo de tarefas" (pedido do usuário) — cria uma nova tarefa
 * com o NOME do Grupo de Tarefas escolhido (cadastrado em /task-groups,
 * ver TaskGroupsPage) como filha da tarefa `task`, e clona a árvore de
 * itens do grupo como filhas dessa nova tarefa — pra acelerar a criação
 * de estruturas parecidas dentro de um projeto já existente, deixando
 * claro de qual grupo cada "galho" da EAP veio (pedido do usuário depois
 * de ver a primeira versão: "o Agrupador precisa ser uma tarefa também, e
 * as subtarefas dele vêm como filhas do [grupo]"). Ver
 * services.apply_task_group_to_task no backend pro que exatamente é
 * criado/clonado (sem data/recurso/dependência) e `recalculate_wbs`,
 * rodado logo em seguida, pro WBS/EAP renumerar com os nós novos. */
function ApplyTaskGroupModal({ task, onClose, onApplied }) {
  const { t } = useLanguage()
  const [groups, setGroups] = useState([])
  const [taskGroupId, setTaskGroupId] = useState('')
  const [loadingGroups, setLoadingGroups] = useState(true)
  const [applying, setApplying] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    taskGroupsApi
      .listTaskGroups()
      .then(setGroups)
      .catch((err) => setError(err.message))
      .finally(() => setLoadingGroups(false))
  }, [])

  async function handleSubmit(event) {
    event.preventDefault()
    if (!taskGroupId) return
    setApplying(true)
    setError('')
    try {
      await tasksApi.applyTaskGroup(task.id, taskGroupId)
      onApplied()
    } catch (err) {
      setError(err.message)
    } finally {
      setApplying(false)
    }
  }

  return (
    <Modal title={`${t('Aplicar grupo de tarefas')} — ${task.wbs_code} ${task.name}`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          {t('O grupo escolhido entra como uma nova tarefa-filha desta tarefa, com as tarefas do grupo como filhas dela. Sem datas, recursos alocados nem dependências — ajuste isso depois, se precisar.')}
        </p>
        <FormField label={t('Grupo de tarefas')} required>
          <Select required value={taskGroupId} onChange={(event) => setTaskGroupId(event.target.value)} disabled={loadingGroups}>
            <option value="">{t('Selecione…')}</option>
            {groups.map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
          </Select>
        </FormField>
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="submit" disabled={applying || !taskGroupId}>
            {applying ? t('Aplicando…') : t('Aplicar')}
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

/** Linhas realmente visíveis de uma árvore já achatada (buildOrderedTasks)
 * depois de remover a descendência de toda tarefa-pai recolhida — mesma
 * lógica de "Expandir/recolher" (+/-, estilo MS Project) reusada pela aba
 * Tarefas e pelo Gantt. */
function filterCollapsedTasks(orderedTasks, collapsedTaskIds) {
  if (collapsedTaskIds.size === 0) return orderedTasks
  const visible = []
  let skipFromDepth = null
  for (const task of orderedTasks) {
    if (skipFromDepth !== null) {
      if (task.depth > skipFromDepth) continue
      skipFromDepth = null
    }
    visible.push(task)
    if (collapsedTaskIds.has(task.id)) skipFromDepth = task.depth
  }
  return visible
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
  const { t } = useLanguage()
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
    <Modal title={t('Colunas da grade de tarefas')} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          {t('Escolha quais colunas aparecem e em que ordem — WBS, nome da tarefa e as ações da linha ficam sempre fixas nas pontas.')}
        </p>
        <ul className="divide-y divide-[var(--border)] rounded-lg border border-[var(--border)]">
          {draftOrder.map((key, index) => (
            <li key={key} className="flex items-center gap-3 px-3 py-2">
              <label className="flex flex-1 items-center gap-2 text-sm text-[var(--text-primary)]">
                <input type="checkbox" checked={!draftHidden.has(key)} onChange={() => toggle(key)} />
                {t(TASK_COLUMN_LABELS[key])}
              </label>
              <div className="flex gap-1">
                <button
                  type="button"
                  disabled={index === 0}
                  onClick={() => move(index, -1)}
                  className="rounded px-1.5 py-0.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--page)] disabled:opacity-30"
                  title={t('Mover para cima')}
                >
                  ↑
                </button>
                <button
                  type="button"
                  disabled={index === draftOrder.length - 1}
                  onClick={() => move(index, 1)}
                  className="rounded px-1.5 py-0.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--page)] disabled:opacity-30"
                  title={t('Mover para baixo')}
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
            {t('Restaurar padrão')}
          </Button>
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              {t('Cancelar')}
            </Button>
            <Button type="button" onClick={() => onSave({ order: draftOrder, hidden: [...draftHidden] })}>
              {t('Salvar')}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  )
}

/** Confirmação antes de marcar TODAS as tarefas elegíveis do projeto como
 * "Em andamento" de uma vez (pedido do usuário). Só afeta Não
 * iniciada/Atrasada — Concluída e Encerrada (desativada) ficam como
 * estavam, pra não desfazer um trabalho já fechado (decisão confirmada
 * com o usuário). Sem endpoint de bulk update no backend: PATCH um a um,
 * mesmo padrão já usado em ServiceOrdersPage.handleBulkStatus. */
function StartAllTasksConfirmModal({ count, onClose, onConfirm }) {
  const { t } = useLanguage()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleConfirm() {
    setSaving(true)
    setError('')
    try {
      await onConfirm()
      onClose()
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  return (
    <Modal title={t('Marcar todas como Em andamento?')} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          {t(
            'Muda {n} tarefa(s) Não iniciada/Atrasada para Em andamento. Tarefas Concluídas ou Encerradas não são afetadas.',
            { n: count },
          )}
        </p>
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="button" disabled={saving} onClick={handleConfirm}>
            {saving ? t('Atualizando…') : t('Confirmar')}
          </Button>
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
  const { t } = useLanguage()
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
    <Modal title={t('Apagar tarefa')} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          {t('Tem certeza que quer apagar')} <span className="font-medium text-[var(--text-primary)]">{task.wbs_code} {task.name}</span>?{' '}
          {t('Essa ação não pode ser desfeita.')}
        </p>
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="button" variant="danger" disabled={deleting} onClick={handleDelete}>
            {deleting ? t('Apagando…') : t('Apagar')}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

function TasksTab({ projectId, canWrite, onTaskCreated }) {
  const { labels, t } = useLanguage()
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
  const [applyingGroupToTask, setApplyingGroupToTask] = useState(null)
  const [showBaselineModal, setShowBaselineModal] = useState(false)
  const [showColumnsModal, setShowColumnsModal] = useState(false)
  const [showCopyTasksModal, setShowCopyTasksModal] = useState(false)
  const [showStartAllModal, setShowStartAllModal] = useState(false)
  const [columnPrefs, setColumnPrefs] = useState(loadTaskColumnPrefs)
  // Expandir/recolher tarefas-pai (+ -, estilo MS Project) — só visual, não
  // persiste entre sessões (reabrir a tela sempre mostra tudo expandido).
  const [collapsedTaskIds, setCollapsedTaskIds] = useState(() => new Set())

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
  // Tarefa "pai" = tem ao menos uma outra tarefa apontando pra ela via
  // parent_task_id — calculado direto da lista (não de orderedTasks) pra não
  // depender da árvore já estar montada/ordenada.
  const parentTaskIds = useMemo(
    () => new Set((schedule?.tasks || []).map((t) => t.parent_task_id).filter(Boolean)),
    [schedule],
  )
  // Linhas realmente mostradas na grade — orderedTasks (a árvore completa,
  // em ordem de exibição) menos a descendência de qualquer tarefa-pai
  // recolhida. orderedTasks continua intacto (usado por outros lugares,
  // como os seletores de pai/predecessora, que precisam enxergar tudo
  // independente do que está recolhido na grade).
  const visibleTasks = useMemo(() => filterCollapsedTasks(orderedTasks, collapsedTaskIds), [orderedTasks, collapsedTaskIds])
  const startEligibleCount = useMemo(
    () => (schedule?.tasks || []).filter((t) => t.status === 'NOT_STARTED' || t.status === 'DELAYED').length,
    [schedule],
  )

  function toggleTaskCollapsed(taskId) {
    setCollapsedTaskIds((prev) => {
      const next = new Set(prev)
      if (next.has(taskId)) next.delete(taskId)
      else next.add(taskId)
      return next
    })
  }

  function expandAllTasks() {
    setCollapsedTaskIds(new Set())
  }

  function collapseAllTasks() {
    setCollapsedTaskIds(new Set(parentTaskIds))
  }
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
    return owner ? owner.name : resourceFunctionLevelLabel(resource, labels) || '—'
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
    withBusy(t('Atualizando data de status…'), () => projectsApi.updateProject(projectId, { status_date: statusDateInput || null }))
  }

  /** "Ativar/Desativar tarefa" (pedido do usuário) — atalho na própria
   * linha da grade pra alternar o status CLOSED sem abrir o modal de
   * edição inteiro. Reativar sempre volta para NOT_STARTED (não há como
   * saber qual era o status anterior sem guardar um campo à parte) — quem
   * precisar de outro status ajusta depois pelo modal de edição normal. */
  function handleToggleTaskActive(task) {
    const nextStatus = task.status === 'CLOSED' ? 'NOT_STARTED' : 'CLOSED'
    withBusy(nextStatus === 'CLOSED' ? t('Desativando tarefa…') : t('Ativando tarefa…'), () =>
      tasksApi.updateTask(task.id, { status: nextStatus }),
    )
  }

  /** "Marcar todas como Em andamento" (pedido do usuário) — só as tarefas
   * Não iniciada/Atrasada entram; Concluída/Encerrada ficam como estavam
   * (decisão confirmada com o usuário). PATCH um a um (não existe bulk
   * update no backend) — deixa o erro propagar pro catch do próprio modal
   * de confirmação (StartAllTasksConfirmModal), em vez de usar withBusy
   * (que engole o erro em setError e fecharia o modal mesmo numa falha). */
  async function handleStartAllTasks() {
    const eligible = (schedule?.tasks || []).filter((t) => t.status === 'NOT_STARTED' || t.status === 'DELAYED')
    for (const task of eligible) {
      await tasksApi.updateTask(task.id, { status: 'IN_PROGRESS' })
    }
    loadSchedule()
  }

  async function handleExport() {
    setBusyMessage(t('Gerando planilha…'))
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

  function handleTasksCopied() {
    setShowCopyTasksModal(false)
    loadSchedule()
    onTaskCreated?.()
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
      header: t('Duração'),
      align: 'right',
      render: (row) => `${formatNumber(row.rollup_duration_days ?? row.duration_days)} d`,
    },
    estimated_hours: {
      key: 'estimated_hours',
      header: t('Trabalho'),
      align: 'right',
      render: (row) => `${formatNumber(row.rollup_estimated_hours ?? row.estimated_hours)} h`,
    },
    planned_start_date: {
      key: 'planned_start_date',
      header: t('Início'),
      render: (row) => formatDate(row.rollup_start_date ?? row.planned_start_date),
    },
    planned_end_date: {
      key: 'planned_end_date',
      header: t('Fim'),
      render: (row) => formatDate(row.rollup_end_date ?? row.planned_end_date),
    },
    resources: {
      key: 'resources',
      header: t('Recursos'),
      render: (row) => {
        if (row.is_client_activity) {
          const names = (row.client_user_ids || []).map((id) => userById[id]?.name).filter(Boolean)
          return (
            <span>
              <span className="text-[var(--text-muted)]">{t('Cliente')}</span>
              {names.length > 0 ? `: ${names.join(', ')}` : ''}
            </span>
          )
        }
        const assignments = assignmentsByTask[row.id] || []
        if (assignments.length === 0) return <span className="text-[var(--text-muted)]">—</span>
        return assignments.map((a) => resourceLabel(a.resource_id)).join(', ')
      },
    },
    predecessors: {
      key: 'predecessors',
      header: t('Predecessora(s)'),
      render: (row) => {
        const deps = predecessorsBySuccessor.get(row.id) || []
        if (deps.length === 0) return <span className="text-[var(--text-muted)]">{t('Nenhuma')}</span>
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
      header: t('% realizado'),
      align: 'right',
      // Tarefa-pai mostra o agregado das filhas (rollup, ponderado por horas):
      // o backend nunca grava % Realizado numa tarefa-pai.
      render: (row) => formatPercent(row.rollup_progress_percentage ?? row.progress_percentage),
    },
    planned_percent_complete: {
      key: 'planned_percent_complete',
      header: t('% previsto'),
      align: 'right',
      render: (row) => formatPercent(row.planned_percent_complete),
    },
    spi: { key: 'spi', header: 'SPI', align: 'right', render: (row) => formatIndex(row.spi) },
    cpi: { key: 'cpi', header: 'CPI', align: 'right', render: (row) => formatIndex(row.cpi) },
    baseline: {
      key: 'baseline',
      header: t('Linha base (início)'),
      // Só a data de início importa aqui (o que o usuário quer comparar é
      // "começou quando devia?") — fim e trabalho da linha base continuam
      // disponíveis no título/tooltip pra quem precisar, sem poluir a
      // coluna com um intervalo inteiro.
      render: (row) =>
        row.baseline_start_date ? (
          <span
            title={`${t('Fim na linha base:')} ${formatDate(row.baseline_end_date)} · ${t('Trabalho na linha base:')} ${row.baseline_estimated_hours ? `${formatNumber(row.baseline_estimated_hours)}h` : '—'}`}
          >
            {formatDate(row.baseline_start_date)}
          </span>
        ) : (
          <span className="text-[var(--text-muted)]">—</span>
        ),
    },
    status: {
      key: 'status',
      header: t('Status'),
      render: (row) => (
        <StatusPill
          label={labels.TASK_STATUS_LABELS_SHORT[row.status] || row.status}
          title={labels.TASK_STATUS_LABELS[row.status]}
          tone={TASK_STATUS_TONE[row.status]}
        />
      ),
    },
    client_approval_status: {
      key: 'client_approval_status',
      header: t('Aprovação do cliente'),
      render: (row) => (
        <StatusPill
          label={labels.APPROVAL_STATUS_LABELS_SHORT[row.client_approval_status]}
          title={labels.APPROVAL_STATUS_LABELS[row.client_approval_status]}
          tone={APPROVAL_STATUS_TONE[row.client_approval_status]}
        />
      ),
    },
  }

  const columns = [
    { key: 'status_dot', header: '', render: (row) => <StatusDot color={row.status_dot} /> },
    {
      key: 'wbs_code',
      header: 'WBS',
      render: (row) => <span className={parentTaskIds.has(row.id) ? 'font-semibold' : ''}>{row.wbs_code}</span>,
    },
    {
      key: 'name',
      header: t('Nome da tarefa'),
      nowrap: true,
      render: (row) => (
        <span
          style={{ paddingLeft: row.depth * 18 }}
          className={`flex items-center gap-1.5 ${parentTaskIds.has(row.id) ? 'font-semibold' : ''}`}
        >
          {parentTaskIds.has(row.id) ? (
            <button
              type="button"
              onClick={() => toggleTaskCollapsed(row.id)}
              title={collapsedTaskIds.has(row.id) ? t('Expandir') : t('Recolher')}
              className="flex h-4 w-4 shrink-0 items-center justify-center rounded text-[var(--text-muted)] hover:bg-[var(--page)]"
            >
              {collapsedTaskIds.has(row.id) ? <ChevronRightIcon className="h-3 w-3" /> : <ChevronDownIcon className="h-3 w-3" />}
            </button>
          ) : (
            <span className="inline-block h-4 w-4 shrink-0" />
          )}
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
      // Fixa a coluna de ações na borda direita da grade (pedido do
      // usuário: "no item (tarefa), ter um botão para importar
      // agrupadores" — o botão "Aplicar grupo de tarefas" já existia aqui,
      // mas com todas as colunas opcionais ligadas por padrão (Duração,
      // Trabalho, % completado, Início, Fim, Recursos, Predecessora(s), %
      // previsto, SPI, CPI, Linha base, Status, Aprovação do cliente) ele
      // ficava fora da tela, só visível rolando bem pra direita — por isso
      // parecia não existir). Ver `sticky` em components/Table.jsx.
      sticky: true,
      render: (row) => (
        <div className="flex justify-end gap-1.5">
          <IconButton
            icon={PencilIcon}
            label={t('Editar tarefa')}
            onClick={() => {
              setEditingTask(row)
              setShowModal(true)
            }}
          />
          <IconButton icon={MoveIcon} label={t('Mover tarefa')} onClick={() => setMovingTask(row)} />
          <IconButton
            icon={row.status === 'CLOSED' ? CheckIcon : XIcon}
            label={row.status === 'CLOSED' ? t('Ativar tarefa') : t('Desativar tarefa')}
            disabled={Boolean(busyMessage)}
            onClick={() => handleToggleTaskActive(row)}
          />
          <IconButton icon={LayersIcon} label={t('Aplicar grupo de tarefas')} onClick={() => setApplyingGroupToTask(row)} />
          <IconButton icon={TrashIcon} label={t('Apagar tarefa')} variant="danger" onClick={() => setDeletingTask(row)} />
        </div>
      ),
    })
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <form onSubmit={handleApplyStatusDate} className="flex items-end gap-2">
          <FormField label={t('Data de status')} hint={t('Data-base para % previsto e status das tarefas.')}>
            <TextInput type="date" value={statusDateInput} onChange={(event) => setStatusDateInput(event.target.value)} disabled={!canWrite} />
          </FormField>
          {canWrite && (
            <Button type="submit" variant="secondary" disabled={Boolean(busyMessage)}>
              {t('Aplicar')}
            </Button>
          )}
        </form>
        <div className="flex flex-wrap gap-1.5">
          <IconButton icon={ColumnsIcon} label={t('Colunas')} onClick={() => setShowColumnsModal(true)} />
          {parentTaskIds.size > 0 && (
            <>
              <IconButton icon={ChevronDownIcon} label={t('Expandir tudo')} onClick={expandAllTasks} />
              <IconButton icon={ChevronRightIcon} label={t('Recolher tudo')} onClick={collapseAllTasks} />
            </>
          )}
          {/* Exportar não depende de canWrite: é leitura, então também fica
              disponível para perfis externos (CLIENT_PM/CLIENT_USER). */}
          <IconButton icon={DownloadIcon} label={t('Exportar (Excel)')} disabled={Boolean(busyMessage)} onClick={handleExport} />
          {canWrite && !loading && orderedTasks.length === 0 && (
            <IconButton
              icon={CopyIcon}
              label={t('Copiar estrutura de outro projeto')}
              disabled={Boolean(busyMessage)}
              onClick={() => setShowCopyTasksModal(true)}
            />
          )}
          {canWrite && (
            <>
              <IconButton icon={FlagIcon} label={t('Salvar linha de base')} disabled={Boolean(busyMessage)} onClick={() => setShowBaselineModal(true)} />
              <IconButton
                icon={HashIcon}
                label={t('Recalcular WBS/EAP')}
                disabled={Boolean(busyMessage)}
                onClick={() => withBusy(t('Recalculando WBS/EAP…'), () => tasksApi.recalculateWbs(projectId))}
              />
              <IconButton
                icon={RefreshIcon}
                label={t('Recalcular tudo')}
                disabled={Boolean(busyMessage)}
                onClick={() => withBusy(t('Recalculando datas do projeto…'), () => tasksApi.rescheduleProject(projectId))}
              />
              <IconButton
                icon={ClockIcon}
                label={t('Marcar todas como Em andamento')}
                disabled={Boolean(busyMessage) || startEligibleCount === 0}
                onClick={() => setShowStartAllModal(true)}
              />
              <IconButton
                icon={PlusIcon}
                label={t('Nova tarefa')}
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
          <Table columns={columns} rows={visibleTasks} getRowKey={(row) => row.id} emptyMessage={t('Nenhuma tarefa cadastrada ainda.')} dense />
        </Card>
      )}

      {showBaselineModal && <BaselineModal projectId={projectId} onClose={() => setShowBaselineModal(false)} onSaved={handleBaselineSaved} />}

      {showCopyTasksModal && (
        <CopyTasksModal projectId={projectId} onClose={() => setShowCopyTasksModal(false)} onCopied={handleTasksCopied} />
      )}

      {applyingGroupToTask && (
        <ApplyTaskGroupModal
          task={applyingGroupToTask}
          onClose={() => setApplyingGroupToTask(null)}
          onApplied={() => {
            setApplyingGroupToTask(null)
            loadSchedule()
          }}
        />
      )}

      {showStartAllModal && (
        <StartAllTasksConfirmModal count={startEligibleCount} onClose={() => setShowStartAllModal(false)} onConfirm={handleStartAllTasks} />
      )}

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
  // "Nível mínimo" exigido pra executar a tarefa (pedido do usuário,
  // "melhorias parte 4") — default 1 = "qualquer nível serve" (mesmo
  // default do backend, ver schemas.TaskCreate.min_level).
  min_level: 1,
  // Onde a tarefa pode ser executada (pedido do usuário, "melhorias parte
  // 5") — default BOTH ("Ambos"), mesmo default do backend.
  modality: 'BOTH',
  // "Atividade do cliente": executada por usuários do cliente do projeto
  // (sem Nível mínimo nem Recurso alocado).
  is_client_activity: false,
}

/** Sugestão de Código WBS pra "Nova tarefa" — mesma convenção de
 * services.recalculate_wbs (índice sequencial dentro do escopo do pai,
 * "1", "1.1", "1.2", "2"...): próximo índice = nº de irmãs já existentes
 * sob esse pai + 1. Só um PONTO DE PARTIDA editável (o campo continua
 * obrigatório e digitável) — se a EAP tiver buracos (por exclusão de
 * tarefa, por exemplo) o usuário ainda pode ajustar à mão, ou usar
 * "Recalcular WBS/EAP" depois pra renumerar tudo de vez. */
function suggestWbsCode(allTasks, parentId) {
  const parent = parentId ? allTasks.find((t) => t.id === parentId) : null
  const siblings = allTasks.filter((t) => (t.parent_task_id || 'root') === (parentId || 'root'))
  const nextIndex = siblings.length + 1
  return parent ? `${parent.wbs_code}.${nextIndex}` : `${nextIndex}`
}

function TaskFormModal({ projectId, task, allTasks, resources, resourceLabel, initialDependencies, initialAssignments, onClose, onSaved }) {
  const { labels, t } = useLanguage()
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
          min_level: task.min_level,
          modality: task.modality,
          is_client_activity: Boolean(task.is_client_activity),
        }
      : { ...EMPTY_TASK_FORM, wbs_code: suggestWbsCode(allTasks, '') },
  )
  // Qual dos dois campos do par Duração/Trabalho o usuário editou por
  // último — decide o que vai no payload (ver services.apply_effort_driven:
  // informar um recalcula o outro; os dois nunca vão juntos).
  const [effortField, setEffortField] = useState(null)
  // Usuário já mexeu no Código WBS manualmente? Enquanto não mexer, trocar
  // a Tarefa pai (só existe em "Nova tarefa") continua atualizando a
  // sugestão automaticamente; depois que ele digita algo, o valor dele
  // nunca mais é sobrescrito (mesmo trocando o pai de novo).
  const [wbsTouched, setWbsTouched] = useState(false)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const [dependencies, setDependencies] = useState(initialDependencies)
  const [assignments, setAssignments] = useState(initialAssignments)
  const [depForm, setDepForm] = useState({ predecessor_task_id: '', dependency_type: 'FS', lag_days: '0' })
  const [assignForm, setAssignForm] = useState({ resource_id: '', allocated_hours: '' })
  // "Atividade do cliente": candidatos (usuários do cliente do projeto) e
  // seleção. Diferente de Recursos alocados, a seleção só é gravada no
  // "Salvar" (syncClientUsers) — o backend só aceita usuário do cliente
  // numa tarefa que JÁ está marcada como atividade do cliente, e a marca em
  // si só é gravada no Salvar.
  const [clientCandidates, setClientCandidates] = useState([])
  const [clientUserIds, setClientUserIds] = useState(() => (isEdit ? task.client_user_ids || [] : []))
  const [persistedClientIds, setPersistedClientIds] = useState(() => (isEdit ? task.client_user_ids || [] : []))
  const [clientUserSelect, setClientUserSelect] = useState('')
  useEffect(() => {
    tasksApi
      .listProjectClientUsers(projectId)
      .then(setClientCandidates)
      .catch(() => setClientCandidates([]))
  }, [projectId])
  const [depError, setDepError] = useState('')
  const [assignError, setAssignError] = useState('')
  // "Nova tarefa": ainda não existe task.id quando o usuário monta
  // predecessoras/recursos, então cada item entra como rascunho local (id
  // temporário prefixado "draft-") e só vira registro de verdade na API
  // dentro de handleSubmit, logo depois que a tarefa em si é criada.
  // created_task_id guarda o id da tarefa assim que a criação (o primeiro
  // passo de handleSubmit) tiver sucesso — existe pra cobrir o caso de uma
  // falha no meio da sequência de chamadas (ex.: anexar um recurso dá
  // erro): reenviar o formulário não tenta criar a tarefa de novo (isso
  // duplicaria), só retoma de onde parou, persistindo os rascunhos que
  // ainda não viraram registro real.
  const [createdTaskId, setCreatedTaskId] = useState(null)

  function isDraftId(id) {
    return typeof id === 'string' && id.startsWith('draft-')
  }

  function makeDraftId() {
    return `draft-${Date.now()}-${Math.random().toString(36).slice(2)}`
  }

  function updateField(field) {
    return (event) => {
      const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
      setForm((prev) => {
        const next = { ...prev, [field]: value }
        // Só em "Nova tarefa" (isEdit trava o Código WBS, ver campo abaixo)
        // e só enquanto o usuário não tiver digitado nada nele ainda.
        if (!isEdit && field === 'parent_task_id' && !wbsTouched) {
          next.wbs_code = suggestWbsCode(allTasks, value)
        }
        return next
      })
      if (field === 'is_client_activity' && !value) setClientUserIds([])
      if (field === 'duration_days') setEffortField('duration')
      if (field === 'estimated_hours') setEffortField('hours')
      if (field === 'wbs_code') setWbsTouched(true)
    }
  }

  // Grava no backend a diferença entre a seleção atual de usuários do
  // cliente e o que já estava gravado. Só roda em atividade do cliente —
  // desmarcar a opção faz o próprio backend soltar os usuários (PATCH).
  async function syncClientUsers(taskId) {
    if (!form.is_client_activity) return
    const toAdd = clientUserIds.filter((id) => !persistedClientIds.includes(id))
    const toRemove = persistedClientIds.filter((id) => !clientUserIds.includes(id))
    for (const id of toAdd) {
      await tasksApi.assignClientUser(taskId, { user_id: id })
      setPersistedClientIds((prev) => [...prev, id])
    }
    for (const id of toRemove) {
      await tasksApi.removeClientUser(taskId, id)
      setPersistedClientIds((prev) => prev.filter((x) => x !== id))
    }
  }

  function clientUserName(id) {
    return clientCandidates.find((u) => u.id === id)?.name || '—'
  }

  function handleAddClientUser() {
    if (!clientUserSelect) return
    setClientUserIds((prev) => (prev.includes(clientUserSelect) ? prev : [...prev, clientUserSelect]))
    setClientUserSelect('')
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
          // Fim planejado nunca vai no payload — o backend sempre recalcula
          // a partir de Início + Duração (ver routers/tasks.py
          // update_task), então mandar o valor do formulário só arriscava
          // "travar" um Fim desatualizado ou zerá-lo por engano quando o
          // campo ainda estava vazio (era exatamente o bug relatado).
          progress_percentage: form.progress_percentage,
          status: form.status,
          is_milestone: form.is_milestone,
          notes: form.notes || null,
          min_level: form.is_client_activity ? 1 : Number(form.min_level),
          modality: form.modality,
          is_client_activity: form.is_client_activity,
        }
        if (effortField === 'duration') payload.duration_days = form.duration_days
        if (effortField === 'hours') payload.estimated_hours = form.estimated_hours
        await tasksApi.updateTask(task.id, payload)
        await syncClientUsers(task.id)
      } else {
        let newTaskId = createdTaskId
        if (!newTaskId) {
          const payload = {
            name: form.name,
            wbs_code: form.wbs_code,
            task_type: form.task_type,
            is_milestone: form.is_milestone,
            min_level: form.is_client_activity ? 1 : Number(form.min_level),
            modality: form.modality,
            is_client_activity: form.is_client_activity,
          }
          if (form.notes) payload.notes = form.notes
          if (form.parent_task_id) payload.parent_task_id = form.parent_task_id
          if (form.planned_start_date) payload.planned_start_date = form.planned_start_date
          // Fim planejado não vai no payload de criação pelo mesmo motivo do
          // update acima — sempre calculado no backend a partir de Início +
          // Duração (ver routers/tasks.py create_task).
          if (effortField === 'duration' && form.duration_days) payload.duration_days = form.duration_days
          if (effortField === 'hours' && form.estimated_hours) payload.estimated_hours = form.estimated_hours
          const created = await tasksApi.createTask(projectId, payload)
          newTaskId = created.id
          setCreatedTaskId(created.id)
        }
        // Predecessoras e recursos escolhidos antes de a tarefa existir
        // (rascunhos locais, id "draft-...") são persistidos agora, um a
        // um — os que já viraram registro real (retomando depois de uma
        // falha parcial) são pulados.
        for (const dep of dependencies.filter((d) => isDraftId(d.id))) {
          const createdDep = await tasksApi.createDependency({
            predecessor_task_id: dep.predecessor_task_id,
            successor_task_id: newTaskId,
            dependency_type: dep.dependency_type,
            lag_days: dep.lag_days,
          })
          setDependencies((prev) => prev.map((d) => (d.id === dep.id ? createdDep : d)))
        }
        for (const a of assignments.filter((x) => isDraftId(x.id))) {
          const createdAssignment = await tasksApi.assignResource(newTaskId, {
            resource_id: a.resource_id,
            allocated_hours: a.allocated_hours,
          })
          setAssignments((prev) => prev.map((x) => (x.id === a.id ? createdAssignment : x)))
        }
        await syncClientUsers(newTaskId)
      }
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  // Id real da tarefa, se já existir (edição — ou "Nova tarefa" depois que
  // handleSubmit já criou a tarefa numa tentativa anterior). Enquanto for
  // null, Predecessoras/Recursos ficam em rascunho local (ver
  // makeDraftId/isDraftId) até a tarefa ser efetivamente criada.
  const activeTaskId = task?.id || createdTaskId

  async function handleAddDependency(event) {
    event.preventDefault()
    setDepError('')
    if (!depForm.predecessor_task_id) {
      setDepError(t('Selecione a tarefa predecessora.'))
      return
    }
    const lagDays = Number(depForm.lag_days) || 0
    if (!activeTaskId) {
      setDependencies((prev) => [
        ...prev,
        {
          id: makeDraftId(),
          predecessor_task_id: depForm.predecessor_task_id,
          dependency_type: depForm.dependency_type,
          lag_days: lagDays,
        },
      ])
      setDepForm({ predecessor_task_id: '', dependency_type: 'FS', lag_days: '0' })
      return
    }
    try {
      const created = await tasksApi.createDependency({
        predecessor_task_id: depForm.predecessor_task_id,
        successor_task_id: activeTaskId,
        dependency_type: depForm.dependency_type,
        lag_days: lagDays,
      })
      setDependencies((prev) => [...prev, created])
      setDepForm({ predecessor_task_id: '', dependency_type: 'FS', lag_days: '0' })
    } catch (err) {
      setDepError(err.message)
    }
  }

  async function handleRemoveDependency(dependencyId) {
    setDepError('')
    if (isDraftId(dependencyId)) {
      setDependencies((prev) => prev.filter((dep) => dep.id !== dependencyId))
      return
    }
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
      setAssignError(t('Selecione o recurso e informe as horas alocadas.'))
      return
    }
    if (!activeTaskId) {
      setAssignments((prev) => [
        ...prev,
        {
          id: makeDraftId(),
          resource_id: assignForm.resource_id,
          allocated_hours: assignForm.allocated_hours,
        },
      ])
      setAssignForm({ resource_id: '', allocated_hours: '' })
      return
    }
    try {
      const created = await tasksApi.assignResource(activeTaskId, {
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
    if (isDraftId(assignmentId)) {
      setAssignments((prev) => prev.filter((a) => a.id !== assignmentId))
      return
    }
    try {
      await tasksApi.removeAssignment(activeTaskId, assignmentId)
      setAssignments((prev) => prev.filter((a) => a.id !== assignmentId))
    } catch (err) {
      setAssignError(err.message)
    }
  }

  // Tarefa-pai pode ser predecessora (vale o intervalo das filhas), mas não da
  // própria tarefa-filha nem do contrário — o backend recusa (dependência
  // circular), então esses itens nem aparecem na lista.
  const taskParentById = new Map(allTasks.map((t) => [t.id, t.parent_task_id]))
  function ancestorIdsOf(taskId) {
    const ids = new Set()
    let current = taskParentById.get(taskId)
    while (current && !ids.has(current)) {
      ids.add(current)
      current = taskParentById.get(current)
    }
    return ids
  }
  const ownAncestorIds = task ? ancestorIdsOf(task.id) : new Set(form.parent_task_id ? [form.parent_task_id, ...ancestorIdsOf(form.parent_task_id)] : [])
  const predecessorOptions = allTasks.filter(
    (t) => t.id !== task?.id && !ownAncestorIds.has(t.id) && !(task && ancestorIdsOf(t.id).has(task.id)),
  )
  const assignedResourceIds = new Set(assignments.map((a) => a.resource_id))
  // "Nível mínimo" da tarefa (pedido do usuário, "melhorias parte 4") só
  // FILTRA este seletor — um recurso sem nível definido continua aparecendo
  // (ainda não dá pra saber se ele cumpre o mínimo ou não), e nada é
  // bloqueado no backend. Number(form.min_level) porque o <Select> guarda o
  // valor como string.
  const minLevel = Number(form.min_level) || 1
  const resourceOptions = resources.filter((r) => !assignedResourceIds.has(r.id) && (!r.level || r.level >= minLevel))

  return (
    <Modal title={isEdit ? `${t('Editar tarefa')} — ${task.wbs_code} ${task.name}` : t('Nova tarefa')} onClose={onClose} wide>
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Ordem dos campos pedida pelo usuário: Nome, Tarefa pai, WBS/EAP,
         * Tipo (na edição, "Tarefa pai" não se aplica — trocar de pai é a
         * ação "Mover tarefa" à parte — então o Status ocupa o mesmo lugar,
         * mantendo o layout consistente entre criar/editar). */}
        <div className="grid grid-cols-2 gap-4">
          <FormField label={t('Nome')} required>
            <TextInput required value={form.name} onChange={updateField('name')} />
          </FormField>
          {!isEdit ? (
            <FormField label={t('Tarefa pai')} hint={t('Deixe em branco para uma tarefa de topo (raiz).')}>
              <Select value={form.parent_task_id} onChange={updateField('parent_task_id')}>
                <option value="">{t('Nenhuma (raiz)')}</option>
                {allTasks.map((t) => (
                  <option key={t.id} value={t.id}>
                    {'—'.repeat(t.depth)} {t.wbs_code} {t.name}
                  </option>
                ))}
              </Select>
            </FormField>
          ) : (
            <FormField label={t('Status')}>
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
          <FormField
            label={t('Código WBS')}
            required
            hint={isEdit ? t('Use "Recalcular WBS/EAP" para renumerar.') : t('Sugerido a partir da Tarefa pai — pode editar.')}
          >
            <TextInput required disabled={isEdit} value={form.wbs_code} onChange={updateField('wbs_code')} />
          </FormField>
          <FormField label={t('Tipo')} required>
            <Select required value={form.task_type} onChange={updateField('task_type')}>
              <option value="CONSULTING">{t('Consultoria')}</option>
              <option value="MANAGEMENT">{t('Gestão')}</option>
            </Select>
          </FormField>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <FormField label={t('Duração (dias)')} hint={t('Editar recalcula o Trabalho.')}>
            {/* step="0.5" rejeitava qualquer valor com centavos que não caísse
                na grade min + n*0.5 (ex.: 2.00 ou 1.75) — o navegador acusava
                "valor inválido" mesmo sendo um número perfeitamente válido
                para o campo. step="0.01" aceita duas casas decimais, que é a
                precisão que Duração/Trabalho já usam no backend (Decimal). */}
            <TextInput type="number" min="0.01" step="0.01" value={form.duration_days} onChange={updateField('duration_days')} placeholder={t('Ex.: 2')} />
          </FormField>
          <FormField label={t('Trabalho (horas)')} hint={t('Editar recalcula a Duração.')}>
            <TextInput type="number" min="0" step="0.01" value={form.estimated_hours} onChange={updateField('estimated_hours')} placeholder={t('Ex.: 16')} />
          </FormField>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <FormField label={t('Início planejado')} hint={t('Sem predecessora, esta data fica manual.')}>
            <TextInput type="date" value={form.planned_start_date} onChange={updateField('planned_start_date')} />
          </FormField>
          <FormField label={t('Fim planejado')} hint={t('Calculado automaticamente (Início + Duração).')}>
            <TextInput type="date" disabled value={form.planned_end_date} onChange={updateField('planned_end_date')} />
          </FormField>
        </div>
        {isEdit && (
          <FormField label={t('% Realizado')}>
            <TextInput type="number" min="0" max="100" step="1" value={form.progress_percentage} onChange={updateField('progress_percentage')} />
          </FormField>
        )}
        <div className="grid grid-cols-2 gap-4">
          {!form.is_client_activity && (
            <FormField
              label={t('Nível mínimo')}
              hint={t('Filtra o seletor de Recurso abaixo — recursos sem nível definido continuam aparecendo.')}
            >
              <Select value={form.min_level} onChange={updateField('min_level')}>
                {Object.entries(labels.RESOURCE_LEVEL_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </FormField>
          )}
          <FormField label={t('Modalidade')} hint={t('Onde a tarefa pode ser executada.')}>
            <Select value={form.modality} onChange={updateField('modality')}>
              {Object.entries(labels.TASK_MODALITY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </FormField>
        </div>
        <FormField label={t('Observações')}>
          <TextArea rows={2} value={form.notes} onChange={updateField('notes')} />
        </FormField>
        <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <input type="checkbox" checked={form.is_milestone} onChange={updateField('is_milestone')} />
          {t('É um marco (milestone)')}
        </label>
        <div>
          <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
            <input
              type="checkbox"
              checked={form.is_client_activity}
              disabled={!form.is_client_activity && assignments.length > 0}
              onChange={updateField('is_client_activity')}
            />
            {t('Atividade do cliente')}
          </label>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            {!form.is_client_activity && assignments.length > 0
              ? t('Remova os recursos alocados abaixo para marcar como atividade do cliente.')
              : t('Executada por pessoas do cliente: sem Nível mínimo e sem Recurso — o responsável é escolhido entre os usuários do cliente do projeto.')}
          </p>
        </div>

        <ErrorBanner message={error} />

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? t('Salvando…') : t('Salvar')}
          </Button>
        </div>
      </form>

      <div className="mt-6 space-y-5 border-t border-[var(--border)] pt-5">
          {!isEdit && (
            <p className="text-xs text-[var(--text-muted)]">
              {t('Predecessoras e recursos escolhidos aqui são gravados junto com a tarefa ao clicar em "Salvar".')}
            </p>
          )}
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{t('Predecessoras')}</h3>
            {dependencies.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">{t('Nenhuma — a data de início desta tarefa fica manual.')}</p>
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
                        {t('Remover')}
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
            <form onSubmit={handleAddDependency} className="mt-3 flex flex-wrap items-end gap-2">
              <FormField label={t('Nova predecessora')}>
                <Select value={depForm.predecessor_task_id} onChange={(event) => setDepForm((prev) => ({ ...prev, predecessor_task_id: event.target.value }))}>
                  <option value="">{t('Selecione…')}</option>
                  {predecessorOptions.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.wbs_code} — {t.name}
                    </option>
                  ))}
                </Select>
              </FormField>
              <FormField label={t('Tipo')}>
                <Select value={depForm.dependency_type} onChange={(event) => setDepForm((prev) => ({ ...prev, dependency_type: event.target.value }))}>
                  {Object.entries(labels.DEPENDENCY_TYPE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </Select>
              </FormField>
              <FormField label={t('Atraso (dias)')}>
                <TextInput
                  type="number"
                  step="1"
                  value={depForm.lag_days}
                  onChange={(event) => setDepForm((prev) => ({ ...prev, lag_days: event.target.value }))}
                  className="w-24"
                />
              </FormField>
              <Button type="submit" variant="secondary">
                {t('Adicionar')}
              </Button>
            </form>
            <ErrorBanner message={depError} />
          </div>

          {form.is_client_activity ? (
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{t('Usuários do cliente')}</h3>
            {clientUserIds.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">{t('Nenhum usuário do cliente selecionado.')}</p>
            ) : (
              <ul className="space-y-1.5">
                {clientUserIds.map((id) => (
                  <li key={id} className="flex items-center justify-between rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm">
                    <span>{clientUserName(id)}</span>
                    <button
                      type="button"
                      onClick={() => setClientUserIds((prev) => prev.filter((x) => x !== id))}
                      className="text-xs text-[var(--status-critical)] hover:underline"
                    >
                      {t('Remover')}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-3 flex flex-wrap items-end gap-2">
              <FormField label={t('Usuário do cliente')}>
                <Select value={clientUserSelect} onChange={(event) => setClientUserSelect(event.target.value)}>
                  <option value="">{t('Selecione…')}</option>
                  {clientCandidates
                    .filter((u) => !clientUserIds.includes(u.id))
                    .map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name}
                      </option>
                    ))}
                </Select>
              </FormField>
              <Button type="button" variant="secondary" onClick={handleAddClientUser}>
                {t('Adicionar')}
              </Button>
            </div>
            {clientCandidates.length === 0 && (
              <p className="mt-2 text-xs text-[var(--text-muted)]">{t('Este cliente ainda não tem usuários ativos cadastrados.')}</p>
            )}
            <p className="mt-2 text-xs text-[var(--text-muted)]">{t('Salvo ao clicar em "Salvar".')}</p>
          </div>
          ) : (
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{t('Recursos alocados')}</h3>
            {assignments.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">{t('Nenhum recurso alocado — o Trabalho usa uma FTE genérica de 8h/dia.')}</p>
            ) : (
              <ul className="space-y-1.5">
                {assignments.map((a) => (
                  <li key={a.id} className="flex items-center justify-between rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm">
                    <span>
                      {resourceLabel(a.resource_id)} · {formatNumber(a.allocated_hours)}h {t('alocadas')}
                    </span>
                    <button type="button" onClick={() => handleRemoveAssignment(a.id)} className="text-xs text-[var(--status-critical)] hover:underline">
                      {t('Remover')}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <form onSubmit={handleAddAssignment} className="mt-3 flex flex-wrap items-end gap-2">
              <FormField label={t('Recurso')}>
                <Select value={assignForm.resource_id} onChange={(event) => setAssignForm((prev) => ({ ...prev, resource_id: event.target.value }))}>
                  <option value="">{t('Selecione…')}</option>
                  {resourceOptions.map((r) => {
                    const functionLevel = resourceFunctionLevelLabel(r, labels)
                    return (
                      <option key={r.id} value={r.id}>
                        {resourceLabel(r.id)}
                        {functionLevel ? ` (${functionLevel})` : ''}
                      </option>
                    )
                  })}
                </Select>
              </FormField>
              <FormField label={t('Horas alocadas')}>
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
                {t('Adicionar')}
              </Button>
            </form>
            <ErrorBanner message={assignError} />
          </div>
          )}
      </div>
    </Modal>
  )
}

function MoveTaskModal({ task, allTasks, onClose, onSaved }) {
  const { t } = useLanguage()
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
    <Modal title={`${t('Mover tarefa')} — ${task.wbs_code} ${task.name}`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField label={t('Nova tarefa pai')} hint={t('Deixe em branco para mover para a raiz do projeto.')}>
          <Select
            value={newParentId}
            onChange={(event) => {
              setNewParentId(event.target.value)
              setBeforeTaskId('')
            }}
          >
            <option value="">{t('Nenhuma (raiz)')}</option>
            {parentOptions.map((t) => (
              <option key={t.id} value={t.id}>
                {'—'.repeat(t.depth)} {t.wbs_code} {t.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label={t('Colocar antes de')} hint={t('Deixe em branco para colocar por último entre as irmãs.')}>
          <Select value={beforeTaskId} onChange={(event) => setBeforeTaskId(event.target.value)}>
            <option value="">{t('Por último')}</option>
            {siblingOptions.map((t) => (
              <option key={t.id} value={t.id}>
                {t.wbs_code} — {t.name}
              </option>
            ))}
          </Select>
        </FormField>
        <p className="text-xs text-[var(--text-muted)]">
          {t('Depois de mover, use "Recalcular WBS/EAP" para renumerar e "Recalcular tudo" se a tarefa tiver predecessoras.')}
        </p>
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? t('Movendo…') : t('Mover')}
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

// Largura MÍNIMA da coluna fixa (WBS + descrição) — a largura real é
// calculada dinamicamente por computeGanttLabelColPx, pelo maior texto entre
// as tarefas visíveis (pedido do usuário: "se puder colocar dinâmico, pelo
// maior tamanho de texto, melhor"), nunca menor que este valor.
const GANTT_LABEL_COL_MIN_PX = 220
// ...e nunca maior que este, pra uma descrição absurdamente longa não tomar
// a tela toda — o texto nesse caso ainda assim só trunca no PNG exportado
// (ganttTruncateForCanvas); na tela, a coluna é sticky e o texto quebra via
// "truncate" normalmente.
const GANTT_LABEL_COL_MAX_PX = 560
const GANTT_DAY_PX = 34
const GANTT_ROW_PX = 30
// Segunda-feira de referência (03/01/2000) só pra achar o índice de semana
// ISO-like de qualquer data por subtração de datas — não é uma data real do
// projeto, é só uma âncora fixa de cálculo.
const GANTT_WEEK_ANCHOR_MS = Date.UTC(2000, 0, 3)
// Um formatador por idioma da interface (não só pt-BR fixo) — senão o
// cabeçalho de mês/ano do Gantt continuava em português mesmo com a
// interface toda em espanhol.
const GANTT_MONTH_YEAR_FORMATTERS = {
  'pt-BR': new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric', timeZone: 'UTC' }),
  es: new Intl.DateTimeFormat('es-ES', { month: 'long', year: 'numeric', timeZone: 'UTC' }),
}
function getGanttMonthYearFormatter(lang) {
  return GANTT_MONTH_YEAR_FORMATTERS[lang] || GANTT_MONTH_YEAR_FORMATTERS['pt-BR']
}

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
function buildGanttLayout(rangeStartDate, rangeEndDate, totalDays, lang) {
  const monthYearFormatter = getGanttMonthYearFormatter(lang)
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
    const label = monthYearFormatter.format(cursor)
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

// Mesmo rótulo "WBS - descrição" (+ sufixo de predecessoras, quando houver)
// usado tanto na coluna fixa da tela quanto no texto desenhado no PNG
// exportado — centralizado aqui pra não divergir entre os dois.
function ganttRowLabel(task, predecessorCount, t) {
  const preds = predecessorCount[task.id] || 0
  let label = `${task.wbs_code} - ${task.name}`
  if (preds > 0) {
    label += ` · ${preds} ${preds > 1 ? t('predecessoras') : t('predecessora')}`
  }
  return label
}

/** Largura da coluna fixa (WBS + descrição) do Gantt, calculada pelo maior
 * texto entre as tarefas visíveis — pedido do usuário pra parar de cortar a
 * descrição. Mede com <canvas> (mesma técnica do export PNG) pra bater com
 * o tamanho real do texto renderizado, respeitando recuo por profundidade e
 * o espaço do botão de expandir/recolher; limitada a um mínimo/máximo
 * razoável (GANTT_LABEL_COL_MIN_PX/MAX_PX). */
function computeGanttLabelColPx(tasks, predecessorCount, parentTaskIds, t) {
  if (typeof document === 'undefined' || tasks.length === 0) return GANTT_LABEL_COL_MIN_PX
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  const TOGGLE_PX = 18 // botão expandir/recolher: h-4 w-4 + mr-0.5
  const RIGHT_PAD_PX = 10 // pr-2 + folga de segurança
  const DEPTH_INDENT_PX = 14 // mesmo valor do paddingLeft: task.depth * 14 no JSX
  let maxPx = 0
  for (const task of tasks) {
    ctx.font = parentTaskIds.has(task.id) ? '600 12px sans-serif' : '12px sans-serif'
    const textPx = ctx.measureText(ganttRowLabel(task, predecessorCount, t)).width
    const rowPx = task.depth * DEPTH_INDENT_PX + TOGGLE_PX + textPx + RIGHT_PAD_PX
    if (rowPx > maxPx) maxPx = rowPx
  }
  return Math.min(GANTT_LABEL_COL_MAX_PX, Math.max(GANTT_LABEL_COL_MIN_PX, Math.ceil(maxPx)))
}

function GanttTab({ projectId, project }) {
  const { t, language } = useLanguage()
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

  // Tarefa "pai" = tem ao menos uma outra tarefa apontando pra ela via
  // parent_task_id (mesmo critério usado na aba Tarefas). Precisa ficar
  // antes dos "return" condicionais abaixo — hooks não podem vir depois.
  const parentTaskIds = useMemo(() => new Set((data?.tasks || []).map((task) => task.parent_task_id).filter(Boolean)), [data])
  // Expandir/recolher tarefas-pai (+ -, estilo MS Project) — mesma lógica
  // da aba Tarefas (buildOrderedTasks/filterCollapsedTasks), reaproveitada
  // aqui. orderedTasks dá a ordem hierárquica + depth; visibleTasks é o que
  // realmente é desenhado (linhas da timeline e do PNG exportado).
  const [collapsedTaskIds, setCollapsedTaskIds] = useState(() => new Set())
  const orderedTasks = useMemo(() => buildOrderedTasks(data?.tasks || []), [data])
  const visibleTasks = useMemo(() => filterCollapsedTasks(orderedTasks, collapsedTaskIds), [orderedTasks, collapsedTaskIds])

  function toggleTaskCollapsed(taskId) {
    setCollapsedTaskIds((prev) => {
      const next = new Set(prev)
      if (next.has(taskId)) next.delete(taskId)
      else next.add(taskId)
      return next
    })
  }

  if (loading) return <Spinner />
  if (error) return <ErrorBanner message={error} />
  if (!data || data.tasks.length === 0) {
    return <p className="text-sm text-[var(--text-muted)]">{t('Nenhuma tarefa cadastrada ainda.')}</p>
  }

  const scheduled = data.tasks.filter((task) => ganttStart(task) && ganttEnd(task))
  if (scheduled.length === 0) {
    return (
      <p className="text-sm text-[var(--text-muted)]">
        {t('Nenhuma tarefa tem datas planejadas ainda — o Gantt aparece assim que houver início/fim planejados.')}
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

  const layout = buildGanttLayout(rangeStartDate, rangeEndDate, totalDays, language)

  const predecessorCount = {}
  for (const dependency of data.dependencies) {
    predecessorCount[dependency.successor_task_id] = (predecessorCount[dependency.successor_task_id] || 0) + 1
  }

  // Coluna "WBS - descrição" dinâmica (pedido do usuário) — recalculada a
  // cada render porque depende do idioma (t) e de quais tarefas estão
  // visíveis (expandir/recolher muda a lista, não só o texto).
  const labelColPx = computeGanttLabelColPx(visibleTasks, predecessorCount, parentTaskIds, t)

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
    const width = labelColPx + layout.totalWidthPx + padX * 2
    const height = headerH + visibleTasks.length * rowH + legendH + padY * 2

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
    const progressGood = resolveGanttColor('var(--status-good)')
    const progressWarning = resolveGanttColor('var(--status-warning)')

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
      ctx.fillText(m.label, labelColPx + m.leftPx + 4, titleH + monthRowH / 2)
    })

    ctx.strokeStyle = border
    ctx.beginPath()
    ctx.moveTo(0, titleH + monthRowH)
    ctx.lineTo(width - padX * 2, titleH + monthRowH)
    ctx.stroke()

    ctx.font = '10px sans-serif'
    layout.units.forEach((u) => {
      const x = labelColPx + u.leftPx
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
    visibleTasks.forEach((task, idx) => {
      const y = headerH + idx * rowH
      const start = ganttStart(task)
      const end = ganttEnd(task)
      const color = resolveGanttColor(TASK_TYPE_COLORS[task.task_type] || 'var(--text-muted)')
      const progress = Math.min(100, Math.max(0, Number(task.rollup_progress_percentage ?? task.progress_percentage) || 0))
      const progressColor = progress >= 100 ? progressGood : progress > 0 ? progressWarning : null

      ctx.strokeStyle = border
      layout.units.forEach((u) => {
        const x = labelColPx + u.leftPx
        ctx.beginPath()
        ctx.moveTo(x, y)
        ctx.lineTo(x, y + rowH)
        ctx.stroke()
      })

      ctx.fillStyle = textSecondary
      ctx.textAlign = 'left'
      // Tarefa-pai em negrito no PNG exportado também, pra bater com o que
      // aparece na tela (ver isParentTask/parentTaskIds no JSX abaixo).
      ctx.font = parentTaskIds.has(task.id) ? 'bold 11px sans-serif' : '11px sans-serif'
      const label = `${task.wbs_code} - ${task.name}`
      ctx.fillText(ganttTruncateForCanvas(ctx, label, labelColPx - 8 - task.depth * 10), task.depth * 10, y + rowH / 2)
      ctx.font = '11px sans-serif'

      if (start && end) {
        const left = labelColPx + layout.pxFromDate(start)
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
          const barY = y + rowH / 2 - 6
          ganttRoundRect(ctx, left, barY, w, 12, 3)
          ctx.fill()
          // % de progresso em outra cor (laranja parcial, verde concluído —
          // pedido do usuário), clipado ao mesmo contorno arredondado da
          // barra pra não "vazar" quadrado pelos cantos.
          if (progressColor) {
            ctx.save()
            ganttRoundRect(ctx, left, barY, w, 12, 3)
            ctx.clip()
            ctx.fillStyle = progressColor
            ctx.fillRect(left, barY, w * (progress / 100), 12)
            ctx.restore()
          }
        }
      }
    })

    const legendY = headerH + visibleTasks.length * rowH + legendH / 2
    ctx.font = '10px sans-serif'
    ctx.textAlign = 'left'
    let lx = 0
    ;[
      { label: t('Consultoria'), color: resolveGanttColor(TASK_TYPE_COLORS.CONSULTING) },
      { label: t('Gestão'), color: resolveGanttColor(TASK_TYPE_COLORS.MANAGEMENT) },
      { label: t('Progresso parcial'), color: progressWarning },
      { label: t('Progresso concluído'), color: progressGood },
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
          <FormField label={t('Início do período exibido')}>
            <TextInput
              type="date"
              value={rangeOverride.start || rangeStartStr}
              onChange={(event) => setRangeOverride((prev) => ({ ...prev, start: event.target.value }))}
            />
          </FormField>
          <FormField label={t('Fim do período exibido')}>
            <TextInput
              type="date"
              value={rangeOverride.end || rangeEndStr}
              onChange={(event) => setRangeOverride((prev) => ({ ...prev, end: event.target.value }))}
            />
          </FormField>
          {hasCustomRange && (
            <Button variant="secondary" onClick={() => setRangeOverride({ start: '', end: '' })}>
              {t('Restaurar período do projeto')}
            </Button>
          )}
        </div>
        <div className="flex gap-1.5">
          {parentTaskIds.size > 0 && (
            <>
              <IconButton icon={ChevronDownIcon} label={t('Expandir tudo')} onClick={() => setCollapsedTaskIds(new Set())} />
              <IconButton
                icon={ChevronRightIcon}
                label={t('Recolher tudo')}
                onClick={() => setCollapsedTaskIds(new Set(parentTaskIds))}
              />
            </>
          )}
          <IconButton icon={DownloadIcon} label={t('Exportar PNG')} onClick={handleExportPng} />
        </div>
      </div>

      <div className="overflow-x-auto">
        <div style={{ width: labelColPx + layout.totalWidthPx }}>
          {/* Régua de mês/ano */}
          <div className="flex">
            <span className="sticky left-0 z-10 shrink-0 bg-[var(--surface)]" style={{ width: labelColPx }} />
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
            <span className="sticky left-0 z-10 shrink-0 bg-[var(--surface)]" style={{ width: labelColPx }} />
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
            {visibleTasks.map((task) => {
              const start = ganttStart(task)
              const end = ganttEnd(task)
              const hasDates = Boolean(start && end)
              const color = TASK_TYPE_COLORS[task.task_type] || 'var(--text-muted)'
              const preds = predecessorCount[task.id] || 0
              const isParentTask = parentTaskIds.has(task.id)
              const progress = Math.min(100, Math.max(0, Number(task.rollup_progress_percentage ?? task.progress_percentage) || 0))
              const progressColor = progress >= 100 ? 'var(--status-good)' : progress > 0 ? 'var(--status-warning)' : null
              return (
                // Sem "items-center" aqui de propósito: com ele, a coluna
                // fixa (sticky) abaixo só ficava tão alta quanto o texto
                // (~16px) dentro de uma linha de 30px, deixando ~7px sem
                // fundo opaco em cima/embaixo — aí, ao rolar a barra
                // horizontal, as linhas de grade e as barras da timeline
                // (que ficam por baixo da coluna fixa) apareciam por essa
                // fresta, dando a impressão de que as semanas "avançavam"
                // sobre a descrição da tarefa. Fixando a altura da linha e
                // da coluna e centralizando o texto com flex, a coluna fixa
                // cobre a linha inteira.
                <div key={task.id} className="flex" style={{ height: GANTT_ROW_PX }}>
                  <span
                    className={`sticky left-0 z-10 flex shrink-0 items-center truncate bg-[var(--surface)] pr-2 text-xs text-[var(--text-secondary)] ${
                      isParentTask ? 'font-semibold' : ''
                    }`}
                    style={{ width: labelColPx, height: GANTT_ROW_PX, paddingLeft: task.depth * 14 }}
                    title={task.name}
                  >
                    {isParentTask ? (
                      <button
                        type="button"
                        onClick={() => toggleTaskCollapsed(task.id)}
                        title={collapsedTaskIds.has(task.id) ? t('Expandir') : t('Recolher')}
                        className="mr-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded text-[var(--text-muted)] hover:bg-[var(--page)]"
                      >
                        {collapsedTaskIds.has(task.id) ? <ChevronRightIcon className="h-3 w-3" /> : <ChevronDownIcon className="h-3 w-3" />}
                      </button>
                    ) : (
                      <span className="mr-0.5 inline-block h-4 w-4 shrink-0" />
                    )}
                    <span className="text-[var(--text-muted)]">{task.wbs_code}</span> - {task.name}
                    {preds > 0 && (
                      <span className="text-[var(--text-muted)]">
                        {' '}
                        · {preds} {preds > 1 ? t('predecessoras') : t('predecessora')}
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
                          title={`${t('Marco:')} ${formatDate(start)}`}
                        />
                      ) : (
                        <span
                          className="absolute top-1/2 h-4 -translate-y-1/2 overflow-hidden rounded"
                          style={{
                            left: layout.pxFromDate(start),
                            width: layout.pxWidthBetween(start, end),
                            backgroundColor: color,
                          }}
                          title={`${formatDate(start)} – ${formatDate(end)} · ${formatPercent(progress)}`}
                        >
                          {/* % de progresso em outra cor (laranja parcial,
                              verde concluído — pedido do usuário), preenchida
                              da esquerda pra direita por cima da cor de tipo
                              da tarefa (que continua visível no restante da
                              barra). */}
                          {progressColor && <span className="block h-full" style={{ width: `${progress}%`, backgroundColor: progressColor }} />}
                        </span>
                      )
                    ) : (
                      <span className="absolute inset-y-0 left-2 flex items-center text-xs text-[var(--text-muted)]">{t('sem datas')}</span>
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
          {t('Consultoria')}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: TASK_TYPE_COLORS.MANAGEMENT }} />
          {t('Gestão')}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rotate-45" style={{ backgroundColor: 'var(--text-muted)' }} />
          {t('Marco')}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: 'var(--status-warning)' }} />
          {t('Progresso parcial')}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: 'var(--status-good)' }} />
          {t('Progresso concluído')}
        </span>
      </div>
    </Card>
  )
}
