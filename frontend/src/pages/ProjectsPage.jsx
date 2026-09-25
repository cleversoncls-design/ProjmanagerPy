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
import { formatCurrency, formatPercent } from '../utils/format'
import { MANAGEMENT_ROLES, PROJECT_STATUS_TONE } from '../utils/labels'
import { useLanguage } from '../context/LanguageContext'

const EMPTY_FORM = {
  client_id: '',
  manager_id: '',
  code: '',
  name: '',
  management_hours: '0',
  management_rate: '0',
  consulting_hours: '0',
  consulting_rate: '0',
  start_date: '',
  end_date: '',
}

export default function ProjectsPage() {
  const { user } = useAuth()
  const { labels, t } = useLanguage()
  const canCreate = MANAGEMENT_ROLES.includes(user.role)

  const [rows, setRows] = useState([])
  const [clients, setClients] = useState([])
  const [managers, setManagers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const [deletingProject, setDeletingProject] = useState(null)

  function loadRows() {
    setLoading(true)
    reportsApi
      .getPortfolio()
      .then(setRows)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadRows, [])

  useEffect(() => {
    if (!canCreate) return
    clientsApi.listClients().then(setClients).catch(() => {})
    usersApi
      .listUsers({ role: 'INTERNAL_PM' })
      .then((internalPms) => usersApi.listUsers({ role: 'ADMIN' }).then((admins) => setManagers([...admins, ...internalPms])))
      .catch(() => {})
  }, [canCreate])

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

      {loading && <Spinner />}
      <ErrorBanner message={error} />

      {!loading && !error && (
        <Card>
          <Table
            columns={[
              {
                key: 'code',
                header: t('Projeto'),
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
