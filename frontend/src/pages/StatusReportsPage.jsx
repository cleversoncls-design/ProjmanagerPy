import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import * as statusReportsApi from '../api/statusReports'
import * as projectsApi from '../api/projects'
import * as usersApi from '../api/users'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Table from '../components/Table'
import StatTile from '../components/StatTile'
import StatusPill from '../components/StatusPill'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import Button from '../components/Button'
import Modal from '../components/Modal'
import StatusReportDeleteModal from '../components/StatusReportDeleteModal'
import StatusReportPrintSheet from '../components/StatusReportPrintSheet'
import { PencilIcon, PrinterIcon, TrashIcon } from '../components/icons'
import { FormField, Select, TextArea, TextInput } from '../components/FormField'
import { formatCurrency, formatDate, formatHoursDuration, formatPercent } from '../utils/format'
import { MANAGEMENT_ROLES, RAG_STATUS_TONE, RISK_LEVEL_TONE, RISK_STATUS_TONE } from '../utils/labels'

const RAG_FIELDS = [
  { key: 'rag_schedule', label: 'Prazo' },
  { key: 'rag_cost', label: 'Custo' },
  { key: 'rag_margin', label: 'Margem' },
  { key: 'rag_scope', label: 'Escopo' },
  { key: 'rag_risk', label: 'Risco' },
]

function emptyForm() {
  return {
    period_start: '',
    period_end: '',
    rag_schedule: 'GOOD',
    rag_cost: 'GOOD',
    rag_margin: 'GOOD',
    rag_scope: 'GOOD',
    rag_risk: 'GOOD',
    executive_summary: '',
    next_steps_client: '',
    next_steps_internal: '',
  }
}

/** Status Report por período (pedido do usuário: "pode implementar os 2
 * modelos e colocar na opção de relatorios", depois dos mockups "Interno"
 * (diretoria/gerências) e "Cliente" (gerente de projeto do cliente)
 * validados no canvas de design). Uma única tela pros dois perfis: quem
 * pode escrever (MANAGEMENT_ROLES) vê o botão "Novo Status Report", os
 * campos financeiros e as ações de editar/excluir/imprimir; PM do cliente
 * (que ganhou acesso ao menu Relatórios pela primeira vez, ver
 * STATUS_REPORT_VISIBLE_ROLES em utils/labels.js) só lista, abre e imprime
 * os relatórios do próprio projeto, sem os campos financeiros/ações
 * internas — o próprio backend já os devolve como null/[] (ver
 * app/routers/status_reports.py), nunca escondidos só na UI.
 *
 * Pedido do usuário (depois de testar em produção): "ter opção de
 * modificar"/"ter opção de excluir"/"os indicadores [...] venham
 * calculados pelo sistema [...] mas que o gerente possa modificar"/"onde
 * imprimir o status?" — os 4 atendidos aqui: formMode compartilha o mesmo
 * modal entre criar e editar; StatusReportDeleteModal confirma a exclusão
 * (nunca window.confirm); abrir "Novo Status Report" busca a sugestão de
 * GET .../suggested-rag pra pré-preencher os 5 semáforos (o gerente ainda
 * escolhe livremente antes de salvar, e pode trocar depois via "Editar");
 * "Imprimir" usa o mesmo padrão de portal + window.print() de
 * ServiceOrdersPage/ServiceOrderPrintSheet. */
