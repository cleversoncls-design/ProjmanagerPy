import { useEffect, useState } from 'react'
import * as knowledgeApi from '../api/knowledge'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Table from '../components/Table'
import Button from '../components/Button'
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import StatusPill from '../components/StatusPill'
import { TextArea, Select } from '../components/FormField'
import { useLanguage } from '../context/LanguageContext'
import { useAuth } from '../context/AuthContext'
import { formatDateTime } from '../utils/format'
import { KNOWLEDGE_STATUS_TONE } from '../utils/labels'

const TABS = [
  { key: 'SUBMITTED', label: 'Pendentes' },
  { key: 'APPROVED', label: 'Aprovados' },
  { key: 'REJECTED', label: 'Rejeitados' },
]

/** "Revisão e Aprovação" (pedido do usuário, "NOVAS MELHORIAS") — decisões
 * confirmadas com o usuário: aprovação é SEMPRE do envio inteiro (nunca
 * item a item) e o revisor PODE ajustar o nível de qualquer item antes de
 * aprovar. Um revisor não pode revisar a própria autoavaliação (ver
 * review_submission em app/routers/knowledge.py) — um Gerente de Projetos
 * está nos dois grupos de acesso ao mesmo tempo (autoavaliação e revisão),
 * então precisa de outra pessoa pra aprovar a dele. */
