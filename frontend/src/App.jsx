import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { LanguageProvider } from './context/LanguageContext'
import ProtectedRoute from './components/ProtectedRoute'
import ErrorBoundary from './components/ErrorBoundary'
import Layout from './components/Layout'
import HomeRoute from './components/HomeRoute'
import LoginPage from './pages/LoginPage'
import ProjectsPage from './pages/ProjectsPage'
import ProjectDetailPage from './pages/ProjectDetailPage'
import ClientsPage from './pages/ClientsPage'
import UsersPage from './pages/UsersPage'
import EmailSettingsPage from './pages/EmailSettingsPage'
import CalendarsPage from './pages/CalendarsPage'
import TaskGroupsPage from './pages/TaskGroupsPage'
import TaskGroupDetailPage from './pages/TaskGroupDetailPage'
import SchedulesPage from './pages/SchedulesPage'
import TimesheetsPage from './pages/TimesheetsPage'
import TimesheetApprovalsPage from './pages/TimesheetApprovalsPage'
import ServiceOrdersPage from './pages/ServiceOrdersPage'
import ReportsIndexPage from './pages/ReportsIndexPage'
import HoursBreakdownReportPage from './pages/HoursBreakdownReportPage'
import StatusReportsPage from './pages/StatusReportsPage'
import NoAccessPage from './pages/NoAccessPage'
import { ADMIN_LIKE_ROLES, INTERNAL_ROLES, MANAGEMENT_ROLES, PROJECTS_VISIBLE_ROLES, STATUS_REPORT_VISIBLE_ROLES } from './utils/labels'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <LanguageProvider>
          <ErrorBoundary>
            <Routes>
              <Route path="/login" element={<LoginPage />} />

              <Route element={<ProtectedRoute />}>
                <Route element={<Layout />}>
                  <Route path="/" element={<HomeRoute />} />
                  {/* Home do Usuário-chave (reorganização de menus: perfil
                      ficou sem nenhum item de menu por enquanto, ver
                      ROLE_HOME_PATH em utils/labels.js) — sem `roles`, de
                      propósito: qualquer perfil logado pode abrir, mas só
                      quem não tem mais nenhuma rota cai aqui. */}
                  <Route path="/no-access" element={<NoAccessPage />} />

                  <Route element={<ProtectedRoute roles={PROJECTS_VISIBLE_ROLES} />}>
                    <Route path="/projects" element={<ProjectsPage />} />
                    <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
                  </Route>

                  <Route element={<ProtectedRoute roles={INTERNAL_ROLES} />}>
                    <Route path="/timesheets" element={<TimesheetsPage />} />
                    <Route path="/service-orders" element={<ServiceOrdersPage />} />
                  </Route>

                  <Route element={<ProtectedRoute roles={ADMIN_LIKE_ROLES} />}>
                    <Route path="/clients" element={<ClientsPage />} />
                    <Route path="/users" element={<UsersPage />} />
                    {/* Configurador de SMTP (pedido do usuário: "processo de
                        envio de emails") — mesmo critério de acesso de
                        Usuários, dado sensível. */}
                    <Route path="/email-settings" element={<EmailSettingsPage />} />
                  </Route>

                  {/* "Agenda de consultores" e "Relatórios" saíram de
                      INTERNAL_ROLES/ADMIN_LIKE_ROLES pra MANAGEMENT_ROLES
                      na reorganização de menus (pedido do usuário): Consultor
                      perdeu a Agenda, Gerente de Projetos ganhou Relatórios
                      — ver Sidebar.jsx e app/routers/reports.py. */}
                  <Route element={<ProtectedRoute roles={MANAGEMENT_ROLES} />}>
                    <Route path="/schedules" element={<SchedulesPage />} />
                    <Route path="/timesheet-approvals" element={<TimesheetApprovalsPage />} />
                    <Route path="/calendars" element={<CalendarsPage />} />
                    <Route path="/task-groups" element={<TaskGroupsPage />} />
                    <Route path="/task-groups/:groupId" element={<TaskGroupDetailPage />} />
                    <Route path="/reports/hours-breakdown" element={<HoursBreakdownReportPage />} />
                  </Route>

                  {/* Status Report (pedido do usuário: "pode implementar os
                      2 modelos e colocar na opção de relatorios") — PM do
                      cliente ganhou acesso ao índice de Relatórios e ao
                      Status Report pela primeira vez (ver
                      STATUS_REPORT_VISIBLE_ROLES em utils/labels.js), mas
                      continua sem "Horas por tipo" acima, que fica só com
                      MANAGEMENT_ROLES. */}
                  <Route element={<ProtectedRoute roles={STATUS_REPORT_VISIBLE_ROLES} />}>
                    <Route path="/reports" element={<ReportsIndexPage />} />
                    <Route path="/reports/status-report" element={<StatusReportsPage />} />
                  </Route>
                </Route>
              </Route>

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </ErrorBoundary>
        </LanguageProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
