import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Building2, ChevronDown, Download, RefreshCw } from 'lucide-react'
import { reportesApi } from '../../api'
import { formatApiError } from '../../api/client'

type EmpresaParque = {
  id_eot: string
  nombre: string
  linea: string
  label: string
  total_buses: number
  sheet_name: string
}

function EmpresaMultiSelect({
  empresas,
  selected,
  onChange,
}: {
  empresas: EmpresaParque[]
  selected: string[]
  onChange: (ids: string[]) => void
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return empresas
    return empresas.filter(
      e =>
        e.label?.toLowerCase().includes(q) ||
        e.nombre?.toLowerCase().includes(q) ||
        e.linea?.toLowerCase().includes(q),
    )
  }, [empresas, search])

  const toggle = (id: string) => {
    if (selected.includes(id)) onChange(selected.filter(x => x !== id))
    else onChange([...selected, id])
  }

  const label =
    selected.length === 0
      ? 'Todas las empresas con parque'
      : selected.length === 1
        ? empresas.find(e => e.id_eot === selected[0])?.label ?? '1 empresa'
        : `${selected.length} empresas seleccionadas`

  return (
    <div className="multi-select" ref={ref}>
      <button
        type="button"
        className="form-control multi-select-trigger"
        onClick={() => setOpen(o => !o)}
      >
        <Building2 size={14} style={{ flexShrink: 0, opacity: 0.7 }} />
        <span className="multi-select-label">{label}</span>
        <ChevronDown size={14} style={{ flexShrink: 0, opacity: 0.6 }} />
      </button>

      {open && (
        <div className="multi-select-dropdown">
          <div className="multi-select-search">
            <input
              className="form-control"
              placeholder="Buscar empresa..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              autoFocus
            />
          </div>
          <div className="multi-select-actions">
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => onChange(empresas.map(e => e.id_eot))}
            >
              Todas
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => onChange([])}>
              Ninguna
            </button>
          </div>
          <div className="multi-select-list">
            {filtered.length === 0 ? (
              <div className="multi-select-empty">Sin resultados</div>
            ) : (
              filtered.map(e => {
                const checked = selected.includes(e.id_eot)
                return (
                  <label key={e.id_eot} className={`check-row ${checked ? 'is-checked' : ''}`}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(e.id_eot)}
                    />
                    <span>
                      {e.label}
                      <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>
                        ({e.total_buses} buses)
                      </span>
                    </span>
                  </label>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function PlanillaParqueView() {
  const [empresasSel, setEmpresasSel] = useState<string[]>([])
  const [modo, setModo] = useState<'empresa' | 'operativa'>('empresa')
  const [downloading, setDownloading] = useState(false)

  const {
    data: empresasData,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ['reportes-planilla-parque-empresas'],
    queryFn: () => reportesApi.planillaParqueEmpresas(),
    staleTime: 60_000,
  })

  const empresas: EmpresaParque[] = empresasData?.data?.empresas ?? []
  const errMsg = error ? formatApiError(error, 'Error al cargar empresas') : ''

  const totalBuses = useMemo(() => {
    if (empresasSel.length === 0) {
      return empresas.reduce((s, e) => s + (e.total_buses || 0), 0)
    }
    return empresas
      .filter(e => empresasSel.includes(e.id_eot))
      .reduce((s, e) => s + (e.total_buses || 0), 0)
  }, [empresas, empresasSel])

  const hojasCount = empresasSel.length === 0
    ? empresas.filter(e => e.total_buses > 0).length
    : empresasSel.length

  const handleDescargar = async () => {
    if (downloading) return
    setDownloading(true)
    try {
      const params: Record<string, string> = { modo }
      if (empresasSel.length) params.empresas = empresasSel.join(',')
      const response = await reportesApi.planillaParqueExcel(params)
      const fecha = new Date().toISOString().slice(0, 10)
      const tag = modo === 'operativa' ? 'Operativas' : 'Empresa'
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `Planillas_Parque_${tag}_${fecha}.xlsx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      alert(formatApiError(err, 'Error al generar el libro Excel.'))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: 16, padding: '14px 18px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontWeight: 600 }}>Planillas por empresa</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>
              Un libro Excel · una hoja por empresa · sin columna POD/RTD
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => void handleDescargar()}
              disabled={downloading || isLoading || empresas.length === 0}
            >
              <Download size={14} />
              <span>{downloading ? 'Generando…' : 'Descargar Excel'}</span>
            </button>
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
      </div>

      <div className="card report-section" style={{ marginBottom: 16 }}>
        <div className="report-section-header">
          <Building2 size={16} />
          <h2>Tipo de planilla</h2>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 8 }}>
          <label className={`check-row ${modo === 'empresa' ? 'is-checked' : ''}`} style={{ cursor: 'pointer' }}>
            <input
              type="radio"
              name="modo-planilla"
              checked={modo === 'empresa'}
              onChange={() => setModo('empresa')}
            />
            <span>
              <strong>Empresa (informes)</strong>
              <span style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Incluye buses con ITV vencida / sin fecha (ej. EAE380, EAE387) · pie con totales ITV
              </span>
            </span>
          </label>
          <label className={`check-row ${modo === 'operativa' ? 'is-checked' : ''}`} style={{ cursor: 'pointer' }}>
            <input
              type="radio"
              name="modo-planilla"
              checked={modo === 'operativa'}
              onChange={() => setModo('operativa')}
            />
            <span>
              <strong>Operativa (subsidio)</strong>
              <span style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Solo buses con ITV · excluye vencidas sin fecha · pie por tipo de servicio
              </span>
            </span>
          </label>
        </div>
      </div>

      <div className="card report-section" style={{ marginBottom: 16 }}>
        <div className="report-section-header">
          <Building2 size={16} />
          <h2>Empresas a incluir</h2>
        </div>
        <p className="report-section-hint">
          Dejá vacío para exportar todas las empresas permisionarias con buses activos.
          Cada empresa se exporta en una hoja distinta del mismo archivo.
        </p>

        {errMsg && <div className="error-message" style={{ marginBottom: 12 }}>{errMsg}</div>}

        {isLoading ? (
          <div className="loading-spinner"><div className="spinner" /></div>
        ) : (
          <>
            <EmpresaMultiSelect
              empresas={empresas}
              selected={empresasSel}
              onChange={setEmpresasSel}
            />
            <p className="report-section-hint" style={{ marginTop: 12, marginBottom: 0 }}>
              Modo {modo === 'empresa' ? 'empresa/informes' : 'operativa/subsidio'} · {hojasCount} hoja(s)
              · {totalBuses} buses activos en DB
              {empresasSel.length === 0 ? ' · todas las empresas' : ''}
              {modo === 'operativa' ? ' (en operativa se excluyen los sin ITV)' : ''}
            </p>
          </>
        )}
      </div>

      {!isLoading && empresas.length > 0 && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="planilla-toolbar">
            <strong>Vista previa de hojas</strong>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginLeft: 10 }}>
              {empresas.length} empresas disponibles
            </span>
          </div>
          <div className="planilla-table-wrap">
            <table className="planilla-table">
              <thead>
                <tr className="planilla-header-row">
                  <th>Empresa — Línea</th>
                  <th>Línea</th>
                  <th>Buses activos</th>
                  <th>Nombre de hoja Excel</th>
                </tr>
              </thead>
              <tbody>
                {(empresasSel.length
                  ? empresas.filter(e => empresasSel.includes(e.id_eot))
                  : empresas
                ).map(e => (
                  <tr key={e.id_eot}>
                    <td>{e.label}</td>
                    <td>{e.linea || '—'}</td>
                    <td>{e.total_buses}</td>
                    <td>{e.sheet_name}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
