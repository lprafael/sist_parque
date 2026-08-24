import { useState, useEffect, useRef } from 'react'
import { X, Save } from 'lucide-react'
import { busesApi } from '../../api'
import { formatApiError } from '../../api/client'

interface BusModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  busToEdit?: any
  marcas: any[]
  tiposCarroceria: any[]
  marcasCarroceria: any[]
  tiposServicio: any[]
}

export default function BusModal({
  isOpen,
  onClose,
  onSuccess,
  busToEdit,
  marcas,
  tiposCarroceria,
  marcasCarroceria,
  tiposServicio
}: BusModalProps) {
  const firstFieldRef = useRef<HTMLInputElement>(null)
  const [formData, setFormData] = useState({
    rua: '',
    numero_chassis: '',
    año: new Date().getFullYear(),
    numero_orden: '',
    id_marca: '',
    id_tipo_carroceria: '',
    id_marca_carroceria: '',
    capacidad_pasajeros: '',
    combustible: 'DIESEL',
    color: '',
    estado_bus: 'ACTIVO',
    tiene_rampa: false,
    id_tipo_servicio: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (busToEdit) {
      setFormData({
        rua: busToEdit.rua || '',
        numero_chassis: busToEdit.numero_chassis || '',
        año: busToEdit.año || new Date().getFullYear(),
        numero_orden: busToEdit.numero_orden || '',
        id_marca: busToEdit.id_marca ? String(busToEdit.id_marca) : '',
        id_tipo_carroceria: busToEdit.id_tipo_carroceria ? String(busToEdit.id_tipo_carroceria) : '',
        id_marca_carroceria: busToEdit.id_marca_carroceria ? String(busToEdit.id_marca_carroceria) : '',
        capacidad_pasajeros: busToEdit.capacidad_pasajeros || '',
        combustible: busToEdit.combustible || 'DIESEL',
        color: busToEdit.color || '',
        estado_bus: busToEdit.estado_bus || 'ACTIVO',
        tiene_rampa: Boolean(busToEdit.tiene_rampa),
        id_tipo_servicio: busToEdit.id_tipo_servicio ? String(busToEdit.id_tipo_servicio) : '',
      })
    } else {
      const convencional = tiposServicio.find(
        (t: any) => String(t.nombre || '').toUpperCase() === 'CONVENCIONAL',
      )
      setFormData({
        rua: '',
        numero_chassis: '',
        año: new Date().getFullYear(),
        numero_orden: '',
        id_marca: marcas[0]?.id_marca ? String(marcas[0].id_marca) : '',
        id_tipo_carroceria: tiposCarroceria[0]?.id_tipo ? String(tiposCarroceria[0].id_tipo) : '',
        id_marca_carroceria: marcasCarroceria[0]?.id_marca_carroceria ? String(marcasCarroceria[0].id_marca_carroceria) : '',
        capacidad_pasajeros: '',
        combustible: 'DIESEL',
        color: '',
        estado_bus: 'ACTIVO',
        tiene_rampa: false,
        id_tipo_servicio: convencional?.id_tipo_servicio
          ? String(convencional.id_tipo_servicio)
          : (tiposServicio[0]?.id_tipo_servicio ? String(tiposServicio[0].id_tipo_servicio) : ''),
      })
    }
    setError('')
  }, [busToEdit, isOpen, marcas, tiposCarroceria, marcasCarroceria, tiposServicio])

  // Foco en RUA al abrir (alta y edición)
  useEffect(() => {
    if (!isOpen) return
    const focusFirst = () => {
      const el = firstFieldRef.current
      if (!el) return
      el.focus({ preventScroll: true })
      el.select()
    }
    const raf = requestAnimationFrame(focusFirst)
    const t = window.setTimeout(focusFirst, 120)
    return () => {
      cancelAnimationFrame(raf)
      window.clearTimeout(t)
    }
  }, [isOpen, busToEdit?.id_bus])

  // Escape para cerrar (alta y edición)
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
      rua: formData.rua,
      numero_chassis: formData.numero_chassis,
      año: Number(formData.año),
      numero_orden: formData.numero_orden ? Number(formData.numero_orden) : null,
      id_marca: formData.id_marca ? Number(formData.id_marca) : null,
      id_tipo_carroceria: formData.id_tipo_carroceria ? Number(formData.id_tipo_carroceria) : null,
      id_marca_carroceria: formData.id_marca_carroceria ? Number(formData.id_marca_carroceria) : null,
      capacidad_pasajeros: formData.capacidad_pasajeros ? Number(formData.capacidad_pasajeros) : null,
      combustible: formData.combustible,
      color: formData.color,
      estado_bus: formData.estado_bus,
      tiene_rampa: Boolean(formData.tiene_rampa),
      id_tipo_servicio: formData.id_tipo_servicio ? Number(formData.id_tipo_servicio) : null,
    }

    try {
      if (busToEdit) {
        await busesApi.actualizar(busToEdit.id_bus, payload)
      } else {
        await busesApi.crear(payload)
      }
      onSuccess()
      onClose()
    } catch (err: unknown) {
      setError(formatApiError(err, 'Error al guardar la información del vehículo.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={busToEdit ? 'Editar Vehículo' : 'Registrar Nuevo Bus'}
      style={{
        position: 'fixed', inset: 0, backgroundColor: 'rgba(15, 23, 42, 0.65)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, backdropFilter: 'blur(4px)'
      }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !loading) onClose()
      }}
    >
      <div className="modal-content card" style={{ width: '100%', maxWidth: '650px', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>
            {busToEdit ? 'Editar Vehículo' : 'Registrar Nuevo Bus'}
          </h3>
          <button type="button" className="btn-icon btn" onClick={onClose} disabled={loading} aria-label="Cerrar" tabIndex={-1}>
            <X size={18} />
          </button>
        </div>

        {error && (
          <div style={{ padding: '0.75rem 1rem', borderRadius: '8px', backgroundColor: '#FEE2E2', color: '#991B1B', marginBottom: '1rem', fontSize: '0.875rem' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <div>
            <label className="form-label" htmlFor="bus-rua">RUA / Matrícula *</label>
            <input
              id="bus-rua"
              ref={firstFieldRef}
              type="text"
              className="form-control"
              required
              autoFocus
              autoComplete="off"
              value={formData.rua}
              onChange={e => setFormData({ ...formData, rua: e.target.value.toUpperCase() })}
              placeholder="ej. ABC 123"
            />
          </div>

          <div>
            <label className="form-label" htmlFor="bus-chasis">Número de Chasis *</label>
            <input
              id="bus-chasis"
              type="text"
              className="form-control"
              required
              autoComplete="off"
              value={formData.numero_chassis}
              onChange={e => setFormData({ ...formData, numero_chassis: e.target.value.toUpperCase() })}
              placeholder="Chasis vin/nro"
            />
          </div>

          <div>
            <label className="form-label" htmlFor="bus-anio">Año de Fabricación *</label>
            <input
              id="bus-anio"
              type="number"
              className="form-control"
              required
              value={formData.año}
              onChange={e => setFormData({ ...formData, año: Number(e.target.value) })}
            />
          </div>

          <div>
            <label className="form-label" htmlFor="bus-orden">Número de Orden</label>
            <input
              id="bus-orden"
              type="number"
              className="form-control"
              value={formData.numero_orden}
              onChange={e => setFormData({ ...formData, numero_orden: e.target.value })}
              placeholder="N° correlativo"
            />
          </div>

          <div>
            <label className="form-label" htmlFor="bus-marca">Marca Chasis</label>
            <select
              id="bus-marca"
              className="form-control"
              value={formData.id_marca}
              onChange={e => setFormData({ ...formData, id_marca: e.target.value })}
            >
              <option value="">-- Seleccionar Marca --</option>
              {marcas.map(m => (
                <option key={m.id_marca} value={m.id_marca}>{m.nombre}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="form-label" htmlFor="bus-marca-carr">Marca Carrocería</label>
            <select
              id="bus-marca-carr"
              className="form-control"
              value={formData.id_marca_carroceria}
              onChange={e => setFormData({ ...formData, id_marca_carroceria: e.target.value })}
            >
              <option value="">-- Seleccionar --</option>
              {marcasCarroceria.map(m => (
                <option key={m.id_marca_carroceria} value={m.id_marca_carroceria}>{m.nombre}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="form-label" htmlFor="bus-tipo-carr">Tipo Carrocería</label>
            <select
              id="bus-tipo-carr"
              className="form-control"
              value={formData.id_tipo_carroceria}
              onChange={e => setFormData({ ...formData, id_tipo_carroceria: e.target.value })}
            >
              <option value="">-- Seleccionar Tipo --</option>
              {tiposCarroceria.map(t => (
                <option key={t.id_tipo} value={t.id_tipo}>{t.descripcion}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="form-label" htmlFor="bus-combustible">Combustible</label>
            <select
              id="bus-combustible"
              className="form-control"
              value={formData.combustible}
              onChange={e => setFormData({ ...formData, combustible: e.target.value })}
            >
              <option value="DIESEL">DIESEL</option>
              <option value="ELECTRICO">ELÉCTRICO</option>
              <option value="HIBRIDO">HÍBRIDO</option>
              <option value="NAFTA">NAFTA</option>
            </select>
          </div>

          <div>
            <label className="form-label" htmlFor="bus-estado">Estado Bus</label>
            <select
              id="bus-estado"
              className="form-control"
              value={formData.estado_bus}
              onChange={e => setFormData({ ...formData, estado_bus: e.target.value })}
              disabled={(busToEdit?.estado_bus || '').toUpperCase() === 'BAJA'}
            >
              <option value="ACTIVO">ACTIVO</option>
              <option value="INACTIVO">INACTIVO</option>
              <option value="EN_MANTENIMIENTO">EN MANTENIMIENTO</option>
              {(busToEdit?.estado_bus || '').toUpperCase() === 'BAJA' && (
                <option value="BAJA">BAJA</option>
              )}
            </select>
            {(busToEdit?.estado_bus || '').toUpperCase() !== 'BAJA' && (
              <p style={{ margin: '6px 0 0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Para dar de baja use el botón de la lista (motivo + cierra asignación e ITV).
              </p>
            )}
          </div>

          <div>
            <label className="form-label" htmlFor="bus-rampa">Rampa para discapacitados</label>
            <select
              id="bus-rampa"
              className="form-control"
              value={formData.tiene_rampa ? 'si' : 'no'}
              onChange={e => setFormData({ ...formData, tiene_rampa: e.target.value === 'si' })}
            >
              <option value="no">No</option>
              <option value="si">Sí</option>
            </select>
          </div>

          <div>
            <label className="form-label" htmlFor="bus-tipo-servicio">Tipo de servicio</label>
            <select
              id="bus-tipo-servicio"
              className="form-control"
              value={formData.id_tipo_servicio}
              onChange={e => setFormData({ ...formData, id_tipo_servicio: e.target.value })}
            >
              <option value="">-- Seleccionar --</option>
              {tiposServicio.map(t => (
                <option key={t.id_tipo_servicio} value={t.id_tipo_servicio}>
                  {t.nombre}
                </option>
              ))}
            </select>
          </div>

          <div style={{ gridColumn: 'span 2', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              <Save size={16} />
              <span>{loading ? 'Guardando...' : 'Guardar Bus'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
