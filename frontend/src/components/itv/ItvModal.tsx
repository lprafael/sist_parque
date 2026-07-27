import { useState, useEffect } from 'react'
import { X, Save } from 'lucide-react'
import { itvApi } from '../../api'

interface ItvModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  itvToEdit?: any
}

export default function ItvModal({
  isOpen,
  onClose,
  onSuccess,
  itvToEdit
}: ItvModalProps) {
  const [formData, setFormData] = useState({
    id_bus: '',
    fecha_itv: new Date().toISOString().split('T')[0],
    fecha_vencimiento: new Date().toISOString().split('T')[0],
    resultado_itv: 'TOTAL',
    centro_itv: '',
    numero_certificado: '',
    observaciones: ''
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (itvToEdit) {
      setFormData({
        id_bus: itvToEdit.id_bus ? String(itvToEdit.id_bus) : '',
        fecha_itv: itvToEdit.fecha_itv ? new Date(itvToEdit.fecha_itv).toISOString().split('T')[0] : '',
        fecha_vencimiento: itvToEdit.fecha_vencimiento ? new Date(itvToEdit.fecha_vencimiento).toISOString().split('T')[0] : '',
        resultado_itv: itvToEdit.resultado_itv || 'TOTAL',
        centro_itv: itvToEdit.centro_itv || '',
        numero_certificado: itvToEdit.numero_certificado || '',
        observaciones: itvToEdit.observaciones || ''
      })
    } else {
      setFormData({
        id_bus: '',
        fecha_itv: new Date().toISOString().split('T')[0],
        fecha_vencimiento: new Date().toISOString().split('T')[0],
        resultado_itv: 'TOTAL',
        centro_itv: '',
        numero_certificado: '',
        observaciones: ''
      })
    }
    setError('')
  }, [itvToEdit, isOpen])

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    const payload = {
      id_bus: Number(formData.id_bus),
      fecha_itv: formData.fecha_itv,
      fecha_vencimiento: formData.fecha_vencimiento,
      resultado_itv: formData.resultado_itv,
      centro_itv: formData.centro_itv,
      numero_certificado: formData.numero_certificado,
      observaciones: formData.observaciones
    }

    try {
      if (itvToEdit) {
        await itvApi.actualizar(itvToEdit.id_itv, payload)
      } else {
        await itvApi.registrar(payload)
      }
      onSuccess()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al guardar el registro ITV')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '500px' }}>
        <div className="modal-header">
          <h2 className="modal-title">{itvToEdit ? 'Editar ITV' : 'Nuevo Registro ITV'}</h2>
          <button className="modal-close" onClick={onClose} disabled={loading}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          {error && <div className="error-message" style={{ marginBottom: '15px' }}>{error}</div>}

          <div style={{ display: 'grid', gap: '15px' }}>
            <div className="form-group">
              <label className="form-label">ID Bus *</label>
              <input
                type="number"
                className="form-control"
                required
                value={formData.id_bus}
                onChange={e => setFormData(p => ({ ...p, id_bus: e.target.value }))}
                disabled={!!itvToEdit} // No permitir cambiar de bus al editar
              />
              {!itvToEdit && <small style={{ color: 'var(--text-muted)' }}>Ingrese el ID numérico del Bus.</small>}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
              <div className="form-group">
                <label className="form-label">Fecha ITV *</label>
                <input
                  type="date"
                  className="form-control"
                  required
                  value={formData.fecha_itv}
                  onChange={e => setFormData(p => ({ ...p, fecha_itv: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Fecha Vencimiento *</label>
                <input
                  type="date"
                  className="form-control"
                  required
                  value={formData.fecha_vencimiento}
                  onChange={e => setFormData(p => ({ ...p, fecha_vencimiento: e.target.value }))}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
              <div className="form-group">
                <label className="form-label">Resultado</label>
                <select
                  className="form-control"
                  value={formData.resultado_itv}
                  onChange={e => setFormData(p => ({ ...p, resultado_itv: e.target.value }))}
                >
                  <option value="TOTAL">TOTAL</option>
                  <option value="PARCIAL">PARCIAL</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">N° Certificado</label>
                <input
                  type="text"
                  className="form-control"
                  value={formData.numero_certificado}
                  onChange={e => setFormData(p => ({ ...p, numero_certificado: e.target.value }))}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Centro ITV</label>
              <input
                type="text"
                className="form-control"
                value={formData.centro_itv}
                onChange={e => setFormData(p => ({ ...p, centro_itv: e.target.value }))}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Observaciones</label>
              <textarea
                className="form-control"
                rows={3}
                value={formData.observaciones}
                onChange={e => setFormData(p => ({ ...p, observaciones: e.target.value }))}
              />
            </div>
          </div>

          <div className="modal-footer" style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button type="button" className="btn" style={{ background: 'var(--surface)', color: 'var(--text)' }} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              <Save size={16} /> {loading ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
