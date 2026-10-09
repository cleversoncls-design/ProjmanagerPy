import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import DashboardPage from '../pages/DashboardPage'
import SchedulesPage from '../pages/SchedulesPage'
import { DASHBOARD_ROLES, ROLE_HOME_PATH } from '../utils/labels'

/** "/" não pode ter `roles` num <ProtectedRoute> comum — quem for barrado
 * volta pra "/" (ver ProtectedRoute.jsx), então restringir a própria "/"
 * geraria um redirecionamento em loop. Em vez disso, "/" sempre existe,
 * mas só renderiza o Dashboard pra quem está em DASHBOARD_ROLES (pedido do
 * usuário: Gerente de Projetos e Consultor perderam esse item) — os
 * demais perfis são mandados direto pra primeira tela que eles têm
 * (ROLE_HOME_PATH), sem nunca ver o Dashboard piscar na tela. */
export default function HomeRoute() {
  const { user } = useAuth()
  // ProtectedRoute (que envolve esta rota) já garante `user` carregado e
  // autenticado antes de chegar aqui.
  if (!user) return null
  if (DASHBOARD_ROLES.includes(user.role)) return <DashboardPage />
  // Consultor: a página inicial é a própria agenda (pedido do usuário).
  if (user.role === 'CONSULTANT') return <SchedulesPage />
  return <Navigate to={ROLE_HOME_PATH[user.role] || '/projects'} replace />
}
