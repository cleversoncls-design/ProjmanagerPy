import { useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { BellIcon, MoonIcon, SunIcon } from './icons'

const HEADING_BY_PREFIX = [
  { prefix: '/projects/', crumb: 'Projetos', title: 'Detalhe do projeto' },
  { prefix: '/projects', crumb: 'Portfólio', title: 'Projetos' },
  { prefix: '/clients', crumb: 'Cadastros', title: 'Clientes' },
  { prefix: '/users', crumb: 'Cadastros', title: 'Usuários e recursos' },
  { prefix: '/calendars', crumb: 'Cadastros', title: 'Calendários' },
  { prefix: '/', crumb: 'Visão geral', title: 'Dashboard' },
]

function usePageHeading() {
  const { pathname } = useLocation()
  return HEADING_BY_PREFIX.find((entry) => pathname.startsWith(entry.prefix)) || HEADING_BY_PREFIX[HEADING_BY_PREFIX.length - 1]
}

function initialsOf(name) {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  const first = parts[0]?.[0] ?? ''
  const last = parts.length > 1 ? parts[parts.length - 1][0] : ''
  return (first + last).toUpperCase()
}

/** Cabeçalho fixo do topo — estrutura portada do app de referência Resultar
 * Servicios (components/app-header.tsx): breadcrumb + título à esquerda,
 * botões de ação (tema, notificações) e avatar do usuário à direita. */
export default function Header() {
  const { user } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const { crumb, title } = usePageHeading()

  return (
    <header
      className="flex h-16 shrink-0 items-center justify-between border-b px-7"
      style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }}
    >
      <div>
        <p className="text-[11px] font-bold uppercase tracking-wide text-[var(--text-muted)]">{crumb}</p>
        <p className="mt-0.5 text-base font-extrabold text-[var(--text-primary)]">{title}</p>
      </div>
      <div className="flex items-center gap-3.5">
        <button
          type="button"
          aria-label={theme === 'dark' ? 'Usar tema claro' : 'Usar tema escuro'}
          onClick={toggleTheme}
          className="flex h-9 w-9 items-center justify-center rounded-[10px] border border-[var(--border)] bg-[var(--surface)] text-[var(--text-muted)] transition-colors hover:bg-[var(--page)]"
        >
          {theme === 'dark' ? <MoonIcon size={17} /> : <SunIcon size={17} />}
        </button>
        <button
          type="button"
          aria-label="Notificações"
          className="flex h-9 w-9 items-center justify-center rounded-[10px] border border-[var(--border)] bg-[var(--surface)] text-[var(--text-muted)] transition-colors hover:bg-[var(--page)]"
        >
          <BellIcon size={17} />
        </button>
        <div className="h-7 w-px bg-[var(--border)]" />
        <div className="flex items-center gap-2.5">
          <div className="flex h-[34px] w-[34px] items-center justify-center rounded-full bg-[var(--text-primary)]">
            <span className="text-xs font-extrabold text-[var(--page)]">{initialsOf(user?.name)}</span>
          </div>
          <div className="hidden sm:block">
            <p className="max-w-[160px] truncate text-[12.5px] font-bold text-[var(--text-primary)]">{user?.name || 'Usuário autenticado'}</p>
            <p className="max-w-[160px] truncate text-[11px] text-[var(--text-muted)]">{user?.email || ''}</p>
          </div>
        </div>
      </div>
    </header>
  )
}
