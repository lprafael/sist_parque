import { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { busesApi, empresasApi, itvApi } from '../api'
import { Search, Plus, RefreshCw, Edit2, X, Building2, Clock, Ban, Hash, Shield } from 'lucide-react'
import { useRol } from '../hooks/useRol'
import BusModal from '../components/buses/BusModal'
import BajaModal from '../components/buses/BajaModal'
import ItvHistoryModal from '../components/itv/ItvHistoryModal'
import ItvModal from '../components/itv/ItvModal'
import SeguroHistoryModal from '../components/seguros/SeguroHistoryModal'

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
  const { puedeEditar } = useRol()
  const [searchParams, setSearchParams] = useSearchParams()
  const empresaParam = searchParams.get('empresa') ?? ''
  const estadoBusParam = searchParams.get('estado_bus') ?? ''
  const estadoItvParam = searchParams.get('estado_itv') ?? ''

  const [search, setSearch]           = useState('')
  const [page, setPage]               = useState(1)
  const [estadoBus, setEstadoBus]     = useState(estadoBusParam)
  const [estadoItv, setEstadoItv]     = useState(estadoItvParam)
  const [empresa, setEmpresa]         = useState(empresaParam)

  // Filtro número de orden
  const [ordenInput, setOrdenInput]         = useState('')
  const [ordenSelected, setOrdenSelected]   = useState<number | null>(null)
  const [ordenOpen, setOrdenOpen]           = useState(false)
  const [ordenModo, setOrdenModo]           = useState<'igual' | 'contiene'>('contiene')
  const [ordenFiltro, setOrdenFiltro]       = useState('')
  const ordenRef = useRef<HTMLDivElement>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [busToEdit, setBusToEdit]     = useState<any>(null)
  const [isBajaOpen, setIsBajaOpen]   = useState(false)
  const [busToBaja, setBusToBaja]     = useState<any>(null)

  // Modales ITV / Seguro
  const [isHistoryOpen, setIsHistoryOpen]                 = useState(false)
  const [isSeguroHistoryOpen, setIsSeguroHistoryOpen]     = useState(false)
  const [selectedBusForHistory, setSelectedBusForHistory] = useState<any>(null)
  const [isItvModalOpen, setIsItvModalOpen]               = useState(false)
  const [itvToEdit, setItvToEdit]                         = useState<any>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  const PAGE_SIZE = 25

  const anyModalOpen = isModalOpen || isHistoryOpen || isSeguroHistoryOpen || isItvModalOpen || isBajaOpen

  // Foco en el buscador al entrar y al cerrar modales
  useEffect(() => {
    if (anyModalOpen) return
    const t = window.setTimeout(() => searchRef.current?.focus(), 0)
    return () => window.clearTimeout(t)
  }, [anyModalOpen])

  // Sincronizar parámetros URL si cambian externamente (Dashboard → lista)
  useEffect(() => {
    setEmpresa(empresaParam)
    setEstadoBus(estadoBusParam)
    setEstadoItv(estadoItvParam)
    setPage(1)
  }, [empresaParam, estadoBusParam, estadoItvParam])

  // Catálogo de empresas permisionarias para el dropdown de filtro
  const { data: empresasData } = useQuery<{ data: { items: any[] } }>({
    queryKey: ['empresas-filtro-buses'],
    queryFn: () => empresasApi.listar({ page: 1, page_size: 200, solo_activas: true, solo_permisionarias: true })
  })

  const empresasLista = empresasData?.data?.items ?? []

  // Opciones autocomplete orden
  const { data: ordenData } = useQuery<{ data: { numero_orden: number; rua: string }[] }>({
    queryKey: ['buses-ordenes', ordenInput],
    queryFn: () => busesApi.numerosOrden(ordenInput || undefined),
    enabled: ordenOpen,
    staleTime: 30_000,
  })
  const ordenOpciones = ordenData?.data ?? []

  // Cerrar dropdown de orden al click fuera
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ordenRef.current && !ordenRef.current.contains(e.target as Node)) {
        setOrdenOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const { data, isLoading, refetch } = useQuery<{ data: { items: any[]; total: number } }>({
    queryKey: ['buses', page, search, estadoBus, estadoItv, empresa, ordenFiltro, ordenModo],
    queryFn: () => busesApi.listar({
      page, page_size: PAGE_SIZE,
      ...(search        && { search }),
      ...(estadoBus     && { estado_bus: estadoBus }),
      ...(estadoItv     && { estado_itv: estadoItv }),
      ...(empresa       && { empresa }),
      ...(ordenFiltro   && { numero_orden: ordenFiltro, orden_modo: ordenModo }),
    }),
  })

  // Catálogos
  const { data: marcasData } = useQuery<{ data: any[] }>({ queryKey: ['marcas'], queryFn: busesApi.marcas })
  const { data: tiposData } = useQuery<{ data: any[] }>({ queryKey: ['tipos-carroceria'], queryFn: busesApi.tiposCarroceria })
  const { data: marcasCarrData } = useQuery<{ data: any[] }>({ queryKey: ['marcas-carroceria'], queryFn: busesApi.marcasCarroceria })

  const buses = data?.data?.items ?? []
  const total = data?.data?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  const syncParams = (next: { empresa?: string; estado_bus?: string; estado_itv?: string }) => {
    const p = new URLSearchParams()
    const emp = next.empresa !== undefined ? next.empresa : empresa
    const eb = next.estado_bus !== undefined ? next.estado_bus : estadoBus
    const ei = next.estado_itv !== undefined ? next.estado_itv : estadoItv
    if (emp) p.set('empresa', emp)
    if (eb) p.set('estado_bus', eb)
    if (ei) p.set('estado_itv', ei)
    setSearchParams(p)
  }

  const handleEmpresaChange = (val: string) => {
    setEmpresa(val)
    setPage(1)
    syncParams({ empresa: val })
  }

  const handleOpenCreate = () => {
    setBusToEdit(null)
    setIsModalOpen(true)
  }

  const handleOpenEdit = (bus: any) => {
    setBusToEdit(bus)
    setIsModalOpen(true)
  }

  const handleOpenBaja = (bus: any) => {
    setBusToBaja(bus)
    setIsBajaOpen(true)
  }

  const handleOpenHistory = (bus: any) => {
    setSelectedBusForHistory(bus)
    setIsHistoryOpen(true)
  }

  const handleOpenSeguroHistory = (bus: any) => {
    setSelectedBusForHistory(bus)
    setIsSeguroHistoryOpen(true)
  }

  const handleOpenEditItv = async (busId: number) => {
    try {
      const res = await itvApi.listar({
        id_bus: busId,
        solo_vigentes: true,
        page: 1,
        page_size: 1,
      })
      const vigente = res.data?.items?.[0]
      // Con id_itv → editar vigente; sin id_itv → registrar nueva ITV para el bus
      setItvToEdit(vigente ?? { id_bus: busId })
    } catch {
      setItvToEdit({ id_bus: busId })
    }
    setIsItvModalOpen(true)
  }

  // Nombre de la empresa seleccionada si está filtrando
  const empSeleccionadaObj = empresasLista.find((e: any) => e.id_eot_vmt_hex === empresa || e.eot_nombre === empresa)

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
          {puedeEditar && (
            <button className="btn btn-primary" onClick={handleOpenCreate}>
              <Plus size={16} /> Nuevo Bus
            </button>
          )}
        </div>
      </div>

      {/* Filtros */}
      <div className="card" style={{ marginBottom: '20px', padding: '16px 20px' }}>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          <div className="search-bar">
            <Search size={15} className="icon" />
            <input
              ref={searchRef}
              autoFocus
              placeholder="Buscar por RUA o Nº Chassis..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  refetch()
                }
              }}
              aria-label="Buscar buses por RUA o chasis"
            />
          </div>

          {/* Filtro Número de Orden: modo + input con autocomplete */}
          <select
            className="form-control"
            style={{ width: 110, fontSize: '0.78rem' }}
            value={ordenModo}
            onChange={e => {
              setOrdenModo(e.target.value as 'igual' | 'contiene')
              if (ordenFiltro) {
                setPage(1)
              }
            }}
            title="Modo de búsqueda del Nº Orden"
          >
            <option value="contiene">Contiene</option>
            <option value="igual">Es igual</option>
          </select>

          <div ref={ordenRef} style={{ position: 'relative' }}>
            <div className="search-bar" style={{ minWidth: 150 }}>
              <Hash size={14} className="icon" />
              <input
                placeholder="Nº Orden..."
                value={ordenSelected !== null ? String(ordenSelected) : ordenInput}
                onChange={e => {
                  const v = e.target.value
                  setOrdenInput(v)
                  if (ordenSelected !== null) { setOrdenSelected(null) }
                  setOrdenOpen(true)
                }}
                onFocus={() => setOrdenOpen(true)}
                onKeyDown={e => {
                  if (e.key === 'Escape') { setOrdenOpen(false) }
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    const val = ordenSelected !== null ? String(ordenSelected) : ordenInput.trim()
                    setOrdenFiltro(val)
                    setOrdenOpen(false)
                    setPage(1)
                  }
                  if (e.key === 'Backspace' && ordenSelected !== null) {
                    setOrdenSelected(null)
                    setOrdenInput('')
                    setOrdenFiltro('')
                    setPage(1)
                  }
                }}
                aria-label="Filtrar por número de orden"
              />
              {(ordenSelected !== null || ordenInput || ordenFiltro) && (
                <button
                  type="button"
                  onClick={() => {
                    setOrdenSelected(null)
                    setOrdenInput('')
                    setOrdenFiltro('')
                    setOrdenOpen(false)
                    setPage(1)
                  }}
                  style={{ background: 'none', border: 'none', padding: '0 4px', cursor: 'pointer',
                    color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}
                  title="Limpiar filtro"
                >
                  <X size={13} />
                </button>
              )}
            </div>
            {ordenOpen && ordenOpciones.length > 0 && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, zIndex: 100,
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: 8, marginTop: 4, minWidth: 220, maxHeight: 260,
                overflowY: 'auto', boxShadow: '0 4px 20px rgba(0,0,0,0.35)'
              }}>
                {ordenOpciones.map(op => (
                  <div
                    key={op.numero_orden}
                    onMouseDown={e => {
                      e.preventDefault()
                      setOrdenSelected(op.numero_orden)
                      setOrdenInput('')
                      setOrdenFiltro(String(op.numero_orden))
                      setOrdenOpen(false)
                      setPage(1)
                    }}
                    style={{
                      padding: '8px 14px', cursor: 'pointer', display: 'flex',
                      gap: 10, alignItems: 'center', fontSize: '0.85rem',
                      background: ordenSelected === op.numero_orden ? 'var(--bg-hover)' : 'transparent',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                    onMouseLeave={e => (e.currentTarget.style.background =
                      ordenSelected === op.numero_orden ? 'var(--bg-hover)' : 'transparent')}
                  >
                    <span style={{ fontWeight: 700, fontFamily: 'monospace', minWidth: 36 }}>
                      {op.numero_orden}
                    </span>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>{op.rua}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <select className="form-control" style={{ maxWidth: '240px' }}
            value={empresa} onChange={e => handleEmpresaChange(e.target.value)}>
            <option value="">Todas las empresas</option>
            {empresasLista.map((e: any) => (
              <option key={e.eot_id} value={e.id_eot_vmt_hex}>
                {e.eot_nombre}
              </option>
            ))}
          </select>

          <select className="form-control" style={{ width: '160px' }}
            value={estadoBus} onChange={e => {
              const val = e.target.value
              setEstadoBus(val)
              setPage(1)
              syncParams({ estado_bus: val })
            }}>
            <option value="">Todos los estados</option>
            <option value="ACTIVO">Activo</option>
            <option value="BAJA">Baja</option>
            <option value="INACTIVO">Inactivo</option>
          </select>
          <select className="form-control" style={{ width: '180px' }}
            value={estadoItv} onChange={e => {
              const val = e.target.value
              setEstadoItv(val)
              setPage(1)
              syncParams({ estado_itv: val })
            }}>
            <option value="">Todos los ITV</option>
            <option value="VIGENTE">ITV Vigente</option>
            <option value="POR_VENCER">Por Vencer</option>
            <option value="CRITICO">Crítico</option>
            <option value="VENCIDO">Vencido</option>
            <option value="SIN_ITV">Sin ITV</option>
          </select>

          {empresa && (
            <button
              className="btn btn-secondary btn-sm"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                background: 'rgba(33,150,243,0.12)',
                color: '#82b1ff',
                borderColor: 'rgba(33,150,243,0.3)',
                fontSize: '0.78rem'
              }}
              onClick={() => handleEmpresaChange('')}
            >
              <Building2 size={13} />
              Empresa: <strong>{empSeleccionadaObj?.eot_nombre ?? empresa}</strong>
              <X size={13} style={{ marginLeft: 2 }} />
            </button>
          )}
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
                    <th>Chasis</th>
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
                      <td style={{ fontFamily: 'monospace', fontSize: '0.78rem', maxWidth: '160px',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        title={bus.numero_chassis ?? ''}>
                        {bus.numero_chassis ?? '—'}
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
                      <td style={{ whiteSpace: 'nowrap' }}>
                        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              fontSize: '0.75rem',
                              padding: '4px 8px',
                              color: '#82b1ff',
                              borderColor: 'rgba(33,150,243,0.3)',
                              background: 'rgba(33,150,243,0.08)'
                            }}
                            onClick={() => handleOpenHistory(bus)}
                            title="Ver histórico de ITV de este bus"
                          >
                            <Clock size={13} /> Ver hist. ITV
                          </button>
                          <button
                            className="btn btn-secondary btn-sm"
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              fontSize: '0.75rem',
                              padding: '4px 8px',
                              color: '#6ee7b7',
                              borderColor: 'rgba(16,185,129,0.35)',
                              background: 'rgba(16,185,129,0.08)'
                            }}
                            onClick={() => handleOpenSeguroHistory(bus)}
                            title="Ver histórico de seguro de este bus"
                          >
                            <Shield size={13} /> Ver hist. Seguro
                          </button>

                          {puedeEditar && (
                            <button
                              className="btn btn-secondary btn-sm btn-icon"
                              onClick={() => handleOpenEdit(bus)}
                              title="Editar bus"
                            >
                              <Edit2 size={14} />
                            </button>
                          )}
                          {puedeEditar && (bus.estado_bus || '').toUpperCase() !== 'BAJA' && (
                            <button
                              className="btn btn-secondary btn-sm btn-icon"
                              onClick={() => handleOpenBaja(bus)}
                              title="Dar de baja"
                              style={{ color: '#f87171', borderColor: 'rgba(248,113,113,0.35)' }}
                            >
                              <Ban size={14} />
                            </button>
                          )}
                        </div>
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

      <BajaModal
        isOpen={isBajaOpen}
        onClose={() => setIsBajaOpen(false)}
        onSuccess={() => refetch()}
        bus={busToBaja}
      />

      <ItvHistoryModal
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        busId={selectedBusForHistory?.id_bus ?? 0}
        busRua={selectedBusForHistory?.rua}
        onEditItv={handleOpenEditItv}
      />

      <SeguroHistoryModal
        isOpen={isSeguroHistoryOpen}
        onClose={() => setIsSeguroHistoryOpen(false)}
        busId={selectedBusForHistory?.id_bus ?? 0}
        busRua={selectedBusForHistory?.rua}
      />

      <ItvModal
        isOpen={isItvModalOpen}
        onClose={() => setIsItvModalOpen(false)}
        itvToEdit={itvToEdit}
        onSuccess={() => {
          setIsItvModalOpen(false)
          refetch()
        }}
      />
    </div>
  )
}
