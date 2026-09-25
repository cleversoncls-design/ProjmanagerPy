import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import { MANAGEMENT_ROLES } from '../utils/labels'
import logo from '../assets/resultar-logo.png'
import { BriefcaseIcon, BuildingIcon, CalendarIcon, HomeIcon, UsersIcon } from './icons'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true, icon: HomeIcon },
  { to: '/projects', label: 'Projetos', icon: BriefcaseIcon },
  { to: '/clients', label: 'Clientes', roles: MANAGEMENT_ROLES, icon: BuildingIcon },
  { to: '/users', label: 'Usuários e recursos', roles: MANAGEMENT_ROLES, icon: UsersIcon },
  { to: '/calendars', label: 'Calendários', roles: MANAGEMENT_ROLES, icon: CalendarIcon },
]

const WIDTH_EXPANDED = 252
const WIDTH_COLLAPSED = 76

/** Menu lateral — estrutura e paleta ("chrome") portadas do app de
 * referência Resultar Servicios (components/app-sidebar.tsx). A paleta
 * (--nav-*) é fixa e não segue o tema claro/escuro do conteúdo.
 *
 * Recolhe/expande com o mouse: fica recolhido (só ícones) por padrão e
 * expande enquanto o ponteiro está sobre ele. Continua no fluxo normal do
 * layout (flex item, não overlay), então o conteúdo à direita redimensiona
 * junto, em tempo real, como o resto da tela. */
export default function Sidebar() {
  const { user } = useAuth()
  const { t } = useLanguage()
  const items = NAV_ITEMS.filter((item) => !item.roles || item.roles.includes(user.role))
  const [expanded, setExpanded] = useState(false)

  return (
    <aside
      className="flex shrink-0 flex-col overflow-hidden border-r transition-[width] duration-150 ease-out"
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
          <nav className="space-y-1">
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `nav-link flex min-h-[40px] items-center rounded-lg px-2.5 py-2 transition-colors ${!expanded ? 'justify-center' : ''} ${isActive ? 'nav-link--active' : ''}`
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
                        {t(item.label)}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
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
