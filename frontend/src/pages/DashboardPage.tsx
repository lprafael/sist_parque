import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { dashboardApi, alertasApi, empresasApi } from '../api'
import { Trash2, Building2, Info, BookOpen, ChevronDown } from 'lucide-react'
import { useRol } from '../hooks/useRol'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend, LineChart, Line
} from 'recharts'

/** Diccionario de indicadores del dashboard (contexto de negocio). */
const KPI_DICCIONARIO: { termino: string; grupo: string; definicion: string }[] = [
  {
    grupo: 'Buses',
    termino: 'Total Buses',
    definicion:
      'Histórico completo del parque: incluye activos, inactivos y bajas. No representa el parque operativo del día.',
  },
  {
    grupo: 'Buses',
    termino: 'Buses Activos',
    definicion:
      'Vehículos con estado ACTIVO. Es el parque operativo de referencia para ITV, seguros y desglose por tipo de servicio.',
  },
  {
    grupo: 'Buses',
    termino: 'Parque (tipo / rampa)',
    definicion:
      'Desglose solo de buses ACTIVOS: convencional, diferenciado, eléctrico y con rampa de accesibilidad.',
  },
  {
    grupo: 'ITV',
    termino: 'ITV Vigentes',
    definicion:
      'Inspecciones con fecha de vencimiento ≥ hoy (equivalente a APROBADA en planilla). Incluye las que están por vencer en ≤30 días.',
  },
  {
    grupo: 'ITV',
    termino: 'ITV Por Vencer',
    definicion:
      'Subconjunto de las vigentes: ITV que vencen en los próximos 30 días. No se suma aparte al total de vigentes.',
  },
  {
    grupo: 'ITV',
    termino: 'ITV Vencidas',
    definicion:
      'Buses activos con ITV vencida o sin ITV vigente. Explica la diferencia con Buses Activos: Activos ≈ Vigentes + Vencidas.',
  },
  {
    grupo: 'Seguros',
    termino: 'Seguro Pasajeros / Terceros Vigentes',
    definicion:
      'Pólizas vigentes (fecha ≥ hoy) de buses ACTIVOS. “Por vencer” es un subconjunto de las vigentes (≤30 días).',
  },
  {
    grupo: 'Seguros',
    termino: 'Seguro Pasajeros / Terceros Vencidos',
    definicion:
      'Pólizas con fecha de vencimiento ya pasada, asociadas a buses ACTIVOS.',
  },
  {
    grupo: 'Alertas',
    termino: 'Alertas Pendientes',
    definicion:
      'Alertas del sistema aún no atendidas (vencimientos, documentación, etc.).',
  },
]

function KpiInfo({ text }: { text: string }) {
  return (
    <span
      className="kpi-info"
      title={text}
      aria-label={text}
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
      }}
    >
      <Info size={13} />
    </span>
  )
}

