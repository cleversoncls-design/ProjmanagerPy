import { useState } from 'react'
import * as authApi from '../api/auth'
import { setToken } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import Modal from './Modal'
import Button from './Button'
import ErrorBanner from './ErrorBanner'
import { FormField, TextInput } from './FormField'

const EMPTY_FORM = { current: '', next: '', confirm: '' }

/** Troca da PRÓPRIA senha — qualquer perfil logado.
 *
 * Dois usos:
 * - voluntário (Header → "Alterar senha"): `onClose` fecha o modal;
 * - obrigatório (`forced`, usuário recém-criado ou com senha redefinida pelo
 *   ADMIN — ver Layout): sem ✕ nem "Cancelar"; as únicas saídas são trocar a
 *   senha ou sair da aplicação.
 *
 * A API devolve um token novo (as outras sessões são encerradas); guardamos
 * ele e recarregamos o usuário pra a sessão atual seguir sem novo login. */
export default function ChangePasswordModal({ onClose, forced = false }) {
  const { reload, logout } = useAuth()
  const { t } = useLanguage()
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)

  const update = (field) => (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    if (form.next.length < 8) {
      setError(t('A nova senha deve ter no mínimo 8 caracteres.'))
      return
    }
    if (form.next !== form.confirm) {
      setError(t('A confirmação não confere com a nova senha.'))
      return
    }
    if (form.next === form.current) {
      setError(t('A nova senha deve ser diferente da senha atual.'))
      return
    }
    setSaving(true)
    try {
      const result = await authApi.changePassword(form.current, form.next)
      setToken(result.access_token)
      setForm(EMPTY_FORM)
      if (forced) {
        // Recarregar o usuário zera `must_change_password` e o Layout libera o app.
        await reload()
      } else {
        setDone(true)
        await reload()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const title = forced ? t('Defina sua nova senha') : t('Alterar senha')

  if (done) {
    return (
      <Modal title={title} onClose={onClose}>
        <p className="text-sm text-[var(--text-primary)]">
          {t('Senha alterada com sucesso. Suas outras sessões abertas foram encerradas.')}
        </p>
        <div className="flex justify-end pt-4">
          <Button type="button" onClick={onClose}>
            {t('Fechar')}
          </Button>
        </div>
      </Modal>
    )
  }

  return (
    <Modal title={title} onClose={forced ? undefined : onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {forced && (
          <p className="text-[13px] text-[var(--text-secondary)]">
            {t('Você está usando uma senha provisória. Por segurança, defina uma nova senha para continuar.')}
          </p>
        )}
        <FormField label={forced ? t('Senha provisória (atual)') : t('Senha atual')} required>
          <TextInput type="password" required autoComplete="current-password" value={form.current} onChange={update('current')} />
        </FormField>
        <FormField label={t('Nova senha')} required hint={t('Mínimo de 8 caracteres.')}>
          <TextInput type="password" required minLength={8} autoComplete="new-password" value={form.next} onChange={update('next')} />
        </FormField>
        <FormField label={t('Confirmar nova senha')} required>
          <TextInput type="password" required minLength={8} autoComplete="new-password" value={form.confirm} onChange={update('confirm')} />
        </FormField>

        <ErrorBanner message={error} />

        <div className="flex justify-end gap-2 pt-1">
          {forced ? (
            <Button type="button" variant="secondary" onClick={logout}>
              {t('Sair')}
            </Button>
          ) : (
            <Button type="button" variant="secondary" onClick={onClose}>
              {t('Cancelar')}
            </Button>
          )}
          <Button type="submit" disabled={saving}>
            {saving ? t('Salvando…') : t('Salvar')}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
