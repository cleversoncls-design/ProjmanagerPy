import { useEffect, useMemo, useState } from 'react'
import * as knowledgeApi from '../api/knowledge'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Table from '../components/Table'
import Button from '../components/Button'
import IconButton from '../components/IconButton'
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import StatusPill from '../components/StatusPill'
import { FormField, TextInput, TextArea, Select } from '../components/FormField'
import { PencilIcon, PlusIcon, TrashIcon } from '../components/icons'
import { useLanguage } from '../context/LanguageContext'
import { KNOWLEDGE_REQUIREMENT_TONE } from '../utils/labels'

/** "Cadastro das Funcionalidades" (pedido do usuário, "NOVAS MELHORIAS":
 * processo de registro de conhecimento dos consultores) — catálogo em 3
 * níveis (Sistema > Módulo > Funcionalidade), tela única (sem lista+detalhe
 * separados como Grupos de Tarefas: o catálogo tende a ser mais estável e
 * menor, não precisa da navegação em duas telas). Restrita a
 * KNOWLEDGE_CATALOG_ROLES (ver App.jsx/Sidebar.jsx) — a autoavaliação
 * (KnowledgeSelfAssessmentPage) e a revisão (KnowledgeReviewPage) são
 * telas à parte, com seus próprios acessos.
 *
 * `applies_to_consultant`/`applies_to_internal_pm` no Módulo (decisão
 * confirmada com o usuário) controlam quem vê aquele módulo na
 * autoavaliação — mostrados aqui como dois selos, nunca escondidos: quem
 * cadastra precisa ver pra quem o módulo está liberado.
 *
 * Visão em WBS/EAP (pedido do usuário, olhando a tela pronta: "existe a
 * possibilidade de colocar em formato de WBS/EAP?") — substitui os cards
 * aninhados por uma única tabela achatada (Sistema > Módulo >
 * Funcionalidade), numerada e indentada, mesmo padrão já usado em Grupos
 * de Tarefas (`TaskGroupDetailPage.jsx`: `computeWbsCodes`/`flattenTree`).
 * A numeração aqui é só "de visualização" (recalculada pela posição atual
 * de cada item), sem nenhum campo novo no backend. */
function flattenCatalog(systems) {
  const rows = []
  systems.forEach((system, systemIndex) => {
    const systemCode = String(systemIndex + 1)
    rows.push({ _key: `system-${system.id}`, type: 'system', depth: 0, wbs: systemCode, data: system })
    if (system.modules.length === 0) {
      rows.push({ _key: `empty-modules-${system.id}`, type: 'empty', depth: 1, message: 'Nenhum módulo cadastrado neste sistema.' })
    }
    system.modules.forEach((module, moduleIndex) => {
      const moduleCode = `${systemCode}.${moduleIndex + 1}`
      rows.push({ _key: `module-${module.id}`, type: 'module', depth: 1, wbs: moduleCode, data: module, systemId: system.id })
      if (module.functionalities.length === 0) {
        rows.push({
          _key: `empty-functionalities-${module.id}`,
          type: 'empty',
          depth: 2,
          message: 'Nenhuma funcionalidade cadastrada neste módulo.',
        })
      }
      module.functionalities.forEach((functionality, functionalityIndex) => {
        rows.push({
          _key: `functionality-${functionality.id}`,
          type: 'functionality',
          depth: 2,
          wbs: `${moduleCode}.${functionalityIndex + 1}`,
          data: functionality,
          moduleId: module.id,
        })
      })
    })
  })
  return rows
}

