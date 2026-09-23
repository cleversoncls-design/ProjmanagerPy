import { useEffect, useState } from 'react'
import * as clientsApi from '../api/clients'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Table from '../components/Table'
import Button from '../components/Button'
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import { FormField, TextInput } from '../components/FormField'

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
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

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

  return (
    <div>
      <PageHeader
        title="Clientes"
        subtitle="Cadastro de clientes atendidos pela consultoria."
        action={<Button onClick={() => setShowModal(true)}>Novo cliente</Button>}
      />

      {loading && <Spinner />}
      <ErrorBanner message={error} />

      {!loading && !error && (
        <Card>
          <Table
            columns={[
              { key: 'code', header: 'Código' },
              { key: 'legal_name', header: 'Razão social' },
              { key: 'trade_name', header: 'Nome fantasia' },
              { key: 'location', header: 'Cidade/UF', render: (row) => [row.city, row.state].filter(Boolean).join('/') || '—' },
              { key: 'primary_contact_name', header: 'Contato' },
              { key: 'primary_contact_email', header: 'E-mail do contato' },
            ]}
            rows={clients}
            getRowKey={(row) => row.id}
            emptyMessage="Nenhum cliente cadastrado ainda."
          />
        </Card>
      )}

      {showModal && (
        <Modal title="Novo cliente" onClose={() => setShowModal(false)} wide>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Código" required>
                <TextInput required value={form.code} onChange={updateField('code')} />
              </FormField>
              <FormField label="Razão social" required>
                <TextInput required value={form.legal_name} onChange={updateField('legal_name')} />
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Nome fantasia">
                <TextInput value={form.trade_name} onChange={updateField('trade_name')} />
              </FormField>
              <FormField label="CNPJ/CPF">
                <TextInput value={form.tax_id} onChange={updateField('tax_id')} />
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Cidade">
                <TextInput value={form.city} onChange={updateField('city')} />
              </FormField>
              <FormField label="UF" hint="2 letras">
                <TextInput maxLength={2} value={form.state} onChange={updateField('state')} />
              </FormField>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <FormField label="Nome do contato">
                <TextInput value={form.primary_contact_name} onChange={updateField('primary_contact_name')} />
              </FormField>
              <FormField label="E-mail do contato">
                <TextInput type="email" value={form.primary_contact_email} onChange={updateField('primary_contact_email')} />
              </FormField>
              <FormField label="Telefone do contato">
                <TextInput value={form.primary_contact_phone} onChange={updateField('primary_contact_phone')} />
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
