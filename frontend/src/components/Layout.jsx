import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { MANAGEMENT_ROLES, ROLE_LABELS } from '../utils/labels'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/projects', label: 'Projetos' },
  { to: '/clients', label: 'Clientes', roles: MANAGEMENT_ROLES },
  { to: '/users', label: 'Usuários e recursos', roles: MANAGEMENT_ROLES },
  { to: '/calendars', label: 'Calendários', roles: MANAGEMENT_ROLES },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const items = NAV_ITEMS.filter((item) => !item.roles || item.roles.includes(user.role))

  return (
    <div className="flex min-h-screen bg-[var(--page)]">
      <aside className="flex w-60 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)]">
        <div className="border-b border-[var(--border)] px-5 py-5">
          <p className="text-sm font-semibold tracking-tight text-[var(--text-primary)]">ProjmanagerPy</p>
          <p className="mt-0.5 text-xs text-[var(--text-muted)]">Gestão de projetos</p>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-[var(--series-1)]/10 text-[var(--series-1)]'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--page)]'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-[var(--border)] px-4 py-4">
          <p className="truncate text-sm font-medium text-[var(--text-primary)]">{user.name}</p>
          <p className="truncate text-xs text-[var(--text-muted)]">{ROLE_LABELS[user.role] || user.role}</p>
          <button
            type="button"
            onClick={logout}
            className="mt-3 text-xs font-medium text-[var(--text-secondary)] underline underline-offset-2 hover:text-[var(--text-primary)]"
          >
            Sair
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-8 py-8">
        <Outlet />
      </main>
    </div>
  )
}
