import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import ToastContainer from './components/ui/ToastContainer'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import ProjectPage from './pages/ProjectPage'
import ProjectOverviewPage from './pages/ProjectOverviewPage'
import DailyTaskPage from './pages/DailyTaskPage'
import TemplatesPage from './pages/TemplatesPage'
import CalendarPage from './pages/CalendarPage'
import SettingsPage from './pages/SettingsPage'
import ArchivedProjectsPage from './pages/ArchivedProjectsPage'
import Layout from './components/ui/Layout'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user)
  const loading = useAuthStore((s) => s.loading)
  if (loading) return <div className="flex items-center justify-center h-screen text-gray-400">載入中…</div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  const fetchMe = useAuthStore((s) => s.fetchMe)

  useEffect(() => {
    if (localStorage.getItem('access_token')) fetchMe()
  }, [])

  return (
    <>
    <ToastContainer />
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <Layout>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/overview" element={<ProjectOverviewPage />} />
                <Route path="/projects/:projectId/*" element={<ProjectPage />} />
                <Route path="/daily" element={<DailyTaskPage />} />
                <Route path="/templates" element={<TemplatesPage />} />
                <Route path="/calendar" element={<CalendarPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/archived" element={<ArchivedProjectsPage />} />
              </Routes>
            </Layout>
          </RequireAuth>
        }
      />
    </Routes>
    </>
  )
}
