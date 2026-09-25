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
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import StatusPill from '../components/StatusPill'
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
  const { labels } = useLanguage()
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
        title="Projetos"
        subtitle="Portfólio de projetos no seu escopo."
        action={canCreate && <Button onClick={() => setShowModal(true)}>Novo projeto</Button>}
      />

      {loading && <Spinner />}
      <ErrorBanner message={error} />

      {!loading && !error && (
        <Card>
          <Table
            columns={[
              {
                key: 'code',
                header: 'Projeto',
                render: (row) => (
                  <Link to={`/projects/${row.id}`} className="font-medium text-[var(--series-1)] hover:underline">
                    {row.code} — {row.name}
                  </Link>
                ),
              },
              {
                key: 'status',
                header: 'Status',
                render: (row) => <StatusPill label={labels.PROJECT_STATUS_LABELS[row.status] || row.status} tone={PROJECT_STATUS_TONE[row.status]} />,
              },
              { key: 'percent_complete', header: '% concluído', align: 'right', render: (row) => formatPercent(row.percent_complete) },
              { key: 'tasks_remaining', header: 'Tarefas restantes', align: 'right' },
              {
                key: 'margin',
                header: 'Margem',
                align: 'right',
                render: (row) => (row.margin === null || row.margin === undefined ? '—' : formatCurrency(row.margin)),
              },
            ]}
            rows={rows}
            getRowKey={(row) => row.id}
            emptyMessage="Nenhum projeto no seu escopo ainda."
          />
        </Card>
      )}

      {showModal && (
        <Modal title="Novo projeto" onClose={() => setShowModal(false)} wide>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Código" required>
                <TextInput required value={form.code} onChange={updateField('code')} />
              </FormField>
              <FormField label="Nome" required>
                <TextInput required value={form.name} onChange={updateField('name')} />
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Cliente" required>
                <Select required value={form.client_id} onChange={updateField('client_id')}>
                  <option value="">Selecione…</option>
                  {clients.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.legal_name}
                    </option>
                  ))}
                </Select>
              </FormField>
              <FormField label="Gerente responsável" required hint="Precisa ser ADMIN ou gerente de projetos interno.">
                <Select required value={form.manager_id} onChange={updateField('manager_id')}>
                  <option value="">Selecione…</option>
                  {managers.map((manager) => (
                    <option key={manager.id} value={manager.id}>
                      {manager.name}
                    </option>
                  ))}
                </Select>
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
              <p className="mt-3 text-sm">
                Valor total vendido (calculado): <span className="font-semibold">{formatCurrency(soldValuePreview)}</span>
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <FormField label="Início planejado">
                <TextInput type="date" value={form.start_date} onChange={updateField('start_date')} />
              </FormField>
              <FormField label="Fim planejado">
                <TextInput type="date" value={form.end_date} onChange={updateField('end_date')} />
              </FormField>
            </div>

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
