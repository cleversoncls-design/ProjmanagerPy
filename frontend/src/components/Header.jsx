import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { useLanguage } from '../context/LanguageContext'
import ChangePasswordModal from './ChangePasswordModal'
import CalendarInviteModal from './CalendarInviteModal'
import * as resourcesApi from '../api/resources'
import { BellIcon, CalendarIcon, ChevronDownIcon, KeyIcon, LogoutIcon, MoonIcon, SunIcon } from './icons'

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
  const [menuOpen, setMenuOpen] = useState(false)
  const [changingPassword, setChangingPassword] = useState(false)
  // Convite de calendário (Agenda → Google Calendar): null enquanto carrega
  // ou quando o usuário não tem recurso vinculado (404) — nesse caso o item
  // "Meu Google Calendar" não aparece no menu.
  const [calendarInvite, setCalendarInvite] = useState(null)
  const [editingCalendarInvite, setEditingCalendarInvite] = useState(false)

  useEffect(() => {
    let active = true
    resourcesApi
      .getMyCalendarInvite()
      .then((data) => active && setCalendarInvite(data))
      .catch(() => active && setCalendarInvite(null))
    return () => {
      active = false
    }
  }, [user?.id])
  const menuRef = useRef(null)
  const dropdownRef = useRef(null)
  const [menuPos, setMenuPos] = useState({ top: 0, right: 0 })

  // O <header> tem overflow-x-auto (vira overflow:auto nos dois eixos) e
  // cortaria um menu `absolute` pendurado nele — por isso o menu é renderizado
  // num portal em document.body, com posição `fixed` calculada a partir do
  // botão do avatar.
  function toggleMenu() {
    if (!menuOpen && menuRef.current) {
      const rect = menuRef.current.getBoundingClientRect()
      setMenuPos({ top: rect.bottom + 8, right: Math.max(8, window.innerWidth - rect.right) })
    }
    setMenuOpen((open) => !open)
  }

  // Fecha o menu do usuário ao clicar fora, apertar Esc, rolar ou redimensionar.
  useEffect(() => {
    if (!menuOpen) return undefined
    const close = () => setMenuOpen(false)
    window.addEventListener('resize', close)
    const onPointerDown = (event) => {
      const inButton = menuRef.current && menuRef.current.contains(event.target)
      const inMenu = dropdownRef.current && dropdownRef.current.contains(event.target)
      if (!inButton && !inMenu) setMenuOpen(false)
    }
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      window.removeEventListener('resize', close)
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [menuOpen])

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
        {/* Menu do usuário: qualquer perfil troca a PRÓPRIA senha por aqui. */}
        <div ref={menuRef} className="relative shrink-0">
          <button
            type="button"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            onClick={toggleMenu}
            className="flex shrink-0 items-center gap-2.5 rounded-[10px] px-1.5 py-1 text-left transition-colors hover:bg-[var(--page)]"
          >
            <div className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full bg-[var(--text-primary)]">
              <span className="text-xs font-extrabold text-[var(--page)]">{initialsOf(user?.name)}</span>
            </div>
            <div className="hidden sm:block">
              <p className="max-w-[160px] truncate text-[12.5px] font-bold text-[var(--text-primary)]">{user?.name || t('Usuário autenticado')}</p>
              <p className="max-w-[160px] truncate text-[11px] text-[var(--text-muted)]">{user?.email || ''}</p>
            </div>
            <ChevronDownIcon size={14} className="shrink-0 text-[var(--text-muted)]" />
          </button>
          {menuOpen &&
            createPortal(
            <div
              ref={dropdownRef}
              role="menu"
              style={{ position: 'fixed', top: menuPos.top, right: menuPos.right }}
              className="z-40 w-48 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)] py-1 shadow-xl print:hidden"
            >
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false)
                  setChangingPassword(true)
                }}
                className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-[12.5px] font-semibold text-[var(--text-secondary)] transition-colors hover:bg-[var(--page)] hover:text-[var(--text-primary)]"
              >
                <KeyIcon size={15} />
                {t('Alterar senha')}
              </button>
              {calendarInvite && (
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setMenuOpen(false)
                    setEditingCalendarInvite(true)
                  }}
                  className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-[12.5px] font-semibold text-[var(--text-secondary)] transition-colors hover:bg-[var(--page)] hover:text-[var(--text-primary)]"
                >
                  <CalendarIcon size={15} />
                  {t('Meu Google Calendar')}
                </button>
              )}
              <button
                type="button"
                role="menuitem"
                onClick={logout}
                className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-[12.5px] font-semibold text-[var(--text-secondary)] transition-colors hover:bg-[var(--page)] hover:text-[var(--text-primary)]"
              >
                <LogoutIcon size={15} />
                {t('Sair')}
              </button>
            </div>,
            document.body,
          )}
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
      {changingPassword && <ChangePasswordModal onClose={() => setChangingPassword(false)} />}
      {editingCalendarInvite && calendarInvite && (
        <CalendarInviteModal initial={calendarInvite} onClose={() => setEditingCalendarInvite(false)} onSaved={setCalendarInvite} />
      )}
    </header>
  )
}
