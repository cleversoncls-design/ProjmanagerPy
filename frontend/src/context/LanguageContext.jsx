import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useAuth } from './AuthContext'
import * as usersApi from '../api/users'
import { getStoredLanguage, setStoredLanguage, translate } from '../i18n/translations'
import { getLabels } from '../utils/labels'

const LanguageContext = createContext(null)

/** Idioma da interface (pt-BR/es).
 *
 * Fonte de verdade quando autenticado é o cadastro do usuário
 * (`User.language`, trocado via `PATCH /users/me` — ver api/users.js), pra
 * seguir o usuário entre dispositivos/navegadores. O localStorage
 * (i18n/translations.js) é só o fallback pré-login (ex.: LoginPage) e evita
 * um "flash" em Português enquanto o /users/me da sessão ainda carrega. */
export function LanguageProvider({ children }) {
  const { user } = useAuth()
  const [language, setLanguageState] = useState(getStoredLanguage)

  // Assim que o usuário autenticado carrega (ou troca), o idioma salvo no
  // cadastro dele manda — sincroniza estado e localStorage (outra aba/
  // navegador pode ter gravado um idioma diferente localmente).
  useEffect(() => {
    if (user?.language && user.language !== language) {
      setLanguageState(user.language)
      setStoredLanguage(user.language)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.language])

  const setLanguage = useCallback(
    async (lang) => {
      setLanguageState(lang)
      setStoredLanguage(lang)
      if (user) {
        try {
          await usersApi.updateMyLanguage(lang)
        } catch {
          // Best-effort: a troca já vale localmente (localStorage) mesmo se
          // salvar no cadastro falhar agora (ex.: rede instável) — o
          // próximo carregamento volta a sincronizar a partir do backend.
        }
      }
    },
    [user],
  )

  const t = useCallback((text, vars) => translate(language, text, vars), [language])
  const labels = useMemo(() => getLabels(language), [language])

  const value = useMemo(() => ({ language, setLanguage, t, labels }), [language, setLanguage, t, labels])

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage() {
  const ctx = useContext(LanguageContext)
  if (!ctx) {
    throw new Error('useLanguage precisa ser usado dentro de <LanguageProvider>')
  }
  return ctx
}