export default function KnowledgeCatalogPage() {
  const { t, labels } = useLanguage()
  const [systems, setSystems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [systemModal, setSystemModal] = useState(null) // { mode, system } | null
  const [moduleModal, setModuleModal] = useState(null) // { mode, systemId, module } | null
  const [functionalityModal, setFunctionalityModal] = useState(null) // { mode, moduleId, functionality } | null
  const [deleteTarget, setDeleteTarget] = useState(null) // { kind, id, name } | null

  function load() {
    setLoading(true)
    knowledgeApi
      .getCatalog()
      .then(setSystems)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  function handleSaved() {
    setSystemModal(null)
    setModuleModal(null)
    setFunctionalityModal(null)
    load()
  }

  async function handleConfirmDelete() {
    const { kind, id } = deleteTarget
    if (kind === 'system') await knowledgeApi.deleteSystem(id)
    else if (kind === 'module') await knowledgeApi.deleteModule(id)
    else await knowledgeApi.deleteFunctionality(id)
    setDeleteTarget(null)
    load()
  }

  const rows = useMemo(() => flattenCatalog(systems), [systems])

  const columns = [
    { key: 'wbs', header: 'WBS', render: (row) => <span className="font-mono text-xs text-[var(--text-muted)]">{row.wbs || ''}</span> },
    {
      key: 'name',
      header: t('Nome'),
      nowrap: true,
      render: (row) => {
        if (row.type === 'empty') {
          return <span style={{ paddingLeft: row.depth * 18 }} className="text-xs italic text-[var(--text-muted)]">{t(row.message)}</span>
        }
        const isSystem = row.type === 'system'
        // Perfil (Consultor/Gerente de Projetos) agora também existe no
        // Sistema, além do Módulo (pedido do usuário, 2ª rodada) — mas só
        // como classificação: não filtra nada na autoavaliação (ver
        // docstring de KnowledgeSystem em app/models.py).
        return (
          <span style={{ paddingLeft: row.depth * 18 }} className="flex items-center gap-2">
            <span className={isSystem ? 'font-semibold text-[var(--text-primary)]' : row.type === 'module' ? 'font-medium text-[var(--text-primary)]' : 'text-[var(--text-primary)]'}>
              {row.data.name}
            </span>
            {(row.type === 'system' || row.type === 'module') && (
              <>
                {row.data.applies_to_consultant && <StatusPill label={t('Consultor')} tone="good" />}
                {row.data.applies_to_internal_pm && <StatusPill label={t('Gerente de Projetos')} tone="good" />}
              </>
            )}
          </span>
        )
      },
    },
    {
      key: 'requirement',
      header: t('Conhecimento'),
      // Necessário/Desejável agora também existe no Sistema e no Módulo
      // (pedido do usuário, 2ª rodada) — só classificação neste nível; o
      // badge "oficial" mostrado na autoavaliação/revisão continua vindo
      // só da Funcionalidade (sem mudança nenhuma aí).
      render: (row) =>
        row.type !== 'empty' ? (
          <StatusPill label={labels.KNOWLEDGE_REQUIREMENT_LABELS[row.data.requirement]} tone={KNOWLEDGE_REQUIREMENT_TONE[row.data.requirement]} />
        ) : (
          ''
        ),
    },
    {
      key: 'description',
      header: t('Detalhes'),
      render: (row) => (row.type === 'empty' ? '' : row.data.description || '—'),
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      sticky: true,
      render: (row) => {
        if (row.type === 'system') {
          return (
            <div className="flex justify-end gap-1">
              <IconButton icon={PlusIcon} label={t('Novo módulo')} onClick={() => setModuleModal({ mode: 'create', systemId: row.data.id })} />
              <IconButton icon={PencilIcon} label={t('Editar sistema')} onClick={() => setSystemModal({ mode: 'edit', system: row.data })} />
              <IconButton
                icon={TrashIcon}
                label={t('Excluir sistema')}
                variant="danger"
                onClick={() => setDeleteTarget({ kind: 'system', id: row.data.id, name: row.data.name })}
              />
            </div>
          )
        }
        if (row.type === 'module') {
          return (
            <div className="flex justify-end gap-1">
              <IconButton
                icon={PlusIcon}
                label={t('Nova funcionalidade')}
                onClick={() => setFunctionalityModal({ mode: 'create', moduleId: row.data.id })}
              />
              <IconButton
                icon={PencilIcon}
                label={t('Editar módulo')}
                onClick={() => setModuleModal({ mode: 'edit', systemId: row.systemId, module: row.data })}
              />
              <IconButton
                icon={TrashIcon}
                label={t('Excluir módulo')}
                variant="danger"
                onClick={() => setDeleteTarget({ kind: 'module', id: row.data.id, name: row.data.name })}
              />
            </div>
          )
        }
        if (row.type === 'functionality') {
          return (
            <div className="flex justify-end gap-1">
              <IconButton
                icon={PencilIcon}
                label={t('Editar funcionalidade')}
                onClick={() => setFunctionalityModal({ mode: 'edit', moduleId: row.moduleId, functionality: row.data })}
              />
              <IconButton
                icon={TrashIcon}
                label={t('Excluir funcionalidade')}
                variant="danger"
                onClick={() => setDeleteTarget({ kind: 'functionality', id: row.data.id, name: row.data.name })}
              />
            </div>
          )
        }
        return null
      },
    },
  ]

  return (
    <div>
      <PageHeader
        title={t('Cadastro de Funcionalidades')}
        subtitle={t('Catálogo de Sistema / Módulo / Funcionalidade usado no registro de conhecimento dos consultores.')}
        action={<Button onClick={() => setSystemModal({ mode: 'create' })}>{t('Novo sistema')}</Button>}
      />

      {loading && <Spinner />}
      <ErrorBanner message={error} />

      {!loading && !error && (
        <Card dense>
          <Table columns={columns} rows={rows} getRowKey={(row) => row._key} emptyMessage={t('Nenhum sistema cadastrado ainda.')} dense />
        </Card>
      )}

      {systemModal && <SystemFormModal modal={systemModal} onClose={() => setSystemModal(null)} onSaved={handleSaved} />}
      {moduleModal && <ModuleFormModal modal={moduleModal} onClose={() => setModuleModal(null)} onSaved={handleSaved} />}
      {functionalityModal && (
        <FunctionalityFormModal modal={functionalityModal} onClose={() => setFunctionalityModal(null)} onSaved={handleSaved} />
      )}
      {deleteTarget && (
        <ConfirmDeleteModal target={deleteTarget} onClose={() => setDeleteTarget(null)} onConfirm={handleConfirmDelete} />
      )}
    </div>
  )
}

function SystemFormModal({ modal, onClose, onSaved }) {
  const { t } = useLanguage()
  const editing = modal.mode === 'edit'
  const [name, setName] = useState(editing ? modal.system.name : '')
  const [description, setDescription] = useState(editing ? modal.system.description || '' : '')
  const [appliesConsultant, setAppliesConsultant] = useState(editing ? modal.system.applies_to_consultant : true)
  const [appliesPm, setAppliesPm] = useState(editing ? modal.system.applies_to_internal_pm : true)
  const [requirement, setRequirement] = useState(editing ? modal.system.requirement : 'REQUIRED')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    if (!appliesConsultant && !appliesPm) {
      setError(t('Selecione ao menos um perfil (Consultor e/ou Gerente de Projeto)'))
      return
    }
    setSaving(true)
    try {
      const payload = {
        name,
        description: description || null,
        applies_to_consultant: appliesConsultant,
        applies_to_internal_pm: appliesPm,
        requirement,
      }
      if (editing) await knowledgeApi.updateSystem(modal.system.id, payload)
      else await knowledgeApi.createSystem(payload)
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={editing ? t('Editar sistema') : t('Novo sistema')} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField label={t('Nome')} required>
          <TextInput required value={name} onChange={(event) => setName(event.target.value)} />
        </FormField>
        <FormField label={t('Descrição')}>
          <TextArea rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
        </FormField>
        {/* Perfil + Necessário/Desejável (pedido do usuário, 2ª rodada) —
            só classificação/organização neste nível (ver docstring de
            KnowledgeSystem em app/models.py): não filtra a autoavaliação
            nem muda o badge mostrado na revisão, que continuam vindo do
            Módulo e da Funcionalidade, respectivamente. */}
        <FormField label={t('Perfil')} hint={t('Pelo menos um dos dois precisa ficar marcado.')}>
          <div className="flex flex-col gap-1.5 pt-1">
            <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]">
              <input type="checkbox" checked={appliesConsultant} onChange={(event) => setAppliesConsultant(event.target.checked)} />
              {t('Consultor')}
            </label>
            <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]">
              <input type="checkbox" checked={appliesPm} onChange={(event) => setAppliesPm(event.target.checked)} />
              {t('Gerente de Projetos')}
            </label>
          </div>
        </FormField>
        <FormField label={t('Conhecimento')} required>
          <Select value={requirement} onChange={(event) => setRequirement(event.target.value)}>
            <option value="REQUIRED">{t('Necessário')}</option>
            <option value="DESIRABLE">{t('Desejável')}</option>
          </Select>
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

function ModuleFormModal({ modal, onClose, onSaved }) {
  const { t } = useLanguage()
  const editing = modal.mode === 'edit'
  const [name, setName] = useState(editing ? modal.module.name : '')
  const [description, setDescription] = useState(editing ? modal.module.description || '' : '')
  const [appliesConsultant, setAppliesConsultant] = useState(editing ? modal.module.applies_to_consultant : true)
  const [appliesPm, setAppliesPm] = useState(editing ? modal.module.applies_to_internal_pm : true)
  const [requirement, setRequirement] = useState(editing ? modal.module.requirement : 'REQUIRED')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    if (!appliesConsultant && !appliesPm) {
      setError(t('Selecione ao menos um perfil (Consultor e/ou Gerente de Projeto)'))
      return
    }
    setSaving(true)
    try {
      const payload = {
        name,
        description: description || null,
        applies_to_consultant: appliesConsultant,
        applies_to_internal_pm: appliesPm,
        requirement,
      }
      if (editing) await knowledgeApi.updateModule(modal.module.id, payload)
      else await knowledgeApi.createModule(modal.systemId, payload)
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={editing ? t('Editar módulo') : t('Novo módulo')} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField label={t('Nome')} required>
          <TextInput required value={name} onChange={(event) => setName(event.target.value)} />
        </FormField>
        <FormField label={t('Descrição')}>
          <TextArea rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
        </FormField>
        <FormField label={t('Visível na autoavaliação para')} hint={t('Pelo menos um dos dois precisa ficar marcado.')}>
          <div className="flex flex-col gap-1.5 pt-1">
            <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]">
              <input type="checkbox" checked={appliesConsultant} onChange={(event) => setAppliesConsultant(event.target.checked)} />
              {t('Consultor')}
            </label>
            <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]">
              <input type="checkbox" checked={appliesPm} onChange={(event) => setAppliesPm(event.target.checked)} />
              {t('Gerente de Projetos')}
            </label>
          </div>
        </FormField>
        {/* Necessário/Desejável no Módulo (pedido do usuário, 2ª rodada) —
            só classificação neste nível, igual no Sistema acima; o badge
            mostrado na autoavaliação/revisão continua vindo só da
            Funcionalidade. */}
        <FormField label={t('Conhecimento')} required>
          <Select value={requirement} onChange={(event) => setRequirement(event.target.value)}>
            <option value="REQUIRED">{t('Necessário')}</option>
            <option value="DESIRABLE">{t('Desejável')}</option>
          </Select>
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

function FunctionalityFormModal({ modal, onClose, onSaved }) {
  const { t } = useLanguage()
  const editing = modal.mode === 'edit'
  const [name, setName] = useState(editing ? modal.functionality.name : '')
  const [description, setDescription] = useState(editing ? modal.functionality.description || '' : '')
  const [requirement, setRequirement] = useState(editing ? modal.functionality.requirement : 'REQUIRED')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSaving(true)
    try {
      const payload = { name, description: description || null, requirement }
      if (editing) await knowledgeApi.updateFunctionality(modal.functionality.id, payload)
      else await knowledgeApi.createFunctionality(modal.moduleId, payload)
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={editing ? t('Editar funcionalidade') : t('Nova funcionalidade')} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField label={t('Nome')} required>
          <TextInput required value={name} onChange={(event) => setName(event.target.value)} />
        </FormField>
        <FormField label={t('Conhecimento')} required>
          <Select value={requirement} onChange={(event) => setRequirement(event.target.value)}>
            <option value="REQUIRED">{t('Necessário')}</option>
            <option value="DESIRABLE">{t('Desejável')}</option>
          </Select>
        </FormField>
        <FormField
          label={t('Detalhes')}
          hint={t('Quais detalhes desta funcionalidade são necessários ou fazem parte deste processo.')}
        >
          <TextArea rows={3} value={description} onChange={(event) => setDescription(event.target.value)} />
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

const DELETE_TITLES = {
  system: 'Excluir sistema',
  module: 'Excluir módulo',
  functionality: 'Excluir funcionalidade',
}

const DELETE_WARNINGS = {
  system: 'Isso também apaga todos os módulos, funcionalidades e autoavaliações registradas dentro dele.',
  module: 'Isso também apaga todas as funcionalidades e autoavaliações registradas dentro dele.',
  functionality: 'Isso também apaga as autoavaliações registradas nesta funcionalidade.',
}

function ConfirmDeleteModal({ target, onClose, onConfirm }) {
  const { t } = useLanguage()
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')

  async function handleDelete() {
    setDeleting(true)
    setError('')
    try {
      await onConfirm()
    } catch (err) {
      setError(err.message)
      setDeleting(false)
    }
  }

  return (
    <Modal title={t(DELETE_TITLES[target.kind])} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          {t('Tem certeza que quer excluir')} <span className="font-medium text-[var(--text-primary)]">{target.name}</span>?
        </p>
        <p className="text-xs text-[var(--text-muted)]">{t(DELETE_WARNINGS[target.kind])}</p>
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
