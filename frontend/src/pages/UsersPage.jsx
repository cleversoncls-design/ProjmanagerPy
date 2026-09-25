import { useEffect, useState } from 'react'
import * as usersApi from '../api/users'
import * as resourcesApi from '../api/resources'
import * as calendarsApi from '../api/calendars'
import * as clientsApi from '../api/clients'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Table from '../components/Table'
import Button from '../components/Button'
import IconButton from '../components/IconButton'
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import StatusPill from '../components/StatusPill'
import { BriefcaseIcon, KeyIcon, PencilIcon, TrashIcon } from '../components/icons'
import { FormField, TextInput, Select } from '../components/FormField'
import { formatCurrency } from '../utils/format'
import { USER_STATUS_TONE } from '../utils/labels'
import { useLanguage } from '../context/LanguageContext'

const EXTERNAL_ROLES = ['CLIENT_PM', 'CLIENT_USER']

const EMPTY_USER_FORM = { name: '', email: '', password: '', role: 'CONSULTANT', client_id: '' }
const EMPTY_RESOURCE_FORM = { role_title: '', internal_cost_per_hour: '', billing_rate_per_hour: '', daily_capacity_hours: '8', calendar_id: '' }

export default function UsersPage() {
  const { labels, t } = useLanguage()
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
  // Presente = editando o recurso já vinculado a resourceTarget; null =
  // vinculando um recurso novo (POST). Mesmo modal/form pros dois casos —
  // só muda o título e se salvar chama create ou update.
  const [editingResourceId, setEditingResourceId] = useState(null)
  const [resourceForm, setResourceForm] = useState(EMPTY_RESOURCE_FORM)
  const [resourceFormError, setResourceFormError] = useState('')
  const [savingResource, setSavingResource] = useState(false)

  const [editTarget, setEditTarget] = useState(null)
  const [editForm, setEditForm] = useState(null)
  const [editFormError, setEditFormError] = useState('')
  const [savingEdit, setSavingEdit] = useState(false)

  const [passwordTarget, setPasswordTarget] = useState(null)
  const [newPassword, setNewPassword] = useState('')
  const [passwordFormError, setPasswordFormError] = useState('')
  const [savingPassword, setSavingPassword] = useState(false)

  const [deletingResourceTarget, setDeletingResourceTarget] = useState(null)

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

  function openLinkResourceModal(row) {
    setResourceTarget(row)
    setEditingResourceId(null)
    setResourceForm(EMPTY_RESOURCE_FORM)
    setResourceFormError('')
  }

  function openEditResourceModal(row) {
    const resource = resourceByUserId[row.id]
    if (!resource) return
    setResourceTarget(row)
    setEditingResourceId(resource.id)
    setResourceForm({
      role_title: resource.role_title,
      internal_cost_per_hour: String(resource.internal_cost_per_hour),
      billing_rate_per_hour: String(resource.billing_rate_per_hour),
      daily_capacity_hours: String(resource.daily_capacity_hours),
      calendar_id: resource.calendar_id || '',
    })
    setResourceFormError('')
  }

  async function handleSaveResource(event) {
    event.preventDefault()
    setResourceFormError('')
    setSavingResource(true)
    try {
      const payload = {
        role_title: resourceForm.role_title,
        internal_cost_per_hour: resourceForm.internal_cost_per_hour,
        billing_rate_per_hour: resourceForm.billing_rate_per_hour,
        daily_capacity_hours: resourceForm.daily_capacity_hours || '8',
        calendar_id: resourceForm.calendar_id || null,
      }
      if (editingResourceId) {
        await resourcesApi.updateResource(editingResourceId, payload)
      } else {
        await resourcesApi.createResource({ ...payload, user_id: resourceTarget.id })
      }
      setResourceTarget(null)
      setEditingResourceId(null)
      setResourceForm(EMPTY_RESOURCE_FORM)
      loadAll()
    } catch (err) {
      setResourceFormError(err.message)
    } finally {
      setSavingResource(false)
    }
  }

  function openEditModal(row) {
    setEditTarget(row)
    setEditForm({ name: row.name, role: row.role, client_id: row.client_id || '', status: row.status })
    setEditFormError('')
  }

  function updateEditField(field) {
    return (event) => setEditForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  async function handleSaveEdit(event) {
    event.preventDefault()
    setEditFormError('')
    setSavingEdit(true)
    try {
      const payload = { name: editForm.name, role: editForm.role, status: editForm.status }
      payload.client_id = EXTERNAL_ROLES.includes(editForm.role) ? editForm.client_id : null
      await usersApi.updateUser(editTarget.id, payload)
      setEditTarget(null)
      setEditForm(null)
      loadAll()
    } catch (err) {
      setEditFormError(err.message)
    } finally {
      setSavingEdit(false)
    }
  }

  async function handleResetPassword(event) {
    event.preventDefault()
    setPasswordFormError('')
    setSavingPassword(true)
    try {
      await usersApi.resetPassword(passwordTarget.id, { new_password: newPassword })
      setPasswordTarget(null)
      setNewPassword('')
    } catch (err) {
      setPasswordFormError(err.message)
    } finally {
      setSavingPassword(false)
    }
  }

  return (
    <div>
      <PageHeader
        title={t('Usuários e recursos')}
        subtitle={t('Usuários internos e externos, e o custo/capacidade de cada um como recurso alocável.')}
        action={<Button onClick={() => setShowUserModal(true)}>{t('Novo usuário')}</Button>}
      />

      {loading && <Spinner />}
      <ErrorBanner message={error} />

      {!loading && !error && (
        <Card>
          <Table
            columns={[
              { key: 'name', header: t('Nome') },
              { key: 'email', header: t('E-mail') },
              { key: 'role', header: t('Perfil'), render: (row) => <StatusPill label={labels.ROLE_LABELS[row.role] || row.role} tone="muted" /> },
              {
                key: 'status',
                header: t('Situação'),
                render: (row) => <StatusPill label={labels.USER_STATUS_LABELS[row.status] || row.status} tone={USER_STATUS_TONE[row.status] || 'muted'} />,
              },
              { key: 'client', header: t('Cliente'), render: (row) => (row.client_id ? clientById[row.client_id]?.legal_name || '—' : '—') },
              {
                key: 'resource',
                header: t('Recurso (custo/h)'),
                render: (row) => {
                  const resource = resourceByUserId[row.id]
                  if (!resource) return <span className="text-[var(--text-muted)]">{t('Não cadastrado')}</span>
                  return `${resource.role_title} · ${formatCurrency(resource.internal_cost_per_hour)}/h`
                },
              },
              {
                key: 'actions',
                header: '',
                align: 'right',
                render: (row) => (
                  <div className="flex justify-end gap-1.5">
                    <IconButton icon={PencilIcon} label={t('Editar')} onClick={() => openEditModal(row)} />
                    <IconButton
                      icon={KeyIcon}
                      label={t('Redefinir senha')}
                      onClick={() => {
                        setPasswordTarget(row)
                        setNewPassword('')
                        setPasswordFormError('')
                      }}
                    />
                    {resourceByUserId[row.id] ? (
                      <>
                        <IconButton icon={BriefcaseIcon} label={t('Editar recurso')} onClick={() => openEditResourceModal(row)} />
                        {/* Recurso do Administrador nunca é excluível por aqui — o resto
                            (inclusive perfis de cliente) segue liberado, e a checagem de
                            alocação/apontamento de horas no backend (DELETE /resources/{id})
                            continua sendo a proteção de verdade contra apagar um recurso
                            em uso. */}
                        {row.role !== 'ADMIN' && (
                          <IconButton
                            icon={TrashIcon}
                            label={t('Excluir recurso')}
                            variant="danger"
                            onClick={() => setDeletingResourceTarget({ row, resource: resourceByUserId[row.id] })}
                          />
                        )}
                      </>
                    ) : (
                      <IconButton icon={BriefcaseIcon} label={t('Vincular como recurso')} onClick={() => openLinkResourceModal(row)} />
                    )}
                  </div>
                ),
              },
            ]}
            rows={users}
            getRowKey={(row) => row.id}
            emptyMessage={t('Nenhum usuário cadastrado ainda.')}
          />
        </Card>
      )}

      {showUserModal && (
        <Modal title={t('Novo usuário')} onClose={() => setShowUserModal(false)}>
          <form onSubmit={handleCreateUser} className="space-y-4">
            <FormField label={t('Nome')} required>
              <TextInput required value={userForm.name} onChange={updateUserField('name')} />
            </FormField>
            <FormField label={t('E-mail')} required>
              <TextInput type="email" required value={userForm.email} onChange={updateUserField('email')} />
            </FormField>
            <FormField label={t('Senha provisória')} required hint={t('Mínimo de 8 caracteres.')}>
              <TextInput type="password" required minLength={8} value={userForm.password} onChange={updateUserField('password')} />
            </FormField>
            <FormField label={t('Perfil')} required>
              <Select required value={userForm.role} onChange={updateUserField('role')}>
                {Object.entries(labels.ROLE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </FormField>
            {EXTERNAL_ROLES.includes(userForm.role) && (
              <FormField label={t('Cliente')} required hint={t('Obrigatório para perfis do cliente.')}>
                <Select required value={userForm.client_id} onChange={updateUserField('client_id')}>
                  <option value="">{t('Selecione…')}</option>
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
                {t('Cancelar')}
              </Button>
              <Button type="submit" disabled={savingUser}>
                {savingUser ? t('Salvando…') : t('Salvar')}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {resourceTarget && (
        <Modal
          title={`${editingResourceId ? t('Editar recurso') : t('Vincular recurso')} — ${resourceTarget.name}`}
          onClose={() => {
            setResourceTarget(null)
            setEditingResourceId(null)
          }}
        >
          <form onSubmit={handleSaveResource} className="space-y-4">
            <FormField label={t('Função')} required hint={t('Ex.: "Consultor sênior", "Gerente de projetos".')}>
              <TextInput required value={resourceForm.role_title} onChange={updateResourceField('role_title')} />
            </FormField>
            <div className="grid grid-cols-2 gap-4">
              <FormField label={t('Custo interno (US$/h)')} required>
                <TextInput type="number" min="0" step="0.01" required value={resourceForm.internal_cost_per_hour} onChange={updateResourceField('internal_cost_per_hour')} />
              </FormField>
              <FormField label={t('Valor de faturamento (US$/h)')} required>
                <TextInput type="number" min="0" step="0.01" required value={resourceForm.billing_rate_per_hour} onChange={updateResourceField('billing_rate_per_hour')} />
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label={t('Capacidade diária (h)')} required>
                <TextInput type="number" min="1" max="24" step="0.5" required value={resourceForm.daily_capacity_hours} onChange={updateResourceField('daily_capacity_hours')} />
              </FormField>
              <FormField label={t('Calendário pessoal')} hint={t('Opcional.')}>
                <Select value={resourceForm.calendar_id} onChange={updateResourceField('calendar_id')}>
                  <option value="">{t('Nenhum')}</option>
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
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setResourceTarget(null)
                  setEditingResourceId(null)
                }}
              >
                {t('Cancelar')}
              </Button>
              <Button type="submit" disabled={savingResource}>
                {savingResource ? t('Salvando…') : t('Salvar')}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {editTarget && editForm && (
        <Modal title={`${t('Editar usuário')} — ${editTarget.name}`} onClose={() => setEditTarget(null)}>
          <form onSubmit={handleSaveEdit} className="space-y-4">
            <FormField label={t('Nome')} required>
              <TextInput required value={editForm.name} onChange={updateEditField('name')} />
            </FormField>
            <FormField label={t('Perfil')} required>
              <Select required value={editForm.role} onChange={updateEditField('role')}>
                {Object.entries(labels.ROLE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </FormField>
            {EXTERNAL_ROLES.includes(editForm.role) && (
              <FormField label={t('Cliente')} required hint={t('Obrigatório para perfis do cliente.')}>
                <Select required value={editForm.client_id} onChange={updateEditField('client_id')}>
                  <option value="">{t('Selecione…')}</option>
                  {clients.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.legal_name}
                    </option>
                  ))}
                </Select>
              </FormField>
            )}
            <FormField label={t('Situação')} required hint={t('Bloqueado impede login imediatamente.')}>
              <Select required value={editForm.status} onChange={updateEditField('status')}>
                {Object.entries(labels.USER_STATUS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </FormField>

            <ErrorBanner message={editFormError} />

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="secondary" onClick={() => setEditTarget(null)}>
                {t('Cancelar')}
              </Button>
              <Button type="submit" disabled={savingEdit}>
                {savingEdit ? t('Salvando…') : t('Salvar')}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {passwordTarget && (
        <Modal title={`${t('Redefinir senha')} — ${passwordTarget.name}`} onClose={() => setPasswordTarget(null)}>
          <form onSubmit={handleResetPassword} className="space-y-4">
            <FormField label={t('Nova senha')} required hint={t('Mínimo de 8 caracteres.')}>
              <TextInput type="password" required minLength={8} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
            </FormField>

            <ErrorBanner message={passwordFormError} />

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="secondary" onClick={() => setPasswordTarget(null)}>
                {t('Cancelar')}
              </Button>
              <Button type="submit" disabled={savingPassword}>
                {savingPassword ? t('Salvando…') : t('Salvar')}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {deletingResourceTarget && (
        <ResourceDeleteModal
          target={deletingResourceTarget}
          onClose={() => setDeletingResourceTarget(null)}
          onDeleted={() => {
            setDeletingResourceTarget(null)
            loadAll()
          }}
        />
      )}
    </div>
  )
}

/** Modal de confirmação pra excluir o vínculo de recurso de um usuário — a
 * API recusa (409) se o recurso estiver alocado em alguma tarefa
 * (TaskAssignment) ou já tiver apontamento de horas lançado (Timesheet),
 * já que as duas FKs são ondelete="CASCADE" e apagar sem essa checagem
 * destruiria alocações/horas de outras pessoas junto (ver DELETE
 * /resources/{id}). A mensagem de erro do backend já explica qual dos dois
 * casos é, então basta repassá-la. */
function ResourceDeleteModal({ target, onClose, onDeleted }) {
  const { t } = useLanguage()
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')

  async function handleDelete() {
    setDeleting(true)
    setError('')
    try {
      await resourcesApi.deleteResource(target.resource.id)
      onDeleted()
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Modal title={t('Excluir recurso')} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          {t('Tem certeza que quer excluir o recurso de')} <span className="font-medium text-[var(--text-primary)]">{target.row.name}</span>{' '}
          ({target.resource.role_title})? {t('Só é possível excluir um recurso que não esteja alocado em projetos ou tarefas.')}
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
