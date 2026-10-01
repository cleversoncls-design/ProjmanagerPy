import { useState } from 'react'
import * as timesheetsApi from '../api/timesheets'
import { useLanguage } from '../context/LanguageContext'
import Modal from './Modal'
import Button from './Button'
import ErrorBanner from './ErrorBanner'
import TimesheetFieldsForm from './TimesheetFieldsForm'
import { entryToTimesheetForm, previewTimesheetHours, timesheetFormToPayload } from '../utils/timesheetForm'

/** Modal de edição de um apontamento — usado na coluna de ações da Ordem
 * de Serviço (ServiceOrdersPage), onde não existe (e não faria sentido
 * ter) o card "Novo apontamento" que TimesheetsPage usa pra editar inline.
 * Mesmos campos (TimesheetFieldsForm) e mesma regra de negócio de
 * TimesheetsPage: disponível em qualquer status — inclusive Aprovado ou
 * Rejeitado (`isTimesheetEditable`, ver utils/timesheetForm.js) — e editar
 * sempre volta o apontamento pro status Pendente (ver PUT /timesheets/{id}).
 *
 * `projects`/`allTasks`/`tasksById`/`labels` vêm de quem chama (mesmas
 * listas já carregadas pra tela toda, sem duplicar as chamadas de API). */
export default function TimesheetEditModal({ entry, projects, allTasks, tasksById, labels, onClose, onSaved }) {
  const { t } = useLanguage()
  const [form, setForm] = useState(() => entryToTimesheetForm(entry, tasksById))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // Tarefas "pai" (têm tarefas-filhas na EAP) não entram no seletor — mesmo
  // critério de TimesheetsPage.jsx (a API também recusa).
  const parentTaskIds = new Set(allTasks.map((task) => task.parent_task_id).filter(Boolean))
  const taskOptions = allTasks.filter((task) => task.project_id === form.project_id && !parentTaskIds.has(task.id))

  function updateField(field) {
    return (event) => {
      const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
      setForm((prev) => {
        if (field === 'project_id') return { ...prev, project_id: value, task_id: '', is_transit: false }
        if (field === 'task_id') return { ...prev, task_id: value, is_transit: value ? false : prev.is_transit }
        if (field === 'is_transit') return { ...prev, is_transit: value, task_id: value ? '' : prev.task_id }
        return { ...prev, [field]: value }
      })
    }
  }

  function formTypeLabel() {
    if (form.is_transit) return labels.TASK_TYPE_LABELS.TRASLADO
    if (form.task_id) {
      const task = tasksById[form.task_id]
      return task ? labels.TASK_TYPE_LABELS[task.task_type] : '—'
    }
    if (form.project_id) return labels.TASK_TYPE_LABELS.ADHOC
    return t('Interno')
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSaving(true)
    try {
      const saved = await timesheetsApi.updateTimesheet(entry.id, timesheetFormToPayload(form))
      onSaved(saved)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={t('Editar apontamento')} onClose={onClose} wide>
      <p className="-mt-1 mb-4 text-xs text-[var(--text-muted)]">{t('A alteração volta o status para Pendente e exige nova aprovação.')}</p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <TimesheetFieldsForm
          form={form}
          updateField={updateField}
          projects={projects}
          taskOptions={taskOptions}
          formTypeLabel={formTypeLabel}
          preview={previewTimesheetHours(form)}
        />
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
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
