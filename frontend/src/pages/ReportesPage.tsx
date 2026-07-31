import { useMemo, useRef, useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Download, Building2, Filter, Columns3, BarChart3,
  ChevronDown, X, CheckSquare, Square,
} from 'lucide-react'
import { reportesApi, empresasApi, busesApi } from '../api'
import PlanillaTabs from '../components/reportes/PlanillaTabs'

const CAMPOS_DEFAULT = [
  { key: 'id_bus', label: 'N° ID', default: true },
  { key: 'numero_orden', label: 'N° Orden', default: true },
  { key: 'rua', label: 'RUA / Placa', default: true },
  { key: 'numero_chassis', label: 'Chasis', default: true },
  { key: 'año', label: 'Año', default: true },
  { key: 'antiguedad', label: 'Antigüedad (años)', default: false },
  { key: 'marca', label: 'Marca', default: true },
  { key: 'tipo_carroceria', label: 'Tipo Carrocería', default: true },
  { key: 'marca_carroceria', label: 'Marca Carrocería', default: true },
  { key: 'empresa', label: 'Empresa', default: true },
  { key: 'combustible', label: 'Combustible', default: true },
  { key: 'capacidad_pasajeros', label: 'Capacidad', default: false },
  { key: 'cilindrada', label: 'Cilindrada', default: false },
  { key: 'color', label: 'Color', default: false },
  { key: 'tipo_servicio', label: 'Tipo Servicio', default: false },
  { key: 'estado_bus', label: 'Estado Bus', default: true },
  { key: 'itv_vencimiento', label: 'ITV Vencimiento', default: true },
  { key: 'itv_estado', label: 'Estado ITV', default: true },
  { key: 'fecha_itv', label: 'Fecha ITV', default: false },
]

const RESUMENES_DEFAULT = [
  { key: 'total', label: 'Cantidad total de buses', default: true },
  { key: 'promedio_antiguedad', label: 'Promedio de antigüedad', default: true },
  { key: 'antiguedad_max', label: 'Antigüedad máxima', default: true },
  { key: 'antiguedad_min', label: 'Antigüedad mínima', default: false },
  { key: 'itv_vencido', label: 'Buses con ITV vencido', default: true },
  { key: 'itv_por_vencer', label: 'Buses con ITV por vencer', default: true },
  { key: 'itv_critico', label: 'Buses con ITV crítico', default: false },
  { key: 'itv_vigente', label: 'Buses con ITV vigente', default: false },
  { key: 'sin_itv', label: 'Buses sin ITV', default: false },
  { key: 'activos', label: 'Buses activos', default: false },
  { key: 'inactivos', label: 'Buses inactivos', default: false },
]

function keysFromDefaults(items: { key: string; default: boolean }[]) {
  return new Set(items.filter(i => i.default).map(i => i.key))
}

