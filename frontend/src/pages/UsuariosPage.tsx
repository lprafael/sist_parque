import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { usuariosApi } from '../api'
import { RefreshCw } from 'lucide-react'

export default function UsuariosPage() {
  const [page] = useState(1)

  const { data, isLoading, refetch } = useQuery<{ data: { items: any[] } }>({
    queryKey: ['usuarios', page],
    queryFn: () => usuariosApi.listar({ page, page_size: 20 }),
  })

  const usuarios = data?.data?.items ?? []

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-header-title">Usuarios y Permisos</h1>
          <p className="page-header-sub">Usuarios habilitados en SIGPA (Parque Automotor)</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={() => refetch()}>
          <RefreshCw size={14} /> Actualizar
        </button>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {isLoading ? (
          <div className="loading-spinner"><div className="spinner" /></div>
        ) : usuarios.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">👤</div>
            <div className="empty-title">Sin usuarios adicionales</div>
            <p>Solo existe el usuario administrador actual.</p>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Usuario</th>
                  <th>Nombre Completo</th>
                  <th>Email</th>
                  <th>Rol</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {usuarios.map((u: any) => (
                  <tr key={u.id_usuario}>
                    <td>#{u.id_usuario}</td>
                    <td style={{ fontWeight: 600 }}>{u.username}</td>
                    <td>{u.nombre_completo || '—'}</td>
                    <td>{u.email}</td>
                    <td>
                      <span className="badge badge-primary">
                        {u.rol}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${u.estado_usuario === 'ACTIVO' ? 'badge-vigente' : 'badge-vencido'}`}>
                        {u.estado_usuario}
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
