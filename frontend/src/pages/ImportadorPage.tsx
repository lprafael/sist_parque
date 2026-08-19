import { useState } from 'react'
import { Upload, FileSpreadsheet, CheckCircle, AlertCircle, Search, Play, Building2 } from 'lucide-react'
import { importadorApi } from '../api'
import { formatApiError } from '../api/client'
import { useRol } from '../hooks/useRol'

type PreviewData = {
  status: string
  filename: string
  hoja: string
  fecha_corte?: string
  total_excel: number
  matched_rua: number
  matched_chassis: number
  matched_total: number
  solo_excel: number
  solo_db_activos: number
  itv_actualizar: number
  itv_igual: number
  itv_sin_fecha: number
  con_seguro_pasajeros: number
  con_seguro_terceros: number
  tipos_servicio: Record<string, number>
  muestra_solo_excel: Array<Record<string, unknown>>
  muestra_solo_db: Array<Record<string, unknown>>
  muestra_itv_diff: Array<Record<string, unknown>>
  hoja_bajas?: string | null
  total_bajas_excel?: number
  bajas_a_aplicar?: number
  bajas_ya_en_db?: number
  bajas_sin_match_db?: number
  muestra_bajas?: Array<Record<string, unknown>>
  mensaje: string
}

type ApplyData = {
  status: string
  mensaje: string
  buses_creados: number
  buses_actualizados: number
  buses_activados: number
  buses_inactivados: number
  buses_baja?: number
  itv_insertados: number
  itv_sin_cambio: number
  seguros_insertados: number
  auxiliar_filas: number
  errores: string[]
}

type EmpresaPreviewData = {
  status: string
  filename: string
  hoja: string
  fecha_corte?: string
  total_excel: number
  matched_bus: number
  ok_mismo_eot: number
  a_transferir: number
  a_alta: number
  sin_bus: number
  sin_match_eot: number
  eot_sin_mapear: Record<string, number>
  por_eot_destino: Record<string, number>
  muestra_transferencias: Array<Record<string, unknown>>
  muestra_altas: Array<Record<string, unknown>>
  muestra_sin_eot: Array<Record<string, unknown>>
  mensaje: string
}

type EmpresaApplyData = {
  status: string
  mensaje: string
  transferencias: number
  altas: number
  sin_cambio: number
  omitidos: number
  errores: string[]
}

