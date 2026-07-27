import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { busesApi } from '../api'
import { Search, Plus, RefreshCw, Edit2 } from 'lucide-react'
import BusModal from '../components/buses/BusModal'

function estadoBadge(estado: string) {
  const map: Record<string, string> = {
    VIGENTE: 'badge-vigente', POR_VENCER: 'badge-por-vencer',
    VENCIDO: 'badge-vencido', CRITICO: 'badge-critico', SIN_ITV: 'badge-sin-itv',
  }
  return map[estado] ?? 'badge-sin-itv'
}

function diasLabel(venc: string | null) {
  if (!venc) return '—'
  const diff = Math.round((new Date(venc).getTime() - Date.now()) / 86400000)
  if (diff < 0) return `Hace ${Math.abs(diff)}d`
  if (diff === 0) return 'Hoy'
  return `${diff}d`
}

export default function BusesPage() {
  const [search, setSearch]       = useState('')
  const [page, setPage]           = useState(1)
  const [estadoBus, setEstadoBus] = useState('')
  const [estadoItv, setEstadoItv] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [busToEdit, setBusToEdit] = useState<any>(null)
  const PAGE_SIZE = 25

  const { data, isLoading, refetch } = useQuery<{ data: { items: any[]; total: number } }>({
    queryKey: ['buses', page, search, estadoBus, estadoItv],
    queryFn: () => busesApi.listar({
      page, page_size: PAGE_SIZE,
      ...(search    && { search }),
      ...(estadoBus && { estado_bus: estadoBus }),
      ...(estadoItv && { estado_itv: estadoItv }),
    }),
  })

  // Catálogos
  const { data: marcasData } = useQuery<{ data: any[] }>({ queryKey: ['marcas'], queryFn: busesApi.marcas })
  const { data: tiposData } = useQuery<{ data: any[] }>({ queryKey: ['tipos-carroceria'], queryFn: busesApi.tiposCarroceria })
  const { data: marcasCarrData } = useQuery<{ data: any[] }>({ queryKey: ['marcas-carroceria'], queryFn: busesApi.marcasCarroceria })

  const buses = data?.data?.items ?? []
  const total = data?.data?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  const handleOpenCreate = () => {
    setBusToEdit(null)
    setIsModalOpen(true)
  }

  const handleOpenEdit = (bus: any) => {
    setBusToEdit(bus)
    setIsModalOpen(true)
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-header-title">Buses</h1>
          <p className="page-header-sub">{total} vehículos registrados en el sistema</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary btn-sm" onClick={() => refetch()}>
            <RefreshCw size={14} /> Actualizar
          </button>
          <button className="btn btn-primary" onClick={handleOpenCreate}>
            <Plus size={16} /> Nuevo Bus
          </button>
        </div>
      </div>

      {/* Filtros */}
      <div className="card" style={{ marginBottom: '20px', padding: '16px 20px' }}>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          <div className="search-bar">
            <Search size={15} className="icon" />
            <input
              placeholder="Buscar por RUA o Nº Chassis..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }}
            />
          </div>
          <select className="form-control" style={{ width: '160px' }}
            value={estadoBus} onChange={e => { setEstadoBus(e.target.value); setPage(1) }}>
            <option value="">Todos los estados</option>
            <option value="ACTIVO">Activo</option>
            <option value="INACTIVO">Inactivo</option>
          </select>
          <select className="form-control" style={{ width: '180px' }}
            value={estadoItv} onChange={e => { setEstadoItv(e.target.value); setPage(1) }}>
            <option value="">Todos los ITV</option>
            <option value="VIGENTE">ITV Vigente</option>
            <option value="POR_VENCER">Por Vencer</option>
            <option value="CRITICO">Crítico</option>
            <option value="VENCIDO">Vencido</option>
            <option value="SIN_ITV">Sin ITV</option>
          </select>
        </div>
      </div>

      {/* Tabla */}
      <div className="card" style={{ padding: 0 }}>
        {isLoading ? (
          <div className="loading-spinner"><div className="spinner" /></div>
        ) : buses.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">🚌</div>
            <div className="empty-title">No se encontraron buses</div>
            <p>Ajustá los filtros o registrá un nuevo bus.</p>
          </div>
        ) : (
          <>
            <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>RUA</th>
                    <th>Marca</th>
                    <th>Año</th>
                    <th>Carrocería</th>
                    <th>Empresa</th>
                    <th>ITV Vencimiento</th>
                    <th>Estado ITV</th>
                    <th>Estado Bus</th>
                    <th>Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {buses.map((bus: any) => (
                    <tr key={bus.id_bus}>
                      <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                        {bus.numero_orden ?? '—'}
                      </td>
                      <td style={{ fontWeight: 700, fontFamily: 'monospace', letterSpacing: '0.5px' }}>
                        {bus.rua}
                      </td>
                      <td>{bus.marca_nombre ?? '—'}</td>
                      <td>{bus.año}</td>
                      <td style={{ fontSize: '0.8rem' }}>
                        {bus.marca_carroceria_nombre ?? '—'}
                        {bus.tipo_carroceria_nombre && (
                          <span style={{ color: 'var(--text-muted)', marginLeft: 4 }}>
                            ({bus.tipo_carroceria_nombre})
                          </span>
                        )}
                      </td>
                      <td style={{ fontSize: '0.8rem', maxWidth: '180px',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {bus.empresa_actual ?? <span style={{ color: 'var(--text-muted)' }}>Sin asignar</span>}
                      </td>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>
                        {bus.itv_vencimiento
                          ? new Date(bus.itv_vencimiento).toLocaleDateString('es-PY')
                          : '—'}
                        {bus.itv_vencimiento && (
                          <span style={{ color: 'var(--text-muted)', marginLeft: 6, fontSize: '0.75rem' }}>
                            ({diasLabel(bus.itv_vencimiento)})
                          </span>
                        )}
                      </td>
                      <td>
                        <span className={`badge ${estadoBadge(bus.itv_estado)}`}>
                          {bus.itv_estado?.replace('_', ' ') ?? 'SIN ITV'}
                        </span>
                      </td>
                      <td>
                        <span className={`badge badge-${bus.estado_bus?.toLowerCase()}`}>
                          {bus.estado_bus}
                        </span>
                      </td>
                      <td>
                        <button
                          className="btn btn-secondary btn-sm btn-icon"
                          onClick={() => handleOpenEdit(bus)}
                          title="Editar bus"
                        >
                          <Edit2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Paginación */}
            {totalPages > 1 && (
              <div className="pagination">
                <span className="pagination-info">
                  Mostrando {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} de {total}
                </span>
                <div className="pagination-controls">
                  <button className="page-btn" disabled={page === 1} onClick={() => setPage(p => p - 1)}>‹</button>
                  {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => i + 1).map(p => (
                    <button key={p} className={`page-btn ${page === p ? 'active' : ''}`} onClick={() => setPage(p)}>{p}</button>
                  ))}
                  <button className="page-btn" disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>›</button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <BusModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={() => refetch()}
        busToEdit={busToEdit}
        marcas={marcasData?.data ?? []}
        tiposCarroceria={tiposData?.data ?? []}
        marcasCarroceria={marcasCarrData?.data ?? []}
      />
    </div>
  )
}
