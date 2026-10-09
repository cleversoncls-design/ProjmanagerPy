import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import {
  ADMIN_LIKE_ROLES,
  DASHBOARD_ROLES,
  INTERNAL_ROLES,
  KNOWLEDGE_CATALOG_ROLES,
  KNOWLEDGE_REVIEW_ROLES,
  KNOWLEDGE_SELF_ASSESSMENT_ROLES,
  MANAGEMENT_ROLES,
  PROJECTS_VISIBLE_ROLES,
  STATUS_REPORT_VISIBLE_ROLES,
} from '../utils/labels'
import logo from '../assets/resultar-logo.png'
import {
  BadgeCheckIcon,
  BarChartIcon,
  BookIcon,
  BriefcaseIcon,
  BuildingIcon,
  CalendarIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ClipboardCheckIcon,
  ClockIcon,
  FileTextIcon,
  FlagIcon,
  HomeIcon,
  LayersIcon,
  MailIcon,
  UsersIcon,
} from './icons'

// Reorganização de menus (pedido do usuário): o menu deixou de ser uma
// lista única e virou "Painel" + "Relatórios" soltos, com três seções
// agrupadas no meio (Projetos / Apontamentos / Configurações) — cada
// seção lista suas próprias rotas, cada rota com seus próprios `roles`
// (os mesmos grupos de sempre, ver utils/labels.js). Uma seção some
// inteira quando nenhum item dela é visível pro perfil logado (ex.:
// Consultor nunca vê a seção "Projetos").
const NAV_SECTIONS = [
  { type: 'item', to: '/', label: 'Dashboard', end: true, icon: HomeIcon, roles: DASHBOARD_ROLES },
  {
    type: 'group',
    key: 'projetos',
    label: 'Projetos',
    items: [
      { to: '/calendars', label: 'Calendários', icon: CalendarIcon, roles: MANAGEMENT_ROLES },
      { to: '/clients', label: 'Clientes', icon: BuildingIcon, roles: ADMIN_LIKE_ROLES },
      { to: '/projects', label: 'Projetos', icon: BriefcaseIcon, roles: PROJECTS_VISIBLE_ROLES },
      { to: '/task-groups', label: 'Grupos de Tarefas', icon: LayersIcon, roles: MANAGEMENT_ROLES },
      // "Agendas" (pedido do usuário): saiu de INTERNAL_ROLES pra
      // MANAGEMENT_ROLES — Consultor perdeu este item do menu (decisão
      // confirmada com o usuário na reorganização de menus).
      { to: '/schedules', label: 'Agenda de consultores', icon: ClockIcon, roles: MANAGEMENT_ROLES },
    ],
  },
  // Menu próprio de Tickets (pedido do usuário): a lista de tickets, que todo
  // perfil interno (inclusive Consultor) usa para abrir e acompanhar os seus,
  // e o Dashboard com os indicadores, só para perfis de gestão.
  {
    type: 'group',
    key: 'tickets',
    label: 'Tickets',
    items: [
      { to: '/tickets', label: 'Tickets', end: true, icon: FlagIcon, roles: INTERNAL_ROLES },
      { to: '/tickets/dashboard', label: 'Dashboard Tickets', icon: BarChartIcon, roles: MANAGEMENT_ROLES },
    ],
  },
  {
    type: 'group',
    key: 'apontamentos',
    label: 'Apontamentos',
    items: [
      { to: '/timesheets', label: 'Apontamento de horas', icon: ClipboardCheckIcon, roles: INTERNAL_ROLES },
      { to: '/service-orders', label: 'Ordens de Serviço', icon: FileTextIcon, roles: INTERNAL_ROLES },
      { to: '/timesheet-approvals', label: 'Aprovações de horas', icon: BadgeCheckIcon, roles: MANAGEMENT_ROLES },
    ],
  },
  // "Conhecimento" (pedido do usuário, "NOVAS MELHORIAS": processo de
  // registro de conhecimento dos consultores) — três telas, cada uma com
  // seu próprio `roles` exatamente como o usuário especificou (ver
  // KNOWLEDGE_CATALOG_ROLES/KNOWLEDGE_SELF_ASSESSMENT_ROLES/
  // KNOWLEDGE_REVIEW_ROLES em utils/labels.js); a seção some inteira pra
  // quem não tem acesso a nenhuma das três (ex.: perfis de cliente).
  {
    type: 'group',
    key: 'conhecimento',
    label: 'Conhecimento',
    items: [
      { to: '/knowledge/catalog', label: 'Cadastro de Funcionalidades', icon: BookIcon, roles: KNOWLEDGE_CATALOG_ROLES },
      {
        to: '/knowledge/self-assessment',
        label: 'Registro de Conhecimento',
        icon: BadgeCheckIcon,
        roles: KNOWLEDGE_SELF_ASSESSMENT_ROLES,
      },
      { to: '/knowledge/review', label: 'Revisão e Aprovação', icon: ClipboardCheckIcon, roles: KNOWLEDGE_REVIEW_ROLES },
    ],
  },
  {
    type: 'group',
    key: 'configuracoes',
    label: 'Configurações',
    items: [
      { to: '/users', label: 'Usuários e recursos', icon: UsersIcon, roles: ADMIN_LIKE_ROLES },
      // "Processo de envio de emails" (pedido do usuário) — configurador
      // de SMTP, mesmo critério de acesso de Usuários (dado sensível).
      { to: '/email-settings', label: 'E-mail', icon: MailIcon, roles: ADMIN_LIKE_ROLES },
    ],
  },
  // "Relatórios" (pedido do usuário): saiu de ADMIN_LIKE_ROLES pra
  // MANAGEMENT_ROLES — Gerente de Projetos ganhou este item do menu
  // (decisão confirmada com o usuário na reorganização de menus; mesma
  // mudança replicada em GET /reports/hours-breakdown no backend). Depois,
  // com o Status Report (pedido do usuário: "pode implementar os 2
  // modelos e colocar na opção de relatorios"), PM do cliente passou a
  // enxergar este item pela primeira vez — mas ReportsIndexPage.jsx
  // mostra só o card do Status Report pra ele, nunca "Horas por tipo".
  { type: 'item', to: '/reports', label: 'Relatórios', icon: BarChartIcon, roles: STATUS_REPORT_VISIBLE_ROLES },
]

