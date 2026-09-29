import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import * as reportsApi from '../api/reports'
import * as projectsApi from '../api/projects'
import * as clientsApi from '../api/clients'
import * as usersApi from '../api/users'
import { useAuth } from '../context/AuthContext'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Table from '../components/Table'
import Button from '../components/Button'
import IconButton from '../components/IconButton'
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import StatusPill from '../components/StatusPill'
import { TrashIcon } from '../components/icons'
import { FormField, TextInput, Select } from '../components/FormField'
import ColorListPicker from '../components/ColorListPicker'
import { formatCurrency, formatPercent } from '../utils/format'
import { INTERNAL_ROLES, MANAGEMENT_ROLES, PROJECT_STATUS_LABELS, PROJECT_STATUS_TONE } from '../utils/labels'
import { DEFAULT_PROJECT_COLOR, PROJECT_COLOR_PALETTE } from '../utils/colorPalette'
import { useLanguage } from '../context/LanguageContext'

const EMPTY_FORM = {
  client_id: '',
  manager_id: '',
  code: '',
  name: '',
  color: DEFAULT_PROJECT_COLOR,
  management_hours: '0',
  management_rate: '0',
  consulting_hours: '0',
  consulting_rate: '0',
  start_date: '',
  end_date: '',
}

const EMPTY_FILTERS = { status: '', client_id: '', manager_id: '', includeModelo: false }

