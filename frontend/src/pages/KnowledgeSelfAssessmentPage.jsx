import { useEffect, useMemo, useState } from 'react'
import * as knowledgeApi from '../api/knowledge'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Button from '../components/Button'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import StatusPill from '../components/StatusPill'
import { TextInput, Select } from '../components/FormField'
import { useLanguage } from '../context/LanguageContext'
import { formatDateTime } from '../utils/format'
import { KNOWLEDGE_REQUIREMENT_TONE, KNOWLEDGE_STATUS_TONE } from '../utils/labels'

/** "Registro de Funcionalidades por Consultor / Gerente" (pedido do
 * usuário, "NOVAS MELHORIAS") — autoavaliação de nível de conhecimento
 * (0 a 4) nas funcionalidades do catálogo liberadas pro perfil de quem
 * está logado (decisão confirmada com o usuário: o vínculo de perfil fica
 * no Módulo, ver GET /knowledge/my-catalog). Um passo só: o recurso atribui
 * um nível direto às funcionalidades que fazem parte do trabalho dele; o
 * que não mexer fica "Não avaliado" (sem precisar marcar/selecionar antes).
 *
 * Linhas já SUBMITTED (aguardando revisão) ficam travadas pra edição — só
 * DRAFT (nunca enviado, ou devolvido numa rejeição) e APPROVED (reabre um
 * novo ciclo, decisão confirmada: editar depois de aprovado volta pra
 * DRAFT) podem ser editadas. Isso evita o recurso "puxar" por engano um
 * item de dentro de um envio que já está sendo revisado.
 */
