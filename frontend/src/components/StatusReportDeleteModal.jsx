import { useState } from 'react'
import * as statusReportsApi from '../api/statusReports'
import { useLanguage } from '../context/LanguageContext'
import Modal from './Modal'
import Button from './Button'
import ErrorBanner from './ErrorBanner'
import { formatDate } from '../utils/format'

/** Confirmação de exclusão de um Status Report (pedido do usuário: "ter
 * opção de excluir") — mesmo padrão de TimesheetDeleteModal, nunca
 * `window.confirm`. */
export default function StatusReportDeleteModal({ projectId, report, onClose, onDeleted }) {
  const { t } = useLanguage()
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')

  async function handleDelete() {
    setDeleting(true)
    setError('')
    try {
      await statusReportsApi.deleteStatusReport(projectId, report.id)
      onDeleted()
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Modal title={t('Excluir Status Report')} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          {t('Tem certeza que quer excluir o Status Report do período')}{' '}
          <span className="font-medium text-[var(--text-primary)]">
            {formatDate(report.period_start)} – {formatDate(report.period_end)}
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