export default function ProjectsPage() {
  const { user } = useAuth()
  const { labels, t } = useLanguage()
  const canCreate = MANAGEMENT_ROLES.includes(user.role)
  // Filtro por cliente só faz sentido pra quem enxerga mais de um cliente
  // — perfil externo (CLIENT_PM/CLIENT_USER) já é travado no próprio
  // cliente (ver _scoped_projects no backend), então a lista viria sempre
  // com um só. Mesmo grupo de papéis que o backend aceita em client_id
  // (GET /reports/portfolio).
  const canFilterByClient = INTERNAL_ROLES.includes(user.role)
  // Filtro por gerente (pedido do usuário) reaproveita a mesma lista de
  // ADMIN/INTERNAL_PM já carregada pra popular "Gerente responsável" no
  // form de Novo projeto — GET /users só é liberado pra esses dois papéis
  // (ver require_roles em routers/users.py), então só faz sentido mostrar
  // o filtro pra quem também tem canCreate (o mesmo conjunto de papéis).
  const canFilterByManager = canCreate
  // Classes literais (não geradas via template) pra o scanner do Tailwind
  // JIT conseguir achar cada uma no código-fonte — ver mesmo padrão já
  // usado antes pra Cliente/Projetos Modelo.
  const filterColumnsClass =
    canFilterByClient && canFilterByManager ? 'md:grid-cols-4' : canFilterByClient || canFilterByManager ? 'md:grid-cols-3' : 'md:grid-cols-2'

  const [rows, setRows] = useState([])
  const [clients, setClients] = useState([])
  const [managers, setManagers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState(EMPTY_FILTERS)

  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  // Map<hex em maiúsculo, "código — nome"> dos projetos que já disputam a
  // exclusividade de cor (fora de COMPLETED/CANCELLED/MODELO — mesmo
  // escopo de _ensure_color_available no backend), pra desabilitar essas
  // opções no ColorListPicker. Buscado à parte de `rows` (que reflete os
  // filtros da tela) porque um filtro de Status/Cliente não pode influenciar
  // quais cores já estão em uso — o cálculo precisa sempre do universo
  // completo do escopo do usuário, não só do que está sendo exibido agora.
  const [usedColors, setUsedColors] = useState(new Map())

  const [deletingProject, setDeletingProject] = useState(null)

  function loadRows() {
    setLoading(true)
    reportsApi
      .getPortfolio({
        status: filters.status || undefined,
        client_id: filters.client_id || undefined,
        manager_id: filters.manager_id || undefined,
        include_modelo: filters.includeModelo || undefined,
      })
      .then(setRows)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadRows, [filters.status, filters.client_id, filters.manager_id, filters.includeModelo])

  useEffect(() => {
    if (canFilterByClient) {
      clientsApi.listClients().then(setClients).catch(() => {})
    }
  }, [canFilterByClient])

  useEffect(() => {
    if (!canCreate) return
    usersApi
      .listUsers({ role: 'INTERNAL_PM' })
      .then((internalPms) => usersApi.listUsers({ role: 'ADMIN' }).then((admins) => setManagers([...admins, ...internalPms])))
      .catch(() => {})
  }, [canCreate])

  // Cores já em uso — recarrega toda vez que o modal "Novo projeto" abre,
  // pra pegar projetos criados/finalizados desde a última vez (mesmo
  // escopo global "todos os clientes" confirmado pelo usuário).
  useEffect(() => {
    if (!showModal) return
    projectsApi
      .listProjects()
      .then((allProjects) => {
        const map = new Map()
        for (const project of allProjects) {
          if (['COMPLETED', 'CANCELLED', 'MODELO'].includes(project.status)) continue
          map.set((project.color || '').toUpperCase(), `${project.code} — ${project.name}`)
        }
        setUsedColors(map)
        // Cor padrão (DEFAULT_PROJECT_COLOR) já em uso por outro projeto
        // ativo? Com a exclusividade agora valendo, manter sempre o mesmo
        // default faria quase toda "Novo projeto" colidir depois da
        // primeira vez — troca pra primeira cor da paleta ainda livre
        // (só se o usuário não tiver mexido no campo).
        setForm((prev) => {
          if (prev.color !== DEFAULT_PROJECT_COLOR || !map.has(DEFAULT_PROJECT_COLOR)) return prev
          const free = PROJECT_COLOR_PALETTE.find((entry) => !map.has(entry.hex))
          return free ? { ...prev, color: free.hex } : prev
        })
      })
      .catch(() => {})
  }, [showModal])

  function updateFilter(field) {
    return (event) => setFilters((prev) => ({ ...prev, [field]: event.target.value }))
  }

  // Botão "Mostrar projetos Modelo": desligar enquanto o filtro de Status
  // está travado em MODELO não faria sentido (lista sempre vazia), então
  // volta o Status pra "Todos" junto.
  function toggleIncludeModelo(event) {
    const includeModelo = event.target.checked
    setFilters((prev) => ({
      ...prev,
      includeModelo,
      status: !includeModelo && prev.status === 'MODELO' ? '' : prev.status,
    }))
  }

  const soldValuePreview = useMemo(() => {
    const managementHours = Number(form.management_hours) || 0
    const managementRate = Number(form.management_rate) || 0
    const consultingHours = Number(form.consulting_hours) || 0
    const consultingRate = Number(form.consulting_rate) || 0
    return managementHours * managementRate + consultingHours * consultingRate
  }, [form.management_hours, form.management_rate, form.consulting_hours, form.consulting_rate])

  function updateField(field) {
    return (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError('')
    setSubmitting(true)
    try {
      const payload = { ...form }
      if (!payload.start_date) delete payload.start_date
      if (!payload.end_date) delete payload.end_date
      await projectsApi.createProject(payload)
      setShowModal(false)
      setForm(EMPTY_FORM)
      loadRows()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <PageHeader
        title={t('Projetos')}
        subtitle={t('Portfólio de projetos no seu escopo.')}
        action={canCreate && <Button onClick={() => setShowModal(true)}>{t('Novo projeto')}</Button>}
      />

      <Card className="mb-4">
        <div className={`grid grid-cols-2 gap-3 ${filterColumnsClass}`}>
          <FormField label={t('Status')}>
            <Select value={filters.status} onChange={updateFilter('status')}>
              <option value="">{t('Todos')}</option>
              {Object.keys(PROJECT_STATUS_LABELS)
                // MODELO só entra na lista quando "Mostrar projetos Modelo"
                // está ligado — do contrário selecioná-lo sempre voltaria
                // uma lista vazia (ver _scoped_projects no backend).
                .filter((status) => status !== 'MODELO' || filters.includeModelo)
                .map((status) => (
                  <option key={status} value={status}>
                    {labels.PROJECT_STATUS_LABELS[status] || status}
                  </option>
                ))}
            </Select>
          </FormField>
          {canFilterByClient && (
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
          )}
          {canFilterByManager && (
            <FormField label={t('Gerente')}>
              <Select value={filters.manager_id} onChange={updateFilter('manager_id')}>
                <option value="">{t('Todos')}</option>
                {managers.map((manager) => (
                  <option key={manager.id} value={manager.id}>
                    {manager.name}
                  </option>
                ))}
              </Select>
            </FormField>
          )}
          <FormField label={t('Projetos Modelo')}>
            <label className="flex h-[38px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 text-sm text-[var(--text-secondary)]">
              <input type="checkbox" checked={filters.includeModelo} onChange={toggleIncludeModelo} />
              {t('Mostrar')}
            </label>
          </FormField>
        </div>
      </Card>

      {loading && <Spinner />}
      <ErrorBanner message={error} />

      {!loading && !error && (
        <Card>
          <Table
            columns={[
              {
                key: 'code',
                header: t('Projeto'),
                // Pedido do usuário: a bolinha de cor (usada pra identificar o
                // projeto na Agenda de consultores) não precisa aparecer
                // aqui — a lista de Projetos já tem Status pra isso; a cor
                // continua valendo normalmente na Agenda e no editor de
                // projeto (ColorListPicker).
                render: (row) => (
                  <Link to={`/projects/${row.id}`} className="font-medium text-[var(--series-1)] hover:underline">
                    {row.code} — {row.name}
                  </Link>
                ),
              },
              {
                key: 'status',
                header: t('Status'),
                render: (row) => <StatusPill label={labels.PROJECT_STATUS_LABELS[row.status] || row.status} tone={PROJECT_STATUS_TONE[row.status]} />,
              },
              // Gerente responsável — pedido do usuário, pra não precisar
              // abrir o projeto só pra ver quem o conduz.
              { key: 'manager_name', header: t('Gerente'), render: (row) => row.manager_name || '—' },
              { key: 'percent_complete', header: t('% concluído'), align: 'right', render: (row) => formatPercent(row.percent_complete) },
              { key: 'tasks_remaining', header: t('Tarefas restantes'), align: 'right' },
              {
                key: 'margin',
                header: t('Margem'),
                align: 'right',
                render: (row) => (row.margin === null || row.margin === undefined ? '—' : formatCurrency(row.margin)),
              },
              // Excluir projeto — cobre o caso de um cadastro por engano.
              // Só aparece pra quem também pode criar projeto (ADMIN/
              // INTERNAL_PM), mesmo perfil exigido pelo backend (DELETE
              // /projects/{id}). "tasks_remaining" desta linha não serve pra
              // decidir se mostra o botão (é só tarefa NÃO concluída — um
              // projeto todo concluído tem tasks_remaining=0 mas ainda tem
              // tarefas, e por isso não pode ser excluído); então o botão
              // fica sempre visível e é o backend quem trava de verdade,
              // explicando o motivo na mensagem de erro do modal.
              ...(canCreate
                ? [
                    {
                      key: 'actions',
                      header: '',
                      align: 'right',
                      render: (row) => (
                        <IconButton icon={TrashIcon} label={t('Excluir projeto')} variant="danger" onClick={() => setDeletingProject(row)} />
                      ),
                    },
                  ]
                : []),
            ]}
            rows={rows}
            getRowKey={(row) => row.id}
            emptyMessage={t('Nenhum projeto no seu escopo ainda.')}
          />
        </Card>
      )}

      {showModal && (
        <Modal title={t('Novo projeto')} onClose={() => setShowModal(false)} wide>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <FormField label={t('Código')} required>
                <TextInput required value={form.code} onChange={updateField('code')} />
              </FormField>
              <FormField label={t('Nome')} required>
                <TextInput required value={form.name} onChange={updateField('name')} />
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label={t('Cliente')} required>
                <Select required value={form.client_id} onChange={updateField('client_id')}>
                  <option value="">{t('Selecione…')}</option>
                  {clients.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.legal_name}
                    </option>
                  ))}
                </Select>
              </FormField>
              <FormField label={t('Gerente responsável')} required hint={t('Precisa ser ADMIN ou gerente de projetos interno.')}>
                <Select required value={form.manager_id} onChange={updateField('manager_id')}>
                  <option value="">{t('Selecione…')}</option>
                  {managers.map((manager) => (
                    <option key={manager.id} value={manager.id}>
                      {manager.name}
                    </option>
                  ))}
                </Select>
              </FormField>
            </div>

            <FormField label={t('Cor do projeto')} hint={t('Usada na Agenda de consultores para identificar este projeto.')}>
              <ColorListPicker value={form.color} onChange={(color) => setForm((prev) => ({ ...prev, color }))} usedColors={usedColors} />
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
              <p className="mt-3 text-sm">
                {t('Valor total vendido (calculado):')} <span className="font-semibold">{formatCurrency(soldValuePreview)}</span>
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <FormField label={t('Início planejado')}>
                <TextInput type="date" value={form.start_date} onChange={updateField('start_date')} />
              </FormField>
              <FormField label={t('Fim planejado')}>
                <TextInput type="date" value={form.end_date} onChange={updateField('end_date')} />
              </FormField>
            </div>

            <ErrorBanner message={formError} />

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="secondary" onClick={() => setShowModal(false)}>
                {t('Cancelar')}
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? t('Salvando…') : t('Salvar')}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {deletingProject && (
        <ProjectDeleteModal
          project={deletingProject}
          onClose={() => setDeletingProject(null)}
          onDeleted={() => {
            setDeletingProject(null)
            loadRows()
          }}
        />
      )}
    </div>
  )
}

/** Modal de confirmação pra excluir um projeto cadastrado por engano — a
 * API (DELETE /projects/{id}) recusa (409) se o projeto já tiver qualquer
 * tarefa, linha de base, despesa, risco, solicitação de mudança ou
 * apontamento de horas avulso, já que todas essas FKs são
 * ondelete="CASCADE" e apagar sem checar destruiria esse dado junto. A
 * mensagem de erro do backend já diz qual desses é o caso, então basta
 * repassá-la. */
function ProjectDeleteModal({ project, onClose, onDeleted }) {
  const { t } = useLanguage()
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')

  async function handleDelete() {
    setDeleting(true)
    setError('')
    try {
      await projectsApi.deleteProject(project.id)
      onDeleted()
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Modal title={t('Excluir projeto')} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          {t('Tem certeza que quer excluir o projeto')} <span className="font-medium text-[var(--text-primary)]">
            {project.code} — {project.name}
          </span>
          ? {t('Só é possível excluir um projeto que ainda não tenha nenhuma tarefa cadastrada.')}
        </p>
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="button" variant="danger" disabled={deleting} onClick={handleDelete}>
            {deleting ? t('Excluindo…') : t('Excluir')}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
