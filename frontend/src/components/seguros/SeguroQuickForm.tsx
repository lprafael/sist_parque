import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { busesApi, segurosApi } from '../../api'
import { formatApiError } from '../../api/client'

type TipoSeguro = { id_tipo_seguro: number; nombre: string }
type Compania = { id_compania: number; nombre: string }
type BusHit = { id_bus: number; rua?: string; numero_chassis?: string; año?: number }

const emptyForm = () => ({
  rua: '',
  id_tipo_seguro: '',
  fecha_vencimiento: '',
  fecha_inicio: new Date().toISOString().slice(0, 10),
  id_compania: '',
  numero_poliza: '',
})

interface SeguroQuickFormProps {
  onSuccess: () => void
}

export default function SeguroQuickForm({ onSuccess }: SeguroQuickFormProps) {
  const [form, setForm] = useState(emptyForm)
  const [bus, setBus] = useState<BusHit | null>(null)
  const [busHint, setBusHint] = useState('')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const ruaRef = useRef<HTMLInputElement>(null)
  const tipoRef = useRef<HTMLSelectElement>(null)
  const vencRef = useRef<HTMLInputElement>(null)
  const inicioRef = useRef<HTMLInputElement>(null)
  const companiaRef = useRef<HTMLSelectElement>(null)
  const polizaRef = useRef<HTMLInputElement>(null)

  const fieldRefs = [ruaRef, tipoRef, vencRef, inicioRef, companiaRef, polizaRef] as const

  const { data: tiposData } = useQuery({
    queryKey: ['seguros-tipos'],
    queryFn: () => segurosApi.tipos(),
  })
  const { data: companiasData } = useQuery({
    queryKey: ['seguros-companias'],
    queryFn: () => segurosApi.companias(),
  })

  const tipos: TipoSeguro[] = tiposData?.data ?? []
  const companias: Compania[] = companiasData?.data ?? []

  const focusFirst = useCallback(() => {
    requestAnimationFrame(() => {
      ruaRef.current?.focus()
      ruaRef.current?.select()
    })
  }, [])

  const focusAt = useCallback((index: number) => {
    const refs = [ruaRef, tipoRef, vencRef, inicioRef, companiaRef, polizaRef]
    const el = refs[index]?.current
    if (!el) return
    requestAnimationFrame(() => {
      el.focus()
      if (el instanceof HTMLInputElement && el.type !== 'date') {
        el.select()
      }
    })
  }, [])

  useEffect(() => {
    focusFirst()
  }, [focusFirst])

  // Prefijar tipo PASAJEROS si existe
  useEffect(() => {
    if (!form.id_tipo_seguro && tipos.length) {
      const pas = tipos.find((t) => t.nombre.toUpperCase() === 'PASAJEROS') || tipos[0]
      setForm((p) => ({ ...p, id_tipo_seguro: String(pas.id_tipo_seguro) }))
    }
  }, [tipos, form.id_tipo_seguro])

  const resolveBus = async (ruaRaw: string): Promise<BusHit | null> => {
    const rua = ruaRaw.trim().toUpperCase()
    if (!rua) {
      setBus(null)
      setBusHint('')
      return null
    }
    try {
      const res = await busesApi.listar({ search: rua, page_size: 10, page: 1 })
      const items: BusHit[] = res.data?.items ?? []
      const exact =
        items.find((b) => (b.rua || '').toUpperCase() === rua) ||
        items.find((b) => (b.numero_chassis || '').toUpperCase() === rua) ||
        null
      if (exact) {
        setBus(exact)
        setBusHint(`${exact.rua || '—'} · chasis ${exact.numero_chassis || '—'} · #${exact.id_bus}`)
        return exact
      }
      setBus(null)
      setBusHint(items.length ? 'RUA no exacta. Revisá el valor.' : 'Bus no encontrado')
      return null
    } catch {
      setBus(null)
      setBusHint('Error al buscar el bus')
      return null
    }
  }

  const resetForm = (keepTipo = true) => {
    const tipo = keepTipo ? form.id_tipo_seguro : ''
    setForm({ ...emptyForm(), id_tipo_seguro: tipo })
    setBus(null)
    setBusHint('')
    setError('')
    focusFirst()
  }

  const submit = async () => {
    setError('')
    setStatus('')
    setLoading(true)
    try {
      let resolved = bus
      if (!resolved || (resolved.rua || '').toUpperCase() !== form.rua.trim().toUpperCase()) {
        resolved = await resolveBus(form.rua)
      }
      if (!resolved) {
        setError('Ingresá una RUA válida de un bus registrado.')
        focusAt(0)
        return
      }
      if (!form.id_tipo_seguro) {
        setError('Seleccioná el tipo de seguro.')
        focusAt(1)
        return
      }
      if (!form.fecha_vencimiento) {
        setError('Ingresá la fecha de vencimiento.')
        focusAt(2)
        return
      }
      if (!form.fecha_inicio) {
        setError('Ingresá la fecha de inicio.')
        focusAt(3)
        return
      }

      await segurosApi.crear({
        id_bus: resolved.id_bus,
        id_tipo_seguro: Number(form.id_tipo_seguro),
        id_compania: form.id_compania ? Number(form.id_compania) : null,
        numero_poliza: form.numero_poliza.trim() || null,
        fecha_inicio: form.fecha_inicio,
        fecha_vencimiento: form.fecha_vencimiento,
        seguro_vigente: true,
      })

      const tipoNom =
        tipos.find((t) => t.id_tipo_seguro === Number(form.id_tipo_seguro))?.nombre || 'Seguro'
      setStatus(`Guardado: ${resolved.rua || resolved.id_bus} · ${tipoNom} · vence ${form.fecha_vencimiento}`)
      onSuccess()
      resetForm(true)
    } catch (err) {
      setError(formatApiError(err, 'No se pudo guardar el seguro.'))
      focusFirst()
    } finally {
      setLoading(false)
    }
  }

  const onFieldKeyDown = async (
    e: React.KeyboardEvent<HTMLInputElement | HTMLSelectElement>,
    index: number,
  ) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      resetForm(true)
      return
    }
    if (e.key !== 'Enter') return
    e.preventDefault()

    // En RUA: resolver bus y avanzar
    if (index === 0) {
      const found = await resolveBus(form.rua)
      if (!found) {
        setError('Bus no encontrado. Corregí la RUA.')
        focusAt(0)
        return
      }
      setError('')
      focusAt(1)
      return
    }

    // Último campo → guardar
    if (index === fieldRefs.length - 1) {
      await submit()
      return
    }

    focusAt(index + 1)
  }

  const set = (key: keyof ReturnType<typeof emptyForm>, value: string) => {
    setForm((p) => ({ ...p, [key]: value }))
    setStatus('')
  }

  return (
    <div className="card" style={{ marginBottom: 20, padding: '16px 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>Carga rápida de seguro</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Enter avanza de campo · Tab entre campos · Enter en el último guarda y vuelve a RUA · Esc limpia
          </div>
        </div>
        {busHint && (
          <div style={{ fontSize: '0.8rem', color: bus ? 'var(--success, #166534)' : 'var(--danger, #991b1b)' }}>
            {busHint}
          </div>
        )}
      </div>

      {error && (
        <div className="error-message" style={{ marginBottom: 12 }}>{error}</div>
      )}
      {status && !error && (
        <div
          style={{
            marginBottom: 12,
            padding: '8px 12px',
            borderRadius: 8,
            background: '#DCFCE7',
            color: '#166534',
            fontSize: '0.85rem',
          }}
        >
          {status}
        </div>
      )}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: 12,
          alignItems: 'end',
        }}
      >
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">RUA *</label>
          <input
            ref={ruaRef}
            className="form-control"
            value={form.rua}
            autoComplete="off"
            placeholder="Ej. BRT560"
            onChange={(e) => {
              set('rua', e.target.value.toUpperCase())
              setBus(null)
              setBusHint('')
            }}
            onKeyDown={(e) => onFieldKeyDown(e, 0)}
            onBlur={() => {
              if (form.rua.trim()) void resolveBus(form.rua)
            }}
            disabled={loading}
          />
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Tipo *</label>
          <select
            ref={tipoRef}
            className="form-control"
            value={form.id_tipo_seguro}
            onChange={(e) => set('id_tipo_seguro', e.target.value)}
            onKeyDown={(e) => onFieldKeyDown(e, 1)}
            disabled={loading}
          >
            {tipos.map((t) => (
              <option key={t.id_tipo_seguro} value={t.id_tipo_seguro}>
                {t.nombre}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Vencimiento *</label>
          <input
            ref={vencRef}
            type="date"
            className="form-control"
            value={form.fecha_vencimiento}
            onChange={(e) => set('fecha_vencimiento', e.target.value)}
            onKeyDown={(e) => onFieldKeyDown(e, 2)}
            disabled={loading}
          />
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Inicio *</label>
          <input
            ref={inicioRef}
            type="date"
            className="form-control"
            value={form.fecha_inicio}
            onChange={(e) => set('fecha_inicio', e.target.value)}
            onKeyDown={(e) => onFieldKeyDown(e, 3)}
            disabled={loading}
          />
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Compañía</label>
          <select
            ref={companiaRef}
            className="form-control"
            value={form.id_compania}
            onChange={(e) => set('id_compania', e.target.value)}
            onKeyDown={(e) => onFieldKeyDown(e, 4)}
            disabled={loading}
          >
            <option value="">— Sin compañía —</option>
            {companias.map((c) => (
              <option key={c.id_compania} value={c.id_compania}>
                {c.nombre}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">N° Póliza</label>
          <input
            ref={polizaRef}
            className="form-control"
            value={form.numero_poliza}
            autoComplete="off"
            placeholder="Opcional"
            onChange={(e) => set('numero_poliza', e.target.value)}
            onKeyDown={(e) => onFieldKeyDown(e, 5)}
            disabled={loading}
          />
        </div>
      </div>

      <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={() => void submit()}
          disabled={loading}
        >
          {loading ? 'Guardando...' : 'Guardar (Enter en póliza)'}
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => resetForm(true)}
          disabled={loading}
        >
          Limpiar (Esc)
        </button>
      </div>
    </div>
  )
}
