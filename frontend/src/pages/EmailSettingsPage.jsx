import { useEffect, useState } from 'react'
import * as emailSettingsApi from '../api/emailSettings'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Button from '../components/Button'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import { FormField, TextInput, Select } from '../components/FormField'
import { useLanguage } from '../context/LanguageContext'

const EMPTY_FORM = {
  enabled: false,
  smtp_host: '',
  smtp_port: 587,
  security: 'STARTTLS',
  smtp_username: '',
  smtp_password: '',
  from_email: '',
  from_name: '',
}

function formFromSettings(settings) {
  return {
    enabled: settings.enabled,
    smtp_host: settings.smtp_host,
    smtp_port: settings.smtp_port,
    security: settings.security,
    smtp_username: settings.smtp_username || '',
    smtp_password: '', // nunca vem preenchida (ver EmailSettingsRead) — em branco = "manter a já salva"
    from_email: settings.from_email,
    from_name: settings.from_name || '',
  }
}

/** Tela de Configurações > E-mail (pedido do usuário: "será necessário
 * criar um configurador de dados para envio de email? para indicar
 * servidor, usuario, senha, tipos de autentitcação, email de origem,
 * etc."). Registro único — sem lista, sem modal: carrega e salva a
 * própria tela, igual a uma tela de "perfil". */
