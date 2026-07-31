import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Upload, ChevronLeft, ChevronRight, FileSpreadsheet } from 'lucide-react'
import { reportesApi } from '../../api'
import { formatApiError } from '../../api/client'

function formatCell(val: unknown): string {
  if (val === null || val === undefined || val === '') return ''
  if (typeof val === 'number') {
    if (val > 0 && val <= 1) return `${(val * 100).toFixed(1)}%`
    return String(val)
  }
  return String(val)
}

function isHeaderishRow(row: unknown[]): boolean {
  const texts = row.filter((c) => typeof c === 'string' && String(c).trim().length > 0)
  if (texts.length < 2) return false
  const upper = texts.filter((c) => String(c) === String(c).toUpperCase() || /[A-Za-zÁÉÍÓÚÑ]/.test(String(c)))
  return upper.length >= 2
}

export default function PlanillaTabs() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<string>('')
  const [page, setPage] = useState(1)
  const [uploading, setUploading] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const PAGE_SIZE = 80

  const { data: hojasData, isLoading: loadingHojas, refetch: refetchHojas } = useQuery({
    queryKey: ['reportes-planilla-hojas'],
    queryFn: () => reportesApi.planillaHojas(),
  })

  const hojas: string[] = hojasData?.data?.hojas ?? []
  const disponible = !!hojasData?.data?.disponible
  const filename = hojasData?.data?.filename

  // Preferir pestañas de resumen (no General primero)
  const hojasOrdenadas = useMemo(() => {
    const prefer = [
      'CUADRO DE EDAD',
      'BAJAS',
      'BUSES OPER RESER Y DECLAR',
      'PORCENTAJE INCLUSIVO',
      'GRAFICOS',
      'PORCENTAJE OPERATIVO ITV APROBA',
      'PORCENTAJE OPER RESOL SOBRE DEC',
      'CANTIDAD FALTANTE',
      'PLANILLA DE PARCIALES',
      'BUSES ELECTRICOS',
    ]
    const rest = hojas.filter((h) => !prefer.includes(h))
    return [...prefer.filter((h) => hojas.includes(h)), ...rest]
  }, [hojas])

  useEffect(() => {
    if (!tab && hojasOrdenadas.length) setTab(hojasOrdenadas[0])
  }, [hojasOrdenadas, tab])

  useEffect(() => {
    setPage(1)
  }, [tab])

  const { data: hojaData, isLoading: loadingHoja, isFetching } = useQuery({
    queryKey: ['reportes-planilla-hoja', tab, page, PAGE_SIZE],
    queryFn: () => reportesApi.planillaHoja(tab, { page, page_size: PAGE_SIZE }),
    enabled: !!tab && disponible,
  })

  const filas: unknown[][] = hojaData?.data?.filas ?? []
  const totalFilas = hojaData?.data?.total_filas ?? 0
  const totalPages = hojaData?.data?.total_pages ?? 1
  const titulo = hojaData?.data?.titulo || tab

  const handleUpload = async (file: File | null) => {
    if (!file) return
    setUploading(true)
    setErr('')
    setMsg('')
    const fd = new FormData()
    fd.append('file', file)
    try {
      const res = await reportesApi.planillaCargar(fd)
      setMsg(res.data.mensaje)
      setTab('')
      await refetchHojas()
      queryClient.invalidateQueries({ queryKey: ['reportes-planilla-hoja'] })
    } catch (e) {
      setErr(formatApiError(e, 'Error al cargar la planilla'))
    } finally {
      setUploading(false)
    }
  }

  const shortTab = (name: string) => {
    if (name.length <= 28) return name
    return name.slice(0, 26) + '…'
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: 16, padding: '14px 18px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
              <FileSpreadsheet size={16} />
              Planilla ITV (hojas del Excel)
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>
              {disponible
                ? `Fuente: ${filename || 'planilla cargada'} · elegí una pestaña para ver el cuadro`
                : 'Subí el Excel ITV (ej. ITV - 2026 Base de Datos…) para ver CUADRO DE EDAD, BAJAS, etc.'}
            </div>
          </div>
          <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
            <Upload size={14} />
            <span>{uploading ? 'Cargando…' : 'Cargar / actualizar Excel'}</span>
            <input
              type="file"
              accept=".xlsx,.xls"
              style={{ display: 'none' }}
              disabled={uploading}
              onChange={(e) => {
                void handleUpload(e.target.files?.[0] ?? null)
                e.target.value = ''
              }}
            />
          </label>
        </div>
        {msg && <div style={{ marginTop: 10, color: '#166534', fontSize: '0.85rem' }}>{msg}</div>}
        {err && <div className="error-message" style={{ marginTop: 10 }}>{err}</div>}
      </div>

      {!disponible && !loadingHojas ? (
        <div className="card empty-state" style={{ padding: 32 }}>
          <div className="empty-title">Sin planilla cargada</div>
          <p>Usá el botón “Cargar / actualizar Excel” con el archivo ITV 2026.</p>
        </div>
      ) : (
        <>
          <div className="report-tabs" role="tablist">
            {hojasOrdenadas.map((h) => (
              <button
                key={h}
                type="button"
                role="tab"
                aria-selected={tab === h}
                className={`report-tab ${tab === h ? 'active' : ''}`}
                title={h}
                onClick={() => setTab(h)}
              >
                {shortTab(h)}
              </button>
            ))}
          </div>

          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div className="planilla-toolbar">
              <div>
                <strong>{titulo}</strong>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginLeft: 10 }}>
                  {totalFilas} filas · pág. {page}/{totalPages}
                  {isFetching ? ' · actualizando…' : ''}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page <= 1 || loadingHoja}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft size={14} /> Anterior
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page >= totalPages || loadingHoja}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Siguiente <ChevronRight size={14} />
                </button>
              </div>
            </div>

            {loadingHoja ? (
              <div className="loading-spinner"><div className="spinner" /></div>
            ) : (
              <div className="planilla-table-wrap">
                <table className="planilla-table">
                  <tbody>
                    {filas.map((row, ri) => {
                      const header = page === 1 && ri < 12 && isHeaderishRow(row)
                      return (
                        <tr key={ri} className={header ? 'planilla-header-row' : undefined}>
                          {row.map((cell, ci) => (
                            <td key={ci}>{formatCell(cell)}</td>
                          ))}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                {filas.length === 0 && (
                  <div className="empty-state" style={{ padding: 24 }}>
                    <div className="empty-title">Hoja vacía</div>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
