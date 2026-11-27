import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Cpu, X } from 'lucide-react'
import { samApi } from '../../api'
import { formatApiError } from '../../api/client'
import { useRol } from '../../hooks/useRol'

interface SamHistoryModalProps {
  isOpen: boolean
  onClose: () => void
  busId: number
  busRua?: string
}

function formatDateTime(dateStr?: string | null) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  if (Number.isNaN(d.getTime())) {
    const clean = String(dateStr).split('T')[0]
    const parts = clean.split('-')
    if (parts.length === 3) return `${Number(parts[2])}/${Number(parts[1])}/${parts[0]}`
    return String(dateStr)
  }
  return d.toLocaleString('es-PY', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function todayLocalInput() {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function SamHistoryModal({
  isOpen,
  onClose,
  busId,
  busRua,
}: SamHistoryModalProps) {
  const { esEps, puedeEditar } = useRol()
  const puedeCambiar = esEps && puedeEditar
  const queryClient = useQueryClient()

  const [showForm, setShowForm] = useState(false)
  const [idSam, setIdSam] = useState('')
  const [samSearch, setSamSearch] = useState('')
  const [fechaInicio, setFechaInicio] = useState(todayLocalInput())
  const [tipoInstalacion, setTipoInstalacion] = useState('TITULAR')
  const [motivo, setMotivo] = useState('')
  const [error, setError] = useState('')

  const { data, isLoading, refetch } = useQuery<{ data: { items: any[]; rua?: string } }>({
    queryKey: ['sam-history', busId],
    queryFn: () => samApi.historialBus(busId),
    enabled: isOpen && !!busId,
  })

  const { data: dispData, isFetching: loadingDisp } = useQuery<{ data: { items: any[] } }>({
    queryKey: ['sam-dispositivos', samSearch],
    queryFn: () =>
      samApi.dispositivos({
        page: 1,
        page_size: 40,
        solo_disponibles: false,
        ...(samSearch.trim() && { search: samSearch.trim() }),
      }),
    enabled: isOpen && showForm && puedeCambiar,
    staleTime: 15_000,
  })

  const dispositivos = dispData?.data?.items ?? []

  const asignarMutation = useMutation({
    mutationFn: () =>
      samApi.asignar({
        id_bus: busId,
        id_sam: idSam.trim(),
        fecha_inicio: new Date(fechaInicio).toISOString(),
        tipo_instalacion: tipoInstalacion || 'TITULAR',
        ...(motivo.trim() && { motivo_asignacion: motivo.trim() }),
      }),
    onSuccess: () => {
      setError('')
      setShowForm(false)
      setIdSam('')
      setMotivo('')
      setFechaInicio(todayLocalInput())
      queryClient.invalidateQueries({ queryKey: ['sam-history', busId] })
      refetch()
    },
    onError: (err) => {
      setError(formatApiError(err, 'No se pudo asignar el SAM.'))
    },
  })

  useEffect(() => {
    if (!isOpen) {
      setShowForm(false)
      setError('')
      setIdSam('')
      setSamSearch('')
      setMotivo('')
      setFechaInicio(todayLocalInput())
      return
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [isOpen, onClose])

  const items = useMemo(() => {
    const list = [...(data?.data?.items ?? [])]
    list.sort((a: any, b: any) => {
      if (a.vigente !== b.vigente) return a.vigente ? -1 : 1
      return String(b.fecha_inicio || '').localeCompare(String(a.fecha_inicio || ''))
    })
    return list
  }, [data])

  const vigente = items.find((i: any) => i.vigente)

  if (!isOpen) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!idSam.trim()) {
      setError('Seleccioná o ingresá el ID del dispositivo SAM.')
      return
    }
    if (!fechaInicio) {
      setError('Indicá la fecha de inicio.')
      return
    }
    asignarMutation.mutate()
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Historial de SAM"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="modal-content" style={{ maxWidth: '920px' }}>
        <div className="modal-header">
          <h2 className="modal-title">
            Historial SAM {busRua ? `— Bus ${busRua}` : `— Bus #${busId}`}
          </h2>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            {puedeCambiar && (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                onClick={() => {
                  setShowForm((v) => !v)
                  setError('')
                }}
              >
                <Cpu size={13} /> {showForm ? 'Cancelar cambio' : 'Cambiar / Asignar SAM'}
              </button>
            )}
            <button type="button" className="modal-close" onClick={onClose} aria-label="Cerrar" tabIndex={-1}>
              <X size={20} />
            </button>
          </div>
        </div>

        <div className="modal-body" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          {vigente && (
            <div
              style={{
                marginBottom: '16px',
                padding: '12px 14px',
                borderRadius: '8px',
                background: 'rgba(251, 191, 36, 0.08)',
                border: '1px solid rgba(251, 191, 36, 0.25)',
                fontSize: '0.88rem',
              }}
            >
              <strong>SAM vigente:</strong>{' '}
              <span style={{ fontFamily: 'monospace' }}>{vigente.id_sam}</span>
              {vigente.eps ? ` · ${vigente.eps}` : ''}
              {' · desde '}
              {formatDateTime(vigente.fecha_inicio)}
            </div>
          )}

          {showForm && puedeCambiar && (
            <form
              onSubmit={handleSubmit}
              style={{
                marginBottom: '18px',
                padding: '14px',
                borderRadius: '8px',
                border: '1px solid var(--border-color, rgba(255,255,255,0.1))',
                display: 'grid',
                gap: '12px',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                {vigente ? 'Reasignar dispositivo SAM' : 'Asignar dispositivo SAM'}
              </div>

              <div>
                <label className="form-label">Buscar dispositivo</label>
                <input
                  className="form-control"
                  value={samSearch}
                  onChange={(e) => setSamSearch(e.target.value)}
                  placeholder="ID SAM, EPS o serie…"
                />
                <div
                  style={{
                    marginTop: '8px',
                    maxHeight: '140px',
                    overflowY: 'auto',
                    border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
                    borderRadius: '6px',
                  }}
                >
                  {loadingDisp ? (
                    <div style={{ padding: '10px', fontSize: '0.82rem', opacity: 0.7 }}>Buscando…</div>
                  ) : dispositivos.length === 0 ? (
                    <div style={{ padding: '10px', fontSize: '0.82rem', opacity: 0.7 }}>Sin resultados</div>
                  ) : (
                    dispositivos.map((d: any) => (
                      <button
                        key={d.id_sam}
                        type="button"
                        onClick={() => setIdSam(d.id_sam)}
                        style={{
                          display: 'block',
                          width: '100%',
                          textAlign: 'left',
                          padding: '8px 10px',
                          border: 'none',
                          background: idSam === d.id_sam ? 'rgba(251,191,36,0.15)' : 'transparent',
                          cursor: 'pointer',
                          fontSize: '0.82rem',
                          color: 'inherit',
                        }}
                      >
                        <span style={{ fontFamily: 'monospace' }}>{d.id_sam}</span>
                        {d.eps ? ` · ${d.eps}` : ''}
                        {d.asignado_actualmente
                          ? ` · en uso (${d.rua_bus_actual || `#${d.id_bus_actual}`})`
                          : ' · disponible'}
                      </button>
                    ))
                  )}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label className="form-label">ID SAM *</label>
                  <input
                    className="form-control"
                    value={idSam}
                    onChange={(e) => setIdSam(e.target.value)}
                    placeholder="ej. 041731e24e6180"
                    required
                    style={{ fontFamily: 'monospace' }}
                  />
                </div>
                <div>
                  <label className="form-label">Fecha inicio *</label>
                  <input
                    type="datetime-local"
                    className="form-control"
                    value={fechaInicio}
                    onChange={(e) => setFechaInicio(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label className="form-label">Tipo instalación</label>
                  <select
                    className="form-control"
                    value={tipoInstalacion}
                    onChange={(e) => setTipoInstalacion(e.target.value)}
                  >
                    <option value="TITULAR">TITULAR</option>
                    <option value="AUXILIAR">AUXILIAR</option>
                  </select>
                </div>
                <div>
                  <label className="form-label">Motivo</label>
                  <input
                    className="form-control"
                    value={motivo}
                    onChange={(e) => setMotivo(e.target.value)}
                    placeholder="Opcional"
                  />
                </div>
              </div>

              {error && (
                <div style={{ color: '#f87171', fontSize: '0.85rem' }}>{error}</div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    setShowForm(false)
                    setError('')
                  }}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={asignarMutation.isPending}
                >
                  {asignarMutation.isPending ? 'Guardando…' : 'Guardar asignación'}
                </button>
              </div>
            </form>
          )}

          {isLoading ? (
            <div className="loading-spinner"><div className="spinner" /></div>
          ) : items.length === 0 ? (
            <div className="empty-state" style={{ padding: '30px' }}>
              <div className="empty-icon"><Cpu size={32} /></div>
              <div className="empty-title">Sin historial</div>
              <p>No hay asignaciones SAM registradas para este bus.</p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>ID SAM</th>
                    <th>EPS</th>
                    <th>Tipo</th>
                    <th>Inicio</th>
                    <th>Fin</th>
                    <th>Estado</th>
                    <th>Usuario</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((asig: any) => (
                    <tr key={asig.id_asignacion_sam}>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>{asig.id_sam}</td>
                      <td>{asig.eps || '—'}</td>
                      <td>{asig.tipo_instalacion || '—'}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>
                        {formatDateTime(asig.fecha_inicio)}
                      </td>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>
                        {formatDateTime(asig.fecha_fin)}
                      </td>
                      <td>
                        <span className={`badge ${asig.vigente ? 'badge-vigente' : 'badge-sin-itv'}`}>
                          {asig.vigente ? 'VIGENTE' : 'CERRADA'}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.82rem', opacity: 0.85 }}>
                        {asig.usuario_registro || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