const WIDTH_EXPANDED = 252
const WIDTH_COLLAPSED = 76

const GROUP_STATE_STORAGE_KEY = 'pmpy_sidebar_open_groups'

function loadOpenGroups() {
  try {
    const raw = localStorage.getItem(GROUP_STATE_STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    // localStorage bloqueado/cheio (modo privado etc.) — todas as seções
    // simplesmente começam abertas (ver isGroupOpen abaixo) e deixam de
    // lembrar estado entre reloads, sem travar a tela.
    return {}
  }
}

function saveOpenGroups(state) {
  try {
    localStorage.setItem(GROUP_STATE_STORAGE_KEY, JSON.stringify(state))
  } catch {
    // Idem acima — falha silenciosa, não é dado crítico.
  }
}

/** Visível pro perfil logado? Sem `roles`, sempre visível. */
function isVisible(entry, role) {
  return !entry.roles || entry.roles.includes(role)
}

/** Monta a estrutura de navegação já filtrada pelo perfil: itens soltos
 * filtrados direto, grupos filtrados por dentro (e removidos inteiros
 * quando nenhum item sobra). */
function buildVisibleSections(role) {
  const sections = []
  for (const section of NAV_SECTIONS) {
    if (section.type === 'item') {
      if (isVisible(section, role)) sections.push(section)
      continue
    }
    const items = section.items.filter((item) => isVisible(item, role))
    if (items.length > 0) sections.push({ ...section, items })
  }
  return sections
}

function NavItem({ item, expanded, indent = false }) {
  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) =>
        `nav-link flex min-h-[40px] items-center rounded-lg py-2 transition-colors ${indent ? 'pl-5 pr-2.5' : 'px-2.5'} ${!expanded ? 'justify-center' : ''} ${isActive ? 'nav-link--active' : ''}`
      }
    >
      {({ isActive }) => (
        <>
          <item.icon size={18} style={{ color: isActive ? 'var(--nav-fg-strong)' : 'var(--nav-fg)' }} />
          {expanded && (
            <span
              className="ml-3 flex-1 text-[13px] font-semibold whitespace-nowrap"
              style={{ color: isActive ? 'var(--nav-fg-strong)' : 'var(--nav-fg)' }}
            >
              {item.label}
            </span>
          )}
        </>
      )}
    </NavLink>
  )
}

/** Menu lateral — estrutura e paleta ("chrome") portadas do app de
 * referência Resultar Servicios (components/app-sidebar.tsx). A paleta
 * (--nav-*) é fixa e não segue o tema claro/escuro do conteúdo.
 *
 * Recolhe/expande com o mouse: fica recolhido (só ícones) por padrão e
 * expande enquanto o ponteiro está sobre ele. Continua no fluxo normal do
 * layout (flex item, não overlay), então o conteúdo à direita redimensiona
 * junto, em tempo real, como o resto da tela.
 *
 * Reorganização de menus (pedido do usuário): as seções (Projetos/
 * Apontamentos/Configurações) são expansíveis/recolhíveis, independente do
 * recolhimento do menu inteiro — com o menu recolhido (só ícones), os
 * grupos somem e tudo aparece numa lista achatada só de ícones (não dá pra
 * clicar num título de seção que não está sendo mostrado). */
