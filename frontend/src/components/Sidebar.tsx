import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Bus, Building2, Wrench, Shield,
  Bell, FileBarChart2, LogOut, FileText, Users, FileSpreadsheet
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useThemeStore } from '../stores/themeStore'
import { alertasApi } from '../api'
import { useQuery } from '@tanstack/react-query'

const navItems = [
  { to: '/',          icon: LayoutDashboard, label: 'Dashboard',  section: 'PRINCIPAL' },
  { to: '/buses',     icon: Bus,             label: 'Buses',       section: 'GESTIÓN' },
  { to: '/empresas',  icon: Building2,       label: 'Empresas',    section: 'GESTIÓN' },
  { to: '/itv',       icon: Wrench,          label: 'ITV',         section: 'GESTIÓN' },
  { to: '/seguros',   icon: Shield,          label: 'Seguros',     section: 'GESTIÓN' },
  { to: '/documentos',icon: FileText,        label: 'Documentos',  section: 'GESTIÓN' },
  { to: '/alertas',   icon: Bell,            label: 'Alertas',     section: 'CONTROL', badge: true },
  { to: '/importador',icon: FileSpreadsheet, label: 'Importar Excel', section: 'HERRAMIENTAS' },
  { to: '/reportes',  icon: FileBarChart2,   label: 'Reportes',    section: 'HERRAMIENTAS' },
  { to: '/usuarios',  icon: Users,           label: 'Usuarios',    section: 'SISTEMA' },
]

export default function Sidebar({
  open = true,
  onClose,
}: {
  open?: boolean
  onClose?: () => void
}) {
  const { usuario, logout } = useAuthStore()
  const theme = useThemeStore((s) => s.theme)
  const navigate = useNavigate()

  const { data: alertasData } = useQuery<{ data: { total: number } }>({
    queryKey: ['alertas-count'],
    queryFn: () => alertasApi.listar({ estado: 'PENDIENTE', prioridad: 'ALTA', page_size: 1 }),
    refetchInterval: 60000,
  })

  const criticalCount = alertasData?.data?.total ?? 0
  const logoSrc = theme === 'light'
    ? '/img/logo-claro-vmt.png'
    : '/img/logo-oscuro-vmt.png'

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const sections = [...new Set(navItems.map(i => i.section))]
  const initials = usuario?.nombre_completo
    ? usuario.nombre_completo.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
    : usuario?.username?.slice(0, 2).toUpperCase() ?? 'US'

  return (
    <aside className={`sidebar${open ? ' open' : ''}`} aria-hidden={!open}>
      <NavLink
        to="/"
        end
        className="sidebar-logo"
        onClick={() => {
          if (window.innerWidth <= 768) onClose?.()
        }}
      >
        <img
          src={logoSrc}
          alt="Viceministerio de Transporte"
          className="sidebar-logo-img"
        />
        <div className="logo-title">Sistema de Gestión de<br />Parque Automotor</div>
        <div className="logo-sub">Depto. Registro y Habilitación</div>
      </NavLink>

      <nav className="sidebar-nav">
        {sections.map(section => (
          <div key={section}>
            <div className="nav-section-label">{section}</div>
            {navItems.filter(i => i.section === section).map(({ to, icon: Icon, label, badge }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }: { isActive: boolean }) => `nav-item ${isActive ? 'active' : ''}`}
                onClick={() => {
                  if (window.innerWidth <= 768) onClose?.()
                }}
              >
                <Icon size={17} className="nav-icon" />
                <span>{label}</span>
                {badge && criticalCount > 0 && (
                  <span className="nav-badge">{criticalCount > 99 ? '99+' : criticalCount}</span>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="user-card">
          <div className="user-avatar">{initials}</div>
          <div className="user-info" style={{ flex: 1, minWidth: 0 }}>
            <div className="user-name" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {usuario?.nombre_completo || usuario?.username}
            </div>
            <div className="user-role">{usuario?.rol}</div>
          </div>
          <button
            onClick={handleLogout}
            className="btn-icon btn"
            title="Cerrar sesión"
            style={{ color: 'var(--text-muted)' }}
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  )
}
