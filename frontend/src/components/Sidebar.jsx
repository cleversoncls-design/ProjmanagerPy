import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { MANAGEMENT_ROLES, ROLE_LABELS } from '../utils/labels'
import logo from '../assets/resultar-logo.png'
import { BriefcaseIcon, BuildingIcon, CalendarIcon, HomeIcon, LogoutIcon, PanelLeftIcon, UsersIcon } from './icons'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true, icon: HomeIcon },
  { to: '/projects', label: 'Projetos', icon: BriefcaseIcon },
  { to: '/clients', label: 'Clientes', roles: MANAGEMENT_ROLES, icon: BuildingIcon },
  { to: '/users', label: 'Usuários e recursos', roles: MANAGEMENT_ROLES, icon: UsersIcon },
  { to: '/calendars', label: 'Calendários', roles: MANAGEMENT_ROLES, icon: CalendarIcon },
]

const STORAGE_KEY = 'pm-sidebar-collapsed'
const WIDTH_EXPANDED = 252
const WIDTH_COLLAPSED = 76

/** Menu lateral — estrutura e paleta ("chrome") portadas do app de
 * referência Resultar Servicios (components/app-sidebar.tsx). A paleta
 * (--nav-*) é fixa e não segue o tema claro/escuro do conteúdo. */
export default function Sidebar() {
  const { user, logout } = useAuth()
  const items = NAV_ITEMS.filter((item) => !item.roles || item.roles.includes(user.role))
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(STORAGE_KEY) === '1')
    } catch {
      // ignore
    }
  }, [])

  function toggleCollapsed() {
    setCollapsed((current) => {
      const next = !current
      try {
        localStorage.setItem(STORAGE_KEY, next ? '1' : '0')
      } catch {
        // ignore
      }
      return next
    })
  }

  const showLabels = !collapsed

  return (
    <aside
      className="flex shrink-0 flex-col border-r"
      style={{ width: collapsed ? WIDTH_COLLAPSED : WIDTH_EXPANDED, backgroundColor: 'var(--nav-bg)', borderColor: 'var(--nav-border)' }}
    >
      <div className="flex flex-1 flex-col px-3 py-[18px]">
        {showLabels ? (
          <div
            className="mb-3.5 flex items-center gap-2.5 border-b px-1.5 pb-4"
            style={{ borderColor: 'var(--nav-border)' }}
          >
            <img src={logo} alt="Resultar Servicios" className="h-7 w-7 shrink-0 rounded-md object-contain" />
            <p className="flex-1 truncate text-[11.5px] font-extrabold tracking-tight" style={{ color: 'var(--nav-fg-strong)' }}>
              RESULTAR SERVICIOS
            </p>
            <button
              type="button"
              aria-label="Recolher menu"
              onClick={toggleCollapsed}
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md transition-colors hover:bg-[var(--nav-hover-bg)]"
              style={{ color: 'var(--nav-fg)' }}
            >
              <PanelLeftIcon size={15} />
            </button>
          </div>
        ) : (
          <button
            type="button"
            aria-label="Expandir menu"
            onClick={toggleCollapsed}
            className="mb-3.5 flex items-center justify-center border-b pb-4"
            style={{ borderColor: 'var(--nav-border)' }}
          >
            <img src={logo} alt="Resultar Servicios" className="h-7 w-7 rounded-md object-contain" />
          </button>
        )}

        <div className="flex-1">
          {showLabels && (
            <p
              className="px-2.5 pb-1.5 text-[10px] font-extrabold uppercase tracking-wider"
              style={{ color: 'var(--nav-fg-muted)' }}
            >
              Workspace
            </p>
          )}
          <nav className="space-y-1">
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `nav-link flex min-h-[40px] items-center rounded-lg px-2.5 py-2 transition-colors ${!showLabels ? 'justify-center' : ''} ${isActive ? 'nav-link--active' : ''}`
                }
              >
                {({ isActive }) => (
                  <>
                    <item.icon size={18} style={{ color: isActive ? 'var(--nav-fg-strong)' : 'var(--nav-fg)' }} />
                    {showLabels && (
                      <span
                        className="ml-3 flex-1 text-[13px] font-semibold"
                        style={{ color: isActive ? 'var(--nav-fg-strong)' : 'var(--nav-fg)' }}
                      >
                        {item.label}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        {showLabels && (
          <div className="mt-1 border-t pt-3" style={{ borderColor: 'var(--nav-border)' }}>
            <div className="mb-1 px-0.5">
              <p className="truncate text-[12.5px] font-bold" style={{ color: 'var(--nav-fg-strong)' }}>
                {user.name}
              </p>
              <p className="truncate text-[11px]" style={{ color: 'var(--nav-fg-muted)' }}>
                {user.email}
              </p>
              <p className="mt-0.5 truncate text-[10.5px] font-medium" style={{ color: 'var(--nav-accent)' }}>
                {ROLE_LABELS[user.role] || user.role}
              </p>
            </div>
            <button
              type="button"
              onClick={logout}
              className="mt-2 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-[13px] font-semibold transition-colors hover:bg-[var(--nav-hover-bg)]"
              style={{ color: 'var(--nav-fg)' }}
            >
              <LogoutIcon size={16} />
              Sair
            </button>
            <div className="mt-3 border-t pt-2.5" style={{ borderColor: 'var(--nav-border)' }}>
              <p className="text-[8.5px] font-bold tracking-wide" style={{ color: 'var(--nav-fg-muted)' }}>
                GESTIÓN DE PROYECTOS
              </p>
              <p className="mt-1 text-[8.5px] font-bold tracking-wide" style={{ color: 'var(--nav-fg-muted)' }}>
                V1.0
              </p>
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}
