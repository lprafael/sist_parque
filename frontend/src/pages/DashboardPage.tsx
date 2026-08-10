import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { dashboardApi, alertasApi } from '../api'
import { Trash2 } from 'lucide-react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend, LineChart, Line
} from 'recharts'


function KpiCard({ value, label, icon, color, to, action }: {
  value: number | string
  label: string
  icon: string
  color: string
  to?: string
  action?: React.ReactNode
}) {
  const inner = (
    <>
      <div className={`kpi-icon ${color}`}>{icon}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
          <div>
            <div className="kpi-value">{value}</div>
            <div className="kpi-label">{label}</div>
          </div>
          {action}
        </div>
      </div>
    </>
  )

  if (to) {
    return (
      <Link
        to={to}
        className="kpi-card"
        style={{ position: 'relative', textDecoration: 'none', color: 'inherit', cursor: 'pointer' }}
      >
        {inner}
      </Link>
    )
  }

  return (
    <div className="kpi-card" style={{ position: 'relative' }}>
      {inner}
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)', padding: '10px 14px', fontSize: '0.82rem',
    }}>
      <p style={{ color: 'var(--text-muted)', marginBottom: 4 }}>{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.color }}>{p.name}: <strong>{p.value}</strong></p>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const qc = useQueryClient()

  const { data: kpisResp, isLoading: kLoading } = useQuery({
    queryKey: ['kpis'],
    queryFn: () => dashboardApi.kpis(),
    refetchInterval: 300000,
  })

  const limpiarAlertasMutation = useMutation({
    mutationFn: () => alertasApi.limpiarTodas(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kpis'] })
      qc.invalidateQueries({ queryKey: ['alertas'] })
    }
  })

  const handleLimpiarAlertas = () => {
    if (window.confirm('¿Está seguro de eliminar todas las alertas pendientes del sistema?')) {
      limpiarAlertasMutation.mutate()
    }
  }

  const { data: vencResp } = useQuery({
    queryKey: ['vencimientos', 30],
    queryFn: () => dashboardApi.vencimientosProximos(30),
  })

  const { data: empResp } = useQuery({
    queryKey: ['distribucion-empresas'],
    queryFn: () => dashboardApi.distribucionEmpresas(),
  })

  const { data: antResp } = useQuery({
    queryKey: ['distribucion-antiguedad'],
    queryFn: () => dashboardApi.distribucionAntiguedad(),
  })

  const { data: tipoServicioResp } = useQuery({
    queryKey: ['distribucion-tipo-servicio'],
    queryFn: () => dashboardApi.distribucionTipoServicio(),
  })

  const { data: marcasResp } = useQuery({
    queryKey: ['distribucion-marcas'],
    queryFn: () => dashboardApi.distribucionMarcas(),
  })

  const kpis = kpisResp?.data
  const vencimientos = vencResp?.data?.items ?? []
  const empresas = (empResp?.data ?? []).slice(0, 8)
  const antiguedadData = antResp?.data?.items ?? []
  const promedioEdad = antResp?.data?.promedio_edad ?? 0
  const tipoServicioData = tipoServicioResp?.data ?? []
  const marcasData = marcasResp?.data ?? []

  // Agrupar vencimientos por tipo para gráfico de área
  const vencByDia = vencimientos.reduce((acc: Record<string, any>, item: any) => {
    const key = item.fecha_vencimiento
    if (!acc[key]) acc[key] = { fecha: key, ITV: 0, SEGURO: 0 }
    if (item.tipo === 'ITV') acc[key].ITV++
    else acc[key].SEGURO++
    return acc
  }, {})
  const areaData = Object.values(vencByDia).sort((a: any, b: any) =>
    a.fecha.localeCompare(b.fecha)
  ).slice(0, 15)

  if (kLoading) return <div className="loading-spinner"><div className="spinner" /></div>

  return (
    <div>
      {/* KPIs */}
      <div className="kpi-grid">
        <KpiCard
          value={kpis?.total_buses ?? 0}
          label="Total Buses"
          icon="🚌"
          color="blue"
          to="/buses"
        />
        <KpiCard
          value={kpis?.buses_activos ?? 0}
          label="Buses Activos"
          icon="✅"
          color="green"
          to="/buses?estado_bus=ACTIVO"
        />
        <KpiCard
          value={kpis?.itv_vigente ?? 0}
          label="ITV Vigentes"
          icon="🔧"
          color="cyan"
          to="/buses?estado_itv=VIGENTE"
        />
        <KpiCard
          value={kpis?.itv_por_vencer ?? 0}
          label="ITV Por Vencer"
          icon="⚠️"
          color="amber"
          to="/buses?estado_itv=POR_VENCER"
        />
        <KpiCard
          value={kpis?.itv_vencido ?? 0}
          label="ITV Vencidas"
          icon="❌"
          color="red"
          to="/buses?estado_itv=VENCIDO"
        />
        <KpiCard
          value={kpis?.seguros_vigentes ?? 0}
          label="Seguros Vigentes"
          icon="🛡️"
          color="green"
          to="/seguros?estado=VIGENTE"
        />
        <KpiCard
          value={kpis?.alertas_pendientes ?? 0}
          label="Alertas Pendientes"
          icon="🔔"
          color="amber"
          to="/alertas?estado=PENDIENTE"
          action={
            <button
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                handleLimpiarAlertas()
              }}
              disabled={limpiarAlertasMutation.isPending}
              className="btn btn-secondary btn-sm"
              style={{
                padding: '4px 8px',
                fontSize: '0.72rem',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                marginTop: '2px',
                background: 'rgba(239,68,68,0.15)',
                color: '#f87171',
                border: '1px solid rgba(239,68,68,0.3)',
              }}
              title="Borrar todas las alertas pendientes"
            >
              <Trash2 size={12} /> Borrar
            </button>
          }
        />
      </div>

      {/* Gráfico de Antigüedad de Buses (Líneas) */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header dashboard-card-header">
          <div>
            <span className="card-title">Antigüedad del Parque Automotor</span>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Distribución por años de antigüedad (Eje X: Edad en años / Eje Y: Cantidad de buses)
            </div>
          </div>
          <div style={{ background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)', padding: '6px 14px', borderRadius: 'var(--radius-md)', textAlign: 'right' }}>
            <div style={{ fontSize: '0.7rem', color: '#a5b4fc', textTransform: 'uppercase', fontWeight: 600 }}>Edad Promedio</div>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#818cf8' }}>
              {promedioEdad} años
            </div>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={antiguedadData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
            <XAxis 
              dataKey="antiguedad" 
              tick={{ fill: '#8b93c4', fontSize: 11 }}
              tickFormatter={val => `${val}a`}
            />
            <YAxis tick={{ fill: '#8b93c4', fontSize: 11 }} />
            <Tooltip content={<CustomTooltip />} />
            <Line 
              type="monotone" 
              dataKey="cantidad" 
              name="Buses"
              stroke="#818cf8" 
              strokeWidth={3} 
              dot={{ r: 4, fill: '#6366f1', strokeWidth: 2, stroke: '#ffffff' }}
              activeDot={{ r: 7, fill: '#4f46e5' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Charts row */}
      <div className="dashboard-charts-row">
        {/* Vencimientos próximos */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Vencimientos Próximos (30 días)</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {vencimientos.length} registros
            </span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={areaData}>
              <defs>
                <linearGradient id="gradITV" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#3f51b5" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#3f51b5" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradSeg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#00bcd4" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#00bcd4" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="fecha" tick={{ fill: '#555e8a', fontSize: 11 }}
                tickFormatter={d => d.slice(5)} />
              <YAxis tick={{ fill: '#555e8a', fontSize: 11 }} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="ITV"    stroke="#3f51b5" fill="url(#gradITV)" strokeWidth={2} />
              <Area type="monotone" dataKey="SEGURO" stroke="#00bcd4" fill="url(#gradSeg)" strokeWidth={2} />
              <Legend wrapperStyle={{ fontSize: '0.8rem', color: '#8b93c4' }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Estado ITV - pie */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Estado ITV del Parque</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={[
                  { name: 'Vigente',    value: kpis?.itv_vigente ?? 0 },
                  { name: 'Por Vencer', value: kpis?.itv_por_vencer ?? 0 },
                  { name: 'Vencida',    value: kpis?.itv_vencido ?? 0 },
                ]}
                cx="50%" cy="50%"
                innerRadius={55} outerRadius={85}
                paddingAngle={3}
                dataKey="value"
              >
                {['#00c853', '#ffab00', '#f44336'].map((color, i) => (
                  <Cell key={i} fill={color} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: '0.78rem', color: '#8b93c4' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Tipo de Servicio - pie */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Tipo de Servicio</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={tipoServicioData}
                cx="50%" cy="50%"
                innerRadius={55} outerRadius={85}
                paddingAngle={3}
                dataKey="value"
              >
                {tipoServicioData.map((_: any, index: number) => {
                  const colors = ['#8b5cf6', '#ec4899', '#3b82f6', '#10b981', '#f59e0b']
                  return <Cell key={index} fill={colors[index % colors.length]} />
                })}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: '0.78rem', color: '#8b93c4' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Empresas + Marcas + alertas críticas */}
      <div className="dashboard-bottom-row">
        
        {/* Distribución por Marcas */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Top Marcas de Buses</span>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={marcasData} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <XAxis type="number" hide />
              <YAxis dataKey="name" type="category" tick={{ fill: '#8b93c4', fontSize: 11 }} width={100} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="value" fill="#8b5cf6" radius={[0, 4, 4, 0]}>
                {marcasData.map((_: any, index: number) => (
                  <Cell key={index} fill={['#8b5cf6', '#3b82f6', '#ec4899', '#10b981', '#f59e0b', '#6366f1', '#14b8a6', '#f43f5e', '#84cc16', '#06b6d4'][index % 10]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Distribución por empresas */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Buses por Empresa</span>
          </div>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={empresas} layout="vertical">
              <XAxis type="number" tick={{ fill: '#555e8a', fontSize: 11 }} />
              <YAxis type="category" dataKey="empresa" width={140}
                tick={{ fill: '#8b93c4', fontSize: 10 }}
                tickFormatter={v => v.length > 20 ? v.slice(0, 18) + '…' : v} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="total_buses" fill="#3f51b5" radius={[0, 4, 4, 0]} label={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Seguros */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Estado de Seguros</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '8px' }}>
            {[
              { label: 'Vigentes',    value: kpis?.seguros_vigentes ?? 0,   color: '#00c853', icon: '✅' },
              { label: 'Por Vencer',  value: kpis?.seguros_por_vencer ?? 0, color: '#ffab00', icon: '⚠️' },
              { label: 'Vencidos',    value: kpis?.seguros_vencidos ?? 0,   color: '#f44336', icon: '❌' },
            ].map(({ label, value, color, icon }) => {
              const total = (kpis?.seguros_vigentes ?? 0) + (kpis?.seguros_por_vencer ?? 0) + (kpis?.seguros_vencidos ?? 0)
              const pct = total ? Math.round((value / total) * 100) : 0
              return (
                <div key={label}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{icon} {label}</span>
                    <span style={{ fontSize: '0.82rem', fontWeight: 700, color }}>{value}</span>
                  </div>
                  <div style={{ height: '6px', background: 'var(--bg-input)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: '3px',
                      transition: 'width 1s ease' }} />
                  </div>
                </div>
              )
            })}
          </div>

          <div style={{ marginTop: '24px' }}>
            <div className="card-title" style={{ marginBottom: '12px' }}>Empresas Registradas</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div className="kpi-icon blue" style={{ width: '44px', height: '44px' }}>🏢</div>
              <div>
                <div className="kpi-value" style={{ fontSize: '1.6rem' }}>{kpis?.total_empresas ?? 0}</div>
                <div className="kpi-label">Empresas activas (EOT)</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