export default function EmailSettingsPage() {
  const { t } = useLanguage()
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [form, setForm] = useState(EMPTY_FORM)
  const [saveError, setSaveError] = useState('')
  const [saving, setSaving] = useState(false)
  const [savedMessage, setSavedMessage] = useState('')

  function load() {
    setLoading(true)
    emailSettingsApi
      .getEmailSettings()
      .then((result) => {
        setSettings(result)
        setForm(formFromSettings(result))
      })
      .catch((err) => setLoadError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  function updateField(field) {
    return (event) => {
      const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
      setForm((prev) => ({ ...prev, [field]: value }))
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setSaveError('')
    setSavedMessage('')
    setSaving(true)
    try {
      const payload = {
        enabled: form.enabled,
        smtp_host: form.smtp_host,
        smtp_port: Number(form.smtp_port),
        security: form.security,
        smtp_username: form.smtp_username || null,
        // Em branco = "manter a senha já salva" (nunca manda string vazia
        // sem querer — isso apagaria a senha, ver EmailSettingsUpdate no
        // backend); só manda o campo quando o usuário de fato digitou algo.
        ...(form.smtp_password ? { smtp_password: form.smtp_password } : {}),
        from_email: form.from_email,
        from_name: form.from_name || null,
      }
      const result = await emailSettingsApi.updateEmailSettings(payload)
      setSettings(result)
      setForm(formFromSettings(result))
      setSavedMessage(t('Configuração salva.'))
    } catch (err) {
      setSaveError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <PageHeader
        title={t('Configuração de E-mail')}
        subtitle={t('Dados de SMTP usados para os avisos automáticos do sistema (agendamentos, aprovações pendentes e outros).')}
      />

      {loading && <Spinner />}
      <ErrorBanner message={loadError} />

      {!loading && !loadError && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card title={t('Servidor SMTP')} className="lg:col-span-2">
            <form onSubmit={handleSubmit} className="space-y-4">
              <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                <input type="checkbox" checked={form.enabled} onChange={updateField('enabled')} />
                {t('Ativo — manda os avisos automáticos de verdade')}
              </label>

              <div className="grid grid-cols-3 gap-4">
                <div className="col-span-2">
                  <FormField label={t('Servidor SMTP')} required>
                    <TextInput
                      required
                      placeholder="smtp.exemplo.com"
                      value={form.smtp_host}
                      onChange={updateField('smtp_host')}
                    />
                  </FormField>
                </div>
                <FormField label={t('Porta')} required>
                  <TextInput type="number" min="1" max="65535" required value={form.smtp_port} onChange={updateField('smtp_port')} />
                </FormField>
              </div>

              <FormField label={t('Segurança da conexão')} required>
                <Select required value={form.security} onChange={updateField('security')}>
                  <option value="NONE">{t('Nenhuma')}</option>
                  <option value="STARTTLS">{t('STARTTLS (recomendado)')}</option>
                  <option value="SSL">SSL/TLS</option>
                </Select>
              </FormField>

              <div className="grid grid-cols-2 gap-4">
                <FormField label={t('Usuário SMTP')}>
                  <TextInput value={form.smtp_username} onChange={updateField('smtp_username')} />
                </FormField>
                <FormField
                  label={t('Senha SMTP')}
                  hint={settings?.password_configured ? t('Já há uma senha salva — deixe em branco para mantê-la.') : undefined}
                >
                  <TextInput
                    type="password"
                    autoComplete="new-password"
                    placeholder={settings?.password_configured ? '••••••••' : ''}
                    value={form.smtp_password}
                    onChange={updateField('smtp_password')}
                  />
                </FormField>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <FormField label={t('E-mail de origem (remetente)')} required>
                  <TextInput
                    type="email"
                    required
                    placeholder="no-reply@exemplo.com"
                    value={form.from_email}
                    onChange={updateField('from_email')}
                  />
                </FormField>
                <FormField label={t('Nome do remetente')}>
                  <TextInput placeholder="ProjmanagerPy" value={form.from_name} onChange={updateField('from_name')} />
                </FormField>
              </div>

              <ErrorBanner message={saveError} />
              {savedMessage && <p className="text-sm text-[var(--status-good)]">{savedMessage}</p>}

              <div className="flex justify-end pt-1">
                <Button type="submit" disabled={saving}>
                  {saving ? t('Salvando…') : t('Salvar')}
                </Button>
              </div>
            </form>
          </Card>

          <TestEmailCard settings={settings} disabled={!settings?.id} onTested={setSettings} />
        </div>
      )}
    </div>
  )
}

function TestEmailCard({ settings, disabled, onTested }) {
  const { t } = useLanguage()
  const [toEmail, setToEmail] = useState('')
  const [testing, setTesting] = useState(false)
  const [testError, setTestError] = useState('')

  async function handleTest(event) {
    event.preventDefault()
    setTestError('')
    setTesting(true)
    try {
      const result = await emailSettingsApi.sendTestEmail(toEmail)
      onTested(result)
    } catch (err) {
      setTestError(err.message)
    } finally {
      setTesting(false)
    }
  }

  return (
    <Card title={t('Enviar e-mail de teste')}>
      <div className="space-y-4">
        <p className="text-xs text-[var(--text-muted)]">
          {t('Manda um e-mail de teste pros dados já salvos ao lado — funciona mesmo com "Ativo" ainda desligado.')}
        </p>

        <form onSubmit={handleTest} className="space-y-3">
          <FormField label={t('Enviar teste para')} required>
            <TextInput
              type="email"
              required
              disabled={disabled}
              placeholder="voce@exemplo.com"
              value={toEmail}
              onChange={(event) => setToEmail(event.target.value)}
            />
          </FormField>
          <ErrorBanner message={testError} />
          <Button type="submit" variant="secondary" className="w-full" disabled={disabled || testing}>
            {testing ? t('Enviando…') : t('Enviar teste')}
          </Button>
          {disabled && <p className="text-xs text-[var(--text-muted)]">{t('Salve a configuração antes de testar.')}</p>}
        </form>

        {settings?.last_test_at && (
          <div
            className={`rounded-lg border px-3 py-2.5 text-xs ${
              settings.last_test_ok
                ? 'border-[var(--status-good)]/30 bg-[var(--status-good)]/10 text-[var(--status-good)]'
                : 'border-[var(--status-critical)]/30 bg-[var(--status-critical)]/10 text-[var(--status-critical)]'
            }`}
          >
            <p className="font-medium">
              {settings.last_test_ok ? t('Último teste: sucesso') : t('Último teste: falhou')}
            </p>
            <p className="mt-0.5 text-[var(--text-muted)]">{new Date(settings.last_test_at).toLocaleString()}</p>
            {!settings.last_test_ok && settings.last_test_error && <p className="mt-1">{settings.last_test_error}</p>}
          </div>
        )}
      </div>
    </Card>
  )
}
