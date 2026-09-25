import { useEffect, useState } from 'react'
import * as calendarsApi from '../api/calendars'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Table from '../components/Table'
import Button from '../components/Button'
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import { FormField, TextInput } from '../components/FormField'
import { formatDate } from '../utils/format'
import { useLanguage } from '../context/LanguageContext'

const DEFAULT_WORKING_DAYS = [0, 1, 2, 3, 4]

export default function CalendarsPage() {
  const { labels } = useLanguage()
  const [calendars, setCalendars] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [name, setName] = useState('')
  const [workingDays, setWorkingDays] = useState(DEFAULT_WORKING_DAYS)
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const [selectedCalendar, setSelectedCalendar] = useState(null)

  function loadCalendars() {
    setLoading(true)
    calendarsApi
      .listCalendars()
      .then(setCalendars)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadCalendars, [])

  function toggleWeekday(day) {
    setWorkingDays((prev) => (prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day].sort()))
  }

  async function handleCreate(event) {
    event.preventDefault()
    setFormError('')
    setSubmitting(true)
    try {
      await calendarsApi.createCalendar({ name, working_days: workingDays })
      setShowModal(false)
      setName('')
      setWorkingDays(DEFAULT_WORKING_DAYS)
      loadCalendars()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Calendários"
        subtitle="Dias úteis e feriados usados no cálculo de cronograma e capacidade."
        action={<Button onClick={() => setShowModal(true)}>Novo calendário</Button>}
      />

      {loading && <Spinner />}
      <ErrorBanner message={error} />

      {!loading && !error && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card title="Calendários cadastrados">
            <Table
              columns={[
                { key: 'name', header: 'Nome' },
                {
                  key: 'working_days',
                  header: 'Dias úteis',
                  render: (row) => row.working_days.map((day) => labels.WEEKDAY_LABELS[day]).join(', '),
                },
                {
                  key: 'actions',
                  header: '',
                  align: 'right',
                  render: (row) => (
                    <button
                      type="button"
                      onClick={() => setSelectedCalendar(row)}
                      className="text-xs font-medium text-[var(--series-1)] hover:underline"
                    >
                      Feriados
                    </button>
                  ),
                },
              ]}
              rows={calendars}
              getRowKey={(row) => row.id}
              emptyMessage="Nenhum calendário cadastrado ainda."
            />
          </Card>

          <Card title={selectedCalendar ? `Feriados — ${selectedCalendar.name}` : 'Feriados'}>
            {selectedCalendar ? (
              <HolidaysPanel calendar={selectedCalendar} />
            ) : (
              <p className="text-sm text-[var(--text-muted)]">Selecione um calendário na lista ao lado para ver e cadastrar feriados.</p>
            )}
          </Card>
        </div>
      )}

      {showModal && (
        <Modal title="Novo calendário" onClose={() => setShowModal(false)}>
          <form onSubmit={handleCreate} className="space-y-4">
            <FormField label="Nome" required>
              <TextInput required value={name} onChange={(event) => setName(event.target.value)} />
            </FormField>
            <FormField label="Dias úteis" required>
              <div className="flex flex-wrap gap-2">
                {labels.WEEKDAY_LABELS.map((label, day) => (
                  <label
                    key={label}
                    className={`cursor-pointer rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors ${
                      workingDays.includes(day)
                        ? 'border-[var(--series-1)] bg-[var(--series-1)]/10 text-[var(--series-1)]'
                        : 'border-[var(--border)] text-[var(--text-secondary)]'
                    }`}
                  >
                    <input type="checkbox" className="hidden" checked={workingDays.includes(day)} onChange={() => toggleWeekday(day)} />
                    {label}
                  </label>
                ))}
              </div>
            </FormField>

            <ErrorBanner message={formError} />

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="secondary" onClick={() => setShowModal(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={submitting || workingDays.length === 0}>
                {submitting ? 'Salvando…' : 'Salvar'}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}

function HolidaysPanel({ calendar }) {
  const [holidays, setHolidays] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [date, setDate] = useState('')
  const [description, setDescription] = useState('')
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function loadHolidays() {
    setLoading(true)
    calendarsApi
      .listHolidays(calendar.id)
      .then((result) => setHolidays(result.sort((a, b) => a.date.localeCompare(b.date))))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadHolidays, [calendar.id])

  async function handleAdd(event) {
    event.preventDefault()
    setFormError('')
    setSubmitting(true)
    try {
      await calendarsApi.addHoliday(calendar.id, { date, description })
      setDate('')
      setDescription('')
      loadHolidays()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleAdd} className="flex items-end gap-2">
        <FormField label="Data" required>
          <TextInput type="date" required value={date} onChange={(event) => setDate(event.target.value)} />
        </FormField>
        <FormField label="Descrição" required>
          <TextInput required value={description} onChange={(event) => setDescription(event.target.value)} />
        </FormField>
        <Button type="submit" disabled={submitting}>
          Adicionar
        </Button>
      </form>
      <ErrorBanner message={formError} />

      {loading && <Spinner />}
      <ErrorBanner message={error} />
      {!loading && !error && (
        <Table
          columns={[
            { key: 'date', header: 'Data', render: (row) => formatDate(row.date) },
            { key: 'description', header: 'Descrição' },
          ]}
          rows={holidays}
          getRowKey={(row) => row.id}
          emptyMessage="Nenhum feriado cadastrado para este calendário."
        />
      )}
    </div>
  )
}
