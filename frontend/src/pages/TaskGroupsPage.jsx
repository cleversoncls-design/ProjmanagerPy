import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import * as taskGroupsApi from '../api/taskGroups'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Table from '../components/Table'
import Button from '../components/Button'
import IconButton from '../components/IconButton'
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import { FormField, TextInput, TextArea } from '../components/FormField'
import { TrashIcon } from '../components/icons'
import { useLanguage } from '../context/LanguageContext'

/** "Grupos de Tarefas" (pedido do usuário): um agrupador reutilizável de
 * tarefas — não um projeto — que pode ser aplicado depois como
 * tarefas-filhas de qualquer tarefa de um projeto real (ver
 * ProjectDetailPage, botão "Aplicar grupo de tarefas"), pra acelerar a
 * criação de projetos parecidos.
 *
 * Tela dividida em duas partes, no mesmo padrão lista/detalhe de Projetos
 * (pedido do usuário: "poderia ser em 2 telas? Parecido ao que temos com
 * os projetos?"): esta página (lista) só cria o grupo e navega para o
 * detalhe; a árvore de tarefas do grupo mora em TaskGroupDetailPage
 * (/task-groups/:groupId), onde "Nova tarefa" abre numa janela flutuante —
 * igual à aba Tarefas de um projeto.
 */

function countItems(nodes) {
  return (nodes || []).reduce((total, node) => total + 1 + countItems(node.children), 0)
}

export default function TaskGroupsPage() {
  const { t } = useLanguage()
  const navigate = useNavigate()
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
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

  function handleCreated(group) {
    setShowCreateModal(false)
    // Grupo recém-criado ainda não tem nenhuma tarefa — vai direto pra tela
    // de detalhe (mesmo padrão de "Novo projeto", que também abre o
    // detalhe em seguida), já que criar um grupo sem nenhuma tarefa não
    // serve pra nada.
    navigate(`/task-groups/${group.id}`)
  }

  function handleDeleted() {
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
        <Card>
          <Table
            columns={[
              {
                key: 'name',
                header: t('Nome'),
                render: (row) => (
                  <Link to={`/task-groups/${row.id}`} className="font-medium text-[var(--series-1)] hover:underline">
                    {row.name}
                  </Link>
                ),
              },
              { key: 'description', header: t('Descrição'), render: (row) => row.description || '—' },
              { key: 'items', header: t('Tarefas'), align: 'right', render: (row) => countItems(row.items) },
              {
                key: 'actions',
                header: '',
                align: 'right',
                render: (row) => (
                  <IconButton icon={TrashIcon} label={t('Excluir grupo de tarefas')} variant="danger" onClick={() => setDeletingGroup(row)} />
                ),
              },
            ]}
            rows={groups}
            getRowKey={(row) => row.id}
            emptyMessage={t('Nenhum grupo de tarefas cadastrado ainda.')}
          />
        </Card>
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
