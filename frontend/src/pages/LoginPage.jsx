import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import { GlobeIcon } from '../components/icons'
import logo from '../assets/resultar-logo.png'

/** Tela de Login redesenhada a partir da referência visual do app irmão
 * "Resultar Servicios" (Controle de Viagens e Frota) — mesma paleta
 * `--nav-*` já usada no menu lateral (ver Sidebar.jsx e o comentário em
 * index.css: "extraída do app de referência Resultar Servicios"), então o
 * Login e o menu ficam com a MESMA identidade visual escura fixa,
 * independente do tema claro/escuro do conteúdo logado (ThemeContext só
 * afeta as telas internas, nunca este splash). */
export default function LoginPage() {
  const { user, loading, login } = useAuth()
  const { language, setLanguage, t } = useLanguage()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [showRecoveryNotice, setShowRecoveryNotice] = useState(false)

  if (!loading && user) {
    const redirectTo = location.state?.from || '/'
    return <Navigate to={redirectTo} replace />
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message || t('Não foi possível entrar.'))
    } finally {
      setSubmitting(false)
    }
  }

  const fieldStyle = {
    borderColor: 'var(--nav-border)',
    backgroundColor: 'var(--nav-bg)',
    color: 'var(--nav-fg-strong)',
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 py-10" style={{ backgroundColor: 'var(--nav-bg)' }}>
      <button
        type="button"
        aria-label={t('Idioma')}
        title={t('Idioma')}
        onClick={() => setLanguage(language === 'es' ? 'pt-BR' : 'es')}
        className="fixed right-5 top-5 flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-[11px] font-bold transition-colors hover:opacity-80"
        style={{ borderColor: 'var(--nav-border)', backgroundColor: 'var(--nav-card)', color: 'var(--nav-fg)' }}
      >
        <GlobeIcon size={14} />
        {language === 'es' ? 'ES' : 'PT'}
      </button>

      <div className="w-full max-w-sm rounded-2xl border p-7" style={{ backgroundColor: 'var(--nav-card)', borderColor: 'var(--nav-border)' }}>
        <div className="flex flex-col items-center text-center">
          <div
            className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border"
            style={{ borderColor: 'var(--nav-border)', backgroundColor: 'var(--nav-bg)' }}
          >
            <img src={logo} alt="Resultar Servicios" className="h-8 w-8 object-contain" />
          </div>
          <p className="text-lg font-extrabold tracking-tight" style={{ color: 'var(--nav-fg-strong)' }}>
            RESULTAR SERVICIOS
          </p>
          <p className="mt-1 text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--nav-fg-muted)' }}>
            Gestión de Proyectos
          </p>
        </div>

        <form onSubmit={handleSubmit} className="mt-7 space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-semibold" style={{ color: 'var(--nav-fg)' }}>
              {t('E-mail')}
            </label>
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="nome@empresa.com"
              className="w-full rounded-lg border px-3 py-2 text-sm outline-none transition-colors"
              style={fieldStyle}
            />
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <label className="text-xs font-semibold" style={{ color: 'var(--nav-fg)' }}>
                {t('Senha')}
              </label>
              <button
                type="button"
                onClick={() => setShowPassword((value) => !value)}
                className="text-[11px] font-semibold hover:underline"
                style={{ color: 'var(--nav-accent)' }}
              >
                {showPassword ? t('Ocultar') : t('Mostrar')}
              </button>
            </div>
            <input
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-lg border px-3 py-2 text-sm outline-none transition-colors"
              style={fieldStyle}
            />
          </div>

          {error && (
            <p className="rounded-lg px-3 py-2 text-xs" style={{ backgroundColor: 'rgba(211, 59, 59, 0.15)', color: '#f4a3a3' }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg py-2.5 text-sm font-bold transition-opacity hover:opacity-90 disabled:opacity-60"
            style={{ backgroundColor: 'var(--nav-accent)', color: 'var(--nav-accent-on)' }}
          >
            {submitting ? t('Entrando…') : t('Entrar')}
          </button>
        </form>

        <div className="mt-3 text-center">
          <button
            type="button"
            onClick={() => setShowRecoveryNotice((value) => !value)}
            className="text-xs font-medium hover:underline"
            style={{ color: 'var(--nav-fg-muted)' }}
          >
            {t('Preciso recuperar meu acesso')}
          </button>
          {showRecoveryNotice && (
            <p className="mt-2 text-[11px] leading-relaxed" style={{ color: 'var(--nav-fg-muted)' }}>
              {t('A redefinição de senha deve ser solicitada ao Administrador.')}
            </p>
          )}
        </div>

        <div className="mt-6 border-t pt-4 text-center" style={{ borderColor: 'var(--nav-border)' }}>
          <p className="text-xs font-semibold" style={{ color: 'var(--nav-fg)' }}>
            {t('Acesso privado da organização')}
          </p>
          <p className="mt-1 text-[11px] leading-relaxed" style={{ color: 'var(--nav-fg-muted)' }}>
            {t('Os usuários e permissões são administrados pelo Administrador.')}
          </p>
        </div>
      </div>

      <p className="fixed bottom-5 left-1/2 -translate-x-1/2 text-[10px] font-bold uppercase tracking-wide" style={{ color: 'var(--nav-fg-muted)' }}>
        GESTIÓN DE PROYECTOS · V1.0
      </p>
    </div>
  )
}
