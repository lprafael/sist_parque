import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { auditoriaApi } from '../api'
import { RefreshCw } from 'lucide-react'

export default function AuditoriaPage() {
  const [page] = useState(1)

  const { data, isLoading, refetch } = useQuery<{ data: { items: any[] } }>({
    queryKey: ['auditoria', page],
    queryFn: () => auditoriaApi.listar({ page, page_size: 20 }),
  })

  const logs = data?.data?.items ?? []

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-header-title">Log de Auditoría</h1>
          <p className="page-header-sub">Historial de inserciones, cambios y eliminaciones en el sistema</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={() => refetch()}>
          <RefreshCw size={14} /> Actualizar
        </button>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {isLoading ? (
          <div className="loading-spinner"><div className="spinner" /></div>
        ) : logs.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📜</div>
            <div className="empty-title">Sin registros de auditoría</div>
            <p>No se registraron cambios recientemente.</p>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Fecha/Hora</th>
                  <th>Tabla Afectada</th>
                  <th>Acción</th>
                  <th>Usuario</th>
                  <th>Detalles</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l: any) => (
                  <tr key={l.id_auditoria}>
                    <td>#{l.id_auditoria}</td>
                    <td style={{ fontSize: '0.8rem', fontFamily: 'monospace' }}>
                      {new Date(l.fecha_accion).toLocaleString('es-PY')}
                    </td>
                    <td>{l.tabla_afectada}</td>
                    <td>
                      <span className={`badge ${
                        l.accion === 'INSERT' ? 'badge-vigente' :
                        l.accion === 'UPDATE' ? 'badge-por-vencer' : 'badge-vencido'
                      }`}>
                        {l.accion}
                      </span>
                    </td>
                    <td>{l.usuario || 'Sistema'}</td>
                    <td style={{ fontSize: '0.75rem', fontFamily: 'monospace', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {JSON.stringify(l.datos_nuevos || l.datos_anteriores)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
