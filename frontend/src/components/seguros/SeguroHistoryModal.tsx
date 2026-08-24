import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { X, Shield } from 'lucide-react'
import { segurosApi } from '../../api'

interface SeguroHistoryModalProps {
  isOpen: boolean
  onClose: () => void
  busId: number
  busRua?: string
}

function estadoBadge(estado: string) {
  const map: Record<string, string> = {
    VIGENTE: 'badge-vigente',
    POR_VENCER: 'badge-por-vencer',
    VENCIDO: 'badge-vencido',
    CRITICO: 'badge-critico',
  }
  return map[estado] ?? 'badge-sin-itv'
}

function formatDate(dateStr?: string | null) {
  if (!dateStr) return '—'
  const cleanStr = String(dateStr).split('T')[0]
  const parts = cleanStr.split('-')
  if (parts.length !== 3) return dateStr
  return `${Number(parts[2])}/${Number(parts[1])}/${parts[0]}`
}

export default function SeguroHistoryModal({
  isOpen,
  onClose,
  busId,
  busRua,
}: SeguroHistoryModalProps) {
  const { data, isLoading } = useQuery<{ data: { items: any[] } }>({
    queryKey: ['seguro-history', busId],
    queryFn: () => segurosApi.historialBus(busId),
    enabled: isOpen && !!busId,
  })

  useEffect(() => {
    if (!isOpen) return
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

  if (!isOpen) return null

  const items = [...(data?.data?.items ?? [])].sort((a: any, b: any) => {
    if (a.seguro_vigente !== b.seguro_vigente) return a.seguro_vigente ? -1 : 1
    return String(b.fecha_vencimiento || '').localeCompare(String(a.fecha_vencimiento || ''))
  })

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Historial de seguro"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="modal-content" style={{ maxWidth: '860px' }}>
        <div className="modal-header">
          <h2 className="modal-title">
            Historial de seguro {busRua ? `— Bus ${busRua}` : `— Bus #${busId}`}
          </h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Cerrar" tabIndex={-1}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
          {isLoading ? (
            <div className="loading-spinner"><div className="spinner" /></div>
          ) : items.length === 0 ? (
            <div className="empty-state" style={{ padding: '30px' }}>
              <div className="empty-icon"><Shield size={32} /></div>
              <div className="empty-title">Sin historial</div>
              <p>No hay pólizas registradas para este bus.</p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Tipo</th>
                    <th>Compañía</th>
                    <th>N° Póliza</th>
                    <th>Inicio</th>
                    <th>Vencimiento</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((seg: any) => {
                    const estado = seg.seguro_vigente
                      ? seg.estado_calculado || 'VIGENTE'
                      : 'NO VIGENTE'
                    return (
                      <tr key={seg.id_seguro}>
                        <td>{seg.tipo_seguro_nombre || '—'}</td>
                        <td>{seg.compania_nombre || '—'}</td>
                        <td style={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>
                          {seg.numero_poliza || '—'}
                        </td>
                        <td style={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>
                          {formatDate(seg.fecha_inicio)}
                        </td>
                        <td style={{ fontFamily: 'monospace', fontSize: '0.82rem', fontWeight: 600 }}>
                          {formatDate(seg.fecha_vencimiento)}
                        </td>
                        <td>
                          <span className={`badge ${estadoBadge(estado)}`}>
                            {String(estado).replace('_', ' ')}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
