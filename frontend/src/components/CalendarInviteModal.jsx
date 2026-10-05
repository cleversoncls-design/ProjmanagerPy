import { useState } from 'react'
import * as resourcesApi from '../api/resources'
import { useLanguage } from '../context/LanguageContext'
import Modal from './Modal'
import Button from './Button'
import ErrorBanner from './ErrorBanner'
import { FormField, TextInput } from './FormField'

/** "Meu Google Calendar" — o próprio consultor liga/desliga o recebimento
 * dos seus agendamentos como convite de calendário (.ics por e-mail). O
 * Google Calendar reconhece o convite e põe o evento na agenda dele;
 * remarcar atualiza e excluir cancela. `initial` vem do Header (GET
 * /resources/me/calendar-invite). */
export default function CalendarInviteModal({ initial, onClose, onSaved }) {
  const { t } = useLanguage()
  const [enabled, setEnabled] = useState(initial.enabled)
  const [email, setEmail] = useState(initial.email || '')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)

  async function save() {
    const saved = await resourcesApi.updateMyCalendarInvite({ enabled, email: email.trim() || null })
    onSaved(saved)
    setEmail(saved.email || '')
    return saved
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setInfo('')
    setSaving(true)
    try {
      await save()
      setInfo(t('Configuração salva.'))
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleTest() {
    setError('')
    setInfo('')
    setTesting(true)
    try {
      await save()
      await resourcesApi.sendMyCalendarInviteTest()
      setInfo(
        t('Convite de teste enviado para {email}. Confira sua caixa de entrada e o Google Calendar (evento de amanhã às 09:00).', {
          email: email.trim() || initial.default_email,
        }),
      )
    } catch (err) {
      setError(err.message)
    } finally {
      setTesting(false)
    }
  }

  return (
    <Modal title={t('Meu Google Calendar')} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-[13px] text-[var(--text-secondary)]">
          {t(
            'Receba os seus agendamentos da Agenda de consultores no Google Calendar: o sistema envia um convite por e-mail, e remarcar ou excluir o agendamento atualiza ou cancela o evento.',
          )}
        </p>

        {!initial.email_service_ready && (
          <p className="rounded-lg border border-[var(--status-warning)] px-3 py-2 text-[12.5px] text-[var(--text-secondary)]">
            {t('O envio de e-mails do sistema está desativado. Peça ao administrador para ativá-lo em Configurações > E-mail.')}
          </p>
        )}

        <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]">
          <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
          {t('Receber meus agendamentos no Google Calendar')}
        </label>

        <FormField label={t('E-mail da conta Google')} hint={t('Deixe em branco para usar o e-mail de login: {email}', { email: initial.default_email })}>
          <TextInput type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder={initial.default_email} />
        </FormField>

        <p className="text-xs text-[var(--text-muted)]">
          {t('Vale só para agendamentos novos ou alterados a partir de agora; os que já existem não são reenviados.')}
        </p>

        <ErrorBanner message={error} />
        {info && <p className="text-[13px] text-[var(--text-primary)]">{info}</p>}

        <div className="flex flex-wrap justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={handleTest} disabled={testing || saving}>
            {testing ? t('Enviando…') : t('Enviar convite de teste')}
          </Button>
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Fechar')}
          </Button>
          <Button type="submit" disabled={saving || testing}>
            {saving ? t('Salvando…') : t('Salvar')}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
