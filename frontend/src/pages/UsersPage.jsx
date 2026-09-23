import { useEffect, useState } from 'react'
import * as usersApi from '../api/users'
import * as resourcesApi from '../api/resources'
import * as calendarsApi from '../api/calendars'
import * as clientsApi from '../api/clients'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Table from '../components/Table'
import Button from '../components/Button'
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import StatusPill from '../components/StatusPill'
import { FormField, TextInput, Select } from '../components/FormField'
import { formatCurrency } from '../utils/format'
import { ROLE_LABELS } from '../utils/labels'

const EXTERNAL_ROLES = ['CLIENT_PM', 'CLIENT_USER']

const EMPTY_USER_FORM = { name: '', email: '', password: '', role: 'CONSULTANT', client_id: '' }
const EMPTY_RESOURCE_FORM = { role_title: '', internal_cost_per_hour: '', billing_rate_per_hour: '', daily_capacity_hours: '8', calendar_id: '' }

export default function UsersPage() {
  const [users, setUsers] = useState([])
  const [resources, setResources] = useState([])
  const [calendars, setCalendars] = useState([])
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [showUserModal, setShowUserModal] = useState(false)
  const [userForm, setUserForm] = useState(EMPTY_USER_FORM)
  const [userFormError, setUserFormError] = useState('')
  const [savingUser, setSavingUser] = useState(false)

  const [resourceTarget, setResourceTarget] = useState(null)
  const [resourceForm, setResourceForm] = useState(EMPTY_RESOURCE_FORM)
  const [resourceFormError, setResourceFormError] = useState('')
  const [savingResource, setSavingResource] = useState(false)

  function loadAll() {
    setLoading(true)
    Promise.all([usersApi.listUsers(), resourcesApi.listResources(), calendarsApi.listCalendars(), clientsApi.listClients()])
      .then(([usersResult, resourcesResult, calendarsResult, clientsResult]) => {
        setUsers(usersResult)
        setResources(resourcesResult)
        setCalendars(calendarsResult)
        setClients(clientsResult)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadAll, [])

  const resourceByUserId = Object.fromEntries(resources.map((resource) => [resource.user_id, resource]))
  const clientById = Object.fromEntries(clients.map((client) => [client.id, client]))

  function updateUserField(field) {
    return (event) => setUserForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  async function handleCreateUser(event) {
    event.preventDefault()
    setUserFormError('')
    setSavingUser(true)
    try {
      const payload = { name: userForm.name, email: userForm.email, password: userForm.password, role: userForm.role }
      if (EXTERNAL_ROLES.includes(userForm.role)) {
        payload.client_id = userForm.client_id
      }
      await usersApi.createUser(payload)
      setShowUserModal(false)
      setUserForm(EMPTY_USER_FORM)
      loadAll()
    } catch (err) {
      setUserFormError(err.message)
    } finally {
      setSavingUser(false)
    }
  }

  function updateResourceField(field) {
    return (event) => setResourceForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  async function handleCreateResource(event) {
    event.preventDefault()
    setResourceFormError('')
    setSavingResource(true)
    try {
      const payload = {
        user_id: resourceTarget.id,
        role_title: resourceForm.role_title,
        internal_cost_per_hour: resourceForm.internal_cost_per_hour,
        billing_rate_per_hour: resourceForm.billing_rate_per_hour,
        daily_capacity_hours: resourceForm.daily_capacity_hours || '8',
      }
      if (resourceForm.calendar_id) payload.calendar_id = resourceForm.calendar_id
      await resourcesApi.createResource(payload)
      setResourceTarget(null)
      setResourceForm(EMPTY_RESOURCE_FORM)
      loadAll()
    } catch (err) {
      setResourceFormError(err.message)
    } finally {
      setSavingResource(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Usuários e recursos"
        subtitle="Usuários internos e externos, e o custo/capacidade de cada um como recurso alocável."
        action={<Button onClick={() => setShowUserModal(true)}>Novo usuário</Button>}
      />

      {loading && <Spinner />}
      <ErrorBanner message={error} />

      {!loading && !error && (
        <Card>
          <Table
            columns={[
              { key: 'name', header: 'Nome' },
              { key: 'email', header: 'E-mail' },
              { key: 'role', header: 'Perfil', render: (row) => <StatusPill label={ROLE_LABELS[row.role] || row.role} tone="muted" /> },
              { key: 'client', header: 'Cliente', render: (row) => (row.client_id ? clientById[row.client_id]?.legal_name || '—' : '—') },
              {
                key: 'resource',
                header: 'Recurso (custo/h)',
                render: (row) => {
                  const resource = resourceByUserId[row.id]
                  if (!resource) return <span className="text-[var(--text-muted)]">Não cadastrado</span>
                  return `${resource.role_title} · ${formatCurrency(resource.internal_cost_per_hour)}/h`
                },
              },
              {
                key: 'actions',
                header: '',
                align: 'right',
                render: (row) =>
                  resourceByUserId[row.id] ? null : (
                    <button
                      type="button"
                      onClick={() => setResourceTarget(row)}
                      className="text-xs font-medium text-[var(--series-1)] hover:underline"
                    >
                      Vincular como recurso
                    </button>
                  ),
              },
            ]}
            rows={users}
            getRowKey={(row) => row.id}
            emptyMessage="Nenhum usuário cadastrado ainda."
          />
        </Card>
      )}

      {showUserModal && (
        <Modal title="Novo usuário" onClose={() => setShowUserModal(false)}>
          <form onSubmit={handleCreateUser} className="space-y-4">
            <FormField label="Nome" required>
              <TextInput required value={userForm.name} onChange={updateUserField('name')} />
            </FormField>
            <FormField label="E-mail" required>
              <TextInput type="email" required value={userForm.email} onChange={updateUserField('email')} />
            </FormField>
            <FormField label="Senha provisória" required hint="Mínimo de 8 caracteres.">
              <TextInput type="password" required minLength={8} value={userForm.password} onChange={updateUserField('password')} />
            </FormField>
            <FormField label="Perfil" required>
              <Select required value={userForm.role} onChange={updateUserField('role')}>
                {Object.entries(ROLE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </FormField>
            {EXTERNAL_ROLES.includes(userForm.role) && (
              <FormField label="Cliente" required hint="Obrigatório para perfis do cliente.">
                <Select required value={userForm.client_id} onChange={updateUserField('client_id')}>
                  <option value="">Selecione…</option>
                  {clients.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.legal_name}
                    </option>
                  ))}
                </Select>
              </FormField>
            )}

            <ErrorBanner message={userFormError} />

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="secondary" onClick={() => setShowUserModal(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={savingUser}>
                {savingUser ? 'Salvando…' : 'Salvar'}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {resourceTarget && (
        <Modal title={`Vincular recurso — ${resourceTarget.name}`} onClose={() => setResourceTarget(null)}>
          <form onSubmit={handleCreateResource} className="space-y-4">
            <FormField label="Função" required hint='Ex.: "Consultor sênior", "Gerente de projetos".'>
              <TextInput required value={resourceForm.role_title} onChange={updateResourceField('role_title')} />
            </FormField>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Custo interno (R$/h)" required>
                <TextInput type="number" min="0" step="0.01" required value={resourceForm.internal_cost_per_hour} onChange={updateResourceField('internal_cost_per_hour')} />
              </FormField>
              <FormField label="Valor de faturamento (R$/h)" required>
                <TextInput type="number" min="0" step="0.01" required value={resourceForm.billing_rate_per_hour} onChange={updateResourceField('billing_rate_per_hour')} />
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Capacidade diária (h)" required>
                <TextInput type="number" min="1" max="24" step="0.5" required value={resourceForm.daily_capacity_hours} onChange={updateResourceField('daily_capacity_hours')} />
              </FormField>
              <FormField label="Calendário pessoal" hint="Opcional.">
                <Select value={resourceForm.calendar_id} onChange={updateResourceField('calendar_id')}>
                  <option value="">Nenhum</option>
                  {calendars.map((calendar) => (
                    <option key={calendar.id} value={calendar.id}>
                      {calendar.name}
                    </option>
                  ))}
                </Select>
              </FormField>
            </div>

            <ErrorBanner message={resourceFormError} />

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="secondary" onClick={() => setResourceTarget(null)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={savingResource}>
                {savingResource ? 'Salvando…' : 'Salvar'}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
