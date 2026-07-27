import { useQuery } from '@tanstack/react-query'
import { X, Calendar } from 'lucide-react'
import { itvApi } from '../../api'

interface ItvHistoryModalProps {
  isOpen: boolean
  onClose: () => void
  busId: number
}

export default function ItvHistoryModal({
  isOpen,
  onClose,
  busId
}: ItvHistoryModalProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['itv-history', busId],
    queryFn: () => itvApi.historialBus(busId),
    enabled: isOpen && !!busId
  })

  if (!isOpen) return null

  const rawItems = data?.data ?? []
  // Deduplicar registros idénticos por combinación de fechas para evitar duplicados en la vista
  const historyItems = rawItems.filter((item: any, index: number, self: any[]) =>
    index === self.findIndex((t: any) => (
      t.fecha_vencimiento_anterior === item.fecha_vencimiento_anterior &&
      t.fecha_itv_actual === item.fecha_itv_actual &&
      t.fecha_vencimiento_actual === item.fecha_vencimiento_actual
    ))
  )

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'N/A'
    const cleanStr = String(dateStr).split('T')[0]
    const parts = cleanStr.split('-')
    if (parts.length !== 3) return dateStr
    return `${Number(parts[2])}/${Number(parts[1])}/${parts[0]}`
  }

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '700px' }}>
        <div className="modal-header">
          <h2 className="modal-title">Historial de ITV - Bus #{busId}</h2>
          <button className="modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
          {isLoading ? (
            <div className="loading-spinner"><div className="spinner" /></div>
          ) : historyItems.length === 0 ? (
            <div className="empty-state" style={{ padding: '30px' }}>
              <div className="empty-icon"><Calendar size={32} /></div>
              <div className="empty-title">Sin Historial</div>
              <p>No hay registros de renovaciones anteriores para este bus.</p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Fecha Registro</th>
                    <th>ITV Anterior (Venc.)</th>
                    <th>ITV Nueva (Fecha)</th>
                    <th>ITV Nueva (Venc.)</th>
                    <th>Diferencia (días)</th>
                  </tr>
                </thead>
                <tbody>
                  {historyItems.map((item: any) => (
                    <tr key={item.id_historial}>
                      <td style={{ color: 'var(--text-muted)' }}>
                        {new Date(item.fecha_registro).toLocaleString('es-PY')}
                      </td>
                      <td style={{ opacity: 0.8 }}>
                        {formatDate(item.fecha_vencimiento_anterior)}
                      </td>
                      <td style={{ fontWeight: 600 }}>
                        {formatDate(item.fecha_itv_actual)}
                      </td>
                      <td style={{ fontWeight: 600 }}>
                        {formatDate(item.fecha_vencimiento_actual)}
                      </td>
                      <td>
                        <span className={`badge ${item.diferencia_dias > 0 ? 'badge-vigente' : 'badge-vencido'}`}>
                          {item.diferencia_dias > 0 ? `+${item.diferencia_dias}` : item.diferencia_dias} días
                        </span>
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
