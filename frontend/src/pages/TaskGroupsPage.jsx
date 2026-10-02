import { useEffect, useMemo, useState } from 'react'
import * as taskGroupsApi from '../api/taskGroups'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Table from '../components/Table'
import Button from '../components/Button'
import IconButton from '../components/IconButton'
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import { FormField, TextInput, Select, TextArea } from '../components/FormField'
import { PlusIcon, TrashIcon } from '../components/icons'
import { useLanguage } from '../context/LanguageContext'

/** "Grupos de Tarefas" (pedido do usuário): um agrupador reutilizável de
 * tarefas — não um projeto — que pode ser aplicado depois como
 * tarefas-filhas de qualquer tarefa de um projeto real (ver
 * ProjectDetailPage, botão "Aplicar grupo de tarefas"), pra acelerar a
 * criação de projetos parecidos. Página própria do menu lateral, mesmo
 * padrão mestre/detalhe de CalendarsPage (lista à esquerda, editor da
 * seleção à direita) — decisões confirmadas com o usuário: cadastro novo
 * e dedicado, hierarquia aninhada, página própria.
 *
 * O editor de árvore (TaskGroupEditor/TaskGroupItemRow abaixo) mostra a
 * estrutura como uma EAP (código WBS "de visualização" + indentação por
 * nível, pedido do usuário) e cobre os campos mais usados (nome, tipo,
 * duração, horas, modalidade, marco); "Observações" e "Nível mínimo" do
 * item ficam com o default (vazio / 1) neste v1 — dá pra editá-los depois,
 * numa tarefa já aplicada num projeto, pelo modal de edição de tarefa
 * normal. */

let _nextLocalKey = 0
function nextLocalKey() {
  _nextLocalKey += 1
  return `new-${_nextLocalKey}`
}

function emptyItem() {
  return {
    _key: nextLocalKey(),
    name: '',
    task_type: 'CONSULTING',
    duration_days: '1',
    estimated_hours: '0',
    is_milestone: false,
    notes: null,
    min_level: 1,
    modality: 'BOTH',
    children: [],
  }
}

function itemFromApi(apiItem) {
  return {
    _key: apiItem.id,
    name: apiItem.name,
    task_type: apiItem.task_type,
    duration_days: String(apiItem.duration_days),
    estimated_hours: String(apiItem.estimated_hours),
    is_milestone: apiItem.is_milestone,
    notes: apiItem.notes || null,
    min_level: apiItem.min_level,
    modality: apiItem.modality,
    children: (apiItem.children || []).map(itemFromApi),
  }
}

function updateNode(nodes, key, patch) {
  return nodes.map((node) => {
    if (node._key === key) return { ...node, ...patch }
    if (node.children.length) return { ...node, children: updateNode(node.children, key, patch) }
    return node
  })
}

function removeNode(nodes, key) {
  return nodes.filter((node) => node._key !== key).map((node) => ({ ...node, children: removeNode(node.children, key) }))
}

function addChild(nodes, parentKey) {
  if (parentKey === null) return [...nodes, emptyItem()]
  return nodes.map((node) => {
    if (node._key === parentKey) return { ...node, children: [...node.children, emptyItem()] }
    if (node.children.length) return { ...node, children: addChild(node.children, parentKey) }
    return node
  })
}

function itemToPayload(node) {
  return {
    name: node.name,
    task_type: node.task_type,
    duration_days: node.duration_days || '1',
    estimated_hours: node.estimated_hours || '0',
    is_milestone: node.is_milestone,
    notes: node.notes || null,
    min_level: Number(node.min_level) || 1,
    modality: node.modality,
    children: node.children.map(itemToPayload),
  }
}

function everyNodeNamed(nodes) {
  return nodes.every((node) => node.name.trim().length > 0 && everyNodeNamed(node.children))
}

function countItems(nodes) {
  return nodes.reduce((total, node) => total + 1 + countItems(node.children), 0)
}