function EmpresaMultiSelect({
  empresas,
  selected,
  onChange,
}: {
  empresas: { id_eot_vmt_hex: string; eot_nombre: string }[]
  selected: string[]
  onChange: (ids: string[]) => void
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return empresas
    return empresas.filter(e => e.eot_nombre?.toLowerCase().includes(q))
  }, [empresas, search])

  const toggle = (id: string) => {
    if (selected.includes(id)) onChange(selected.filter(x => x !== id))
    else onChange([...selected, id])
  }

  const label =
    selected.length === 0
      ? 'Todas las empresas'
      : selected.length === 1
        ? (empresas.find(e => e.id_eot_vmt_hex === selected[0])?.eot_nombre ?? '1 empresa')
        : `${selected.length} empresas seleccionadas`

  return (
    <div className="multi-select" ref={ref}>
      <button
        type="button"
        className="form-control multi-select-trigger"
        onClick={() => setOpen(o => !o)}
      >
        <Building2 size={14} style={{ flexShrink: 0, opacity: 0.7 }} />
        <span className="multi-select-label">{label}</span>
        <ChevronDown size={14} style={{ flexShrink: 0, opacity: 0.6 }} />
      </button>

      {open && (
        <div className="multi-select-dropdown">
          <div className="multi-select-search">
            <input
              className="form-control"
              placeholder="Buscar empresa..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              autoFocus
            />
          </div>
          <div className="multi-select-actions">
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => onChange(empresas.map(e => e.id_eot_vmt_hex))}>
              Todas
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => onChange([])}>
              Ninguna
            </button>
          </div>
          <div className="multi-select-list">
            {filtered.length === 0 ? (
              <div className="multi-select-empty">Sin resultados</div>
            ) : (
              filtered.map(e => {
                const checked = selected.includes(e.id_eot_vmt_hex)
                return (
                  <label key={e.id_eot_vmt_hex} className={`check-row ${checked ? 'is-checked' : ''}`}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(e.id_eot_vmt_hex)}
                    />
                    <span>{e.eot_nombre}</span>
                  </label>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function CheckGroup({
  items,
  selected,
  onChange,
}: {
  items: { key: string; label: string }[]
  selected: Set<string>
  onChange: (next: Set<string>) => void
}) {
  const toggle = (key: string) => {
    const next = new Set(selected)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    onChange(next)
  }

  const allSelected = items.length > 0 && items.every(i => selected.has(i.key))

  return (
    <div>
      <div className="check-group-actions">
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => onChange(new Set(items.map(i => i.key)))}
        >
          <CheckSquare size={13} /> Seleccionar todos
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => onChange(new Set())}
          disabled={selected.size === 0}
        >
          <Square size={13} /> Ninguno
        </button>
        <span className="check-group-count">
          {selected.size}/{items.length}
          {allSelected ? ' · todos' : ''}
        </span>
      </div>
      <div className="check-group-list">
        {items.map(item => (
          <label key={item.key} className={`check-row ${selected.has(item.key) ? 'is-checked' : ''}`}>
            <input
              type="checkbox"
              checked={selected.has(item.key)}
              onChange={() => toggle(item.key)}
            />
            <span>{item.label}</span>
          </label>
        ))}
      </div>
    </div>
  )
}

export default function ReportesPage() {
  const [vista, setVista] = useState<'constructor' | 'planilla'>('planilla')
  const [downloading, setDownloading] = useState(false)
  const [empresasSel, setEmpresasSel] = useState<string[]>([])
  const [estadoBus, setEstadoBus] = useState('')
  const [estadoItv, setEstadoItv] = useState('')
  const [idMarca, setIdMarca] = useState('')
  const [idTipoServicio, setIdTipoServicio] = useState('')
  const [añoDesde, setAñoDesde] = useState('')
  const [añoHasta, setAñoHasta] = useState('')
  const [camposSel, setCamposSel] = useState<Set<string>>(() => keysFromDefaults(CAMPOS_DEFAULT))
  const [resumenesSel, setResumenesSel] = useState<Set<string>>(() => keysFromDefaults(RESUMENES_DEFAULT))

  const { data: opcionesData } = useQuery({
    queryKey: ['reportes-opciones'],
    queryFn: () => reportesApi.opciones(),
    staleTime: 60_000,
  })

  const campos = opcionesData?.data?.campos ?? CAMPOS_DEFAULT
  const resumenes = opcionesData?.data?.resumenes ?? RESUMENES_DEFAULT

  // Sync defaults once when API responds
  const syncedRef = useRef(false)
  useEffect(() => {
    if (syncedRef.current || !opcionesData?.data) return
    if (opcionesData.data.campos) setCamposSel(keysFromDefaults(opcionesData.data.campos))
    if (opcionesData.data.resumenes) setResumenesSel(keysFromDefaults(opcionesData.data.resumenes))
    syncedRef.current = true
  }, [opcionesData])

  const { data: empresasData } = useQuery({
    queryKey: ['empresas-filtro-reportes'],
    queryFn: () => empresasApi.listar({ page: 1, page_size: 200, solo_activas: true, solo_permisionarias: true }),
  })
  const empresasLista = empresasData?.data?.items ?? []

  const { data: marcasData } = useQuery({
    queryKey: ['marcas'],
    queryFn: busesApi.marcas,
  })
  const marcas = marcasData?.data ?? []

  const { data: tiposServicioData } = useQuery({
    queryKey: ['tipos-servicio'],
    queryFn: busesApi.tiposServicio,
  })
  const tiposServicio = tiposServicioData?.data ?? []

  const limpiarFiltros = () => {
    setEmpresasSel([])
    setEstadoBus('')
    setEstadoItv('')
    setIdMarca('')
    setIdTipoServicio('')
    setAñoDesde('')
    setAñoHasta('')
  }

  const puedeDescargar = camposSel.size > 0 || resumenesSel.size > 0

  const handleDescargar = async () => {
    if (!puedeDescargar) {
      alert('Seleccioná al menos un campo del reporte o un resumen.')
      return
    }
    setDownloading(true)
    try {
      const params: Record<string, string | number | boolean> = {
        campos: Array.from(camposSel).join(','),
        resumenes: Array.from(resumenesSel).join(','),
        solo_resumen: camposSel.size === 0,
      }
      if (empresasSel.length) params.empresas = empresasSel.join(',')
      if (estadoBus) params.estado_bus = estadoBus
      if (estadoItv) params.estado_itv = estadoItv
      if (idMarca) params.id_marca = Number(idMarca)
      if (idTipoServicio) params.id_tipo_servicio = Number(idTipoServicio)
      if (añoDesde) params.año_desde = Number(añoDesde)
      if (añoHasta) params.año_hasta = Number(añoHasta)

      const response = await reportesApi.descargarBusesExcel(params)
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'Parque_Automotor_VMT.xlsx')
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      alert('Error al generar el reporte. Revisá los filtros e intentá de nuevo.')
    } finally {
      setDownloading(false)
    }
  }

  const empresasChips = empresasSel
    .map(id => empresasLista.find((e: any) => e.id_eot_vmt_hex === id))
    .filter(Boolean)

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-header-title">Centro de Reportes</h1>
          <p className="page-header-sub">
            {vista === 'planilla'
              ? 'Pestañas de la planilla ITV: CUADRO DE EDAD, BAJAS, operativos, inclusivos…'
              : 'Armá un reporte personalizado: filtrá, elegí columnas y resúmenes, y descargá en Excel'}
          </p>
        </div>
        {vista === 'constructor' && (
          <button
            className="btn btn-primary"
            onClick={handleDescargar}
            disabled={downloading || !puedeDescargar}
          >
            <Download size={16} />
            <span>{downloading ? 'Generando Excel...' : 'Descargar Excel'}</span>
          </button>
        )}
      </div>

      <div className="report-tabs report-tabs-main" role="tablist" style={{ marginBottom: 16 }}>
        <button
          type="button"
          role="tab"
          className={`report-tab ${vista === 'planilla' ? 'active' : ''}`}
          onClick={() => setVista('planilla')}
        >
          Planilla ITV
        </button>
        <button
          type="button"
          role="tab"
          className={`report-tab ${vista === 'constructor' ? 'active' : ''}`}
          onClick={() => setVista('constructor')}
        >
          Constructor Excel
        </button>
      </div>

      {vista === 'planilla' ? (
        <PlanillaTabs />
      ) : (
      <>
      {/* 1) Filtros */}
      <div className="card report-section" style={{ marginBottom: 20 }}>
        <div className="report-section-header">
          <Filter size={16} />
          <h2>Filtros</h2>
          <button type="button" className="btn btn-secondary btn-sm" onClick={limpiarFiltros} style={{ marginLeft: 'auto' }}>
            Limpiar
          </button>
        </div>

        <div className="report-filters-grid">
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Empresas</label>
            <EmpresaMultiSelect
              empresas={empresasLista}
              selected={empresasSel}
              onChange={setEmpresasSel}
            />
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Estado del bus</label>
            <select className="form-control" value={estadoBus} onChange={e => setEstadoBus(e.target.value)}>
              <option value="">Todos</option>
              <option value="ACTIVO">Activo</option>
              <option value="INACTIVO">Inactivo</option>
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Estado ITV</label>
            <select className="form-control" value={estadoItv} onChange={e => setEstadoItv(e.target.value)}>
              <option value="">Todos</option>
              <option value="VIGENTE">Vigente</option>
              <option value="POR_VENCER">Por vencer</option>
              <option value="CRITICO">Crítico</option>
              <option value="VENCIDO">Vencido</option>
              <option value="SIN_ITV">Sin ITV</option>
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Marca</label>
            <select className="form-control" value={idMarca} onChange={e => setIdMarca(e.target.value)}>
              <option value="">Todas</option>
              {marcas.map((m: any) => (
                <option key={m.id_marca} value={m.id_marca}>{m.nombre}</option>
              ))}
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Tipo de servicio</label>
            <select className="form-control" value={idTipoServicio} onChange={e => setIdTipoServicio(e.target.value)}>
              <option value="">Todos</option>
              {tiposServicio.map((t: any) => (
                <option key={t.id_tipo_servicio} value={t.id_tipo_servicio}>{t.nombre}</option>
              ))}
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Año desde</label>
            <input
              className="form-control"
              type="number"
              min={1980}
              max={2100}
              placeholder="Ej. 2010"
              value={añoDesde}
              onChange={e => setAñoDesde(e.target.value)}
            />
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Año hasta</label>
            <input
              className="form-control"
              type="number"
              min={1980}
              max={2100}
              placeholder="Ej. 2024"
              value={añoHasta}
              onChange={e => setAñoHasta(e.target.value)}
            />
          </div>
        </div>

        {empresasChips.length > 0 && (
          <div className="report-chips">
            {empresasChips.map((e: any) => (
              <button
                key={e.id_eot_vmt_hex}
                type="button"
                className="report-chip"
                onClick={() => setEmpresasSel(prev => prev.filter(id => id !== e.id_eot_vmt_hex))}
              >
                <Building2 size={12} />
                {e.eot_nombre}
                <X size={12} />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 2) Campos + 3) Resúmenes */}
      <div className="report-builder-grid">
        <div className="card report-section">
          <div className="report-section-header">
            <Columns3 size={16} />
            <h2>Campos del reporte</h2>
          </div>
          <p className="report-section-hint">
            Marcá las columnas del detalle. Si dejás todo vacío y solo marcás resúmenes, el Excel sale sin tabla de buses.
          </p>
          <CheckGroup items={campos} selected={camposSel} onChange={setCamposSel} />
        </div>

        <div className="card report-section">
          <div className="report-section-header">
            <BarChart3 size={16} />
            <h2>Resúmenes al final</h2>
          </div>
          <p className="report-section-hint">
            Indicadores del reporte. Si no marcás campos, el Excel sale solo con estos resúmenes.
          </p>
          <CheckGroup items={resumenes} selected={resumenesSel} onChange={setResumenesSel} />

          <div className="report-download-footer">
            <button
              className="btn btn-primary btn-lg"
              onClick={handleDescargar}
              disabled={downloading || !puedeDescargar}
              style={{ width: '100%', justifyContent: 'center' }}
            >
              <Download size={18} />
              <span>{downloading ? 'Generando Excel...' : 'Descargar reporte Excel'}</span>
            </button>
            <p className="report-section-hint" style={{ textAlign: 'center', marginTop: 10, marginBottom: 0 }}>
              {camposSel.size === 0 && resumenesSel.size > 0
                ? `Solo resúmenes (${resumenesSel.size})`
                : `${camposSel.size} columnas · ${resumenesSel.size} resúmenes`}
              {empresasSel.length > 0 ? ` · ${empresasSel.length} empresa(s)` : ' · todas las empresas'}
            </p>
          </div>
        </div>
      </div>
      </>
      )}
    </div>
  )
}