function KpiCard({ value, label, icon, color, to, action, hint, definition }: {
  value: number | string
  label: string
  icon: string
  color: string
  to?: string
  action?: React.ReactNode
  hint?: string
  definition?: string
}) {
  const inner = (
    <>
      <div className={`kpi-icon ${color}`}>{icon}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
          <div>
            <div className="kpi-value">{value}</div>
            <div className="kpi-label">
              {label}
              {definition ? <KpiInfo text={definition} /> : null}
            </div>
            {hint ? <div className="kpi-hint">{hint}</div> : null}
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

function ParqueSplitCard({
  items,
  definition,
}: {
  items: { value: number; label: string; to?: string }[]
  definition?: string
}) {
  return (
    <div className="kpi-card kpi-split-card">
      {definition ? (
        <div className="kpi-split-info">
          <KpiInfo text={definition} />
        </div>
      ) : null}
      {items.map((item) => {
        const inner = (
          <>
            <div className="kpi-split-value">{item.value}</div>
            <div className="kpi-split-label">{item.label}</div>
          </>
        )
        if (item.to) {
          return (
            <Link key={item.label} to={item.to} className="kpi-split-cell">
              {inner}
            </Link>
          )
        }
        return (
          <div key={item.label} className="kpi-split-cell">
            {inner}
          </div>
        )
      })}
    </div>
  )
}

function KpiSection({
  title,
  note,
  variant,
  children,
}: {
  title: string
  note?: string
  variant: 'buses' | 'itv' | 'seguros' | 'alertas'
  children: React.ReactNode
}) {
  return (
    <section className="kpi-section">
      <div className="kpi-section-header">
        <h2 className="kpi-section-title">{title}</h2>
        {note ? <p className="kpi-section-note">{note}</p> : null}
      </div>
      <div className={`kpi-grid kpi-grid-${variant}`}>
        {children}
      </div>
    </section>
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
  const { puedeEditar } = useRol()
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [diccionarioAbierto, setDiccionarioAbierto] = useState(false)
  const idEot = searchParams.get('empresa') || ''

  const dashParams = useMemo(
    () => (idEot ? { id_eot: idEot } : undefined),
    [idEot],
  )

  const busesQs = (extra = '') => {
    const parts = [extra, idEot ? `empresa=${encodeURIComponent(idEot)}` : '']
      .filter(Boolean)
      .join('&')
    return parts ? `/buses?${parts}` : '/buses'
  }

  const { data: empresasListaResp } = useQuery({
    queryKey: ['empresas-filtro-dashboard'],
    queryFn: () =>
      empresasApi.listar({
        page: 1,
        page_size: 200,
        solo_activas: true,
        solo_permisionarias: true,
      }),
  })
  const empresasLista = empresasListaResp?.data?.items ?? []

  const handleEmpresaChange = (value: string) => {
    const next = new URLSearchParams(searchParams)
    if (value) next.set('empresa', value)
    else next.delete('empresa')
    setSearchParams(next, { replace: true })
  }

  const { data: kpisResp, isLoading: kLoading } = useQuery({
    queryKey: ['kpis', idEot],
    queryFn: () => dashboardApi.kpis(dashParams),
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
    queryKey: ['vencimientos', 30, idEot],
    queryFn: () => dashboardApi.vencimientosProximos(30, dashParams),
  })

  const { data: empResp } = useQuery({
    queryKey: ['distribucion-empresas', idEot],
    queryFn: () => dashboardApi.distribucionEmpresas(dashParams),
  })

  const { data: antResp } = useQuery({
    queryKey: ['distribucion-antiguedad', idEot],
    queryFn: () => dashboardApi.distribucionAntiguedad(dashParams),
  })

  const { data: tipoServicioResp } = useQuery({
    queryKey: ['distribucion-tipo-servicio', idEot],
    queryFn: () => dashboardApi.distribucionTipoServicio(dashParams),
  })

  const { data: marcasResp } = useQuery({
    queryKey: ['distribucion-marcas', idEot],
    queryFn: () => dashboardApi.distribucionMarcas(dashParams),
  })

  const kpis = kpisResp?.data
  const vencimientos = vencResp?.data?.items ?? []
  const empresas = (empResp?.data ?? []).slice(0, 8)
  const antiguedadData = antResp?.data?.items ?? []
  const promedioEdad = antResp?.data?.promedio_edad ?? 0
  const tipoServicioData = tipoServicioResp?.data ?? []
  const marcasData = marcasResp?.data ?? []

  const empresaSeleccionada = empresasLista.find(
    (e: any) => e.id_eot_vmt_hex === idEot,
  )

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
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px',
          marginBottom: '16px',
        }}
      >
        <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          {empresaSeleccionada
            ? `Mostrando indicadores de ${empresaSeleccionada.eot_nombre}`
            : 'Mostrando indicadores de todas las empresas EOT'}
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setDiccionarioAbierto((v) => !v)}
            aria-expanded={diccionarioAbierto}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <BookOpen size={14} />
            Diccionario
            <ChevronDown
              size={14}
              style={{
                transform: diccionarioAbierto ? 'rotate(180deg)' : undefined,
                transition: 'transform 0.2s ease',
              }}
            />
          </button>
          <Building2 size={18} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
          <select
            className="form-control"
            style={{ minWidth: '240px', maxWidth: '360px' }}
            value={idEot}
            onChange={(e) => handleEmpresaChange(e.target.value)}
            aria-label="Filtrar por empresa EOT"
          >
            <option value="">Todas las empresas</option>
            {empresasLista.map((e: any) => (
              <option key={e.eot_id ?? e.id_eot_vmt_hex} value={e.id_eot_vmt_hex}>
                {e.eot_nombre}
              </option>
            ))}
          </select>
        </div>
      </div>

      {diccionarioAbierto ? (
        <div className="kpi-diccionario card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <span className="card-title">Diccionario de indicadores</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Cómo leer los valores del dashboard
            </span>
          </div>
          <div className="kpi-diccionario-grid">
            {KPI_DICCIONARIO.map((item) => (
              <div key={item.termino} className="kpi-diccionario-item">
                <div className="kpi-diccionario-grupo">{item.grupo}</div>
                <div className="kpi-diccionario-termino">{item.termino}</div>
                <p className="kpi-diccionario-def">{item.definicion}</p>
              </div>
            ))}
          </div>
          <div className="kpi-diccionario-relacion">
            <strong>Relación clave:</strong>{' '}
            Buses Activos ({kpis?.buses_activos ?? 0}) ≈ ITV Vigentes ({kpis?.itv_vigente ?? 0})
            + ITV Vencidas ({kpis?.itv_vencido ?? 0}).
            La diferencia entre activos e ITV vigentes son buses activos sin ITV al día
            {(kpis?.itv_sin_vigente ?? 0) > 0
              ? ` (incluye ${kpis.itv_sin_vigente} sin registro de ITV vigente)`
              : ''}
            .
          </div>
        </div>
      ) : null}

      {/* KPIs agrupados por tema */}
      <KpiSection
        title="Buses"
        note="Total = histórico · Activos = parque operativo · Desglose solo sobre activos"
        variant="buses"
      >
        <KpiCard
          value={kpis?.total_buses ?? 0}
          label="Total Buses"
          icon="🚌"
          color="blue"
          to={busesQs()}
          definition={KPI_DICCIONARIO[0].definicion}
          hint="Histórico (incluye bajas)"
        />
        <KpiCard
          value={kpis?.buses_activos ?? 0}
          label="Buses Activos"
          icon="✅"
          color="green"
          to={busesQs('estado_bus=ACTIVO')}
          definition={KPI_DICCIONARIO[1].definicion}
          hint="Parque operativo"
        />
        <ParqueSplitCard
          definition={KPI_DICCIONARIO[2].definicion}
          items={[
            {
              value: kpis?.buses_convencional ?? 0,
              label: 'Convencional',
              to: busesQs(
                kpis?.id_tipo_convencional
                  ? `estado_bus=ACTIVO&id_tipo_servicio=${kpis.id_tipo_convencional}`
                  : 'estado_bus=ACTIVO',
              ),
            },
            {
              value: kpis?.buses_diferenciado ?? 0,
              label: 'Diferenciado',
              to: busesQs(
                kpis?.id_tipo_diferenciado
                  ? `estado_bus=ACTIVO&id_tipo_servicio=${kpis.id_tipo_diferenciado}`
                  : 'estado_bus=ACTIVO',
              ),
            },
            {
              value: kpis?.buses_electrico ?? 0,
              label: 'Eléctrico',
              to: busesQs(
                kpis?.id_tipo_electrico
                  ? `estado_bus=ACTIVO&id_tipo_servicio=${kpis.id_tipo_electrico}`
                  : 'estado_bus=ACTIVO',
              ),
            },
            {
              value: kpis?.buses_con_rampa ?? 0,
              label: 'Con rampa',
              to: busesQs('estado_bus=ACTIVO&tiene_rampa=true'),
            },
          ]}
        />
      </KpiSection>

      <KpiSection
        title="ITV"
        note={`Activos (${kpis?.buses_activos ?? 0}) ≈ Vigentes (${kpis?.itv_vigente ?? 0}) + Vencidas (${kpis?.itv_vencido ?? 0}). “Por vencer” ya está incluido en vigentes.`}
        variant="itv"
      >
        <KpiCard
          value={kpis?.itv_vigente ?? 0}
          label="ITV Vigentes"
          icon="🔧"
          color="cyan"
          to={busesQs('estado_itv=APROBADO')}
          definition={KPI_DICCIONARIO[3].definicion}
          hint="Aprobadas (incluye por vencer)"
        />
        <KpiCard
          value={kpis?.itv_por_vencer ?? 0}
          label="ITV Por Vencer"
          icon="⚠️"
          color="amber"
          to={busesQs('estado_itv=POR_VENCER')}
          definition={KPI_DICCIONARIO[4].definicion}
          hint="Subconjunto de vigentes (≤30 días)"
        />
        <KpiCard
          value={kpis?.itv_vencido ?? 0}
          label="ITV Vencidas"
          icon="❌"
          color="red"
          to={busesQs('estado_itv=VENCIDO')}
          definition={KPI_DICCIONARIO[5].definicion}
          hint={
            (kpis?.itv_sin_vigente ?? 0) > 0
              ? `${kpis.itv_sin_vigente} sin ITV vigente`
              : undefined
          }
        />
      </KpiSection>

      <KpiSection
        title="Seguros"
        note="Solo pólizas de buses activos. Vigente = fecha ≥ hoy; vencido = fecha ya pasada."
        variant="seguros"
      >
        <KpiCard
          value={kpis?.seguros_pasajeros_vigentes ?? 0}
          label="Seguro Pasajeros Vigentes"
          icon="🛡️"
          color="green"
          to="/seguros?estado=VIGENTE"
          definition={KPI_DICCIONARIO[6].definicion}
        />
        <KpiCard
          value={kpis?.seguros_pasajeros_vencidos ?? 0}
          label="Seguro Pasajeros Vencidos"
          icon="❌"
          color="red"
          to="/seguros?estado=VENCIDO"
          definition={KPI_DICCIONARIO[7].definicion}
        />
        <KpiCard
          value={kpis?.seguros_terceros_vigentes ?? 0}
          label="Seguro Terceros Vigentes"
          icon="🛡️"
          color="cyan"
          to="/seguros?estado=VIGENTE"
          definition={KPI_DICCIONARIO[6].definicion}
        />
        <KpiCard
          value={kpis?.seguros_terceros_vencidos ?? 0}
          label="Seguro Terceros Vencidos"
          icon="❌"
          color="red"
          to="/seguros?estado=VENCIDO"
          definition={KPI_DICCIONARIO[7].definicion}
        />
      </KpiSection>

      <KpiSection title="Alertas" variant="alertas">
        <KpiCard
          value={kpis?.alertas_pendientes ?? 0}
          label="Alertas Pendientes"
          icon="🔔"
          color="amber"
          to="/alertas?estado=PENDIENTE"
          definition={KPI_DICCIONARIO[8].definicion}
          action={puedeEditar ? (
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
          ) : undefined}
        />
      </KpiSection>

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
                  // itv_vigente = APROBADA (incluye por vencer); el gráfico usa tramos exclusivos
                  {
                    name: 'Vigente',
                    value: Math.max(0, (kpis?.itv_vigente ?? 0) - (kpis?.itv_por_vencer ?? 0)),
                  },
                  { name: 'Por Vencer', value: kpis?.itv_por_vencer ?? 0 },
                  { name: 'Vencida', value: kpis?.itv_vencido ?? 0 },
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
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '20px', marginTop: '8px' }}>
            {[
              {
                titulo: 'Pasajeros',
                vigentes: kpis?.seguros_pasajeros_vigentes ?? 0,
                porVencer: kpis?.seguros_pasajeros_por_vencer ?? 0,
                vencidos: kpis?.seguros_pasajeros_vencidos ?? 0,
              },
              {
                titulo: 'Terceros',
                vigentes: kpis?.seguros_terceros_vigentes ?? 0,
                porVencer: kpis?.seguros_terceros_por_vencer ?? 0,
                vencidos: kpis?.seguros_terceros_vencidos ?? 0,
              },
            ].map(({ titulo, vigentes, porVencer, vencidos }) => {
              const ok = Math.max(0, vigentes - porVencer)
              const total = vigentes + vencidos
              const rows = [
                { label: 'Vigentes', value: ok, color: '#00c853', icon: '✅' },
                { label: 'Por Vencer', value: porVencer, color: '#ffab00', icon: '⚠️' },
                { label: 'Vencidos', value: vencidos, color: '#f44336', icon: '❌' },
              ]
              return (
                <div key={titulo}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '10px', color: 'var(--text-primary)' }}>
                    {titulo}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {rows.map(({ label, value, color, icon }) => {
                      const pct = total ? Math.round((value / total) * 100) : 0
                      return (
                        <div key={label}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                            <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{icon} {label}</span>
                            <span style={{ fontSize: '0.82rem', fontWeight: 700, color }}>{value}</span>
                          </div>
                          <div style={{ height: '6px', background: 'var(--bg-input)', borderRadius: '3px', overflow: 'hidden' }}>
                            <div style={{
                              height: '100%', width: `${pct}%`, background: color, borderRadius: '3px',
                              transition: 'width 1s ease',
                            }} />
                          </div>
                        </div>
                      )
                    })}
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
