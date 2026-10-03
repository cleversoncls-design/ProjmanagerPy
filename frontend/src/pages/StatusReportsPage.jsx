import { useEffect, useMemo, useState } from 'react'
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
 * pode escrever (MANAGEMENT_ROLES) vê o botão "Novo Status Report" e os
 * campos financeiros; PM do cliente (que ganhou acesso ao menu Relatórios
 * pela primeira vez, ver STATUS_REPORT_VISIBLE_ROLES em utils/labels.js)
 * só lista e abre os relatórios do próprio projeto, sem os campos
 * financeiros/ações internas — o próprio backend já os devolve como
 * null/[] (ver app/routers/status_reports.py), nunca escondidos só na UI. */
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
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

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

  function loadReports() {
    if (!projectId) return
    setLoading(true)
    setError('')
    statusReportsApi
      .listStatusReports(projectId)
      .then((rows) => {
        setReports(rows)
        setSelected(rows[0] || null)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(loadReports, [projectId])

  const selectedProject = useMemo(() => projects.find((p) => p.id === projectId), [projects, projectId])

  function updateForm(field) {
    return (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  function openForm() {
    setForm(emptyForm())
    setFormError('')
    setShowForm(true)
  }

  function submitForm(event) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    statusReportsApi
      .createStatusReport(projectId, {
        ...form,
        next_steps_internal: form.next_steps_internal || null,
      })
      .then(() => {
        setShowForm(false)
        loadReports()
      })
      .catch((err) => setFormError(err.message))
      .finally(() => setSaving(false))
  }

  return (
    <div>
      <PageHeader
        title={t('Status Report')}
        subtitle={t('Fechamento do período por projeto — indicadores, cronograma, riscos e próximos passos.')}
        action={
          canWrite && projectId ? <Button onClick={openForm}>{t('Novo Status Report')}</Button> : null
        }
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
            <StatusReportDetail report={selected} project={selectedProject} canSeeFinancials={canWrite} t={t} labels={labels} />
          )}
        </>
      )}

      {showForm && (
        <Modal title={t('Novo Status Report')} onClose={() => setShowForm(false)} wide>
          <form onSubmit={submitForm} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <FormField label={t('Início do período')} required>
                <TextInput type="date" required value={form.period_start} onChange={updateForm('period_start')} />
              </FormField>
              <FormField label={t('Fim do período')} required>
                <TextInput type="date" required value={form.period_end} onChange={updateForm('period_end')} />
              </FormField>
            </div>

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
              <Button type="button" variant="secondary" onClick={() => setShowForm(false)}>
                {t('Cancelar')}
              </Button>
              <Button type="submit" disabled={saving}>
                {t('Salvar')}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}

function StatusReportDetail({ report, project, t, labels }) {
  const hasFinancials = report.hours_consumed !== null || report.cost_actual !== null || report.cost_planned !== null
  return (
    <div className="space-y-4">
      <Card title={`${t('Status Report')} — ${project ? `${project.code} — ${project.name}` : ''}`}>
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
