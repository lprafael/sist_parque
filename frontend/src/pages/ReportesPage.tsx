import { useState } from 'react'
import { FileSpreadsheet, FileText, Download } from 'lucide-react'
import { reportesApi } from '../api'

export default function ReportesPage() {
  const [downloading, setDownloading] = useState(false)

  const handleDescargarExcel = async () => {
    setDownloading(true)
    try {
      const response = await reportesApi.descargarBusesExcel()
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'Parque_Automotor_VMT.xlsx')
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (e) {
      alert('Error al descargar la planilla de reportes.')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-header-title">Centro de Reportes</h1>
          <p className="page-header-sub">Exportación y descarga de resúmenes ejecutivos en Excel y PDF</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ padding: '0.75rem', borderRadius: '8px', backgroundColor: '#DCFCE7', color: '#166534' }}>
              <FileSpreadsheet size={24} />
            </div>
            <div>
              <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Parque Automotor Completo</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Lista de buses con RUA, Chasis, Marcas y estado de ITV.</p>
            </div>
          </div>
          <button
            className="btn btn-primary"
            onClick={handleDescargarExcel}
            disabled={downloading}
            style={{ marginTop: 'auto' }}
          >
            <Download size={16} />
            <span>{downloading ? 'Generando Excel...' : 'Descargar Excel (.xlsx)'}</span>
          </button>
        </div>

        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ padding: '0.75rem', borderRadius: '8px', backgroundColor: '#FEE2E2', color: '#991B1B' }}>
              <FileText size={24} />
            </div>
            <div>
              <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Informe de Vencimientos ITV</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Resumen de vehículos con ITV vencido o por vencer.</p>
            </div>
          </div>
          <button
            className="btn btn-secondary"
            onClick={handleDescargarExcel}
            style={{ marginTop: 'auto' }}
          >
            <Download size={16} />
            <span>Descargar Resumen</span>
          </button>
        </div>
      </div>
    </div>
  )
}
