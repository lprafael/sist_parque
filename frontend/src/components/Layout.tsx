import { useEffect, useState, type ReactNode } from 'react'
import { Menu, X } from 'lucide-react'
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

const SIDEBAR_KEY = 'parque-sidebar-open'

function readInitialSidebarOpen(): boolean {
  try {
    const saved = localStorage.getItem(SIDEBAR_KEY)
    if (saved !== null) return saved === 'true'
  } catch {
    /* ignore */
  }
  return typeof window !== 'undefined' ? window.innerWidth > 768 : true
}

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const title = pageTitles[location.pathname] ?? 'Parque Automotor'
  const [sidebarOpen, setSidebarOpen] = useState(readInitialSidebarOpen)

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_KEY, String(sidebarOpen))
    } catch {
      /* ignore */
    }
  }, [sidebarOpen])

  // En móvil, cerrar el menú al cambiar de ruta
  useEffect(() => {
    if (window.innerWidth <= 768) setSidebarOpen(false)
  }, [location.pathname])

  const toggleSidebar = () => setSidebarOpen((v) => !v)

  return (
    <div className={`app-layout${sidebarOpen ? ' sidebar-open' : ''}`}>
      {sidebarOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Cerrar menú"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="main-content">
        <header className="topbar">
          <button
            type="button"
            className="menu-toggle"
            onClick={toggleSidebar}
            aria-label={sidebarOpen ? 'Ocultar menú' : 'Mostrar menú'}
            aria-expanded={sidebarOpen}
            title={sidebarOpen ? 'Ocultar menú' : 'Mostrar menú'}
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <h1 className="topbar-title">{title}</h1>
          <div className="topbar-actions">
            <span className="topbar-date" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
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
