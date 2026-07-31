import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { reportesApi } from '../../api'
import { formatApiError } from '../../api/client'

function formatCell(val: unknown): string {
  if (val === null || val === undefined || val === '') return ''
  if (typeof val === 'number') {
    if (val > 0 && val < 1) return `${(val * 100).toFixed(1)}%`
    return String(val)
  }
  return String(val)
}

type Pestana = { key: string; label: string; titulo: string }

export default function PlanillaTabs() {
  const [tab, setTab] = useState('cuadro_edad')

  const { data: pestanasData } = useQuery({
    queryKey: ['reportes-planilla-pestanas'],
    queryFn: () => reportesApi.planillaPestanas(),
    staleTime: 60_000,
  })

  const pestanas: Pestana[] = pestanasData?.data?.pestanas ?? []

  useEffect(() => {
    if (pestanas.length && !pestanas.some((p) => p.key === tab)) {
      setTab(pestanas[0].key)
    }
  }, [pestanas, tab])

  const {
    data: reporteData,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ['reportes-planilla-db', tab],
    queryFn: () => reportesApi.planillaReporte(tab),
    enabled: !!tab,
  })

  const reporte = reporteData?.data
  const filas: unknown[][] = reporte?.filas ?? []
  const headers: string[] = reporte?.headers ?? []
  const errMsg = error ? formatApiError(error, 'Error al cargar el reporte') : ''

  // Separar filas de metadatos (título/nota) vs tabla
  const dataStart = filas.findIndex(
    (r) => Array.isArray(r) && r.length && headers.length && String(r[0]) === headers[0],
  )
  const metaRows = dataStart > 0 ? filas.slice(0, dataStart) : []
  const tableHeader = dataStart >= 0 ? filas[dataStart] : headers
  const tableRows = dataStart >= 0 ? filas.slice(dataStart + 1) : filas

  return (
    <div>
      <div className="card" style={{ marginBottom: 16, padding: '14px 18px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontWeight: 600 }}>Planilla ITV (datos en vivo)</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>
              Cuadros equivalentes al Excel, calculados desde la base · {reporte?.fecha || '—'}
              {reporte?.fuente ? ` · ${reporte.fuente}` : ''}
            </div>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => void refetch()}
            disabled={isFetching}
          >
            <RefreshCw size={14} />
            <span>{isFetching ? 'Actualizando…' : 'Actualizar'}</span>
          </button>
        </div>
      </div>

      <div className="report-tabs" role="tablist">
        {pestanas.map((p) => (
          <button
            key={p.key}
            type="button"
            role="tab"
            aria-selected={tab === p.key}
            className={`report-tab ${tab === p.key ? 'active' : ''}`}
            title={p.titulo}
            onClick={() => setTab(p.key)}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="planilla-toolbar">
          <div>
            <strong>{reporte?.titulo || pestanas.find((p) => p.key === tab)?.titulo || tab}</strong>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginLeft: 10 }}>
              {reporte?.total_filas ?? 0} filas
              {isFetching ? ' · actualizando…' : ''}
            </span>
            {reporte?.nota && (
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 4 }}>
                {reporte.nota}
              </div>
            )}
          </div>
        </div>

        {errMsg && (
          <div className="error-message" style={{ margin: 16 }}>{errMsg}</div>
        )}

        {isLoading ? (
          <div className="loading-spinner"><div className="spinner" /></div>
        ) : (
          <div className="planilla-table-wrap">
            {metaRows.length > 0 && (
              <div style={{ padding: '10px 16px', fontSize: '0.85rem', borderBottom: '1px solid var(--border)' }}>
                {metaRows.map((r, i) => (
                  <div key={i} style={{ fontWeight: i === 0 ? 700 : 400 }}>
                    {Array.isArray(r) ? r.filter(Boolean).map(String).join(' · ') : String(r)}
                  </div>
                ))}
              </div>
            )}
            <table className="planilla-table">
              <thead>
                <tr className="planilla-header-row">
                  {(tableHeader || []).map((h, i) => (
                    <th key={i}>{formatCell(h)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableRows.map((row, ri) => (
                  <tr key={ri}>
                    {(row as unknown[]).map((cell, ci) => (
                      <td key={ci}>{formatCell(cell)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {tableRows.length === 0 && !errMsg && (
              <div className="empty-state" style={{ padding: 24 }}>
                <div className="empty-title">Sin datos para este cuadro</div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
