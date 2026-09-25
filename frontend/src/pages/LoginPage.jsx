import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import { TextInput, FormField } from '../components/FormField'
import Button from '../components/Button'
import ErrorBanner from '../components/ErrorBanner'
import logo from '../assets/resultar-logo.png'

export default function LoginPage() {
  const { user, loading, login } = useAuth()
  const { language, setLanguage, t } = useLanguage()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

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

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--page)] px-4">
      <div className="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <div className="mb-1 flex items-center justify-between gap-2.5">
          <div className="flex items-center gap-2.5">
            <img src={logo} alt="Resultar Servicios" className="h-8 w-8 rounded-md object-contain" />
            <div>
              <p className="text-sm font-extrabold tracking-tight text-[var(--text-primary)]">RESULTAR SERVICIOS</p>
              <p className="text-[11px] font-medium text-[var(--text-muted)]">Gestión de Proyectos</p>
            </div>
          </div>
          <button
            type="button"
            aria-label={t('Idioma')}
            title={t('Idioma')}
            onClick={() => setLanguage(language === 'es' ? 'pt-BR' : 'es')}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] border border-[var(--border)] bg-[var(--surface)] text-[11px] font-extrabold text-[var(--text-muted)] transition-colors hover:bg-[var(--page)]"
          >
            {language === 'es' ? 'ES' : 'PT'}
          </button>
        </div>
        <p className="mt-4 text-xs text-[var(--text-muted)]">{t('Entre com seu e-mail e senha para continuar.')}</p>

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <FormField label={t('E-mail')} required>
            <TextInput
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </FormField>
          <FormField label={t('Senha')} required>
            <TextInput
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </FormField>

          <ErrorBanner message={error} />

          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? t('Entrando…') : t('Entrar')}
          </Button>
        </form>
      </div>
    </div>
  )
}
