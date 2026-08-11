import { useEffect, useState } from 'react'
import { X, Ban } from 'lucide-react'
import { busesApi } from '../../api'
import { formatApiError } from '../../api/client'

const CAUSALES = [
  { codigo: 'ANTIGUEDAD_20', label: 'Antigüedad +20 años' },
  { codigo: 'SOLICITUD_EMPRESA', label: 'Solicitud de la empresa' },
  { codigo: 'ACCIDENTE', label: 'Accidente / siniestro' },
  { codigo: 'INCENDIO', label: 'Incendio' },
  { codigo: 'ITV_VENCIDA', label: 'ITV vencida' },
  { codigo: 'RESOLUCION', label: 'Resolución / MEU' },
  { codigo: 'OTRO', label: 'Otro' },
]

interface BajaModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  bus?: {
    id_bus: number
    rua?: string
    numero_chassis?: string
    empresa_actual?: string | null
    estado_bus?: string
    itv_estado?: string
  } | null
}

export default function BajaModal({ isOpen, onClose, onSuccess, bus }: BajaModalProps) {
  const [fechaBaja, setFechaBaja] = useState(new Date().toISOString().slice(0, 10))
  const [causal, setCausal] = useState('SOLICITUD_EMPRESA')
  const [detalle, setDetalle] = useState('')
  const [normativa, setNormativa] = useState('')
  const [observaciones, setObservaciones] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!isOpen) return
    setFechaBaja(new Date().toISOString().slice(0, 10))
    setCausal('SOLICITUD_EMPRESA')
    setDetalle('')
    setNormativa('')
    setObservaciones('')
    setError('')
  }, [isOpen, bus?.id_bus])

  useEffect(() => {
    if (!isOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !loading) {
        e.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [isOpen, loading, onClose])

  if (!isOpen || !bus) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (causal === 'OTRO' && !detalle.trim()) {
      setError('Indique el detalle de la causal.')
      return
    }
    setLoading(true)
    setError('')
    try {
      await busesApi.darDeBaja(bus.id_bus, {
        fecha_baja: fechaBaja,
        causal,
        causal_detalle: detalle.trim() || observaciones.trim() || undefined,
        normativa: normativa.trim() || undefined,
        observaciones: observaciones.trim() || undefined,
      })
      onSuccess()
      onClose()
    } catch (err: unknown) {
      setError(formatApiError(err, 'No se pudo dar de baja el bus.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Dar de baja"
      style={{
        position: 'fixed', inset: 0, backgroundColor: 'rgba(15, 23, 42, 0.65)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, backdropFilter: 'blur(4px)',
      }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !loading) onClose()
      }}
    >
      <div className="modal-content card" style={{ width: '100%', maxWidth: '520px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>Dar de baja</h3>
          <button type="button" className="btn-icon btn" onClick={onClose} disabled={loading} aria-label="Cerrar">
            <X size={18} />
          </button>
        </div>

        <p style={{ margin: '0 0 1rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
          RUA <strong>{bus.rua || '—'}</strong>
          {bus.numero_chassis ? ` · ${bus.numero_chassis}` : ''}
          {bus.empresa_actual ? ` · ${bus.empresa_actual}` : ' · sin asignación vigente'}
        </p>

        <div style={{
          padding: '0.75rem 1rem', borderRadius: 8, marginBottom: '1rem',
          background: 'rgba(245, 158, 11, 0.12)', color: 'var(--text-primary)', fontSize: '0.8125rem',
        }}>
          Esta acción pasa el bus a <strong>BAJA</strong>, cierra la asignación vigente
          e invalida el ITV vigente. El histórico de ITV se conserva.
        </div>

        {error && (
          <div style={{
            padding: '0.75rem 1rem', borderRadius: 8, backgroundColor: '#FEE2E2',
            color: '#991B1B', marginBottom: '1rem', fontSize: '0.875rem',
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '0.85rem' }}>
          <div>
            <label className="form-label" htmlFor="baja-fecha">Fecha de baja *</label>
            <input
              id="baja-fecha"
              type="date"
              className="form-control"
              required
              value={fechaBaja}
              onChange={e => setFechaBaja(e.target.value)}
            />
          </div>

          <div>
            <label className="form-label" htmlFor="baja-causal">Motivo / causal *</label>
            <select
              id="baja-causal"
              className="form-control"
              value={causal}
              onChange={e => setCausal(e.target.value)}
            >
              {CAUSALES.map(c => (
                <option key={c.codigo} value={c.codigo}>{c.label}</option>
              ))}
            </select>
          </div>

          {(causal === 'OTRO' || causal === 'RESOLUCION' || causal === 'ITV_VENCIDA') && (
            <div>
              <label className="form-label" htmlFor="baja-detalle">
                {causal === 'OTRO' ? 'Detalle del motivo *' : 'Detalle'}
              </label>
              <input
                id="baja-detalle"
                type="text"
                className="form-control"
                required={causal === 'OTRO'}
                value={detalle}
                onChange={e => setDetalle(e.target.value)}
                placeholder={causal === 'OTRO' ? 'Describa el motivo' : 'Opcional'}
              />
            </div>
          )}

          <div>
            <label className="form-label" htmlFor="baja-meu">Nº MEU / normativa</label>
            <input
              id="baja-meu"
              type="text"
              className="form-control"
              value={normativa}
              onChange={e => setNormativa(e.target.value)}
              placeholder="ej. RES GVMT Nº 35/2022"
            />
          </div>

          <div>
            <label className="form-label" htmlFor="baja-obs">Observaciones</label>
            <textarea
              id="baja-obs"
              className="form-control"
              rows={2}
              value={observaciones}
              onChange={e => setObservaciones(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.25rem' }}>
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              <Ban size={16} />
              <span>{loading ? 'Aplicando…' : 'Confirmar baja'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
