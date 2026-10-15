import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import { useLanguage } from '../context/LanguageContext'

/** Home do perfil Usuário-chave (CLIENT_USER) depois da reorganização de
 * menus (pedido do usuário: "hoje, ele não terá nenhum acesso ainda") — o
 * perfil continua podendo logar, mas nenhum item do menu é visível pra ele
 * (ver DASHBOARD_ROLES/PROJECTS_VISIBLE_ROLES em utils/labels.js) e todas
 * as rotas protegidas por `roles` o barram. Sem esta rota própria (sem
 * `roles` em ProtectedRoute), ROLE_HOME_PATH.CLIENT_USER cairia num
 * redirecionamento em loop (ver HomeRoute.jsx). */
export default function NoAccessPage() {
  const { t } = useLanguage()
  return (
    <div>
      <PageHeader title={t('Sem acesso')} />
      <Card>
        <p className="text-sm text-[var(--text-secondary)]">
          {t('Seu perfil ainda não tem nenhuma funcionalidade liberada neste sistema. Fale com o administrador se isso não for esperado.')}
        </p>
      </Card>
    </div>
  )
}
