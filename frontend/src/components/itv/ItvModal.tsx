import { useState, useEffect, useRef } from 'react'
import { X, Save } from 'lucide-react'
import { itvApi } from '../../api'
import { formatApiError } from '../../api/client'

interface ItvModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  itvToEdit?: any
}

function toDateInput(value?: string | null): string {
  if (!value) return ''
  const raw = String(value)
  if (/^\d{4}-\d{2}-\d{2}/.test(raw)) return raw.slice(0, 10)
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return ''
  return d.toISOString().split('T')[0]
}

export default function ItvModal({
  isOpen,
  onClose,
  onSuccess,
  itvToEdit
}: ItvModalProps) {
  const isEdit = Boolean(itvToEdit?.id_itv)
  const busLocked = Boolean(itvToEdit?.id_bus)
  const firstFieldRef = useRef<HTMLInputElement>(null)

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
        fecha_itv: toDateInput(itvToEdit.fecha_itv) || new Date().toISOString().split('T')[0],
        fecha_vencimiento: toDateInput(itvToEdit.fecha_vencimiento) || new Date().toISOString().split('T')[0],
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

  // Foco en el primer campo editable (alta y edición)
  useEffect(() => {
    if (!isOpen) return
    const focusFirst = () => {
      const el = firstFieldRef.current
      if (!el || el.disabled) return
      el.focus({ preventScroll: true })
      if (el.type !== 'date' && el.type !== 'number') el.select()
    }
    const raf = requestAnimationFrame(focusFirst)
    const t = window.setTimeout(focusFirst, 120)
    return () => {
      cancelAnimationFrame(raf)
      window.clearTimeout(t)
    }
  }, [isOpen, itvToEdit?.id_itv, itvToEdit?.id_bus, busLocked])

  // Escape para cerrar
  useEffect(() => {
    if (!isOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !loading) {
        e.preventDefault()
        e.stopPropagation()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [isOpen, loading, onClose])

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
      centro_itv: formData.centro_itv || null,
      numero_certificado: formData.numero_certificado || null,
      observaciones: formData.observaciones || null
    }

    try {
      if (isEdit) {
        const { id_bus: _idBus, ...updatePayload } = payload
        await itvApi.actualizar(itvToEdit.id_itv, updatePayload)
      } else {
        await itvApi.registrar(payload)
      }
      onSuccess()
    } catch (err: unknown) {
      setError(formatApiError(err, 'Error al guardar el registro ITV'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={isEdit ? 'Editar ITV' : 'Nuevo Registro ITV'}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !loading) onClose()
      }}
    >
      <div className="modal-content" style={{ maxWidth: '500px' }}>
        <div className="modal-header">
          <h2 className="modal-title">{isEdit ? 'Editar ITV' : 'Nuevo Registro ITV'}</h2>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            disabled={loading}
            aria-label="Cerrar"
            tabIndex={-1}
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          {error && <div className="error-message" style={{ marginBottom: '15px' }}>{error}</div>}

          <div style={{ display: 'grid', gap: '15px' }}>
            <div className="form-group">
              <label className="form-label" htmlFor="itv-id-bus">ID Bus *</label>
              <input
                id="itv-id-bus"
                ref={busLocked ? undefined : firstFieldRef}
                type="number"
                className="form-control"
                required
                autoFocus={!busLocked}
                value={formData.id_bus}
                onChange={e => setFormData(p => ({ ...p, id_bus: e.target.value }))}
                disabled={busLocked}
              />
              {!busLocked && <small style={{ color: 'var(--text-muted)' }}>Ingrese el ID numérico del Bus.</small>}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="itv-fecha">Fecha ITV *</label>
                <input
                  id="itv-fecha"
                  ref={busLocked ? firstFieldRef : undefined}
                  type="date"
                  className="form-control"
                  required
                  autoFocus={busLocked}
                  value={formData.fecha_itv}
                  onChange={e => setFormData(p => ({ ...p, fecha_itv: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="itv-venc">Fecha Vencimiento *</label>
                <input
                  id="itv-venc"
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
                <label className="form-label" htmlFor="itv-resultado">Resultado</label>
                <select
                  id="itv-resultado"
                  className="form-control"
                  value={formData.resultado_itv}
                  onChange={e => setFormData(p => ({ ...p, resultado_itv: e.target.value }))}
                >
                  <option value="TOTAL">TOTAL</option>
                  <option value="PARCIAL">PARCIAL</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="itv-cert">N° Certificado</label>
                <input
                  id="itv-cert"
                  type="text"
                  className="form-control"
                  value={formData.numero_certificado}
                  onChange={e => setFormData(p => ({ ...p, numero_certificado: e.target.value }))}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="itv-centro">Centro ITV</label>
              <input
                id="itv-centro"
                type="text"
                className="form-control"
                value={formData.centro_itv}
                onChange={e => setFormData(p => ({ ...p, centro_itv: e.target.value }))}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="itv-obs">Observaciones</label>
              <textarea
                id="itv-obs"
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
