import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { segurosApi } from '../api'
import { Search, RefreshCw } from 'lucide-react'
import SeguroQuickForm from '../components/seguros/SeguroQuickForm'

export default function SegurosPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const estadoParam = searchParams.get('estado') ?? ''

  const [search, setSearch] = useState('')
  const [estado, setEstado] = useState(estadoParam)
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 20

  useEffect(() => {
    setEstado(estadoParam)
    setPage(1)
  }, [estadoParam])

  const { data, isLoading, refetch } = useQuery<{ data: { items: any[]; total?: number } }>({
    queryKey: ['seguros', page, search, estado],
    queryFn: () => segurosApi.listar({
      page,
      page_size: PAGE_SIZE,
      ...(search && { search }),
      ...(estado && { estado }),
    }),
  })

  const items = data?.data?.items ?? []
  const total = data?.data?.total ?? items.length

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-header-title">Seguros de Buses</h1>
          <p className="page-header-sub">
            {total} póliza(s) · Carga: Empresa EOT → RUA filtrada → tipo → fechas
          </p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={() => refetch()}>
          <RefreshCw size={14} /> Actualizar
        </button>
      </div>

      <SeguroQuickForm onSuccess={() => { setPage(1); void refetch() }} />

      <div className="card" style={{ marginBottom: '20px', padding: '16px 20px' }}>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          <div className="search-bar">
            <Search size={15} className="icon" />
            <input
              placeholder="Buscar por N° Póliza o Bus..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
            />
          </div>
          <select
            className="form-control"
            style={{ width: '180px' }}
            value={estado}
            onChange={(e) => {
              const val = e.target.value
              setEstado(val)
              setPage(1)
              if (val) setSearchParams({ estado: val })
              else setSearchParams({})
            }}
          >
            <option value="">Todos los estados</option>
            <option value="VIGENTE">Vigente</option>
            <option value="POR_VENCER">Por Vencer</option>
            <option value="VENCIDO">Vencido</option>
          </select>
        </div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {isLoading ? (
          <div className="loading-spinner"><div className="spinner" /></div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">🛡️</div>
            <div className="empty-title">No hay pólizas registradas</div>
            <p>Usá el formulario de arriba para cargar el primer seguro.</p>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>ID Bus</th>
                  <th>Tipo Seguro</th>
                  <th>Compañía</th>
                  <th>N° Póliza</th>
                  <th>Vencimiento</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {items.map((seg: any) => (
                  <tr key={seg.id_seguro}>
                    <td>#{seg.id_seguro}</td>
                    <td style={{ fontWeight: 600 }}>Bus #{seg.id_bus}</td>
                    <td>{seg.tipo_seguro_nombre || '—'}</td>
                    <td>{seg.compania_nombre || '—'}</td>
                    <td>{seg.numero_poliza || '—'}</td>
                    <td style={{ fontFamily: 'monospace' }}>
                      {new Date(seg.fecha_vencimiento).toLocaleDateString('es-PY')}
                    </td>
                    <td>
                      <span
                        className={`badge ${
                          seg.seguro_vigente
                            ? seg.estado_calculado === 'VENCIDO'
                              ? 'badge-vencido'
                              : 'badge-vigente'
                            : 'badge-sin-itv'
                        }`}
                      >
                        {seg.seguro_vigente
                          ? seg.estado_calculado || 'VIGENTE'
                          : 'NO VIGENTE'}
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
  )
}