export default function StatusReportsPage() {
  const { user } = useAuth()
  const { t, labels } = useLanguage()
  const canWrite = MANAGEMENT_ROLES.includes(user?.role)

  const [projects, setProjects] = useState([])
  const [usersById, setUsersById] = useState({})
  const [projectId, setProjectId] = useState('')
  const [reports, setReports] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [formMode, setFormMode] = useState(null) // null | 'create' | 'edit'
  const [editingReport, setEditingReport] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [loadingSuggestion, setLoadingSuggestion] = useState(false)

  const [deletingReport, setDeletingReport] = useState(null)
  const [printTarget, setPrintTarget] = useState(null)

  useEffect(() => {
    projectsApi
      .listProjects()
      .then((rows) => {
        const visible = rows.filter((p) => p.status !== 'MODELO')
        setProjects(visible)
        if (visible.length > 0) setProjectId(visible[0].id)
      })
      .catch((err) => setError(err.message))
    // Preparado por (nome) só é resolvível por quem pode chamar GET /users
    // (MANAGEMENT_ROLES) — PM do cliente não tem esse acesso, então a
    // tabela simplesmente mostra "—" nesse campo pra ele.
    if (canWrite) {
      usersApi
        .listUsers()
        .then((rows) => setUsersById(Object.fromEntries(rows.map((u) => [u.id, u]))))
        .catch(() => {})
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function loadReports(preferredId) {
    if (!projectId) return
    setLoading(true)
    setError('')
    statusReportsApi
      .listStatusReports(projectId)
      .then((rows) => {
        setReports(rows)
        setSelected(rows.find((r) => r.id === preferredId) || rows[0] || null)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => loadReports(), [projectId])

  const selectedProject = useMemo(() => projects.find((p) => p.id === projectId), [projects, projectId])

  function updateForm(field) {
    return (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  function openCreateForm() {
    setEditingReport(null)
    setForm(emptyForm())
    setFormError('')
    setFormMode('create')
    setLoadingSuggestion(true)
    statusReportsApi
      .getSuggestedRag(projectId)
      .then((suggestion) => setForm((prev) => ({ ...prev, ...suggestion })))
      .catch(() => {
        // Sugestão é só uma conveniência — sem ela, o formulário fica com
        // os padrões "Em dia" mesmo, o gerente escolhe tudo manualmente.
      })
      .finally(() => setLoadingSuggestion(false))
  }

  function openEditForm(report) {
    setEditingReport(report)
    setForm({
      period_start: report.period_start,
      period_end: report.period_end,
      rag_schedule: report.rag_schedule,
      rag_cost: report.rag_cost,
      rag_margin: report.rag_margin,
      rag_scope: report.rag_scope,
      rag_risk: report.rag_risk,
      executive_summary: report.executive_summary,
      next_steps_client: report.next_steps_client,
      next_steps_internal: report.next_steps_internal || '',
    })
    setFormError('')
    setFormMode('edit')
  }

  function closeForm() {
    setFormMode(null)
    setEditingReport(null)
  }

  function submitForm(event) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    const ragAndNarrative = {
      rag_schedule: form.rag_schedule,
      rag_cost: form.rag_cost,
      rag_margin: form.rag_margin,
      rag_scope: form.rag_scope,
      rag_risk: form.rag_risk,
      executive_summary: form.executive_summary,
      next_steps_client: form.next_steps_client,
      next_steps_internal: form.next_steps_internal || null,
    }
    const request =
      formMode === 'edit'
        ? statusReportsApi.updateStatusReport(projectId, editingReport.id, ragAndNarrative)
        : statusReportsApi.createStatusReport(projectId, { ...ragAndNarrative, period_start: form.period_start, period_end: form.period_end })
    request
      .then((saved) => {
        closeForm()
        loadReports(saved.id)
      })
      .catch((err) => setFormError(err.message))
      .finally(() => setSaving(false))
  }

  // Impressão (pedido do usuário: "onde imprimir o status?") — mesmo
  // padrão de ServiceOrdersPage: dispara o diálogo do navegador assim que
  // a folha estiver no portal, e volta a `null` no 'afterprint' (cobre
  // tanto imprimir quanto cancelar o diálogo).
  useEffect(() => {
    if (!printTarget) return
    const raf = requestAnimationFrame(() => window.print())
    return () => cancelAnimationFrame(raf)
  }, [printTarget])

  useEffect(() => {
    function handleAfterPrint() {
      setPrintTarget(null)
    }
    window.addEventListener('afterprint', handleAfterPrint)
    return () => window.removeEventListener('afterprint', handleAfterPrint)
  }, [])

  return (
    <div className="print:hidden">
      <PageHeader
        title={t('Status Report')}
        subtitle={t('Fechamento do período por projeto — indicadores, cronograma, riscos e próximos passos.')}
        action={canWrite && projectId ? <Button onClick={openCreateForm}>{t('Novo Status Report')}</Button> : null}
      />

      <Card className="mb-4">
        <FormField label={t('Projeto')}>
          <Select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.code} — {project.name}
              </option>
            ))}
          </Select>
        </FormField>
      </Card>

      <ErrorBanner message={error} />

      {loading ? (
        <Spinner />
      ) : (
        <>
          <Card title={t('Histórico')} className="mb-4">
            <Table
              columns={[
                {
                  key: 'period',
                  header: t('Período'),
                  render: (row) => `${formatDate(row.period_start)} – ${formatDate(row.period_end)}`,
                },
                {
                  key: 'rag',
                  header: t('Indicadores'),
                  render: (row) => (
                    <div className="flex flex-wrap gap-1">
                      {RAG_FIELDS.map((field) => (
                        <StatusPill
                          key={field.key}
                          label={labels.RAG_STATUS_LABELS[row[field.key]]}
                          tone={RAG_STATUS_TONE[row[field.key]]}
                          title={`${t(field.label)}: ${labels.RAG_STATUS_LABELS[row[field.key]]}`}
                        />
                      ))}
                    </div>
                  ),
                },
                {
                  key: 'prepared_by',
                  header: t('Preparado por'),
                  render: (row) => usersById[row.prepared_by_id]?.name || '—',
                },
                { key: 'created_at', header: t('Criado em'), render: (row) => formatDate(row.created_at) },
                {
                  key: 'actions',
                  header: '',
                  align: 'right',
                  render: (row) => (
                    <button
                      type="button"
                      onClick={() => setSelected(row)}
                      className="text-xs font-medium text-[var(--series-1)] hover:underline"
                    >
                      {t('Ver detalhe')}
                    </button>
                  ),
                },
              ]}
              rows={reports}
              getRowKey={(row) => row.id}
              emptyMessage={t('Nenhum status report registrado ainda.')}
            />
          </Card>

          {selected && (
            <StatusReportDetail
              report={selected}
              project={selectedProject}
              canWrite={canWrite}
              onEdit={() => openEditForm(selected)}
              onDelete={() => setDeletingReport(selected)}
              onPrint={() => setPrintTarget(selected)}
              t={t}
              labels={labels}
            />
          )}
        </>
      )}

      {formMode && (
        <Modal title={formMode === 'edit' ? t('Editar Status Report') : t('Novo Status Report')} onClose={closeForm} wide>
          <form onSubmit={submitForm} className="space-y-4">
            {formMode === 'edit' ? (
              <p className="text-xs text-[var(--text-muted)]">
                {t('Período')}: <span className="font-medium text-[var(--text-primary)]">{formatDate(form.period_start)} – {formatDate(form.period_end)}</span>{' '}
                ({t('não pode ser alterado depois de criado.')})
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <FormField label={t('Início do período')} required>
                  <TextInput type="date" required value={form.period_start} onChange={updateForm('period_start')} />
                </FormField>
                <FormField label={t('Fim do período')} required>
                  <TextInput type="date" required value={form.period_end} onChange={updateForm('period_end')} />
                </FormField>
              </div>
            )}

            <div>
              {formMode === 'create' && loadingSuggestion && (
                <p className="mb-2 text-xs text-[var(--text-muted)]">{t('Calculando sugestão dos indicadores…')}</p>
              )}
              <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                {RAG_FIELDS.map((field) => (
                  <FormField key={field.key} label={t(field.label)}>
                    <Select value={form[field.key]} onChange={updateForm(field.key)}>
                      {Object.entries(labels.RAG_STATUS_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </Select>
                  </FormField>
                ))}
              </div>
              {formMode === 'create' && (
                <p className="mt-1.5 text-xs text-[var(--text-muted)]">
                  {t('Sugestão calculada automaticamente a partir dos dados do projeto — ajuste livremente antes de salvar.')}
                </p>
              )}
            </div>

            <FormField label={t('Resumo executivo')} required>
              <TextArea rows={3} required value={form.executive_summary} onChange={updateForm('executive_summary')} />
            </FormField>

            <FormField label={t('Próximos passos (compartilhado com o cliente)')} required>
              <TextArea rows={3} required value={form.next_steps_client} onChange={updateForm('next_steps_client')} />
            </FormField>

            <FormField label={t('Ações internas (não compartilhadas com o cliente)')} hint={t('Opcional.')}>
              <TextArea rows={2} value={form.next_steps_internal} onChange={updateForm('next_steps_internal')} />
            </FormField>

            <ErrorBanner message={formError} />

            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={closeForm}>
                {t('Cancelar')}
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? t('Salvando…') : t('Salvar')}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {deletingReport && (
        <StatusReportDeleteModal
          projectId={projectId}
          report={deletingReport}
          onClose={() => setDeletingReport(null)}
          onDeleted={() => {
            setDeletingReport(null)
            loadReports()
          }}
        />
      )}

      {printTarget &&
        createPortal(
          <div className="hidden print:block">
            <StatusReportPrintSheet
              report={printTarget}
              project={selectedProject}
              preparedByName={usersById[printTarget.prepared_by_id]?.name}
            />
          </div>,
          document.body,
        )}
    </div>
  )
}

function StatusReportDetail({ report, project, canWrite, onEdit, onDelete, onPrint, t, labels }) {
  const hasFinancials = report.hours_consumed !== null || report.cost_actual !== null || report.cost_planned !== null
  return (
    <div className="space-y-4">
      <Card
        title={`${t('Status Report')} — ${project ? `${project.code} — ${project.name}` : ''}`}
        action={
          <div className="flex gap-1.5">
            <Button type="button" variant="secondary" onClick={onPrint}>
              <PrinterIcon size={14} /> {t('Imprimir')}
            </Button>
            {canWrite && (
              <>
                <Button type="button" variant="secondary" onClick={onEdit}>
                  <PencilIcon size={14} /> {t('Editar')}
                </Button>
                <Button type="button" variant="danger" onClick={onDelete}>
                  <TrashIcon size={14} /> {t('Excluir')}
                </Button>
              </>
            )}
          </div>
        }
      >
        <div className="mb-4 flex flex-wrap gap-1.5">
          {RAG_FIELDS.map((field) => (
            <StatusPill
              key={field.key}
              label={`${t(field.label)}: ${labels.RAG_STATUS_LABELS[report[field.key]]}`}
              tone={RAG_STATUS_TONE[report[field.key]]}
            />
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile
            compact
            label={t('Avanço do cronograma')}
            value={formatPercent(report.schedule_actual_pct)}
            hint={`${t('Previsto')}: ${formatPercent(report.schedule_planned_pct)}`}
            tone="primary"
          />
          {hasFinancials && (
            <>
              <StatTile compact label={t('Horas consumidas')} value={formatHoursDuration(report.hours_consumed)} />
              <StatTile compact label={t('Custo realizado')} value={formatCurrency(report.cost_actual)} />
              <StatTile
                compact
                label={t('Margem realizada')}
                value={report.margin_actual_pct !== null ? formatPercent(report.margin_actual_pct) : '—'}
                tone="good"
              />
            </>
          )}
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <p className="mb-1 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{t('Resumo executivo')}</p>
            <p className="text-sm text-[var(--text-primary)]">{report.executive_summary}</p>
          </div>
          <div>
            <p className="mb-1 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{t('Próximos passos')}</p>
            <p className="text-sm text-[var(--text-primary)]">{report.next_steps_client}</p>
          </div>
        </div>

        {report.next_steps_internal && (
          <div className="mt-4 rounded-lg border border-[var(--border)] bg-[var(--page)] p-3">
            <p className="mb-1 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">
              {t('Ações internas (não compartilhadas com o cliente)')}
            </p>
            <p className="text-sm text-[var(--text-primary)]">{report.next_steps_internal}</p>
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card title={t('Concluído na semana anterior')}>
          <Table
            columns={[
              { key: 'wbs', header: t('WBS'), render: (row) => row.wbs_code },
              { key: 'name', header: t('Tarefa'), render: (row) => row.name },
            ]}
            rows={report.tasks_done}
            getRowKey={(row) => row.id}
            emptyMessage={t('Nenhuma tarefa concluída no período.')}
          />
        </Card>
        <Card title={t('Previsto para a próxima semana')}>
          <Table
            columns={[
              { key: 'wbs', header: t('WBS'), render: (row) => row.wbs_code },
              { key: 'name', header: t('Tarefa'), render: (row) => row.name },
            ]}
            rows={report.tasks_next}
            getRowKey={(row) => row.id}
            emptyMessage={t('Nenhuma tarefa prevista para o próximo período.')}
          />
        </Card>
      </div>

      <Card title={t('Riscos')}>
        <Table
          columns={[
            { key: 'description', header: t('Descrição'), render: (row) => row.description },
            {
              key: 'probability',
              header: t('Probabilidade'),
              render: (row) => (
                <StatusPill label={labels.RISK_LEVEL_LABELS[row.probability]} tone={RISK_LEVEL_TONE[row.probability]} />
              ),
            },
            {
              key: 'impact',
              header: t('Impacto'),
              render: (row) => <StatusPill label={labels.RISK_LEVEL_LABELS[row.impact]} tone={RISK_LEVEL_TONE[row.impact]} />,
            },
            {
              key: 'status',
              header: t('Status'),
              render: (row) => <StatusPill label={labels.RISK_STATUS_LABELS[row.status]} tone={RISK_STATUS_TONE[row.status]} />,
            },
          ]}
          rows={report.risks_snapshot}
          getRowKey={(row) => row.id}
          emptyMessage={t('Nenhum risco registrado neste período.')}
        />
      </Card>
    </div>
  )
}
