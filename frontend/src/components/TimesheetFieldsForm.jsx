import { useMemo } from 'react'
import { useLanguage } from '../context/LanguageContext'
import { FormField, TextInput, Select, TextArea } from './FormField'

/** Campos de um apontamento (Data/Projeto/Tarefa/Tipo/Horário/Intervalo/
 * Total calculado/Descrição) — extraído do card "Novo/Editar apontamento"
 * de TimesheetsPage.jsx pra ser reusado também no modal de edição aberto a
 * partir da Ordem de Serviço (ver TimesheetEditModal.jsx). Sem `<form>`
 * nem botões de ação — quem usa este componente é responsável pelo
 * `<form onSubmit>`/Salvar/Cancelar em volta (formatos diferentes: card
 * inline em TimesheetsPage, `<Modal>` em TimesheetEditModal). */
export default function TimesheetFieldsForm({ form, updateField, projects, taskOptions, parentTaskIds, formTypeLabel, preview }) {
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
            <option value="">{t('Sem tarefa (apontamento no projeto)')}</option>
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
        </FormField>
        <FormField label={t('Tipo de apontamento')} hint={t('Segue automaticamente o tipo da tarefa (Gestão/Consultoria).')}>
          <div className="flex h-[38px] items-center rounded-lg border border-[var(--border)] bg-[var(--page)] px-3 text-sm text-[var(--text-secondary)]">
            {formTypeLabel()}
          </div>
        </FormField>
      </div>
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
