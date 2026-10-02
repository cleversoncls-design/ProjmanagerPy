import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
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
import { PencilIcon, PlusIcon, TrashIcon } from '../components/icons'
import { formatNumber } from '../utils/format'
import { useLanguage } from '../context/LanguageContext'

/** Tela de detalhe de um Grupo de Tarefas — mostra a EAP do grupo numa
 * tabela (igual à aba Tarefas de um projeto) e abre "Nova tarefa"/"Editar
 * tarefa" numa janela flutuante (pedido do usuário: "quando adiciono uma
 * nova tarefa, ela abre em uma janela flutuante, igual nos projetos"), em
 * vez do editor com linhas sempre editáveis da versão anterior.
 *
 * Importante: o backend não tem CRUD por item (só `PUT /task-groups/{id}`,
 * que substitui a árvore inteira — ver update_task_group/
 * apply_task_group_to_task em services.py) — então cada ação desta tela
 * (adicionar/editar/remover uma tarefa) monta a árvore local inteira já
 * com a mudança aplicada e manda ela de novo por completo, igual o editor
 * anterior já fazia; só a interface em volta disso mudou. */

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

function addChild(nodes, parentKey, nodeToAdd) {
  if (parentKey === null || parentKey === undefined || parentKey === '') return [...nodes, nodeToAdd]
  return nodes.map((node) => {
    if (node._key === parentKey) return { ...node, children: [...node.children, nodeToAdd] }
    if (node.children.length) return { ...node, children: addChild(node.children, parentKey, nodeToAdd) }
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

/** Código WBS/EAP "de visualização" (mesma ideia já usada antes: numeração
 * calculada só pela posição de cada item na árvore local, igual
 * `recalculate_wbs` no backend — o `wbs_code` de verdade só nasce quando o
 * grupo é aplicado numa tarefa de projeto de verdade). */
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

/** Achata a árvore em ordem de exibição (pré-ordem), carregando a
 * profundidade de cada nó — usada tanto para as linhas da tabela quanto
 * para as opções do seletor "Tarefa pai" no modal (mesmo padrão de
 * `buildOrderedTasks`/`allTasks` na aba Tarefas de um projeto). */
function flattenTree(nodes, depth = 0) {
  const out = []
  for (const node of nodes) {
    out.push({ ...node, depth })
    out.push(...flattenTree(node.children, depth + 1))
  }
  return out
}

const EMPTY_GROUP_ITEM_FORM = {
  name: '',
  task_type: 'CONSULTING',
  duration_days: '1',
  estimated_hours: '0',
  is_milestone: false,
  modality: 'BOTH',
}

export default function TaskGroupDetailPage() {
  const { groupId } = useParams()
  const navigate = useNavigate()
  const { labels, t } = useLanguage()

  const [group, setGroup] = useState(null)
  const [tree, setTree] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [showEditGroupModal, setShowEditGroupModal] = useState(false)
  const [itemModal, setItemModal] = useState(null) // null | { mode: 'create', parentKey } | { mode: 'edit', item }
  const [deletingItem, setDeletingItem] = useState(null)

  function loadGroup() {
    setLoading(true)
    setError('')
    taskGroupsApi
      .getTaskGroup(groupId)
      .then((result) => {
        setGroup(result)
        setTree(result.items.map(itemFromApi))
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadGroup, [groupId])

  const wbsCodes = useMemo(() => computeWbsCodes(tree), [tree])
  const flatNodes = useMemo(() => flattenTree(tree), [tree])

  if (loading) return <Spinner />
  if (error) return <ErrorBanner message={error} />
  if (!group) return null

  const columns = [
    { key: 'wbs', header: 'WBS', render: (row) => <span className="font-mono text-xs text-[var(--text-muted)]">{wbsCodes.get(row._key)}</span> },
    {
      key: 'name',
      header: t('Nome da tarefa'),
      nowrap: true,
      render: (row) => (
        <span style={{ paddingLeft: row.depth * 18 }} className="flex items-center gap-1.5">
          {row.is_milestone && <span className="inline-block h-2 w-2 shrink-0 rotate-45" style={{ backgroundColor: 'var(--text-muted)' }} />}
          {row.name}
        </span>
      ),
    },
    { key: 'task_type', header: t('Tipo'), render: (row) => labels.TASK_TYPE_LABELS[row.task_type] || row.task_type },
    { key: 'duration_days', header: t('Duração'), align: 'right', render: (row) => `${formatNumber(row.duration_days)} d` },
    { key: 'estimated_hours', header: t('Horas'), align: 'right', render: (row) => `${formatNumber(row.estimated_hours)} h` },
    { key: 'modality', header: t('Modalidade'), render: (row) => labels.TASK_MODALITY_LABELS[row.modality] || row.modality },
    {
      key: 'actions',
      header: '',
      align: 'right',
      sticky: true,
      render: (row) => (
        <div className="flex justify-end gap-1.5">
          <IconButton icon={PlusIcon} label={t('Adicionar sub-tarefa')} onClick={() => setItemModal({ mode: 'create', parentKey: row._key })} />
          <IconButton icon={PencilIcon} label={t('Editar tarefa')} onClick={() => setItemModal({ mode: 'edit', item: row })} />
          <IconButton icon={TrashIcon} label={t('Remover tarefa')} variant="danger" onClick={() => setDeletingItem(row)} />
        </div>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title={group.name}
        subtitle={group.description || undefined}
        action={
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => setShowEditGroupModal(true)}>
              {t('Editar grupo')}
            </Button>
            <Button onClick={() => setItemModal({ mode: 'create', parentKey: '' })}>{t('Nova tarefa')}</Button>
          </div>
        }
      />

      <Card dense>
        <Table columns={columns} rows={flatNodes} getRowKey={(row) => row._key} emptyMessage={t('Nenhuma tarefa adicionada ainda.')} dense />
      </Card>

      {itemModal && (
        <TaskGroupItemModal
          groupId={group.id}
          group={group}
          tree={tree}
          mode={itemModal.mode}
          item={itemModal.item}
          defaultParentKey={itemModal.parentKey}
          flatNodes={flatNodes}
          onClose={() => setItemModal(null)}
          onSaved={() => {
            setItemModal(null)
            loadGroup()
          }}
        />
      )}

      {deletingItem && (
        <DeleteTaskGroupItemModal
          groupId={group.id}
          group={group}
          tree={tree}
          item={deletingItem}
          onClose={() => setDeletingItem(null)}
          onDeleted={() => {
            setDeletingItem(null)
            loadGroup()
          }}
        />
      )}

      {showEditGroupModal && (
        <EditTaskGroupInfoModal
          group={group}
          tree={tree}
          onClose={() => setShowEditGroupModal(false)}
          onSaved={() => {
            setShowEditGroupModal(false)
            loadGroup()
          }}
          onDeleted={() => navigate('/task-groups')}
        />
      )}
    </div>
  )
}

/** Modal flutuante de criar/editar uma tarefa do grupo (pedido do usuário:
 * "igual nos projetos") — mesmos campos estruturais do item (nome, tipo,
 * duração, horas, modalidade, marco) + "Tarefa pai" só na criação (mover
 * uma tarefa de pai não é um fluxo pedido aqui, igual na aba Tarefas de um
 * projeto, onde isso é uma ação à parte). step="any" na Duração/Horas pelo
 * mesmo motivo já corrigido na versão anterior: step fixo (ex. "0.5")
 * bloqueava números inteiros na validação nativa do navegador. */
function TaskGroupItemModal({ groupId, group, tree, mode, item, defaultParentKey, flatNodes, onClose, onSaved }) {
  const { labels, t } = useLanguage()
  const isEdit = mode === 'edit'
  const [form, setForm] = useState(() =>
    isEdit
      ? {
          name: item.name,
          task_type: item.task_type,
          duration_days: item.duration_days,
          estimated_hours: item.estimated_hours,
          is_milestone: item.is_milestone,
          modality: item.modality,
          parent_key: '',
        }
      : { ...EMPTY_GROUP_ITEM_FORM, parent_key: defaultParentKey || '' },
  )
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  function updateField(field) {
    return (event) => {
      const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
      setForm((prev) => ({ ...prev, [field]: value }))
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (!form.name.trim()) {
      setError(t('Informe o nome da tarefa.'))
      return
    }
    setError('')
    setSaving(true)
    const patch = {
      name: form.name,
      task_type: form.task_type,
      duration_days: form.duration_days || '1',
      estimated_hours: form.estimated_hours || '0',
      is_milestone: form.is_milestone,
      modality: form.modality,
    }
    const nextTree = isEdit ? updateNode(tree, item._key, patch) : addChild(tree, form.parent_key || null, { ...emptyItem(), ...patch })
    try {
      await taskGroupsApi.updateTaskGroup(groupId, {
        name: group.name,
        description: group.description || null,
        items: nextTree.map(itemToPayload),
      })
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={isEdit ? `${t('Editar tarefa')} — ${item.name}` : t('Nova tarefa')} onClose={onClose} wide>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <FormField label={t('Nome')} required>
            <TextInput required value={form.name} onChange={updateField('name')} />
          </FormField>
          <FormField label={t('Tipo')}>
            <Select value={form.task_type} onChange={updateField('task_type')}>
              {Object.entries(labels.TASK_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </FormField>
        </div>

        {!isEdit && (
          <FormField label={t('Tarefa pai')} hint={t('Deixe em branco para uma tarefa de topo (raiz).')}>
            <Select value={form.parent_key} onChange={updateField('parent_key')}>
              <option value="">{t('Nenhuma (raiz)')}</option>
              {flatNodes.map((node) => (
                <option key={node._key} value={node._key}>
                  {'—'.repeat(node.depth)} {node.name}
                </option>
              ))}
            </Select>
          </FormField>
        )}

        <div className="grid grid-cols-3 gap-4">
          <FormField label={t('Duração (dias)')}>
            <TextInput type="number" step="any" min="0" value={form.duration_days} onChange={updateField('duration_days')} />
          </FormField>
          <FormField label={t('Horas')}>
            <TextInput type="number" step="any" min="0" value={form.estimated_hours} onChange={updateField('estimated_hours')} />
          </FormField>
          <FormField label={t('Modalidade')}>
            <Select value={form.modality} onChange={updateField('modality')}>
              {Object.entries(labels.TASK_MODALITY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </FormField>
        </div>

        <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <input type="checkbox" checked={form.is_milestone} onChange={updateField('is_milestone')} />
          {t('É um marco (milestone)')}
        </label>

        <ErrorBanner message={error} />

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? t('Salvando…') : t('Salvar')}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function DeleteTaskGroupItemModal({ groupId, group, tree, item, onClose, onDeleted }) {
  const { t } = useLanguage()
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')

  async function handleDelete() {
    setDeleting(true)
    setError('')
    try {
      const nextTree = removeNode(tree, item._key)
      await taskGroupsApi.updateTaskGroup(groupId, {
        name: group.name,
        description: group.description || null,
        items: nextTree.map(itemToPayload),
      })
      onDeleted()
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Modal title={t('Remover tarefa')} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          {t('Tem certeza que quer remover a tarefa')} <span className="font-medium text-[var(--text-primary)]">{item.name}</span>
          {item.children.length > 0 ? ` ${t('e todas as suas sub-tarefas')}?` : '?'}
        </p>
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="button" variant="danger" disabled={deleting} onClick={handleDelete}>
            {deleting ? t('Removendo…') : t('Remover')}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

/** Editar nome/descrição do grupo + excluir o grupo inteiro (volta pra
 * lista) — mesmo papel do botão "Editar projeto" no cabeçalho do detalhe
 * de um projeto. Manda a árvore de itens (`tree`) de volta sem alteração
 * nenhuma junto com o PUT, já que o endpoint substitui tudo de uma vez. */
function EditTaskGroupInfoModal({ group, tree, onClose, onSaved, onDeleted }) {
  const { t } = useLanguage()
  const [name, setName] = useState(group.name)
  const [description, setDescription] = useState(group.description || '')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSaving(true)
    try {
      await taskGroupsApi.updateTaskGroup(group.id, {
        name,
        description: description || null,
        items: tree.map(itemToPayload),
      })
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    setDeleteError('')
    try {
      await taskGroupsApi.deleteTaskGroup(group.id)
      onDeleted()
    } catch (err) {
      setDeleteError(err.message)
      setDeleting(false)
    }
  }

  if (confirmingDelete) {
    return (
      <Modal title={t('Excluir grupo de tarefas')} onClose={() => setConfirmingDelete(false)}>
        <div className="space-y-4">
          <p className="text-sm text-[var(--text-secondary)]">
            {t('Tem certeza que quer excluir o grupo')} <span className="font-medium text-[var(--text-primary)]">{group.name}</span>?
          </p>
          <ErrorBanner message={deleteError} />
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="secondary" onClick={() => setConfirmingDelete(false)}>
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

  return (
    <Modal title={t('Editar grupo de tarefas')} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField label={t('Nome')} required>
          <TextInput required value={name} onChange={(event) => setName(event.target.value)} />
        </FormField>
        <FormField label={t('Descrição')}>
          <TextArea rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
        </FormField>
        <ErrorBanner message={error} />
        <div className="flex items-center justify-between gap-2 pt-1">
          <button type="button" onClick={() => setConfirmingDelete(true)} className="text-xs font-medium text-[var(--status-critical)] hover:underline">
            {t('Excluir grupo de tarefas')}
          </button>
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              {t('Cancelar')}
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? t('Salvando…') : t('Salvar')}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  )
}
