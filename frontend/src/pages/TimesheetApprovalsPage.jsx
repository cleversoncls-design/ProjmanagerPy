import { useEffect, useMemo, useState } from 'react'
import * as timesheetsApi from '../api/timesheets'
import * as resourcesApi from '../api/resources'
import * as usersApi from '../api/users'
import * as projectsApi from '../api/projects'
import * as tasksApi from '../api/tasks'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Button from '../components/Button'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import StatusPill from '../components/StatusPill'
import { FormField, TextInput, Select } from '../components/FormField'
import { CheckIcon, XIcon } from '../components/icons'
import { formatDate, formatTime, formatHoursDuration } from '../utils/format'
import { ADMIN_LIKE_ROLES, resourceFunctionLevelLabel } from '../utils/labels'

/** Página própria pra "Aprovações pendentes" — era uma seção dentro de
 * Apontamento de horas (TimesheetsPage), pedido do usuário pra separar numa
 * rotina própria do menu lateral, já que quem aprova (ADMIN/INTERNAL_PM)
 * nem sempre é quem está apontando as próprias horas ali. A rota já fica
 * restrita a MANAGEMENT_ROLES em App.jsx, então não precisa repetir a
 * checagem de papel aqui dentro — diferente da versão antiga embutida em
 * TimesheetsPage, que também era visível a CONSULTANT e escondia a seção
 * via canManage. */
