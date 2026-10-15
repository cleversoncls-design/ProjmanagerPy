import { useEffect, useState } from 'react'
import * as clientsApi from '../api/clients'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Table from '../components/Table'
import Button from '../components/Button'
import IconButton from '../components/IconButton'
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import { PencilIcon, TrashIcon } from '../components/icons'
import { FormField, TextInput } from '../components/FormField'
import { useLanguage } from '../context/LanguageContext'

const EMPTY_FORM = {
  code: '',
  legal_name: '',
  trade_name: '',
  tax_id: '',
  city: '',
  state: '',
  primary_contact_name: '',
  primary_contact_email: '',
  primary_contact_phone: '',
}

export default function ClientsPage() {
  const { t } = useLanguage()
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Editar cliente (pedido do usuário, "mais melhorias": "O cadastro de
  // clientes não permite modificar dados") — modal separado do de criação,
  // mesmo padrão já usado em UsersPage (editTarget/editForm).
  const [editTarget, setEditTarget] = useState(null)
  const [editForm, setEditForm] = useState(null)
  const [editFormError, setEditFormError] = useState('')
  const [savingEdit, setSavingEdit] = useState(false)

  // Excluir cliente (pedido do usuário, "mais novas melhorias, parte 3") —
  // mesmo padrão de UserDeleteModal/DeleteTaskModal já usados no app.
  const [deletingClient, setDeletingClient] = useState(null)

  function loadClients() {
    setLoading(true)
    clientsApi
      .listClients()
      .then(setClients)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadClients, [])

  function updateField(field) {
    return (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError('')
    setSubmitting(true)
    try {
      const payload = Object.fromEntries(Object.entries(form).filter(([, value]) => value !== ''))
      await clientsApi.createClient(payload)
      setShowModal(false)
      setForm(EMPTY_FORM)
      loadClients()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  function openEditModal(row) {
    setEditTarget(row)
    setEditForm({
      code: row.code,
      legal_name: row.legal_name,
      trade_name: row.trade_name || '',
      tax_id: row.tax_id || '',
      city: row.city || '',
      state: row.state || '',
      primary_contact_name: row.primary_contact_name || '',
      primary_contact_email: row.primary_contact_email || '',
      primary_contact_phone: row.primary_contact_phone || '',
    })
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
      const payload = Object.fromEntries(Object.entries(editForm).filter(([, value]) => value !== ''))
      await clientsApi.updateClient(editTarget.id, payload)
      setEditTarget(null)
      setEditForm(null)
      loadClients()
    } catch (err) {
      setEditFormError(err.message)
    } finally {
      setSavingEdit(false)
    }
  }

  return (
    <div>
      <PageHeader
        title={t('Clientes')}
        subtitle={t('Cadastro de clientes atendidos pela consultoria.')}
        action={<Button onClick={() => setShowModal(true)}>{t('Novo cliente')}</Button>}
      />

      {loading && <Spinner />}
      <ErrorBanner message={error} />

      {!loading && !error && (
        <Card>
          <Table
            columns={[
              { key: 'code', header: t('Código') },
              { key: 'legal_name', header: t('Razão social') },
              { key: 'trade_name', header: t('Nome fantasia') },
              { key: 'location', header: t('Cidade/UF'), render: (row) => [row.city, row.state].filter(Boolean).join('/') || '—' },
              { key: 'primary_contact_name', header: t('Contato') },
              { key: 'primary_contact_email', header: t('E-mail do contato') },
              {
                key: 'actions',
                header: '',
                align: 'right',
                render: (row) => (
                  <div className="flex justify-end gap-1.5">
                    <IconButton icon={PencilIcon} label={t('Editar')} onClick={() => openEditModal(row)} />
                    <IconButton icon={TrashIcon} label={t('Excluir')} variant="danger" onClick={() => setDeletingClient(row)} />
                  </div>
                ),
              },
            ]}
            rows={clients}
            getRowKey={(row) => row.id}
            emptyMessage={t('Nenhum cliente cadastrado ainda.')}
          />
        </Card>
      )}

      {showModal && (
        <Modal title={t('Novo cliente')} onClose={() => setShowModal(false)} wide>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <FormField label={t('Código')} required>
                <TextInput required value={form.code} onChange={updateField('code')} />
              </FormField>
              <FormField label={t('Razão social')} required>
                <TextInput required value={form.legal_name} onChange={updateField('legal_name')} />
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label={t('Nome fantasia')}>
                <TextInput value={form.trade_name} onChange={updateField('trade_name')} />
              </FormField>
              <FormField label="CNPJ/CPF">
                <TextInput value={form.tax_id} onChange={updateField('tax_id')} />
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label={t('Cidade')}>
                <TextInput value={form.city} onChange={updateField('city')} />
              </FormField>
              <FormField label="UF" hint={t('2 letras')}>
                <TextInput maxLength={2} value={form.state} onChange={updateField('state')} />
              </FormField>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <FormField label={t('Nome do contato')}>
                <TextInput value={form.primary_contact_name} onChange={updateField('primary_contact_name')} />
              </FormField>
              <FormField label={t('E-mail do contato')}>
                <TextInput type="email" value={form.primary_contact_email} onChange={updateField('primary_contact_email')} />
              </FormField>
              <FormField label={t('Telefone do contato')}>
                <TextInput value={form.primary_contact_phone} onChange={updateField('primary_contact_phone')} />
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

      {editTarget && editForm && (
        <Modal title={`${t('Editar cliente')} — ${editTarget.legal_name}`} onClose={() => setEditTarget(null)} wide>
          <form onSubmit={handleSaveEdit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <FormField label={t('Código')} required>
                <TextInput required value={editForm.code} onChange={updateEditField('code')} />
              </FormField>
              <FormField label={t('Razão social')} required>
                <TextInput required value={editForm.legal_name} onChange={updateEditField('legal_name')} />
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label={t('Nome fantasia')}>
                <TextInput value={editForm.trade_name} onChange={updateEditField('trade_name')} />
              </FormField>
              <FormField label="CNPJ/CPF">
                <TextInput value={editForm.tax_id} onChange={updateEditField('tax_id')} />
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label={t('Cidade')}>
                <TextInput value={editForm.city} onChange={updateEditField('city')} />
              </FormField>
              <FormField label="UF" hint={t('2 letras')}>
                <TextInput maxLength={2} value={editForm.state} onChange={updateEditField('state')} />
              </FormField>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <FormField label={t('Nome do contato')}>
                <TextInput value={editForm.primary_contact_name} onChange={updateEditField('primary_contact_name')} />
              </FormField>
              <FormField label={t('E-mail do contato')}>
                <TextInput type="email" value={editForm.primary_contact_email} onChange={updateEditField('primary_contact_email')} />
              </FormField>
              <FormField label={t('Telefone do contato')}>
                <TextInput value={editForm.primary_contact_phone} onChange={updateEditField('primary_contact_phone')} />
              </FormField>
            </div>

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

      {deletingClient && (
        <ClientDeleteModal
          target={deletingClient}
          onClose={() => setDeletingClient(null)}
          onDeleted={() => {
            setDeletingClient(null)
            loadClients()
          }}
        />
      )}
    </div>
  )
}

/** Modal de confirmação pra excluir um cliente — a API recusa (409) se ele
 * tiver projeto(s), usuário(s) (PM do cliente/Usuário-chave) ou
 * solicitação(ões) de projeto vinculados (ver DELETE /clients/{id} em
 * app/routers/clients.py) — a mensagem de erro do backend já explica qual
 * dos casos é, então basta repassá-la (mesmo padrão de UserDeleteModal em
 * UsersPage.jsx/DeleteTaskModal em ProjectDetailPage.jsx). */
function ClientDeleteModal({ target, onClose, onDeleted }) {
  const { t } = useLanguage()
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')

  async function handleDelete() {
    setDeleting(true)
    setError('')
    try {
      await clientsApi.deleteClient(target.id)
      onDeleted()
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Modal title={t('Excluir cliente')} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          {t('Tem certeza que quer excluir o cliente')} <span className="font-medium text-[var(--text-primary)]">{target.code} — {target.legal_name}</span>?{' '}
          {t('Essa ação não pode ser desfeita.')}
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
