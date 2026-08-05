import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Building2, X } from 'lucide-react'
import { empresasApi, segurosApi } from '../../api'
import { formatApiError } from '../../api/client'

type TipoSeguro = { id_tipo_seguro: number; nombre: string }
type Compania = { id_compania: number; nombre: string }
type EotItem = {
  eot_id: number
  id_eot_vmt_hex: string
  eot_nombre?: string
  eot_linea?: string
}
type BusHit = {
  id_bus: number
  rua?: string | null
  numero_chassis?: string | null
  año?: number | null
  estado_bus?: string | null
}

const emptyForm = () => ({
  empresa_q: '',
  id_eot: '',
  empresa_label: '',
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
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  /** Empresa fijada: no se limpia al guardar ni con Tab/Enter */
  const [empresaFija, setEmpresaFija] = useState(false)

  const [empOpen, setEmpOpen] = useState(false)
  const [empHi, setEmpHi] = useState(0)
  const [ruaOpen, setRuaOpen] = useState(false)
  const [ruaHi, setRuaHi] = useState(0)

  const empresaRef = useRef<HTMLInputElement>(null)
  const ruaRef = useRef<HTMLInputElement>(null)
  const tipoRef = useRef<HTMLSelectElement>(null)
  const vencRef = useRef<HTMLInputElement>(null)
  const inicioRef = useRef<HTMLInputElement>(null)
  const companiaRef = useRef<HTMLSelectElement>(null)
  const polizaRef = useRef<HTMLInputElement>(null)

  const LAST = 6

  const { data: tiposData } = useQuery({
    queryKey: ['seguros-tipos'],
    queryFn: () => segurosApi.tipos(),
  })
  const { data: companiasData } = useQuery({
    queryKey: ['seguros-companias'],
    queryFn: () => segurosApi.companias(),
  })
  const { data: empresasData } = useQuery({
    queryKey: ['seguros-eots'],
    queryFn: () =>
      empresasApi.listar({
        page: 1,
        page_size: 200,
        solo_activas: true,
        solo_permisionarias: true,
      }),
  })

  const tipos: TipoSeguro[] = tiposData?.data ?? []
  const companias: Compania[] = companiasData?.data ?? []
  const empresas: EotItem[] = empresasData?.data?.items ?? []

  const { data: busesEotData, isFetching: loadingBuses } = useQuery({
    queryKey: ['seguros-eot-buses', form.id_eot],
    queryFn: () => empresasApi.busesDeEmpresa(form.id_eot, { solo_activas: true }),
    enabled: !!form.id_eot,
  })

  const busesEot: BusHit[] = useMemo(() => {
    const raw = busesEotData?.data
    if (Array.isArray(raw)) return raw
    if (raw?.buses && Array.isArray(raw.buses)) return raw.buses
    if (raw?.items && Array.isArray(raw.items)) return raw.items
    return []
  }, [busesEotData])

  const empresasFiltradas = useMemo(() => {
    const q = form.empresa_q.trim().toUpperCase()
    if (!q) return empresas.slice(0, 40)
    return empresas
      .filter((e) => {
        const nom = (e.eot_nombre || '').toUpperCase()
        const lin = (e.eot_linea || '').toUpperCase()
        const hex = (e.id_eot_vmt_hex || '').toUpperCase()
        return nom.includes(q) || lin.includes(q) || hex.includes(q)
      })
      .slice(0, 40)
  }, [empresas, form.empresa_q])

  const ruasFiltradas = useMemo(() => {
    if (!form.id_eot) return []
    const q = form.rua.trim().toUpperCase()
    const list = busesEot.filter((b) => (b.estado_bus || 'ACTIVO').toUpperCase() !== 'INACTIVO')
    if (!q) return list.slice(0, 30)
    return list
      .filter((b) => {
        const rua = (b.rua || '').toUpperCase()
        const ch = (b.numero_chassis || '').toUpperCase()
        return rua.includes(q) || ch.includes(q)
      })
      .slice(0, 30)
  }, [busesEot, form.id_eot, form.rua])

  const focusAt = useCallback((index: number) => {
    const refs = [empresaRef, ruaRef, tipoRef, vencRef, inicioRef, companiaRef, polizaRef]
    const el = refs[index]?.current
    if (!el) return
    requestAnimationFrame(() => {
      el.focus()
      if (el instanceof HTMLInputElement && el.type !== 'date') el.select()
    })
  }, [])

  useEffect(() => {
    if (!empresaFija) focusAt(0)
    else focusAt(1)
  }, [focusAt, empresaFija])

  useEffect(() => {
    if (!form.id_tipo_seguro && tipos.length) {
      const pas = tipos.find((t) => t.nombre.toUpperCase() === 'PASAJEROS') || tipos[0]
      setForm((p) => ({ ...p, id_tipo_seguro: String(pas.id_tipo_seguro) }))
    }
  }, [tipos, form.id_tipo_seguro])

  useEffect(() => {
    setEmpHi(0)
  }, [form.empresa_q])

  useEffect(() => {
    setRuaHi(0)
  }, [form.rua, form.id_eot])

  const set = (key: keyof ReturnType<typeof emptyForm>, value: string) => {
    setForm((p) => ({ ...p, [key]: value }))
    setStatus('')
  }

  const selectEmpresa = (e: EotItem) => {
    setForm((p) => ({
      ...p,
      id_eot: e.id_eot_vmt_hex,
      empresa_label: e.eot_nombre || e.id_eot_vmt_hex,
      empresa_q: e.eot_nombre || e.id_eot_vmt_hex,
      rua: '',
    }))
    setBus(null)
    setEmpresaFija(true)
    setEmpOpen(false)
    setRuaOpen(false)
    setError('')
    setStatus('')
  }

  const cambiarEmpresa = () => {
    setEmpresaFija(false)
    setForm((p) => ({
      ...p,
      id_eot: '',
      empresa_label: '',
      empresa_q: '',
      rua: '',
    }))
    setBus(null)
    setEmpOpen(true)
    setRuaOpen(false)
    setError('')
    setStatus('')
  }

  const selectBus = (b: BusHit) => {
    setBus(b)
    setForm((p) => ({ ...p, rua: (b.rua || '').toUpperCase() }))
    setRuaOpen(false)
    setError('')
    focusAt(2)
  }

  /** Tras guardar: limpia RUA/póliza/vencimiento; mantiene empresa (+ tipo y compañía). */
  const resetParaSiguiente = () => {
    setForm((prev) => ({
      ...emptyForm(),
      id_eot: prev.id_eot,
      empresa_label: prev.empresa_label,
      empresa_q: prev.empresa_label || prev.empresa_q,
      id_tipo_seguro: prev.id_tipo_seguro,
      id_compania: prev.id_compania,
      fecha_inicio: new Date().toISOString().slice(0, 10),
    }))
    setBus(null)
    setError('')
    setEmpOpen(false)
    setRuaOpen(false)
    setEmpresaFija(true)
    requestAnimationFrame(() => focusAt(1))
  }

  const limpiarRua = () => {
    setForm((p) => ({
      ...p,
      rua: '',
      fecha_vencimiento: '',
      numero_poliza: '',
      fecha_inicio: new Date().toISOString().slice(0, 10),
    }))
    setBus(null)
    setError('')
    setRuaOpen(false)
    requestAnimationFrame(() => focusAt(1))
  }

  const submit = async () => {
    setError('')
    setStatus('')
    setLoading(true)
    try {
      if (!form.id_eot) {
        setError('Seleccioná una empresa EOT.')
        setEmpresaFija(false)
        focusAt(0)
        return
      }

      let resolved = bus
      const rua = form.rua.trim().toUpperCase()
      if (!resolved || (resolved.rua || '').toUpperCase() !== rua) {
        resolved =
          ruasFiltradas.find((b) => (b.rua || '').toUpperCase() === rua) ||
          busesEot.find((b) => (b.rua || '').toUpperCase() === rua) ||
          null
      }
      if (!resolved) {
        setError('Seleccioná una RUA de la empresa.')
        focusAt(1)
        setRuaOpen(true)
        return
      }
      if (!form.id_tipo_seguro) {
        setError('Seleccioná el tipo de seguro.')
        focusAt(2)
        return
      }
      if (!form.fecha_vencimiento) {
        setError('Ingresá la fecha de vencimiento.')
        focusAt(3)
        return
      }
      if (!form.fecha_inicio) {
        setError('Ingresá la fecha de inicio.')
        focusAt(4)
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
      setStatus(
        `Guardado: ${form.empresa_label} · ${resolved.rua || resolved.id_bus} · ${tipoNom} · vence ${form.fecha_vencimiento}`,
      )
      onSuccess()
      resetParaSiguiente()
    } catch (err) {
      setError(formatApiError(err, 'No se pudo guardar el seguro.'))
      focusAt(1)
    } finally {
      setLoading(false)
    }
  }

  const onEmpresaKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      set('empresa_q', '')
      setEmpOpen(false)
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setEmpOpen(true)
      setEmpHi((i) => Math.min(i + 1, Math.max(empresasFiltradas.length - 1, 0)))
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setEmpHi((i) => Math.max(i - 1, 0))
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      if (empresasFiltradas.length) {
        const pick = empresasFiltradas[Math.min(empHi, empresasFiltradas.length - 1)]
        selectEmpresa(pick)
      }
    }
  }

  const onRuaKeyDown = async (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      setForm((p) => ({ ...p, rua: '' }))
      setBus(null)
      setRuaOpen(false)
      // Mantiene empresa fijada; solo limpia RUA
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setRuaOpen(true)
      setRuaHi((i) => Math.min(i + 1, Math.max(ruasFiltradas.length - 1, 0)))
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setRuaHi((i) => Math.max(i - 1, 0))
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      if (!form.id_eot) {
        setError('Primero seleccioná la empresa EOT.')
        setEmpresaFija(false)
        focusAt(0)
        return
      }
      if (ruasFiltradas.length) {
        const pick = ruasFiltradas[Math.min(ruaHi, ruasFiltradas.length - 1)]
        selectBus(pick)
        return
      }
      setError('No hay buses que coincidan con esa RUA en la empresa.')
      setRuaOpen(true)
    }
  }

  const onFieldKeyDown = async (
    e: React.KeyboardEvent<HTMLInputElement | HTMLSelectElement>,
    index: number,
  ) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      limpiarRua()
      return
    }
    if (e.key !== 'Enter') return
    e.preventDefault()
    if (index === LAST) {
      await submit()
      return
    }
    focusAt(index + 1)
  }

  const dropdownStyle: React.CSSProperties = {
    position: 'absolute',
    zIndex: 30,
    left: 0,
    right: 0,
    top: '100%',
    marginTop: 4,
    maxHeight: 220,
    overflowY: 'auto',
    background: 'var(--bg-card, #fff)',
    border: '1px solid var(--border, #e2e8f0)',
    borderRadius: 8,
    boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
  }

  const itemStyle = (active: boolean): React.CSSProperties => ({
    padding: '8px 10px',
    cursor: 'pointer',
    fontSize: '0.85rem',
    background: active ? 'var(--brand-500, #2563eb)' : 'transparent',
    color: active ? '#fff' : 'inherit',
  })

  return (
    <div className="card" style={{ marginBottom: 20, padding: '16px 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12, gap: 12 }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>Carga rápida de seguro</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Elegí empresa una vez · luego RUA → Tab/Enter · al guardar se mantiene la empresa
          </div>
        </div>
        {form.id_eot && (
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'right' }}>
            {loadingBuses ? 'Cargando buses…' : `${busesEot.length} buses en la EOT`}
            {bus && ` · seleccionado #${bus.id_bus}`}
          </div>
        )}
      </div>

      {error && <div className="error-message" style={{ marginBottom: 12 }}>{error}</div>}
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
          gridTemplateColumns: 'minmax(220px, 1.4fr) repeat(auto-fit, minmax(130px, 1fr))',
          gap: 12,
          alignItems: 'end',
        }}
      >
        {/* Empresa EOT */}
        <div className="form-group" style={{ marginBottom: 0, position: 'relative' }}>
          <label className="form-label">Empresa EOT *</label>
          {empresaFija && form.id_eot ? (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                minHeight: 38,
                padding: '6px 10px',
                borderRadius: 'var(--radius-md, 8px)',
                border: '1px solid rgba(63,81,181,0.35)',
                background: 'rgba(63,81,181,0.1)',
              }}
            >
              <Building2 size={15} style={{ color: 'var(--brand-400)', flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontWeight: 700,
                    fontSize: '0.85rem',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {form.empresa_label}
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                  {form.id_eot} · fijada para carga rápida
                </div>
              </div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={cambiarEmpresa}
                disabled={loading}
                title="Cambiar empresa"
                style={{ padding: '4px 8px', flexShrink: 0 }}
              >
                <X size={13} /> Cambiar
              </button>
            </div>
          ) : (
            <>
              <input
                ref={empresaRef}
                className="form-control"
                value={form.empresa_q}
                autoComplete="off"
                placeholder="Ej: Ñanduti, línea, código..."
                disabled={loading}
                onFocus={() => setEmpOpen(true)}
                onChange={(e) => {
                  set('empresa_q', e.target.value)
                  setEmpOpen(true)
                }}
                onKeyDown={onEmpresaKeyDown}
                onBlur={() => setTimeout(() => setEmpOpen(false), 150)}
              />
              {empOpen && empresasFiltradas.length > 0 && (
                <div style={dropdownStyle} role="listbox">
                  {empresasFiltradas.map((e, i) => (
                    <div
                      key={e.id_eot_vmt_hex}
                      role="option"
                      aria-selected={i === empHi}
                      style={itemStyle(i === empHi)}
                      onMouseDown={(ev) => {
                        ev.preventDefault()
                        selectEmpresa(e)
                      }}
                      onMouseEnter={() => setEmpHi(i)}
                    >
                      <div style={{ fontWeight: 600 }}>{e.eot_nombre}</div>
                      {e.eot_linea && (
                        <div style={{ fontSize: '0.75rem', opacity: 0.85 }}>
                          Líneas: {e.eot_linea.trim()} · {e.id_eot_vmt_hex}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        {/* RUA filtrada por EOT */}
        <div className="form-group" style={{ marginBottom: 0, position: 'relative' }}>
          <label className="form-label">RUA *</label>
          <input
            ref={ruaRef}
            className="form-control"
            value={form.rua}
            autoComplete="off"
            placeholder={form.id_eot ? 'Filtrar RUA...' : 'Elegí empresa primero'}
            disabled={loading || !form.id_eot}
            onFocus={() => form.id_eot && setRuaOpen(true)}
            onChange={(e) => {
              set('rua', e.target.value.toUpperCase())
              setBus(null)
              setRuaOpen(true)
            }}
            onKeyDown={onRuaKeyDown}
            onBlur={() => setTimeout(() => setRuaOpen(false), 150)}
          />
          {ruaOpen && form.id_eot && (
            <div style={dropdownStyle} role="listbox">
              {ruasFiltradas.length === 0 ? (
                <div style={{ padding: '8px 10px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  {loadingBuses ? 'Cargando…' : 'Sin coincidencias'}
                </div>
              ) : (
                ruasFiltradas.map((b, i) => (
                  <div
                    key={b.id_bus}
                    role="option"
                    aria-selected={i === ruaHi}
                    style={itemStyle(i === ruaHi)}
                    onMouseDown={(ev) => {
                      ev.preventDefault()
                      selectBus(b)
                    }}
                    onMouseEnter={() => setRuaHi(i)}
                  >
                    <strong>{b.rua || '—'}</strong>
                    <span style={{ opacity: 0.85 }}> · {b.numero_chassis || '—'} · #{b.id_bus}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Tipo *</label>
          <select
            ref={tipoRef}
            className="form-control"
            value={form.id_tipo_seguro}
            onChange={(e) => set('id_tipo_seguro', e.target.value)}
            onKeyDown={(e) => onFieldKeyDown(e, 2)}
            disabled={loading || !form.id_eot}
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
            onKeyDown={(e) => onFieldKeyDown(e, 3)}
            disabled={loading || !form.id_eot}
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
            onKeyDown={(e) => onFieldKeyDown(e, 4)}
            disabled={loading || !form.id_eot}
          />
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Compañía seguro</label>
          <select
            ref={companiaRef}
            className="form-control"
            value={form.id_compania}
            onChange={(e) => set('id_compania', e.target.value)}
            onKeyDown={(e) => onFieldKeyDown(e, 5)}
            disabled={loading || !form.id_eot}
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
            onKeyDown={(e) => onFieldKeyDown(e, 6)}
            disabled={loading || !form.id_eot}
          />
        </div>
      </div>

      <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={() => void submit()}
          disabled={loading || !form.id_eot}
        >
          {loading ? 'Guardando...' : 'Guardar (Enter en póliza)'}
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={limpiarRua}
          disabled={loading || !form.id_eot}
        >
          Limpiar RUA (mantener empresa)
        </button>
      </div>
    </div>
  )
}