export default function ImportadorPage() {
  const { puedeEditar } = useRol()
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState(false)
  const [preview, setPreview] = useState<PreviewData | null>(null)
  const [applyResult, setApplyResult] = useState<ApplyData | null>(null)
  const [empresaPreview, setEmpresaPreview] = useState<EmpresaPreviewData | null>(null)
  const [empresaApply, setEmpresaApply] = useState<EmpresaApplyData | null>(null)
  const [error, setError] = useState('')
  const [sincronizarEstado, setSincronizarEstado] = useState(false)
  const [crearFaltantes, setCrearFaltantes] = useState(true)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setFile(e.target.files[0])
      setPreview(null)
      setApplyResult(null)
      setEmpresaPreview(null)
      setEmpresaApply(null)
      setError('')
    }
  }

  const handlePreview = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    setPreview(null)
    setApplyResult(null)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await importadorApi.preview(formData)
      setPreview(res.data)
    } catch (err: any) {
      setError(formatApiError(err, 'Error al analizar la planilla Excel.'))
    } finally {
      setLoading(false)
    }
  }

  const handlePreviewEmpresas = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    setEmpresaPreview(null)
    setEmpresaApply(null)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await importadorApi.previewEmpresas(formData)
      setEmpresaPreview(res.data)
    } catch (err: any) {
      setError(formatApiError(err, 'Error al analizar empresas del Excel.'))
    } finally {
      setLoading(false)
    }
  }

  const handleAplicarEmpresas = async () => {
    if (!file || !empresaPreview) return
    const ok = window.confirm(
      '¿Sincronizar asignaciones bus↔empresa según el Excel?\n\n' +
        `${empresaPreview.a_transferir} transferencias y ${empresaPreview.a_alta} altas.\n` +
        'No modifica ITV ni ACTIVO/INACTIVO.',
    )
    if (!ok) return
    setApplying(true)
    setError('')
    setEmpresaApply(null)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await importadorApi.sincronizarEmpresas(formData)
      setEmpresaApply(res.data)
    } catch (err: any) {
      setError(formatApiError(err, 'Error al sincronizar empresas.'))
    } finally {
      setApplying(false)
    }
  }

  const handleAplicar = async () => {
    if (!file || !preview) return
    const ok = window.confirm(
      '¿Aplicar la importación a la base de datos?\n\n' +
        `Se actualizarán hasta ${preview.itv_actualizar} ITV, ` +
        `${preview.solo_excel} buses nuevos potenciales` +
        (preview.bajas_a_aplicar
          ? `, ${preview.bajas_a_aplicar} buses de la hoja BAJAS pasarían a BAJA`
          : '') +
        ', y ' +
        (sincronizarEstado
          ? `${preview.solo_db_activos} activos fuera de General pasarían a INACTIVO (salvo los de BAJAS).`
          : 'no se cambiará ACTIVO/INACTIVO de buses fuera de General (sí se aplican BAJAS).'),
    )
    if (!ok) return

    setApplying(true)
    setError('')
    setApplyResult(null)
    const formData = new FormData()
    formData.append('file', file)
    formData.append('sincronizar_estado', String(sincronizarEstado))
    formData.append('crear_faltantes', String(crearFaltantes))
    try {
      const res = await importadorApi.aplicar(formData)
      setApplyResult(res.data)
    } catch (err: any) {
      setError(formatApiError(err, 'Error al aplicar la importación.'))
    } finally {
      setApplying(false)
    }
  }

  const handleSoloEstado = async () => {
    if (!file) return
    const ok = window.confirm(
      '¿Solo sincronizar ACTIVO/INACTIVO/BAJA según General y BAJAS?\n\n' +
        'No modifica seguros. Al dar de baja, cierra asignación e invalida ITV vigente.',
    )
    if (!ok) return
    setApplying(true)
    setError('')
    setApplyResult(null)
    const formData = new FormData()
    formData.append('file', file)
    formData.append('inactivar_fuera', String(sincronizarEstado))
    try {
      const res = await importadorApi.sincronizarEstado(formData)
      setApplyResult({
        status: res.data.status,
        mensaje: res.data.mensaje,
        buses_creados: 0,
        buses_actualizados: 0,
        buses_activados: res.data.buses_activados,
        buses_inactivados: res.data.buses_inactivados,
        itv_insertados: 0,
        itv_sin_cambio: 0,
        seguros_insertados: 0,
        auxiliar_filas: 0,
        errores: [],
      })
    } catch (err: any) {
      setError(formatApiError(err, 'Error al sincronizar estados.'))
    } finally {
      setApplying(false)
    }
  }

  if (!puedeEditar) {
    return (
      <div>
        <div className="page-header">
          <div>
            <h1 className="page-header-title">Importador Masivo (Excel)</h1>
          </div>
        </div>
        <div className="card" style={{ padding: '3rem', textAlign: 'center' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🔒</div>
          <h3 style={{ marginBottom: '0.5rem' }}>Acceso restringido</h3>
          <p style={{ color: 'var(--text-muted)' }}>
            Tu rol de <strong>Visualizador</strong> no tiene permisos para importar datos.
            Contactá a un Administrador o Supervisor.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-header-title">Importador Masivo (Excel)</h1>
          <p className="page-header-sub">
            Cruza la planilla ITV (hojas General y BAJAS) con registro_habilitacion y aplica
            buses, ITV, seguros y bajas
          </p>
        </div>
      </div>

      <div className="card" style={{ maxWidth: 720, margin: '0 auto', padding: '2rem' }}>
        <div style={{ textAlign: 'center' }}>
          <FileSpreadsheet size={48} style={{ color: 'var(--primary-color)', marginBottom: '1rem' }} />
          <h3 style={{ fontSize: '1.15rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            Planilla ITV / Parque Automotor
          </h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
            Usá un .xlsx con hoja <strong>General</strong> y, si existe, <strong>BAJAS</strong>
            {' '}(ej. ITV - 2026 Base de Datos…). Primero se analiza el cruce; después confirmás la aplicación.
          </p>

          <input
            type="file"
            id="excel-input"
            accept=".xlsx,.xls"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />

          <div style={{ display: 'flex', justifyContent: 'center', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
            <label htmlFor="excel-input" className="btn btn-secondary" style={{ cursor: 'pointer' }}>
              <Upload size={16} />
              <span>{file ? file.name : 'Buscar archivo...'}</span>
            </label>
            {file && (
              <>
              <button className="btn btn-primary" onClick={handlePreview} disabled={loading || applying}>
                <Search size={16} />
                <span>{loading ? 'Analizando...' : 'Analizar ITV'}</span>
              </button>
              <button className="btn btn-secondary" onClick={handlePreviewEmpresas} disabled={loading || applying}>
                <Building2 size={16} />
                <span>Analizar empresas</span>
              </button>
              </>
            )}
          </div>
        </div>

        {error && (
          <div
            style={{
              marginTop: '1rem',
              padding: '1rem',
              backgroundColor: '#FEE2E2',
              color: '#991B1B',
              borderRadius: 8,
              display: 'flex',
              gap: '0.75rem',
              alignItems: 'flex-start',
            }}
          >
            <AlertCircle size={20} style={{ flexShrink: 0 }} />
            <div>{error}</div>
          </div>
        )}

        {empresaPreview && (
          <div style={{ marginTop: '1.5rem', textAlign: 'left' }}>
            <div
              style={{
                padding: '1rem',
                backgroundColor: '#F5F3FF',
                color: '#4C1D95',
                borderRadius: 8,
                marginBottom: '1rem',
              }}
            >
              <strong>{empresaPreview.mensaje}</strong>
              <div style={{ fontSize: '0.85rem', marginTop: 4 }}>
                Alinea <code>bus_empresa</code> con EMPRESA-LINEA del Excel (ej. Capiatá → 001B).
              </div>
            </div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
                gap: '0.75rem',
                marginBottom: '1.25rem',
              }}
            >
              <Stat label="Filas Excel" value={empresaPreview.total_excel} />
              <Stat label="Match bus" value={empresaPreview.matched_bus} />
              <Stat label="Ya correctas" value={empresaPreview.ok_mismo_eot} />
              <Stat label="A transferir" value={empresaPreview.a_transferir} tone="warn" />
              <Stat label="Altas" value={empresaPreview.a_alta} tone="warn" />
              <Stat label="Sin mapear EOT" value={empresaPreview.sin_match_eot} tone="warn" />
              <Stat label="Sin bus en DB" value={empresaPreview.sin_bus} />
            </div>
            {Object.keys(empresaPreview.por_eot_destino || {}).length > 0 && (
              <div style={{ marginBottom: '1rem', fontSize: '0.875rem' }}>
                <strong>Destinos (cambios):</strong>{' '}
                {Object.entries(empresaPreview.por_eot_destino)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(' · ')}
              </div>
            )}
            <SampleTable
              title="Muestra transferencias"
              rows={empresaPreview.muestra_transferencias}
              cols={['rua', 'chassis', 'de', 'a', 'empresa_excel']}
            />
            <SampleTable
              title="Muestra altas (sin empresa vigente)"
              rows={empresaPreview.muestra_altas}
              cols={['rua', 'chassis', 'a', 'empresa_excel']}
            />
            <SampleTable
              title="Muestra sin mapear a EOT"
              rows={empresaPreview.muestra_sin_eot}
              cols={['fila', 'rua', 'empresa_excel', 'codigo']}
            />
            <button
              className="btn btn-primary"
              onClick={handleAplicarEmpresas}
              disabled={applying || loading || (empresaPreview.a_transferir + empresaPreview.a_alta) === 0}
              style={{ width: '100%', marginTop: '0.5rem' }}
            >
              <Play size={16} />
              <span>
                {applying
                  ? 'Sincronizando empresas...'
                  : `Aplicar asignaciones (${empresaPreview.a_transferir + empresaPreview.a_alta})`}
              </span>
            </button>
            {empresaApply && (
              <div
                style={{
                  marginTop: '1rem',
                  padding: '1rem',
                  backgroundColor: '#DCFCE7',
                  color: '#166534',
                  borderRadius: 8,
                }}
              >
                <strong>{empresaApply.mensaje}</strong>
                <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1.1rem', fontSize: '0.85rem' }}>
                  <li>Transferencias: {empresaApply.transferencias}</li>
                  <li>Altas: {empresaApply.altas}</li>
                  <li>Sin cambio: {empresaApply.sin_cambio}</li>
                </ul>
                {empresaApply.errores?.length > 0 && (
                  <div style={{ marginTop: 8, color: '#92400E' }}>
                    <strong>{empresaApply.errores.length} errores</strong>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {preview && (
          <div style={{ marginTop: '1.5rem', textAlign: 'left' }}>
            <div
              style={{
                padding: '1rem',
                backgroundColor: '#EFF6FF',
                color: '#1E3A8A',
                borderRadius: 8,
                marginBottom: '1rem',
              }}
            >
              <strong>{preview.mensaje}</strong>
              {preview.fecha_corte && (
                <div style={{ fontSize: '0.85rem', marginTop: 4 }}>
                  Fecha corte planilla: {preview.fecha_corte} · Hoja: {preview.hoja}
                  {preview.hoja_bajas ? ` · ${preview.hoja_bajas}` : ''}
                </div>
              )}
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
                gap: '0.75rem',
                marginBottom: '1.25rem',
              }}
            >
              <Stat label="En Excel" value={preview.total_excel} />
              <Stat label="Match RUA" value={preview.matched_rua} />
              <Stat label="Match chasis" value={preview.matched_chassis} />
              <Stat label="Solo Excel" value={preview.solo_excel} tone="warn" />
              <Stat label="Activos fuera" value={preview.solo_db_activos} tone="warn" />
              <Stat label="ITV a actualizar" value={preview.itv_actualizar} />
              <Stat label="ITV igual" value={preview.itv_igual} />
              <Stat label="Sin fecha ITV" value={preview.itv_sin_fecha} />
              {preview.hoja_bajas && (
                <>
                  <Stat label="BAJAS en Excel" value={preview.total_bajas_excel || 0} />
                  <Stat label="A dar de baja" value={preview.bajas_a_aplicar || 0} tone="warn" />
                  <Stat label="Ya en BAJA" value={preview.bajas_ya_en_db || 0} />
                </>
              )}
            </div>

            {Object.keys(preview.tipos_servicio || {}).length > 0 && (
              <div style={{ marginBottom: '1rem', fontSize: '0.875rem' }}>
                <strong>Tipos de servicio:</strong>{' '}
                {Object.entries(preview.tipos_servicio)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(' · ')}
              </div>
            )}

            <SampleTable
              title="Muestra solo en Excel (se crearían)"
              rows={preview.muestra_solo_excel}
              cols={['fila', 'rua', 'chassis', 'marca', 'anio']}
            />
            <SampleTable
              title="Muestra activos en DB fuera del Excel"
              rows={preview.muestra_solo_db}
              cols={['id_bus', 'rua', 'chassis']}
            />
            <SampleTable
              title="Muestra ITV distintas"
              rows={preview.muestra_itv_diff}
              cols={['rua', 'itv_db', 'itv_excel', 'match']}
            />
            {preview.hoja_bajas && (
              <SampleTable
                title="Muestra a dar de baja (hoja BAJAS, no en General)"
                rows={preview.muestra_bajas || []}
                cols={['id_bus', 'rua', 'chassis', 'estado_actual']}
              />
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', margin: '1.25rem 0' }}>
              <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: '0.9rem' }}>
                <input
                  type="checkbox"
                  checked={sincronizarEstado}
                  onChange={(e) => setSincronizarEstado(e.target.checked)}
                />
                Sincronizar ACTIVO/INACTIVO con General (BAJAS se aplican siempre)
              </label>
              <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: '0.9rem' }}>
                <input
                  type="checkbox"
                  checked={crearFaltantes}
                  onChange={(e) => setCrearFaltantes(e.target.checked)}
                />
                Crear buses que solo están en el Excel
              </label>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <button
                className="btn btn-primary"
                onClick={handleAplicar}
                disabled={applying || loading}
                style={{ width: '100%' }}
              >
                <Play size={16} />
                <span>{applying ? 'Aplicando importación...' : 'Confirmar y aplicar a la base'}</span>
              </button>
              <button
                className="btn btn-secondary"
                onClick={handleSoloEstado}
                disabled={applying || loading || !file}
                style={{ width: '100%' }}
              >
                <span>Solo recuperar ACTIVO / INACTIVO / BAJA</span>
              </button>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.75rem' }}>
              Si una importación anterior inactivó de más, usá el botón de recuperación con el mismo Excel.
              La hoja BAJAS se aplica al confirmar (estado BAJA, cierra asignación e invalida ITV).
            </p>
          </div>
        )}

        {applyResult && (
          <div
            style={{
              marginTop: '1.5rem',
              padding: '1rem',
              backgroundColor: '#DCFCE7',
              color: '#166534',
              borderRadius: 8,
              textAlign: 'left',
            }}
          >
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle size={20} style={{ flexShrink: 0 }} />
              <div>
                <strong>{applyResult.mensaje}</strong>
                <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1.1rem', fontSize: '0.85rem' }}>
                  <li>Actualizados: {applyResult.buses_actualizados}</li>
                  <li>Creados: {applyResult.buses_creados}</li>
                  <li>Activados: {applyResult.buses_activados}</li>
                  <li>Inactivados: {applyResult.buses_inactivados}</li>
                  <li>Dados de baja: {applyResult.buses_baja ?? 0}</li>
                  <li>ITV nuevas: {applyResult.itv_insertados} (sin cambio: {applyResult.itv_sin_cambio})</li>
                  <li>Seguros: {applyResult.seguros_insertados}</li>
                  <li>Staging auxiliar: {applyResult.auxiliar_filas}</li>
                </ul>
                {applyResult.errores?.length > 0 && (
                  <div style={{ marginTop: 8, color: '#92400E' }}>
                    <strong>{applyResult.errores.length} avisos/errores:</strong>
                    <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.1rem' }}>
                      {applyResult.errores.slice(0, 10).map((e) => (
                        <li key={e}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone?: 'warn'
}) {
  return (
    <div
      style={{
        background: tone === 'warn' ? '#FFFBEB' : 'var(--bg-secondary, #f8fafc)',
        border: '1px solid var(--border-color, #e2e8f0)',
        borderRadius: 8,
        padding: '0.75rem',
      }}
    >
      <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{value}</div>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{label}</div>
    </div>
  )
}

function SampleTable({
  title,
  rows,
  cols,
}: {
  title: string
  rows: Array<Record<string, unknown>>
  cols: string[]
}) {
  if (!rows?.length) return null
  return (
    <div style={{ marginBottom: '1rem' }}>
      <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 4 }}>{title}</div>
      <div style={{ overflowX: 'auto', fontSize: '0.75rem' }}>
        <table className="data-table" style={{ width: '100%' }}>
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {cols.map((c) => (
                  <td key={c}>{r[c] == null ? '—' : String(r[c])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
