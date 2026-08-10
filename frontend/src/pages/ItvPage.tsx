import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { itvApi } from '../api'
import { Search, RefreshCw, Plus, Edit2, Clock } from 'lucide-react'
import ItvModal from '../components/itv/ItvModal'
import ItvHistoryModal from '../components/itv/ItvHistoryModal'

export default function ItvPage() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 20
  const searchRef = useRef<HTMLInputElement>(null)

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [selectedItv, setSelectedItv] = useState<any>(null)
  const [selectedBusId, setSelectedBusId] = useState<number>(0)

  const anyModalOpen = isModalOpen || isHistoryOpen

  useEffect(() => {
    if (anyModalOpen) return
    const t = window.setTimeout(() => searchRef.current?.focus(), 0)
    return () => window.clearTimeout(t)
  }, [anyModalOpen])

  const { data, isLoading, refetch } = useQuery<{ data: { items: any[]; total: number } }>({
    queryKey: ['itv', page, search],
    queryFn: () => itvApi.listar({ page, page_size: PAGE_SIZE, ...(search && { search }) }),
  })

  const items = data?.data?.items ?? []

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-header-title">Inspección Técnica Vehicular (ITV)</h1>
          <p className="page-header-sub">Registro y control de vigencia de inspeciones técnicas</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary btn-sm" onClick={() => refetch()}>
            <RefreshCw size={14} /> Actualizar
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => {
            setSelectedItv(null)
            setIsModalOpen(true)
          }}>
            <Plus size={14} /> Nuevo Registro
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '20px', padding: '16px 20px' }}>
        <div className="search-bar">
          <Search size={15} className="icon" />
          <input
            ref={searchRef}
            autoFocus
            placeholder="Buscar por RUA o N° Certificado..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            onKeyDown={e => {
              if (e.key === 'Enter') {
                e.preventDefault()
                refetch()
              }
            }}
            aria-label="Buscar ITV por RUA o certificado"
          />
        </div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {isLoading ? (
          <div className="loading-spinner"><div className="spinner" /></div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">🔧</div>
            <div className="empty-title">No hay inspecciones registradas</div>
            <p>No se encontraron inspecciones con los filtros ingresados.</p>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>ID Bus</th>
                  <th>Fecha ITV</th>
                  <th>Fecha Vencimiento</th>
                  <th>Resultado</th>
                  <th>Centro ITV</th>
                  <th>N° Certificado</th>
                  <th>Estado</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {items.map((itv: any) => (
                  <tr key={itv.id_itv}>
                    <td>#{itv.id_itv}</td>
                    <td style={{ fontWeight: 600 }}>Bus #{itv.id_bus}</td>
                    <td>{new Date(itv.fecha_itv).toLocaleDateString('es-PY')}</td>
                    <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {new Date(itv.fecha_vencimiento).toLocaleDateString('es-PY')}
                    </td>
                    <td>
                      <span className={`badge ${itv.resultado_itv === 'TOTAL' ? 'badge-vigente' : 'badge-por-vencer'}`}>
                        {itv.resultado_itv || 'PARCIAL'}
                      </span>
                    </td>
                    <td>{itv.centro_itv || '—'}</td>
                    <td>{itv.numero_certificado || '—'}</td>
                    <td>
                      <span className={`badge ${
                        itv.estado_itv === 'VIGENTE' ? 'badge-vigente' :
                        itv.estado_itv === 'POR_VENCER' ? 'badge-por-vencer' : 'badge-vencido'
                      }`}>
                        {itv.estado_itv}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        className="btn btn-sm"
                        style={{ background: 'transparent', padding: '4px', color: 'var(--primary)' }}
                        onClick={() => {
                          setSelectedItv(itv)
                          setIsModalOpen(true)
                        }}
                        title="Editar ITV"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        className="btn btn-sm"
                        style={{ background: 'transparent', padding: '4px', color: '#10b981', marginLeft: '5px' }}
                        onClick={() => {
                          setSelectedBusId(itv.id_bus)
                          setIsHistoryOpen(true)
                        }}
                        title="Ver Historial"
                      >
                        <Clock size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ItvModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        itvToEdit={selectedItv}
        onSuccess={() => {
          setIsModalOpen(false)
          refetch()
        }}
      />

      <ItvHistoryModal
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        busId={selectedBusId}
      />
    </div>
  )
}
