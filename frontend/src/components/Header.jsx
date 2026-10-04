import { useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { useLanguage } from '../context/LanguageContext'
import { BellIcon, LogoutIcon, MoonIcon, SunIcon } from './icons'

const HEADING_BY_PREFIX = [
  { prefix: '/projects/', crumb: 'Projetos', title: 'Detalhe do projeto' },
  { prefix: '/projects', crumb: 'Portfólio', title: 'Projetos' },
  { prefix: '/clients', crumb: 'Cadastros', title: 'Clientes' },
  { prefix: '/users', crumb: 'Cadastros', title: 'Usuários e recursos' },
  { prefix: '/calendars', crumb: 'Cadastros', title: 'Calendários' },
  // Home do Usuário-chave (reorganização de menus) — sem isso, cairia no
  // prefixo "/" abaixo e mostraria "Dashboard" por engano pra um perfil que
  // nem acessa o Dashboard.
  { prefix: '/no-access', crumb: 'Visão geral', title: 'Sem acesso' },
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
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const { language, setLanguage, t } = useLanguage()
  const { crumb, title } = usePageHeading()

  return (
    <header
      className="flex h-16 shrink-0 items-center justify-between gap-2 overflow-x-auto border-b px-3 sm:px-7 print:hidden"
      style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }}
    >
      <div className="min-w-0 shrink-0">
        <p className="text-[11px] font-bold uppercase tracking-wide text-[var(--text-muted)]">{t(crumb)}</p>
        <p className="mt-0.5 truncate text-base font-extrabold text-[var(--text-primary)]">{t(title)}</p>
      </div>
      <div className="flex shrink-0 items-center gap-1.5 sm:gap-3.5">
        <button
          type="button"
          aria-label={t('Idioma')}
          title={t('Idioma')}
          onClick={() => setLanguage(language === 'es' ? 'pt-BR' : 'es')}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] border border-[var(--border)] bg-[var(--surface)] text-[11px] font-extrabold text-[var(--text-muted)] transition-colors hover:bg-[var(--page)]"
        >
          {language === 'es' ? 'ES' : 'PT'}
        </button>
        <button
          type="button"
          aria-label={theme === 'dark' ? t('Usar tema claro') : t('Usar tema escuro')}
          onClick={toggleTheme}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] border border-[var(--border)] bg-[var(--surface)] text-[var(--text-muted)] transition-colors hover:bg-[var(--page)]"
        >
          {theme === 'dark' ? <MoonIcon size={17} /> : <SunIcon size={17} />}
        </button>
        <button
          type="button"
          aria-label={t('Notificações')}
          className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-[10px] border border-[var(--border)] bg-[var(--surface)] text-[var(--text-muted)] transition-colors hover:bg-[var(--page)] sm:flex"
        >
          <BellIcon size={17} />
        </button>
        <div className="hidden h-7 w-px shrink-0 bg-[var(--border)] sm:block" />
        <div className="flex shrink-0 items-center gap-2.5">
          <div className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full bg-[var(--text-primary)]">
            <span className="text-xs font-extrabold text-[var(--page)]">{initialsOf(user?.name)}</span>
          </div>
          <div className="hidden sm:block">
            <p className="max-w-[160px] truncate text-[12.5px] font-bold text-[var(--text-primary)]">{user?.name || t('Usuário autenticado')}</p>
            <p className="max-w-[160px] truncate text-[11px] text-[var(--text-muted)]">{user?.email || ''}</p>
          </div>
        </div>
        <div className="hidden h-7 w-px shrink-0 bg-[var(--border)] sm:block" />
        <button
          type="button"
          onClick={logout}
          aria-label={t('Sair')}
          title={t('Sair')}
          className="flex shrink-0 items-center gap-1.5 rounded-[10px] border border-[var(--border)] bg-[var(--surface)] px-2.5 py-2 text-[12.5px] font-semibold text-[var(--text-secondary)] transition-colors hover:bg-[var(--page)] hover:text-[var(--text-primary)] sm:px-3"
        >
          <LogoutIcon size={15} />
          <span className="hidden sm:inline">{t('Sair')}</span>
        </button>
      </div>
    </header>
  )
}
