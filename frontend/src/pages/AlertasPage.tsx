import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { alertasApi } from '../api'
import { Bell, Check, EyeOff, RefreshCw, Filter } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'

const prioridadBadge: Record<string, string> = {
  ALTA: 'badge-alta', MEDIA: 'badge-media', BAJA: 'badge-baja',
}
const estadoBadge: Record<string, string> = {
  PENDIENTE: 'badge-pendiente', ATENDIDA: 'badge-atendida', IGNORADA: 'badge-inactivo',
}
const tipoIcon: Record<string, string> = {
  ITV: '🔧', SEGURO_PASAJEROS: '🛡️', SEGURO_TERCEROS: '🛡️', DOCUMENTO: '📄',
}

export default function AlertasPage() {
  const [estado, setEstado]     = useState('PENDIENTE')
  const [prioridad, setPrioridad] = useState('')
  const [page, setPage]         = useState(1)
  const { usuario } = useAuthStore()
  const qc = useQueryClient()
  const PAGE_SIZE = 20

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['alertas', page, estado, prioridad],
    queryFn: () => alertasApi.listar({
      page, page_size: PAGE_SIZE,
      ...(estado    && { estado }),
      ...(prioridad && { prioridad }),
    }),
    refetchInterval: 30000,
  })

  const atender = useMutation({
    mutationFn: (id: number) =>
      alertasApi.atender(id, { usuario_atencion: usuario?.username ?? 'sistema' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alertas'] }),
  })

  const ignorar = useMutation({
    mutationFn: (id: number) => alertasApi.ignorar(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alertas'] }),
  })

  const limpiarTodas = useMutation({
    mutationFn: () => alertasApi.limpiarTodas(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alertas'] })
      qc.invalidateQueries({ queryKey: ['kpis'] })
    },
  })

  const handleLimpiar = () => {
    if (window.confirm('¿Está seguro de eliminar todas las alertas del sistema?')) {
      limpiarTodas.mutate()
    }
  }

  const alertas = data?.data?.items ?? []
  const total   = data?.data?.total ?? 0

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-header-title">Alertas y Notificaciones</h1>
          <p className="page-header-sub">{total} alerta(s) encontrada(s)</p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button 
            className="btn btn-secondary btn-sm" 
            onClick={handleLimpiar}
            disabled={limpiarTodas.isPending}
            style={{ color: '#f87171', borderColor: 'rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.1)' }}
          >
            Borrar Todas
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => refetch()}>
            <RefreshCw size={14} /> Actualizar
          </button>
        </div>
      </div>


      {/* Filtros */}
      <div className="card" style={{ marginBottom: '20px', padding: '14px 20px' }}>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <Filter size={15} style={{ color: 'var(--text-muted)' }} />
          {(['PENDIENTE', 'ATENDIDA', 'IGNORADA', ''] as const).map(e => (
            <button key={e}
              className={`btn btn-sm ${estado === e ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => { setEstado(e as string); setPage(1) }}>
              {e || 'Todas'}
            </button>
          ))}
          <div style={{ width: '1px', height: '24px', background: 'var(--border)' }} />
          {(['', 'ALTA', 'MEDIA', 'BAJA'] as const).map(p => (
            <button key={p}
              className={`btn btn-sm ${prioridad === p ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => { setPrioridad(p as string); setPage(1) }}>
              {p || 'Toda prioridad'}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="loading-spinner"><div className="spinner" /></div>
      ) : alertas.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon"><Bell size={48} /></div>
          <div className="empty-title">No hay alertas</div>
          <p>No se encontraron alertas con los filtros seleccionados.</p>
        </div>
      ) : (
        <div>
          {alertas.map((al: any) => (
            <div key={al.id_alerta} className={`alert-item ${al.prioridad?.toLowerCase()}`}>
              <div style={{ fontSize: '1.5rem', flexShrink: 0 }}>
                {tipoIcon[al.tipo_alerta] ?? '🔔'}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>{al.titulo}</span>
                  <span className={`badge ${prioridadBadge[al.prioridad]}`}>{al.prioridad}</span>
                  <span className={`badge ${estadoBadge[al.estado_alerta]}`}>{al.estado_alerta}</span>
                </div>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  {al.descripcion}
                </p>
                <div style={{ display: 'flex', gap: '16px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {al.bus_rua && <span>Bus: <strong style={{ color: 'var(--text-secondary)' }}>{al.bus_rua}</strong></span>}
                  <span>Fecha: {al.fecha_alerta ? new Date(al.fecha_alerta).toLocaleDateString('es-PY') : '—'}</span>
                  {al.fecha_atencion && (
                    <span>Atendida por: <strong>{al.usuario_atencion}</strong></span>
                  )}
                </div>
              </div>
              {al.estado_alerta === 'PENDIENTE' && (
                <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                  <button
                    className="btn btn-success btn-sm"
                    onClick={() => atender.mutate(al.id_alerta)}
                    disabled={atender.isPending}
                    title="Marcar como atendida"
                  >
                    <Check size={13} /> Atender
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => ignorar.mutate(al.id_alerta)}
                    disabled={ignorar.isPending}
                    title="Ignorar alerta"
                  >
                    <EyeOff size={13} />
                  </button>
                </div>
              )}
            </div>
          ))}

          {/* Paginación */}
          {Math.ceil(total / PAGE_SIZE) > 1 && (
            <div className="pagination" style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', marginTop: '12px' }}>
              <span className="pagination-info">
                {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} de {total}
              </span>
              <div className="pagination-controls">
                <button className="page-btn" disabled={page === 1} onClick={() => setPage(p => p - 1)}>‹</button>
                <button className="page-btn" disabled={page === Math.ceil(total / PAGE_SIZE)} onClick={() => setPage(p => p + 1)}>›</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