export default function KnowledgeReviewPage() {
  const { t, labels } = useLanguage()
  const { user } = useAuth()
  const [tab, setTab] = useState('SUBMITTED')
  const [submissions, setSubmissions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [openSubmission, setOpenSubmission] = useState(null)

  function load() {
    setLoading(true)
    setError('')
    knowledgeApi
      .listSubmissions(tab)
      .then(setSubmissions)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [tab])

  function handleReviewed() {
    setOpenSubmission(null)
    load()
  }

  return (
    <div>
      <PageHeader
        title={t('Revisão e Aprovação')}
        subtitle={t('Revise as autoavaliações de conhecimento enviadas por consultores e gerentes de projeto.')}
      />

      <div className="mb-4 flex gap-1.5">
        {TABS.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setTab(item.key)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              tab === item.key
                ? 'bg-[var(--series-1)] text-white'
                : 'border border-[var(--border)] bg-[var(--surface)] text-[var(--text-secondary)] hover:bg-[var(--page)]'
            }`}
          >
            {t(item.label)}
          </button>
        ))}
      </div>

      {loading && <Spinner />}
      <ErrorBanner message={error} />

      {!loading && !error && (
        <Card>
          <Table
            columns={[
              { key: 'resource_name', header: t('Recurso') },
              { key: 'submitted_at', header: t('Enviado em'), render: (row) => formatDateTime(row.submitted_at) },
              { key: 'items', header: t('Itens'), align: 'right', render: (row) => row.items.length },
              ...(tab !== 'SUBMITTED'
                ? [
                    {
                      key: 'reviewed_at',
                      header: t('Revisado em'),
                      render: (row) => `${formatDateTime(row.reviewed_at)} (${row.reviewer_name || '—'})`,
                    },
                  ]
                : []),
              {
                key: 'actions',
                header: '',
                align: 'right',
                render: (row) => (
                  <Button variant="secondary" onClick={() => setOpenSubmission(row)}>
                    {tab === 'SUBMITTED' ? t('Revisar') : t('Ver')}
                  </Button>
                ),
              },
            ]}
            rows={submissions}
            getRowKey={(row) => row.id}
            emptyMessage={
              tab === 'SUBMITTED' ? t('Nenhum envio pendente de revisão.') : t('Nenhum envio encontrado neste filtro.')
            }
          />
        </Card>
      )}

      {openSubmission && (
        <ReviewModal
          submission={openSubmission}
          currentUserId={user?.id}
          onClose={() => setOpenSubmission(null)}
          onReviewed={handleReviewed}
        />
      )}
    </div>
  )
}

function ReviewModal({ submission, currentUserId, onClose, onReviewed }) {
  const { t, labels } = useLanguage()
  const pending = submission.status === 'SUBMITTED'
  const [levels, setLevels] = useState(() =>
    Object.fromEntries(submission.items.map((item) => [item.functionality_id, item.self_level ?? 0])),
  )
  const [reviewNotes, setReviewNotes] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const isOwn = Boolean(currentUserId) && submission.resource_user_id === currentUserId

  async function handleReview(status) {
    setError('')
    if (status === 'REJECTED' && !reviewNotes.trim()) {
      setError(t('Informe o motivo da rejeição em Comentário do revisor'))
      return
    }
    setSaving(true)
    try {
      await knowledgeApi.reviewSubmission(submission.id, {
        status,
        review_notes: reviewNotes || null,
        items: Object.entries(levels).map(([functionality_id, reviewed_level]) => ({
          functionality_id,
          reviewed_level: Number(reviewed_level),
        })),
      })
      onReviewed()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={`${t('Revisão de conhecimento')} — ${submission.resource_name}`} onClose={onClose} wide>
      <div className="space-y-4">
        <p className="text-xs text-[var(--text-muted)]">
          {t('Enviado em')} {formatDateTime(submission.submitted_at)}
        </p>

        <div className="max-h-[50vh] overflow-y-auto rounded-lg border border-[var(--border)]">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--page)]">
                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-[var(--text-muted)]">{t('Funcionalidade')}</th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-[var(--text-muted)]">{t('Autoavaliação')}</th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-[var(--text-muted)]">{t('Nível final')}</th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-[var(--text-muted)]">{t('Observações')}</th>
              </tr>
            </thead>
            <tbody>
              {submission.items.map((item) => (
                <tr key={item.id} className="border-b border-[var(--border)] last:border-0">
                  <td className="px-3 py-2">
                    <div className="font-medium text-[var(--text-primary)]">{item.functionality_name}</div>
                    <div className="text-xs text-[var(--text-muted)]">
                      {item.system_name} / {item.module_name}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-[var(--text-secondary)]">{labels.KNOWLEDGE_LEVEL_SHORT_LABELS[item.self_level]}</td>
                  <td className="px-3 py-2">
                    {pending ? (
                      <Select
                        value={levels[item.functionality_id]}
                        onChange={(event) => setLevels((current) => ({ ...current, [item.functionality_id]: event.target.value }))}
                      >
                        {[0, 1, 2, 3, 4].map((level) => (
                          <option key={level} value={level}>
                            {labels.KNOWLEDGE_LEVEL_SHORT_LABELS[level]}
                          </option>
                        ))}
                      </Select>
                    ) : (
                      <span className="text-[var(--text-primary)]">
                        {item.reviewed_level !== null ? labels.KNOWLEDGE_LEVEL_SHORT_LABELS[item.reviewed_level] : '—'}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs text-[var(--text-muted)]">{item.notes || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {pending && isOwn && (
          <ErrorBanner message={t('Você não pode revisar sua própria autoavaliação — peça para outro Gerente de Projetos, Gerente de Serviços ou Diretor Geral revisar.')} />
        )}
        {pending && !isOwn ? (
          <>
            <div>
              <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                {t('Comentário do revisor')}
                <span className="text-[var(--text-muted)]"> ({t('obrigatório ao rejeitar')})</span>
              </span>
              <TextArea rows={2} value={reviewNotes} onChange={(event) => setReviewNotes(event.target.value)} />
            </div>
            <ErrorBanner message={error} />
            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="secondary" onClick={onClose}>
                {t('Cancelar')}
              </Button>
              <Button type="button" variant="danger" disabled={saving} onClick={() => handleReview('REJECTED')}>
                {t('Rejeitar')}
              </Button>
              <Button type="button" disabled={saving} onClick={() => handleReview('APPROVED')}>
                {saving ? t('Salvando…') : t('Aprovar')}
              </Button>
            </div>
          </>
        ) : pending && isOwn ? (
          <div className="flex justify-end pt-1">
            <Button type="button" variant="secondary" onClick={onClose}>
              {t('Fechar')}
            </Button>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <StatusPill label={labels.KNOWLEDGE_STATUS_LABELS[submission.status]} tone={KNOWLEDGE_STATUS_TONE[submission.status]} />
              <span className="text-xs text-[var(--text-muted)]">
                {t('por')} {submission.reviewer_name} {t('em')} {formatDateTime(submission.reviewed_at)}
              </span>
            </div>
            {submission.review_notes && <p className="text-sm text-[var(--text-secondary)]">{submission.review_notes}</p>}
            <div className="flex justify-end pt-1">
              <Button type="button" variant="secondary" onClick={onClose}>
                {t('Fechar')}
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  )
}
