import { useMemo, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, CalendarRange, Bus, AlertTriangle, Building2 } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { dashboardApi, empresasApi } from '../api'

const TRAMO_COLORS = ['#34d399', '#60a5fa', '#fbbf24', '#f87171']

export default function AntiguedadPage() {
  const [searchParams] = useSearchParams()
  const idEot = searchParams.get('empresa') || ''
  const dashParams = useMemo(
    () => (idEot ? { id_eot: idEot } : undefined),
    [idEot],
  )

  const { data: empListaResp } = useQuery({
    queryKey: ['empresas-lista-ant'],
    queryFn: () => empresasApi.listar({ page: 1, page_size: 500 }),
  })
  const empresasLista = empListaResp?.data?.items ?? []
  const empresaSeleccionada = empresasLista.find(
    (e: any) => e.id_eot_vmt_hex === idEot,
  )

  const { data: resp, isLoading } = useQuery({
    queryKey: ['analisis-antiguedad', idEot],
    queryFn: () => dashboardApi.analisisAntiguedad(dashParams),
  })
  const d = resp?.data

  if (isLoading) {
    return <div className="loading-spinner"><div className="spinner" /></div>
  }

  if (!d || d.total_buses === 0) {
    return (
      <div>
        <Header idEot={idEot} empresa={empresaSeleccionada} />
        <div className="card empty-state" style={{ padding: '2.5rem' }}>
          <div className="empty-title">Sin datos de antigüedad</div>
          <p>No hay buses activos con año/modelo válido para el filtro actual.</p>
        </div>
      </div>
    )
  }

  const umbral20 = d.umbrales?.mas_de_20
  const umbral15 = d.umbrales?.mas_de_15

  return (
    <div>
      <Header idEot={idEot} empresa={empresaSeleccionada} />

      <div style={{
        marginBottom: '1rem',
        padding: '0.85rem 1rem',
        borderRadius: 8,
        background: 'rgba(99,102,241,0.08)',
        border: '1px solid rgba(99,102,241,0.25)',
        fontSize: '0.875rem',
        color: 'var(--text-muted)',
      }}>
        El promedio se calcula con año de referencia <strong style={{ color: 'var(--text-primary)' }}>{d.anio_referencia}</strong>
        {' '}(edad = {d.anio_referencia} − año/modelo), sobre <strong style={{ color: 'var(--text-primary)' }}>{d.total_buses}</strong> buses activos
        con año entre <strong style={{ color: 'var(--text-primary)' }}>{d.anio_desde}</strong> y <strong style={{ color: 'var(--text-primary)' }}>{d.anio_hasta}</strong>.
      </div>

      <div className="kpi-grid" style={{ marginBottom: '1.25rem' }}>
        <StatCard
          label="Edad promedio"
          value={`${d.promedio_edad} años`}
          hint={`Referencia ${d.anio_referencia}`}
        />
        <StatCard
          label="Mediana"
          value={d.mediana_edad != null ? `${d.mediana_edad} años` : '—'}
          hint="Mitad del parque tiene esa edad o menos"
        />
        <StatCard
          label="Moda (más frecuente)"
          value={d.moda ? `${d.moda.antiguedad}a (${d.moda.anio})` : '—'}
          hint={d.moda ? `${d.moda.cantidad} buses` : undefined}
        />
        <StatCard
          label="Rango de años/modelo"
          value={`${d.anio_desde} → ${d.anio_hasta}`}
          hint={`${d.anio_hasta - d.anio_desde} años de amplitud`}
          icon={<CalendarRange size={16} />}
        />
      </div>

      <div className="kpi-grid" style={{ marginBottom: '1.25rem' }}>
        <StatCard
          label="Más antiguos"
          value={`${d.mas_antiguos?.cantidad ?? 0} buses`}
          hint={`Desde año/modelo ${d.mas_antiguos?.anio} (${d.mas_antiguos?.antiguedad} años)`}
          tone="warn"
          icon={<Bus size={16} />}
        />
        <StatCard
          label="Más nuevos"
          value={`${d.mas_nuevos?.cantidad ?? 0} buses`}
          hint={`Año/modelo ${d.mas_nuevos?.anio} (${d.mas_nuevos?.antiguedad} años)`}
        />
        <StatCard
          label="Más de 15 años"
          value={`${umbral15?.cantidad ?? 0}`}
          hint={`${umbral15?.porcentaje ?? 0}% del parque activo`}
          tone="warn"
        />
        <StatCard
          label="Más de 20 años"
          value={`${umbral20?.cantidad ?? 0}`}
          hint={`${umbral20?.porcentaje ?? 0}% · alerta GVMT 145/2026`}
          tone="danger"
          icon={<AlertTriangle size={16} />}
        />
      </div>

      <div className="dashboard-charts-row" style={{ marginBottom: '1.25rem' }}>
        <div className="card">
          <div className="card-header">
            <span className="card-title">Distribución por tramos de edad</span>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={d.tramos ?? []} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
              <XAxis dataKey="label" tick={{ fill: '#8b93c4', fontSize: 11 }} />
              <YAxis tick={{ fill: '#8b93c4', fontSize: 11 }} />
              <Tooltip
                formatter={(value, _name, item) => {
                  const pct = (item?.payload as { porcentaje?: number } | undefined)?.porcentaje ?? 0
                  return [`${value ?? 0} buses (${pct}%)`, 'Cantidad']
                }}
              />
              <Bar dataKey="cantidad" radius={[6, 6, 0, 0]}>
                {(d.tramos ?? []).map((_: unknown, i: number) => (
                  <Cell key={i} fill={TRAMO_COLORS[i % TRAMO_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', padding: '0 1rem 1rem' }}>
            {(d.tramos ?? []).map((t: any, i: number) => (
              <span
                key={t.label}
                style={{
                  fontSize: '0.75rem',
                  padding: '4px 10px',
                  borderRadius: 999,
                  background: `${TRAMO_COLORS[i]}22`,
                  border: `1px solid ${TRAMO_COLORS[i]}55`,
                }}
              >
                {t.label}: <strong>{t.cantidad}</strong> ({t.porcentaje}%)
              </span>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title">Top años/modelo por cantidad</span>
          </div>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Año</th>
                  <th>Edad</th>
                  <th>Buses</th>
                  <th>% parque</th>
                </tr>
              </thead>
              <tbody>
                {(d.top_por_cantidad ?? []).map((r: any) => (
                  <tr key={r.anio}>
                    <td>{r.anio}</td>
                    <td>{r.antiguedad}a</td>
                    <td><strong>{r.cantidad}</strong></td>
                    <td>{((100 * r.cantidad) / d.total_buses).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {!idEot && ((d.empresas_mas_antiguas?.length ?? 0) > 0 || (d.empresas_mas_nuevas?.length ?? 0) > 0) && (
        <div className="dashboard-charts-row" style={{ marginBottom: '1.25rem' }}>
          {(d.empresas_mas_antiguas?.length ?? 0) > 0 && (
            <div className="card">
              <div className="card-header">
                <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Building2 size={16} /> Empresas con flota más antigua
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Mín. 5 buses · mayor promedio</span>
              </div>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Empresa</th>
                      <th>Buses</th>
                      <th>Promedio</th>
                      <th>Edad máx.</th>
                      <th>Año más antiguo</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.empresas_mas_antiguas.map((e: any) => (
                      <tr key={`ant-${e.id_eot || e.empresa}`}>
                        <td>{e.empresa}</td>
                        <td>{e.total_buses}</td>
                        <td>{e.promedio_edad}a</td>
                        <td>{e.edad_max}a</td>
                        <td>{e.anio_mas_antiguo ?? '—'}</td>
                        <td>
                          {e.id_eot && (
                            <Link
                              to={`/dashboard/antiguedad?empresa=${encodeURIComponent(e.id_eot)}`}
                              className="btn btn-secondary btn-sm"
                            >
                              Ver
                            </Link>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {(d.empresas_mas_nuevas?.length ?? 0) > 0 && (
            <div className="card">
              <div className="card-header">
                <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Building2 size={16} /> Empresas con flota más nueva
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Mín. 5 buses · menor promedio</span>
              </div>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Empresa</th>
                      <th>Buses</th>
                      <th>Promedio</th>
                      <th>Edad mín.</th>
                      <th>Año más nuevo</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.empresas_mas_nuevas.map((e: any) => (
                      <tr key={`nue-${e.id_eot || e.empresa}`}>
                        <td>{e.empresa}</td>
                        <td>{e.total_buses}</td>
                        <td>{e.promedio_edad}a</td>
                        <td>{e.edad_min ?? '—'}a</td>
                        <td>{e.anio_mas_nuevo ?? '—'}</td>
                        <td>
                          {e.id_eot && (
                            <Link
                              to={`/dashboard/antiguedad?empresa=${encodeURIComponent(e.id_eot)}`}
                              className="btn btn-secondary btn-sm"
                            >
                              Ver
                            </Link>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <span className="card-title">Muestra de buses más antiguos</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Hasta 25 unidades, ordenadas por año/modelo
          </span>
        </div>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>RUA</th>
                <th>Orden</th>
                <th>Año</th>
                <th>Edad</th>
                <th>Empresa</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(d.muestra_mas_antiguos ?? []).map((b: any) => (
                <tr key={b.id_bus}>
                  <td style={{ fontFamily: 'monospace' }}>{b.rua}</td>
                  <td>{b.numero_orden ?? '—'}</td>
                  <td>{b.anio}</td>
                  <td>
                    <span className={b.antiguedad > 20 ? 'badge badge-vencido' : b.antiguedad > 15 ? 'badge badge-por-vencer' : 'badge badge-vigente'}>
                      {b.antiguedad}a
                    </span>
                  </td>
                  <td>{b.empresa || '—'}</td>
                  <td>
                    <Link to={`/buses?search=${encodeURIComponent(b.rua || '')}`} className="btn btn-secondary btn-sm">
                      Buscar
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function Header({
  idEot,
  empresa,
}: {
  idEot: string
  empresa?: { eot_nombre?: string; eot_linea?: string } | null
}) {
  const back = idEot ? `/?empresa=${encodeURIComponent(idEot)}` : '/'
  return (
    <div className="page-header">
      <div>
        <Link to={back} className="btn btn-secondary btn-sm" style={{ marginBottom: 8 }}>
          <ArrowLeft size={14} /> Volver al dashboard
        </Link>
        <h1 className="page-header-title">Análisis de antigüedad del parque</h1>
        <p className="page-header-sub">
          Detalle del promedio de edad, extremos y umbrales normativos
          {empresa ? ` · ${empresa.eot_nombre || empresa.eot_linea || 'Empresa'}` : ' · Todo el parque'}
        </p>
      </div>
    </div>
  )
}

function StatCard({
  label,
  value,
  hint,
  tone,
  icon,
}: {
  label: string
  value: string
  hint?: string
  tone?: 'warn' | 'danger'
  icon?: ReactNode
}) {
  const border =
    tone === 'danger'
      ? '1px solid rgba(248,113,113,0.35)'
      : tone === 'warn'
        ? '1px solid rgba(251,191,36,0.35)'
        : '1px solid var(--border-color, #e2e8f0)'
  const valueColor =
    tone === 'danger' ? '#f87171' : tone === 'warn' ? '#fbbf24' : 'var(--text-primary)'

  return (
    <div className="card" style={{ padding: '1rem 1.1rem', border }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-muted)', fontWeight: 600 }}>
          {label}
        </div>
        {icon}
      </div>
      <div style={{ fontSize: '1.35rem', fontWeight: 800, color: valueColor }}>{value}</div>
      {hint && (
        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 4 }}>{hint}</div>
      )}
    </div>
  )
}
