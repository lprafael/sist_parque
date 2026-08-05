import type { ReactNode } from 'react'
import Sidebar from './Sidebar'
import ThemeToggle from './ThemeToggle'
import FeedbackWidget from './FeedbackWidget'
import { useLocation } from 'react-router-dom'

const pageTitles: Record<string, string> = {
  '/':         'Dashboard',
  '/buses':    'Gestión de Buses',
  '/empresas': 'Empresas Operadoras',
  '/itv':      'Inspección Técnica Vehicular',
  '/seguros':  'Seguros',
  '/alertas':  'Alertas y Notificaciones',
  '/reportes': 'Reportes',
}

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const title = pageTitles[location.pathname] ?? 'Parque Automotor'

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-content">
        <header className="topbar">
          <h1 className="topbar-title">{title}</h1>
          <div className="topbar-actions">
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {new Date().toLocaleDateString('es-PY', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
            </span>
            <ThemeToggle />
          </div>
        </header>
        <main className="page-content">{children}</main>
      </div>
      <FeedbackWidget />
    </div>
  )
}