export default function TimesheetApprovalsPage() {
  const { user } = useAuth()
  const { labels, t } = useLanguage()

  const [projects, setProjects] = useState([])
  const [allTasks, setAllTasks] = useState([])
  const [resources, setResources] = useState([])
  const [users, setUsers] = useState([])

  const [pending, setPending] = useState([])
  const [loadingPending, setLoadingPending] = useState(true)
  const [listError, setListError] = useState('')
  const [actingId, setActingId] = useState(null)

  const [filters, setFilters] = useState({ start: '', end: '', resource_id: '', project_id: '' })

  useEffect(() => {
    projectsApi
      .listProjects()
      .then((rows) => {
        setProjects(rows)
        Promise.all(rows.map((p) => tasksApi.listTasks(p.id).catch(() => []))).then((lists) => setAllTasks(lists.flat()))
      })
      .catch(() => {})
    resourcesApi.listResources().then(setResources).catch(() => {})
    usersApi.listUsers().then(setUsers).catch(() => {})
  }, [])

  const usersById = useMemo(() => Object.fromEntries(users.map((u) => [u.id, u])), [users])
  const resourcesById = useMemo(
    () =>
      Object.fromEntries(
        resources.map((r) => [r.id, { ...r, userName: usersById[r.user_id]?.name || resourceFunctionLevelLabel(r, labels) || r.id }]),
      ),
    [resources, usersById, labels],
  )
  const projectsById = useMemo(() => Object.fromEntries(projects.map((p) => [p.id, p])), [projects])
  const tasksById = useMemo(() => Object.fromEntries(allTasks.map((task) => [task.id, task])), [allTasks])
  // INTERNAL_PM só vê (e só consegue aprovar, ver GET /timesheets no
  // backend) os projetos onde é o gerente; ADMIN continua enxergando todos
  // — mesmo critério de antes, só que agora é o único filtro de projeto
  // desta página (não compete mais com o de "Meus apontamentos").
  const projectOptions = useMemo(
    () => (user.role === 'INTERNAL_PM' ? projects.filter((p) => p.manager_id === user.id) : projects),
    [projects, user.role, user.id],
  )

  function loadPending() {
    setLoadingPending(true)
    timesheetsApi
      .listTimesheets({
        status_filter: 'PENDING',
        start: filters.start || undefined,
        end: filters.end || undefined,
        resource_id: filters.resource_id || undefined,
        project_id: filters.project_id || undefined,
      })
      .then(setPending)
      .catch((err) => setListError(err.message))
      .finally(() => setLoadingPending(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(loadPending, [filters.start, filters.end, filters.resource_id, filters.project_id])

  function updateFilter(field) {
    return (event) => setFilters((prev) => ({ ...prev, [field]: event.target.value }))
  }

  function entryDescription(entry) {
    if (entry.task_id) {
      const task = tasksById[entry.task_id]
      const project = task ? projectsById[task.project_id] : null
      return {
        projectLabel: project ? `${project.code} — ${project.name}` : '—',
        taskLabel: task ? `${task.wbs_code} ${task.name}` : '—',
        typeLabel: task ? labels.TASK_TYPE_LABELS[task.task_type] : '—',
      }
    }
    if (entry.project_id) {
      const project = projectsById[entry.project_id]
      if (entry.is_transit) {
        return { projectLabel: project ? `${project.code} — ${project.name}` : '—', taskLabel: t('Traslado'), typeLabel: labels.TASK_TYPE_LABELS.TRASLADO }
      }
      return { projectLabel: project ? `${project.code} — ${project.name}` : '—', taskLabel: t('Avulso'), typeLabel: labels.TASK_TYPE_LABELS.ADHOC }
    }
    // Ausência da empresa (pedido do usuário) — qualquer aprovador vê o
    // tipo exato (decisão confirmada: sem mascarar por perfil).
    if (entry.absence_type) {
      return { projectLabel: t('Interno'), taskLabel: '—', typeLabel: labels.ABSENCE_TYPE_LABELS[entry.absence_type] || entry.absence_type }
    }
    return { projectLabel: t('Interno'), taskLabel: '—', typeLabel: t('Interno') }
  }

  async function handleStatus(entry, newStatus) {
    setActingId(entry.id)
    setListError('')
    try {
      await timesheetsApi.updateTimesheetStatus(entry.id, newStatus)
      loadPending()
    } catch (err) {
      setListError(err.message)
    } finally {
      setActingId(null)
    }
  }

  return (
    <div>
      <PageHeader title={t('Aprovações de horas')} subtitle={t('Aprove ou rejeite os apontamentos pendentes dos consultores.')} />

      <ErrorBanner message={listError} />

      <Card title={t('Aprovações pendentes')}>
        <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4">
          <FormField label={t('Data inicial')}>
            <TextInput type="date" value={filters.start} onChange={updateFilter('start')} />
          </FormField>
          <FormField label={t('Data final')}>
            <TextInput type="date" value={filters.end} onChange={updateFilter('end')} />
          </FormField>
          <FormField label={t('Consultor')}>
            <Select value={filters.resource_id} onChange={updateFilter('resource_id')}>
              <option value="">{t('Todos')}</option>
              {resources.map((r) => (
                <option key={r.id} value={r.id}>
                  {resourcesById[r.id]?.userName || r.id}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label={t('Projeto')}>
            <Select value={filters.project_id} onChange={updateFilter('project_id')}>
              <option value="">{t('Todos')}</option>
              {projectOptions.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.code} — {project.name}
                </option>
              ))}
            </Select>
          </FormField>
        </div>
        {loadingPending ? (
          <Spinner />
        ) : pending.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">{t('Nenhum apontamento pendente.')}</p>
        ) : (
          <div className="space-y-1.5">
            {pending.map((entry) => {
              const { projectLabel, taskLabel, typeLabel } = entryDescription(entry)
              const blockedForMe = entry.unscheduled && !ADMIN_LIKE_ROLES.includes(user.role)
              return (
                <div key={entry.id} className="rounded-lg border border-[var(--border)] px-3 py-2.5 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-[var(--text-primary)]">{formatDate(entry.date)}</span>
                      <span className="text-[var(--text-secondary)]">
                        {resourcesById[entry.resource_id]?.userName || '—'} · {projectLabel} · {taskLabel} · {typeLabel}
                      </span>
                      {entry.start_time && (
                        <span className="text-[var(--text-muted)]">
                          {formatTime(entry.start_time)}–{formatTime(entry.end_time)} ({formatHoursDuration(entry.hours_spent)})
                        </span>
                      )}
                      {entry.task_progress_percentage != null && (
                        <span className="text-[var(--text-muted)]">{t('Avanço')}: {entry.task_progress_percentage}%</span>
                      )}
                      {entry.work_classification === 'REWORK' && <StatusPill label={t('Retrabalho')} tone="warning" />}
                      {entry.unscheduled && <StatusPill label={t('Fora da agenda')} tone="serious" />}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={actingId === entry.id || blockedForMe}
                        title={blockedForMe ? t('Só Administrador, Gerente de Serviços ou Diretor Geral podem aprovar apontamentos fora da agenda.') : undefined}
                        onClick={() => handleStatus(entry, 'APPROVED')}
                      >
                        <CheckIcon size={15} /> {t('Aprovar')}
                      </Button>
                      <Button type="button" variant="danger" disabled={actingId === entry.id} onClick={() => handleStatus(entry, 'REJECTED')}>
                        <XIcon size={15} /> {t('Rejeitar')}
                      </Button>
                    </div>
                  </div>
                  {/* Pedido do usuário: o motivo do retrabalho precisa ficar visível
                      direto na tela de aprovação (não só no tooltip do selo
                      "Retrabalho", de difícil descoberta) — mesma ideia de
                      mostrar a Descrição logo abaixo. */}
                  {entry.work_classification === 'REWORK' && (
                    <p className="mt-1 text-xs text-[var(--text-secondary)]">
                      <span className="font-medium">{t('Motivo do retrabalho')}:</span>{' '}
                      {(entry.rework_reasons || []).map((reason) => labels.REWORK_REASON_LABELS[reason] || reason).join(', ') || '—'}
                    </p>
                  )}
                  {entry.description && <p className="mt-1 text-xs text-[var(--text-muted)]">{entry.description}</p>}
                </div>
              )
            })}
          </div>
        )}
      </Card>
    </div>
  )
}
