import { useState } from 'react'

export default function DocumentosPage() {
  const [selectedTipo, setSelectedTipo] = useState('TODOS')

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-header-title">Gestión Documental</h1>
          <p className="page-header-sub">Habilitaciones, certificados POD/RTD y documentación digital</p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '20px', padding: '16px 20px' }}>
        <div style={{ display: 'flex', gap: '10px' }}>
          {['TODOS', 'POD', 'RTD', 'HABILITACION', 'CERTIFICADO'].map(t => (
            <button
              key={t}
              className={`btn btn-sm ${selectedTipo === t ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setSelectedTipo(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="empty-state">
          <div className="empty-icon">📁</div>
          <div className="empty-title">Repositorio Documental Digital</div>
          <p>Módulo de almacenamiento y validación de archivos PDF/imágenes de habilitaciones.</p>
        </div>
      </div>
    </div>
  )
}