export default function Sidebar() {
  const { user } = useAuth()
  const { t } = useLanguage()
  const [expanded, setExpanded] = useState(false)
  const [openGroups, setOpenGroups] = useState(loadOpenGroups)

  const sections = buildVisibleSections(user.role)
  const flatItems = sections.flatMap((section) => (section.type === 'group' ? section.items : [section]))

  function isGroupOpen(key) {
    return openGroups[key] ?? true
  }

  function toggleGroup(key) {
    setOpenGroups((prev) => {
      const next = { ...prev, [key]: !isGroupOpen(key) }
      saveOpenGroups(next)
      return next
    })
  }

  return (
    <aside
      className="flex shrink-0 flex-col overflow-hidden border-r transition-[width] duration-150 ease-out print:hidden"
      style={{
        width: expanded ? WIDTH_EXPANDED : WIDTH_COLLAPSED,
        backgroundColor: 'var(--nav-bg)',
        borderColor: 'var(--nav-border)',
      }}
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
    >
      <div className="flex flex-1 flex-col px-3 py-[18px]">
        <div
          className={`mb-3.5 flex items-center gap-2.5 border-b px-1.5 pb-4 ${!expanded ? 'justify-center' : ''}`}
          style={{ borderColor: 'var(--nav-border)' }}
        >
          <img src={logo} alt="Resultar Servicios" className="h-7 w-7 shrink-0 rounded-md object-contain" />
          {expanded && (
            <p className="flex-1 truncate text-[11.5px] font-extrabold tracking-tight" style={{ color: 'var(--nav-fg-strong)' }}>
              RESULTAR SERVICIOS
            </p>
          )}
        </div>

        <div className="flex-1">
          {expanded && (
            <p
              className="px-2.5 pb-1.5 text-[10px] font-extrabold uppercase tracking-wider"
              style={{ color: 'var(--nav-fg-muted)' }}
            >
              {t('Workspace')}
            </p>
          )}

          {expanded ? (
            <nav className="space-y-1">
              {sections.map((section) =>
                section.type === 'item' ? (
                  <NavItem key={section.to} item={{ ...section, label: t(section.label) }} expanded />
                ) : (
                  <div key={section.key}>
                    <button
                      type="button"
                      onClick={() => toggleGroup(section.key)}
                      className="flex w-full items-center gap-1 rounded-lg px-2.5 py-1.5 text-left"
                    >
                      {isGroupOpen(section.key) ? (
                        <ChevronDownIcon size={12} style={{ color: 'var(--nav-fg-muted)' }} />
                      ) : (
                        <ChevronRightIcon size={12} style={{ color: 'var(--nav-fg-muted)' }} />
                      )}
                      <span
                        className="flex-1 truncate text-[10px] font-extrabold uppercase tracking-wider"
                        style={{ color: 'var(--nav-fg-muted)' }}
                      >
                        {t(section.label)}
                      </span>
                    </button>
                    {isGroupOpen(section.key) && (
                      <div className="space-y-1">
                        {section.items.map((item) => (
                          <NavItem key={item.to} item={{ ...item, label: t(item.label) }} expanded indent />
                        ))}
                      </div>
                    )}
                  </div>
                ),
              )}
            </nav>
          ) : (
            <nav className="space-y-1">
              {flatItems.map((item) => (
                <NavItem key={item.to} item={item} expanded={false} />
              ))}
            </nav>
          )}
        </div>

        <div className="mt-1 border-t pt-2.5" style={{ borderColor: 'var(--nav-border)' }}>
          {expanded ? (
            <>
              <p className="whitespace-nowrap text-[8.5px] font-bold tracking-wide" style={{ color: 'var(--nav-fg-muted)' }}>
                GESTIÓN DE PROYECTOS
              </p>
              <p className="mt-1 whitespace-nowrap text-[8.5px] font-bold tracking-wide" style={{ color: 'var(--nav-fg-muted)' }}>
                V1.0
              </p>
            </>
          ) : (
            <p className="text-center text-[8.5px] font-bold tracking-wide" style={{ color: 'var(--nav-fg-muted)' }}>
              V1.0
            </p>
          )}
        </div>
      </div>
    </aside>
  )
}
