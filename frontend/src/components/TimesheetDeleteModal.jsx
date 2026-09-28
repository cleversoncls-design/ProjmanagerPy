import { useState } from 'react'
import * as timesheetsApi from '../api/timesheets'
import { useLanguage } from '../context/LanguageContext'
import Modal from './Modal'
import Button from './Button'
import ErrorBanner from './ErrorBanner'
import { formatDate } from '../utils/format'

/** Modal de confirmação pra excluir um apontamento — mesmo padrão de
 * ProjectDeleteModal/UserDeleteModal (Projects/UsersPage). Usado tanto em
 * "Meus apontamentos" (TimesheetsPage) quanto na coluna de ações da Ordem
 * de Serviço (ServiceOrdersPage). A API (DELETE /timesheets/{id}) já
 * recusa (403/422) fora do dono/fora de Pendente-Rejeitado, mas quem chama
 * este componente só deve oferecer o botão quando `isTimesheetEditable`
 * (ver utils/timesheetForm.js) já é true — este modal existe só pra evitar
 * um clique acidental apagar um apontamento válido. */
export default function TimesheetDeleteModal({ entry, entryLabel, onClose, onDeleted }) {
  const { t } = useLanguage()
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')

  async function handleDelete() {
    setDeleting(true)
    setError('')
    try {
      await timesheetsApi.deleteTimesheet(entry.id)
      onDeleted()
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Modal title={t('Excluir apontamento')} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          {t('Tem certeza que quer excluir este apontamento?')}{' '}
          <span className="font-medium text-[var(--text-primary)]">
            {formatDate(entry.date)} · {entryLabel.projectLabel} · {entryLabel.taskLabel}
          </span>
          ? {t('Essa ação não pode ser desfeita.')}
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