/** Código WBS/EAP "de visualização" (pedido do usuário: ver a estrutura
 * pai/filho igual à EAP de um projeto) — calculado só pela posição de cada
 * item na árvore local (1, 1.1, 1.2, 2…), mesmo critério de
 * `recalculate_wbs` no backend (services.py). É só pra exibição dentro do
 * editor: o `wbs_code` de verdade só nasce quando o grupo é aplicado numa
 * tarefa de projeto (ver apply_task_group_to_task), porque até lá o grupo
 * nem tem projeto nenhum por trás pra numerar contra. */
function computeWbsCodes(nodes, prefix = []) {
  const codes = new Map()
  nodes.forEach((node, index) => {
    const parts = [...prefix, index + 1]
    codes.set(node._key, parts.join('.'))
    for (const [key, code] of computeWbsCodes(node.children, parts)) {
      codes.set(key, code)
    }
  })
  return codes
}

export default function TaskGroupsPage() {
  const { t } = useLanguage()
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedGroupId, setSelectedGroupId] = useState(null)
  const [deletingGroup, setDeletingGroup] = useState(null)

  function loadGroups() {
    setLoading(true)
    taskGroupsApi
      .listTaskGroups()
      .then(setGroups)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadGroups, [])

  const selectedGroup = useMemo(() => groups.find((g) => g.id === selectedGroupId) || null, [groups, selectedGroupId])

  function handleCreated(group) {
    setShowCreateModal(false)
    setGroups((prev) => [...prev, group])
    setSelectedGroupId(group.id)
  }

  function handleDeleted() {
    if (deletingGroup && deletingGroup.id === selectedGroupId) setSelectedGroupId(null)
    setDeletingGroup(null)
    loadGroups()
  }

  return (
    <div>
      <PageHeader
        title={t('Grupos de Tarefas')}
        subtitle={t(
          'Agrupadores reutilizáveis de tarefas — aplique dentro de uma tarefa de projeto (aba Tarefas) para acelerar a criação de estruturas parecidas.',
        )}
        action={<Button onClick={() => setShowCreateModal(true)}>{t('Novo grupo')}</Button>}
      />

      {loading && <Spinner />}
      <ErrorBanner message={error} />

      {!loading && !error && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card title={t('Grupos cadastrados')}>
            <Table
              columns={[
                { key: 'name', header: t('Nome') },
                { key: 'count', header: t('Tarefas'), render: (row) => countItems(row.items) },
                {
                  key: 'actions',
                  header: '',
                  align: 'right',
                  render: (row) => (
                    <div className="flex justify-end gap-3">
                      <button
                        type="button"
                        onClick={() => setSelectedGroupId(row.id)}
                        className="text-xs font-medium text-[var(--series-1)] hover:underline"
                      >
                        {t('Editar')}
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeletingGroup(row)}
                        className="text-xs font-medium text-[var(--status-critical)] hover:underline"
                      >
                        {t('Excluir')}
                      </button>
                    </div>
                  ),
                },
              ]}
              rows={groups}
              getRowKey={(row) => row.id}
              emptyMessage={t('Nenhum grupo de tarefas cadastrado ainda.')}
            />
          </Card>

          <Card title={selectedGroup ? `${t('Tarefas do grupo')} — ${selectedGroup.name}` : t('Tarefas do grupo')}>
            {selectedGroup ? (
              <TaskGroupEditor key={selectedGroup.id} group={selectedGroup} onSaved={loadGroups} />
            ) : (
              <p className="text-sm text-[var(--text-muted)]">{t('Selecione um grupo na lista ao lado para editar suas tarefas.')}</p>
            )}
          </Card>
        </div>
      )}

      {showCreateModal && <CreateTaskGroupModal onClose={() => setShowCreateModal(false)} onCreated={handleCreated} />}

      {deletingGroup && <DeleteTaskGroupModal group={deletingGroup} onClose={() => setDeletingGroup(null)} onDeleted={handleDeleted} />}
    </div>
  )
}