export default function KnowledgeSelfAssessmentPage() {
  const { t, labels } = useLanguage()
  const [systems, setSystems] = useState([])
  const [submissions, setSubmissions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [savingId, setSavingId] = useState(null)

  function load() {
    setLoading(true)
    setError('')
    Promise.all([knowledgeApi.getMyCatalog(), knowledgeApi.listMySubmissions()])
      .then(([catalog, mySubmissions]) => {
        setSystems(catalog)
        setSubmissions(mySubmissions)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const pendingCount = useMemo(
    () =>
      systems.reduce(
        (total, system) =>
          total +
          system.modules.reduce(
            (moduleTotal, module) => moduleTotal + module.functionalities.filter((f) => f.status === 'DRAFT').length,
            0,
          ),
        0,
      ),
    [systems],
  )

  function patchFunctionality(moduleId, functionalityId, patch) {
    setSystems((current) =>
      current.map((system) => ({
        ...system,
        modules: system.modules.map((module) =>
          module.id !== moduleId
            ? module
            : {
                ...module,
                functionalities: module.functionalities.map((f) => (f.id === functionalityId ? { ...f, ...patch } : f)),
              },
        ),
      })),
    )
  }

  async function handleLevelChange(moduleId, functionality, rawValue) {
    if (rawValue === '') return
    const selfLevel = Number(rawValue)
    setSavingId(functionality.id)
    try {
      const updated = await knowledgeApi.upsertMyRating(functionality.id, { self_level: selfLevel, notes: functionality.notes || null })
      patchFunctionality(moduleId, functionality.id, updated)
    } catch (err) {
      setError(err.message)
    } finally {
      setSavingId(null)
    }
  }

  async function handleNotesBlur(moduleId, functionality, notes) {
    if (functionality.self_level === null || functionality.self_level === undefined) return
    if ((functionality.notes || '') === notes) return
    setSavingId(functionality.id)
    try {
      const updated = await knowledgeApi.upsertMyRating(functionality.id, { self_level: functionality.self_level, notes: notes || null })
      patchFunctionality(moduleId, functionality.id, updated)
    } catch (err) {
      setError(err.message)
    } finally {
      setSavingId(null)
    }
  }

  async function handleSubmit() {
    setSubmitting(true)
    setSubmitError('')
    try {
      await knowledgeApi.submitMyRatings()
      load()
    } catch (err) {
      setSubmitError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const lastSubmission = submissions[0]

  return (
    <div>
      <PageHeader
        title={t('Registro de Conhecimento')}
        subtitle={t('Autoavalie seu nível de conhecimento nas funcionalidades do seu perfil.')}
        action={
          <Button onClick={handleSubmit} disabled={submitting || pendingCount === 0}>
            {submitting ? t('Enviando…') : `${t('Enviar para aprovação')}${pendingCount > 0 ? ` (${pendingCount})` : ''}`}
          </Button>
        }
      />

      {lastSubmission && lastSubmission.status === 'REJECTED' && (
        <div className="mb-4 rounded-lg border border-[var(--status-critical)]/30 bg-[var(--status-critical)]/10 px-3.5 py-2.5 text-sm text-[var(--status-critical)]">
          <strong>{t('Seu último envio foi devolvido')}</strong> ({formatDateTime(lastSubmission.reviewed_at)})
          {lastSubmission.review_notes ? `: ${lastSubmission.review_notes}` : '.'} {t('Ajuste e envie novamente.')}
        </div>
      )}
      {lastSubmission && lastSubmission.status === 'SUBMITTED' && (
        <div className="mb-4 rounded-lg border border-[var(--status-warning)]/30 bg-[var(--status-warning)]/10 px-3.5 py-2.5 text-sm text-[var(--status-warning)]">
          {t('Você tem um envio aguardando revisão desde')} {formatDateTime(lastSubmission.submitted_at)}.
        </div>
      )}

      {loading && <Spinner />}
      <ErrorBanner message={error} />
      <ErrorBanner message={submitError} />

      {!loading && !error && systems.length === 0 && (
        <Card>
          <p className="py-8 text-center text-sm text-[var(--text-muted)]">
            {t('Nenhuma funcionalidade liberada para o seu perfil ainda.')}
          </p>
        </Card>
      )}

      <div className="space-y-4">
        {systems.map((system) => (
          <Card key={system.id} title={system.name}>
            <div className="space-y-4">
              {system.modules.map((module) => (
                <div key={module.id} className="rounded-xl border border-[var(--border)] p-3.5">
                  <h3 className="mb-2 text-sm font-semibold text-[var(--text-primary)]">{module.name}</h3>
                  <div className="space-y-2">
                    {module.functionalities.map((functionality) => {
                      const locked = functionality.status === 'SUBMITTED'
                      return (
                        <div
                          key={functionality.id}
                          className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--border)] px-3 py-2"
                        >
                          <div className="min-w-[200px] flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-[var(--text-primary)]">{functionality.name}</span>
                              <StatusPill
                                label={labels.KNOWLEDGE_REQUIREMENT_LABELS[functionality.requirement]}
                                tone={KNOWLEDGE_REQUIREMENT_TONE[functionality.requirement]}
                              />
                              {functionality.status && (
                                <StatusPill
                                  label={labels.KNOWLEDGE_STATUS_LABELS[functionality.status]}
                                  tone={KNOWLEDGE_STATUS_TONE[functionality.status]}
                                />
                              )}
                            </div>
                            {functionality.description && (
                              <p className="mt-0.5 text-xs text-[var(--text-muted)]">{functionality.description}</p>
                            )}
                          </div>
                          <div className="w-64">
                            <Select
                              value={functionality.self_level ?? ''}
                              disabled={locked || savingId === functionality.id}
                              onChange={(event) => handleLevelChange(module.id, functionality, event.target.value)}
                            >
                              <option value="">{t('Não avaliado')}</option>
                              {[0, 1, 2, 3, 4].map((level) => (
                                <option key={level} value={level}>
                                  {labels.KNOWLEDGE_LEVEL_LABELS[level]}
                                </option>
                              ))}
                            </Select>
                          </div>
                          <div className="w-64">
                            <TextInput
                              placeholder={t('Observações (opcional)')}
                              defaultValue={functionality.notes || ''}
                              disabled={locked || functionality.self_level === null || functionality.self_level === undefined}
                              onBlur={(event) => handleNotesBlur(module.id, functionality, event.target.value)}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
