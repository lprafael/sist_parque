import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from './stores/authStore'
import Layout from './components/Layout'
import LoginPage      from './pages/LoginPage'
import DashboardPage  from './pages/DashboardPage'
import BusesPage      from './pages/BusesPage'
import EmpresasPage   from './pages/EmpresasPage'
import ItvPage        from './pages/ItvPage'
import SegurosPage    from './pages/SegurosPage'
import DocumentosPage from './pages/DocumentosPage'
import AlertasPage    from './pages/AlertasPage'
import UsuariosPage   from './pages/UsuariosPage'
import ImportadorPage from './pages/ImportadorPage'
import ReportesPage   from './pages/ReportesPage'

const qc = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 2 * 60 * 1000,
    },
  },
})

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore(s => s.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function AppRoutes() {
  const isAuthenticated = useAuthStore(s => s.isAuthenticated)

  return (
    <Routes>
      <Route path="/login" element={
        isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />
      } />

      <Route path="/" element={
        <ProtectedRoute>
          <Layout>
            <DashboardPage />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/buses" element={
        <ProtectedRoute>
          <Layout>
            <BusesPage />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/empresas" element={
        <ProtectedRoute>
          <Layout>
            <EmpresasPage />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/itv" element={
        <ProtectedRoute>
          <Layout>
            <ItvPage />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/seguros" element={
        <ProtectedRoute>
          <Layout>
            <SegurosPage />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/documentos" element={
        <ProtectedRoute>
          <Layout>
            <DocumentosPage />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/alertas" element={
        <ProtectedRoute>
          <Layout>
            <AlertasPage />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/usuarios" element={
        <ProtectedRoute>
          <Layout>
            <UsuariosPage />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/importador" element={
        <ProtectedRoute>
          <Layout>
            <ImportadorPage />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/reportes" element={
        <ProtectedRoute>
          <Layout>
            <ReportesPage />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