function CreateTaskGroupModal({ onClose, onCreated }) {
  const { t } = useLanguage()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSaving(true)
    try {
      const created = await taskGroupsApi.createTaskGroup({ name, description: description || null, items: [] })
      onCreated(created)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={t('Novo grupo de tarefas')} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField label={t('Nome')} required>
          <TextInput required value={name} onChange={(event) => setName(event.target.value)} />
        </FormField>
        <FormField label={t('Descrição')}>
          <TextArea rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
        </FormField>
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="submit" disabled={saving || !name.trim()}>
            {saving ? t('Salvando…') : t('Salvar')}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function DeleteTaskGroupModal({ group, onClose, onDeleted }) {
  const { t } = useLanguage()
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')

  async function handleDelete() {
    setDeleting(true)
    setError('')
    try {
      await taskGroupsApi.deleteTaskGroup(group.id)
      onDeleted()
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Modal title={t('Excluir grupo de tarefas')} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          {t('Tem certeza que quer excluir o grupo')} <span className="font-medium text-[var(--text-primary)]">{group.name}</span>?
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

/** Editor da árvore de um grupo — estado local controla toda a árvore
 * (cada nó com uma `_key` estável, igual id real pra item já salvo ou uma
 * chave local pra item novo ainda não salvo) até o usuário clicar em
 * "Salvar grupo", que manda a árvore inteira num PUT só (substitui tudo,
 * ver update_task_group no backend — não existe PATCH incremental de
 * item). */
function TaskGroupEditor({ group, onSaved }) {
  const { t } = useLanguage()
  const [name, setName] = useState(group.name)
  const [description, setDescription] = useState(group.description || '')
  const [items, setItems] = useState(() => group.items.map(itemFromApi))
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const wbsCodes = useMemo(() => computeWbsCodes(items), [items])

  function handleUpdate(key, patch) {
    setItems((prev) => updateNode(prev, key, patch))
  }

  function handleRemove(key) {
    setItems((prev) => removeNode(prev, key))
  }

  function handleAddChild(parentKey) {
    setItems((prev) => addChild(prev, parentKey))
  }

  async function handleSave(event) {
    event.preventDefault()
    setError('')
    if (!name.trim()) {
      setError(t('Informe o nome do grupo.'))
      return
    }
    if (!everyNodeNamed(items)) {
      setError(t('Toda tarefa do grupo precisa de um nome.'))
      return
    }
    setSaving(true)
    try {
      await taskGroupsApi.updateTaskGroup(group.id, {
        name,
        description: description || null,
        items: items.map(itemToPayload),
      })
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSave} className="space-y-4">
      <FormField label={t('Nome')} required>
        <TextInput required value={name} onChange={(event) => setName(event.target.value)} />
      </FormField>
      <FormField label={t('Descrição')}>
        <TextArea rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
      </FormField>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-[var(--text-secondary)]">{t('Tarefas do grupo')}</span>
          <IconButton icon={PlusIcon} label={t('Adicionar tarefa')} onClick={() => handleAddChild(null)} />
        </div>
        {items.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)]">{t('Nenhuma tarefa adicionada ainda.')}</p>
        ) : (
          <div className="space-y-1.5 rounded-lg border border-[var(--border)] p-2">
            <div className="flex flex-wrap items-center gap-1.5 px-2 text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
              <span className="w-12 shrink-0">{t('WBS')}</span>
              <span className="min-w-[160px] flex-1">{t('Nome da tarefa')}</span>
              <span className="w-[6.5rem]">{t('Tipo')}</span>
              <span className="w-20">{t('Duração (dias)')}</span>
              <span className="w-20">{t('Horas')}</span>
              <span className="w-[6.5rem]">{t('Modalidade')}</span>
              <span className="w-14">{t('Marco')}</span>
            </div>
            {items.map((item) => (
              <TaskGroupItemRow
                key={item._key}
                item={item}
                depth={0}
                wbsCodes={wbsCodes}
                onAddChild={handleAddChild}
                onUpdate={handleUpdate}
                onRemove={handleRemove}
              />
            ))}
          </div>
        )}
      </div>

      <ErrorBanner message={error} />

      <div className="flex justify-end pt-1">
        <Button type="submit" disabled={saving}>
          {saving ? t('Salvando…') : t('Salvar grupo')}
        </Button>
      </div>
    </form>
  )
}

/** Uma linha da EAP do grupo — indentada por `depth` (igual à grade de
 * Tarefas de um projeto) e com o código WBS "de visualização" calculado em
 * `computeWbsCodes` à esquerda do nome. Linhas com sub-tarefas (tarefas-pai
 * na EAP) ganham um destaque sutil (borda/fundo na cor da marca) pra
 * diferenciar visualmente de uma tarefa-folha — mesma ideia da bolinha/
 * indicador de tarefa-pai na grade de Tarefas do projeto. */
function TaskGroupItemRow({ item, depth, wbsCodes, onAddChild, onUpdate, onRemove }) {
  const { labels, t } = useLanguage()
  const hasChildren = item.children.length > 0
  return (
    <div>
      <div
        className={`flex flex-wrap items-center gap-1.5 rounded-lg border px-2 py-1.5 ${
          hasChildren ? 'border-[var(--series-1)]/40 bg-[var(--series-1)]/5' : 'border-[var(--border)] bg-[var(--page)]'
        }`}
        style={{ marginLeft: depth * 20 }}
      >
        <span className="w-12 shrink-0 font-mono text-xs font-semibold text-[var(--text-muted)]">{wbsCodes.get(item._key)}</span>
        <TextInput
          value={item.name}
          onChange={(event) => onUpdate(item._key, { name: event.target.value })}
          placeholder={t('Nome da tarefa')}
          className="min-w-[160px] flex-1"
        />
        <Select value={item.task_type} onChange={(event) => onUpdate(item._key, { task_type: event.target.value })} className="w-[6.5rem]">
          {Object.entries(labels.TASK_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
        <TextInput
          type="number"
          step="0.5"
          min="0.01"
          value={item.duration_days}
          onChange={(event) => onUpdate(item._key, { duration_days: event.target.value })}
          title={t('Duração (dias)')}
          className="w-20"
        />
        <TextInput
          type="number"
          step="0.5"
          min="0"
          value={item.estimated_hours}
          onChange={(event) => onUpdate(item._key, { estimated_hours: event.target.value })}
          title={t('Trabalho (horas)')}
          placeholder={t('Horas')}
          className="w-20"
        />
        <Select value={item.modality} onChange={(event) => onUpdate(item._key, { modality: event.target.value })} className="w-[6.5rem]">
          {Object.entries(labels.TASK_MODALITY_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
        <label className="flex w-14 items-center gap-1 whitespace-nowrap text-xs text-[var(--text-secondary)]">
          <input type="checkbox" checked={item.is_milestone} onChange={(event) => onUpdate(item._key, { is_milestone: event.target.checked })} />
          {t('Marco')}
        </label>
        <IconButton icon={PlusIcon} label={t('Adicionar sub-tarefa')} size={14} onClick={() => onAddChild(item._key)} />
        <IconButton icon={TrashIcon} label={t('Remover tarefa')} variant="danger" size={14} onClick={() => onRemove(item._key)} />
      </div>
      {hasChildren && (
        <div className="mt-1.5 space-y-1.5">
          {item.children.map((child) => (
            <TaskGroupItemRow
              key={child._key}
              item={child}
              depth={depth + 1}
              wbsCodes={wbsCodes}
              onAddChild={onAddChild}
              onUpdate={onUpdate}
              onRemove={onRemove}
            />
          ))}
        </div>
      )}
    </div>
  )
}
