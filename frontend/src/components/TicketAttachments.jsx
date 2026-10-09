import { useRef, useState } from 'react'
import * as ticketsApi from '../api/tickets'
import { useLanguage } from '../context/LanguageContext'
import Button from './Button'

// Limites espelhados de app/routers/tickets.py (a API valida de novo).
export const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
export const MAX_FILES_PER_UPLOAD = 5
export const MAX_ATTACHMENTS_PER_TICKET = 10
const ACCEPT = '.png,.jpg,.jpeg,.gif,.pdf,.txt,.log,.csv,.json,.xml,.xlsx,.xls,.docx,.doc,.zip'
const ALLOWED_EXTENSIONS = ACCEPT.replace(/\./g, '').split(',')

export function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Valida a seleção no navegador (a API repete as regras). Devolve a lista
 * aceita e a primeira mensagem de erro encontrada, se houver. */
export function validateSelection(current, picked, alreadyAttached, t) {
  const accepted = [...current]
  let error = ''
  for (const file of picked) {
    const extension = file.name.includes('.') ? file.name.split('.').pop().toLowerCase() : ''
    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      error = `${t('Tipo de arquivo não permitido')}: ${file.name}`
    } else if (file.size > MAX_ATTACHMENT_BYTES) {
      error = `${t('Arquivo acima de 10 MB')}: ${file.name}`
    } else if (file.size === 0) {
      error = `${t('Arquivo vazio')}: ${file.name}`
    } else if (accepted.length >= MAX_FILES_PER_UPLOAD) {
      error = t('Máximo de 5 arquivos por envio')
    } else if (alreadyAttached + accepted.length >= MAX_ATTACHMENTS_PER_TICKET) {
      error = t('O ticket aceita no máximo 10 anexos')
    } else {
      accepted.push(file)
    }
  }
  return { files: accepted, error }
}

/** Seleção de arquivos (botão + lista com remoção). Controlado por `files`. */
export function AttachmentPicker({ files, onChange, alreadyAttached = 0, disabled = false }) {
  const { t } = useLanguage()
  const inputRef = useRef(null)
  const [error, setError] = useState('')

  function handlePick(event) {
    const result = validateSelection(files, Array.from(event.target.files || []), alreadyAttached, t)
    setError(result.error)
    onChange(result.files)
    event.target.value = ''
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <input ref={inputRef} type="file" multiple accept={ACCEPT} onChange={handlePick} className="hidden" />
        <Button type="button" variant="secondary" disabled={disabled} onClick={() => inputRef.current?.click()}>
          {t('Anexar arquivos')}
        </Button>
        <span className="text-xs text-[var(--text-muted)]">
          {t('Imagens, PDF, logs, planilhas e documentos Office (até 10 MB cada).')}
        </span>
      </div>
      {error && <p className="text-xs text-[var(--status-critical)]">{error}</p>}
      {files.length > 0 && (
        <ul className="space-y-1">
          {files.map((file, index) => (
            <li
              key={`${file.name}-${index}`}
              className="flex items-center justify-between gap-2 rounded-lg border border-[var(--border)] px-2.5 py-1.5 text-xs"
            >
              <span className="truncate text-[var(--text-primary)]">
                {file.name} <span className="text-[var(--text-muted)]">({formatFileSize(file.size)})</span>
              </span>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onChange(files.filter((_, position) => position !== index))}
                className="shrink-0 text-[var(--text-muted)] hover:underline"
              >
                {t('Remover')}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Anexos de uma interação do histórico, com botão de download. */
export function AttachmentList({ ticketId, attachments, onError }) {
  const { t } = useLanguage()
  const [downloading, setDownloading] = useState(null)
  if (!attachments || attachments.length === 0) return null

  async function handleDownload(attachment) {
    setDownloading(attachment.id)
    try {
      await ticketsApi.downloadTicketAttachment(ticketId, attachment)
    } catch (err) {
      onError?.(err.message)
    } finally {
      setDownloading(null)
    }
  }

  return (
    <ul className="mt-2 space-y-1">
      {attachments.map((attachment) => (
        <li key={attachment.id} className="flex items-center justify-between gap-2 rounded-md bg-[var(--page)] px-2.5 py-1.5 text-xs">
          <span className="truncate text-[var(--text-primary)]">
            {attachment.filename} <span className="text-[var(--text-muted)]">({formatFileSize(attachment.size_bytes)})</span>
          </span>
          <button
            type="button"
            disabled={downloading === attachment.id}
            onClick={() => handleDownload(attachment)}
            className="shrink-0 font-medium text-[var(--series-1)] hover:underline"
          >
            {downloading === attachment.id ? t('Baixando…') : t('Baixar')}
          </button>
        </li>
      ))}
    </ul>
  )
}
