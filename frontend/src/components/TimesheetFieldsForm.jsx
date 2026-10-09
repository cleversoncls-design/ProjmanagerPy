import { useEffect, useMemo, useState } from 'react'
import * as ticketsApi from '../api/tickets'
import { useLanguage } from '../context/LanguageContext'
import { FormField, TextInput, Select, TextArea } from './FormField'
import { timesheetFormNeedsTaskOrTransit } from '../utils/timesheetForm'

/** Campos de um apontamento (Data/Projeto/Tarefa/Tipo/Horário/Intervalo/
 * Total calculado/Descrição) — extraído do card "Novo/Editar apontamento"
 * de TimesheetsPage.jsx pra ser reusado também no modal de edição aberto a
 * partir da Ordem de Serviço (ver TimesheetEditModal.jsx). Sem `<form>`
 * nem botões de ação — quem usa este componente é responsável pelo
 * `<form onSubmit>`/Salvar/Cancelar em volta (formatos diferentes: card
 * inline em TimesheetsPage, `<Modal>` em TimesheetEditModal). */
export default function TimesheetFieldsForm({
  form,
  updateField,
  projects,
  taskOptions,
  parentTaskIds,
  formTypeLabel,
  preview,
  onToggleReworkReason,
}) {
  const { t, labels } = useLanguage()
  // Só projetos ativos no dropdown pra lançar hora nova (pedido do
  // usuário — não faz sentido apontar num projeto ainda em planejamento ou
  // já parado/concluído; a API já bloqueia isso, ver
  // "Só é possível apontar horas em projetos ativos" em routers/
  // timesheets.py). Mantém o projeto atual na lista mesmo que não esteja
  // mais ativo, senão editar um apontamento antigo de um projeto que
  // fechou depois ficaria com o campo Projeto em branco.
  const projectOptions = useMemo(() => {
    const active = projects.filter((p) => p.status === 'ACTIVE')
    if (form.project_id && !active.some((p) => p.id === form.project_id)) {
      const current = projects.find((p) => p.id === form.project_id)
      if (current) return [...active, current]
    }
    return active
  }, [projects, form.project_id])

  // Pedido do usuário: projeto sem tarefa nem Traslado não é mais um
  // apontamento válido ("avulso" foi descontinuado) — ver
  // timesheetFormNeedsTaskOrTransit, utils/timesheetForm.js.
  const needsTaskOrTransit = timesheetFormNeedsTaskOrTransit(form)

  // Ticket interno (pendente) que originou a hora — opcional. Lista os
  // tickets em aberto direcionados a mim na tarefa escolhida; o ticket já
  // vinculado (edição) sempre aparece, mesmo que tenha fechado depois.
  const [ticketOptions, setTicketOptions] = useState([])
  useEffect(() => {
    if (!form.task_id) {
      setTicketOptions([])
      return
    }
    let cancelled = false
    ticketsApi
      .listTickets({ task_id: form.task_id, scope: 'assigned', open_only: true })
      .then((rows) => {
        if (!cancelled) setTicketOptions(rows)
      })
      .catch(() => {
        if (!cancelled) setTicketOptions([])
      })
    return () => {
      cancelled = true
    }
  }, [form.task_id])
  const selectedTicketMissing = Boolean(form.ticket_id) && !ticketOptions.some((ticket) => ticket.id === form.ticket_id)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <FormField label={t('Data')} required>
          <TextInput type="date" required value={form.date} onChange={updateField('date')} />
        </FormField>
        <FormField label={t('Projeto')} hint={form.absence_type ? t('Desabilitado — o registro é de ausência (custo interno).') : t('Deixe em branco para hora administrativa interna.')}>
          <Select value={form.project_id} onChange={updateField('project_id')} disabled={Boolean(form.absence_type)}>
            <option value="">{t('Interno')}</option>
            {projectOptions.map((project) => (
              <option key={project.id} value={project.id}>
                {project.code} — {project.name}
              </option>
            ))}
          </Select>
        </FormField>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <FormField label={t('Tarefa')} hint={!form.project_id ? t('Selecione um projeto para escolher a tarefa.') : undefined}>
          <Select value={form.task_id} onChange={updateField('task_id')} disabled={!form.project_id || form.is_transit || Boolean(form.absence_type)}>
            {/* Pedido do usuário: projeto sem tarefa (nem Traslado) deixou de
                ser um apontamento válido — esta opção é só o placeholder
                "nada escolhido ainda", nunca um valor final aceito pelo
                backend (ver _resolve_task_and_project, routers/timesheets.py). */}
            <option value="">{t('Selecione uma tarefa…')}</option>
            {taskOptions.map((task) => {
              // Tarefas "pai" (com tarefas-filha) aparecem na lista — servem
              // de referência pra identificar a etapa, já que filhas de
              // etapas diferentes podem ter o mesmo nome — mas não podem
              // ser selecionadas (apontamento só nas tarefas-filha).
              const isParent = parentTaskIds?.has(task.id)
              return (
                <option key={task.id} value={task.id} disabled={isParent}>
                  {task.wbs_code} — {task.name}
                  {isParent ? ` (${t('tarefa-pai, selecione uma tarefa-filha')})` : ''}
                </option>
              )
            })}
          </Select>
          {needsTaskOrTransit && (
            <span className="mt-1 block text-xs text-[var(--status-critical)]">
              {t('Obrigatório — selecione uma tarefa ou marque Traslado abaixo.')}
            </span>
          )}
        </FormField>
        <FormField label={t('Tipo de apontamento')} hint={t('Segue automaticamente o tipo da tarefa (Gestão/Consultoria).')}>
          <div className="flex h-[38px] items-center rounded-lg border border-[var(--border)] bg-[var(--page)] px-3 text-sm text-[var(--text-secondary)]">
            {formTypeLabel()}
          </div>
        </FormField>
      </div>
      {form.task_id && (ticketOptions.length > 0 || form.ticket_id) && (
        <FormField label={t('Ticket')} hint={t('Opcional — vincula esta hora a um ticket direcionado a você nesta tarefa.')}>
          <Select value={form.ticket_id || ''} onChange={updateField('ticket_id')}>
            <option value="">{t('Sem ticket')}</option>
            {selectedTicketMissing && <option value={form.ticket_id}>{t('Ticket vinculado')}</option>}
            {ticketOptions.map((ticket) => (
              <option key={ticket.id} value={ticket.id}>
                {ticket.code} — {ticket.title}
              </option>
            ))}
          </Select>
        </FormField>
      )}
      {form.task_id && (
        <div className="grid grid-cols-2 gap-4">
          <FormField label={t('% de Avanço da Tarefa')} hint={t('Atualiza o % realizado desta tarefa ao salvar.')}>
            <TextInput
              type="number"
              min="0"
              max="100"
              step="1"
              value={form.task_progress_percentage}
              onChange={updateField('task_progress_percentage')}
            />
          </FormField>
          <FormField label={t('Classificação do trabalho')}>
            <div className="flex h-[38px] items-center gap-4 rounded-lg border border-[var(--border)] bg-[var(--page)] px-3 text-sm text-[var(--text-primary)]">
              <label className="flex items-center gap-1.5">
                <input
                  type="radio"
                  name="work_classification"
                  value="NORMAL"
                  checked={form.work_classification !== 'REWORK'}
                  onChange={updateField('work_classification')}
                />
                {t('Normal')}
              </label>
              <label className="flex items-center gap-1.5">
                <input
                  type="radio"
                  name="work_classification"
                  value="REWORK"
                  checked={form.work_classification === 'REWORK'}
                  onChange={updateField('work_classification')}
                />
                {t('Retrabalho')}
              </label>
            </div>
          </FormField>
        </div>
      )}
      {form.task_id && form.work_classification === 'REWORK' && (
        <FormField label={t('Motivo do retrabalho')} required>
          <div className="grid grid-cols-1 gap-x-4 gap-y-1.5 rounded-lg border border-[var(--border)] px-3 py-2 sm:grid-cols-2">
            {Object.entries(labels.REWORK_REASON_LABELS).map(([value, label]) => (
              <label key={value} className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)]">
                <input type="radio" name="rework_reason" checked={(form.rework_reasons || [])[0] === value} onChange={() => onToggleReworkReason?.(value)} />
                {label}
              </label>
            ))}
          </div>
          {(form.rework_reasons || []).length === 0 && (
            <span className="mt-1 block text-xs text-[var(--status-critical)]">{t('Obrigatório — selecione o motivo do retrabalho (apenas um).')}</span>
          )}
        </FormField>
      )}
      <div className="grid grid-cols-2 gap-4 items-end">
        <label
          className={`flex items-center gap-2 text-sm ${form.project_id ? 'text-[var(--text-secondary)]' : 'text-[var(--text-muted)]'}`}
          title={!form.project_id ? t('Selecione um projeto para marcar Traslado.') : undefined}
        >
          <input
            type="checkbox"
            checked={Boolean(form.is_transit)}
            disabled={!form.project_id || Boolean(form.absence_type)}
            onChange={updateField('is_transit')}
          />
          {t('Traslado (deslocamento) — sem tarefa específica')}
        </label>
        <FormField
          label={t('Tipo de ausência')}
          hint={
            form.project_id || form.task_id || form.is_transit
              ? t('Desabilitado — já há Projeto/Tarefa/Traslado selecionado.')
              : t('Férias, licença, folga etc. — nunca um custo de cliente.')
          }
        >
          <Select
            value={form.absence_type}
            onChange={updateField('absence_type')}
            disabled={Boolean(form.project_id) || Boolean(form.task_id) || Boolean(form.is_transit)}
          >
            <option value="">{t('Nenhuma (trabalho normal)')}</option>
            {Object.entries(labels.ABSENCE_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </FormField>
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <FormField label={t('Hora início')} required>
          <TextInput type="time" required value={form.start_time} onChange={updateField('start_time')} />
        </FormField>
        <FormField label={t('Hora fim')} required>
          <TextInput type="time" required value={form.end_time} onChange={updateField('end_time')} />
        </FormField>
        <FormField label={t('Intervalo')}>
          <TextInput type="time" step="300" value={form.break_minutes} onChange={updateField('break_minutes')} />
        </FormField>
        <FormField label={t('Total calculado')}>
          <div className="flex h-[38px] items-center rounded-lg border border-[var(--border)] bg-[var(--page)] px-3 text-sm font-medium text-[var(--text-primary)]">
            {preview ?? '—'}
          </div>
        </FormField>
      </div>
      <FormField label={t('Descrição')}>
        <TextArea rows={2} value={form.description} onChange={updateField('description')} />
      </FormField>
    </div>
  )
}
