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
import CalendarsPage from './pages/CalendarsPage'
import SchedulesPage from './pages/SchedulesPage'
import TimesheetsPage from './pages/TimesheetsPage'
import TimesheetApprovalsPage from './pages/TimesheetApprovalsPage'
import ServiceOrdersPage from './pages/ServiceOrdersPage'
import ReportsIndexPage from './pages/ReportsIndexPage'
import HoursBreakdownReportPage from './pages/HoursBreakdownReportPage'
import { ADMIN_LIKE_ROLES, INTERNAL_ROLES, MANAGEMENT_ROLES, PROJECTS_VISIBLE_ROLES } from './utils/labels'

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

                  <Route element={<ProtectedRoute roles={PROJECTS_VISIBLE_ROLES} />}>
                    <Route path="/projects" element={<ProjectsPage />} />
                    <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
                  </Route>

                  <Route element={<ProtectedRoute roles={INTERNAL_ROLES} />}>
                    <Route path="/schedules" element={<SchedulesPage />} />
                    <Route path="/timesheets" element={<TimesheetsPage />} />
                    <Route path="/service-orders" element={<ServiceOrdersPage />} />
                  </Route>

                  <Route element={<ProtectedRoute roles={ADMIN_LIKE_ROLES} />}>
                    <Route path="/clients" element={<ClientsPage />} />
                    <Route path="/users" element={<UsersPage />} />
                    <Route path="/reports" element={<ReportsIndexPage />} />
                    <Route path="/reports/hours-breakdown" element={<HoursBreakdownReportPage />} />
                  </Route>

                  <Route element={<ProtectedRoute roles={MANAGEMENT_ROLES} />}>
                    <Route path="/timesheet-approvals" element={<TimesheetApprovalsPage />} />
                    <Route path="/calendars" element={<CalendarsPage />} />
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
