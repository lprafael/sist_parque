import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { empresasApi } from '../api'
import { Search, Building2, Bus, ArrowRight } from 'lucide-react'

export default function EmpresasPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [page, setPage]     = useState(1)
  const PAGE_SIZE = 20

  const { data, isLoading } = useQuery<{ data: { items: any[]; total: number } }>({
    queryKey: ['empresas', page, search],
    queryFn: () => empresasApi.listar({
      page, page_size: PAGE_SIZE, solo_activas: true, solo_permisionarias: true,
      ...(search && { search }),
    }),
  })

  const empresas = data?.data?.items ?? []
  const total    = data?.data?.total ?? 0

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-header-title">Empresas Operadoras</h1>
          <p className="page-header-sub">
            {total} empresas permisionarias (activas en CID o con parque asignado)
          </p>
        </div>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: '6px',
          background: 'rgba(33,150,243,0.12)', color: '#82b1ff',
          border: '1px solid rgba(33,150,243,0.25)',
          borderRadius: 'var(--radius-md)', padding: '6px 12px', fontSize: '0.75rem',
        }}>
          🔒 Read-only · public.eots
        </div>
      </div>

      <div className="card" style={{ marginBottom: '20px', padding: '14px 20px' }}>
        <div className="search-bar" style={{ maxWidth: '360px' }}>
          <Search size={15} className="icon" />
          <input
            placeholder="Buscar por nombre, línea, código o email..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
          />
        </div>
      </div>

      {isLoading ? (
        <div className="loading-spinner"><div className="spinner" /></div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '14px' }}>
          {empresas.map((emp: any) => (
            <div
              key={emp.eot_id}
              className="card"
              style={{
                padding: '18px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                transition: 'border-color 0.2s ease, transform 0.2s ease',
              }}
            >
              <div>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                  <div className="kpi-icon blue" style={{ width: '44px', height: '44px', flexShrink: 0 }}>
                    <Building2 size={20} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: '0.88rem', marginBottom: '4px',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {emp.eot_nombre}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                      ID EOT: <strong style={{ color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                        {emp.id_eot_vmt_hex}
                      </strong>
                    </div>
                    {emp.eot_linea && (
                      <div style={{ fontSize: '0.73rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                        Líneas: {emp.eot_linea.trim()}
                      </div>
                    )}
                    <div style={{ display: 'flex', gap: '12px', fontSize: '0.73rem' }}>
                      <span style={{ color: 'var(--text-muted)' }}>
                        <Bus size={11} style={{ display: 'inline', marginRight: 3 }} />
                        {emp.operativo ?? 0} operativos
                      </span>
                      <span style={{ color: 'var(--text-muted)' }}>
                        {emp.autorizado ?? 0} autorizados
                      </span>
                    </div>
                  </div>
                </div>
                {emp.e_mail && (
                  <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid var(--border)',
                    fontSize: '0.73rem', color: 'var(--text-muted)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {emp.e_mail.trim()}
                  </div>
                )}
              </div>

              <button
                className="btn btn-secondary btn-sm"
                style={{
                  marginTop: '14px',
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  color: '#82b1ff',
                  borderColor: 'rgba(33,150,243,0.25)',
                  background: 'rgba(33,150,243,0.08)'
                }}
                onClick={() => navigate(`/buses?empresa=${emp.id_eot_vmt_hex}`)}
              >
                <Bus size={13} /> Ver Buses de Empresa <ArrowRight size={13} />
              </button>
            </div>
          ))}
        </div>
      )}

      {Math.ceil(total / PAGE_SIZE) > 1 && (
        <div className="pagination" style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', marginTop: '16px' }}>
          <span className="pagination-info">{(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} de {total}</span>
          <div className="pagination-controls">
            <button className="page-btn" disabled={page === 1} onClick={() => setPage(p => p - 1)}>‹</button>
            <button className="page-btn" disabled={page >= Math.ceil(total / PAGE_SIZE)} onClick={() => setPage(p => p + 1)}>›</button>
          </div>
        </div>
      )}
    </div>
  )
}
