import { useState } from 'react'
import { Upload, FileSpreadsheet, CheckCircle, AlertCircle } from 'lucide-react'
import { importadorApi } from '../api'

export default function ImportadorPage() {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
      setResult(null)
      setError('')
    }
  }

  const handleUpload = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await importadorApi.uploadExcel(formData)
      setResult(res.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al procesar la plantilla Excel.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-header-title">Importador Masivo (Excel)</h1>
          <p className="page-header-sub">Carga y sincronización masiva de datos de vehículos e inspecciones desde planillas `.xlsx`</p>
        </div>
      </div>

      <div className="card" style={{ maxWidth: '650px', margin: '0 auto', textAlign: 'center', padding: '2.5rem' }}>
        <FileSpreadsheet size={48} style={{ color: 'var(--primary-color)', marginBottom: '1rem' }} />
        <h3 style={{ fontSize: '1.2rem', fontWeight: 600, marginBottom: '0.5rem' }}>
          Selecciona tu archivo de Base de Datos ITV
        </h3>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
          Formatos compatibles: .xlsx, .xls (Ejemplo: ITV - 2026 Base de Datos 30-06-26.xlsx)
        </p>

        <input
          type="file"
          id="excel-input"
          accept=".xlsx, .xls"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />

        <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
          <label htmlFor="excel-input" className="btn btn-secondary" style={{ cursor: 'pointer' }}>
            <Upload size={16} />
            <span>{file ? file.name : 'Buscar archivo...'}</span>
          </label>
        </div>

        {file && (
          <button
            className="btn btn-primary"
            onClick={handleUpload}
            disabled={loading}
            style={{ width: '100%', maxWidth: '280px' }}
          >
            {loading ? 'Procesando Planilla...' : 'Iniciar Importación Masiva'}
          </button>
        )}

        {error && (
          <div style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: '#FEE2E2', color: '#991B1B', borderRadius: '8px', textAlign: 'left', display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <AlertCircle size={20} />
            <div>{error}</div>
          </div>
        )}

        {result && (
          <div style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: '#DCFCE7', color: '#166534', borderRadius: '8px', textAlign: 'left', display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <CheckCircle size={20} />
            <div>
              <strong>¡Importación exitosa!</strong>
              <div style={{ fontSize: '0.85rem', marginTop: '4px' }}>
                {result.mensaje} ({result.filas_detectadas} filas procesadas).
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
