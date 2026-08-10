type FilaEdad = {
  tipo?: string
  n?: number | null
  linea?: string
  empresa?: string
  por_anio?: number[]
  parque_total?: number
  falt_exce?: number
  autoriz?: number
  operat?: number
  reserv?: number
  declar?: number
  match_ok?: boolean
}

type ZonalEdad = {
  titulo: string
  filas: FilaEdad[]
  subtotal: FilaEdad
}

type CuadroEdadData = {
  titulo?: string
  dpto?: string
  banner?: string
  actualizacion?: string
  fecha_parque?: string
  anios?: number[]
  zonales?: ZonalEdad[]
  totales?: FilaEdad
  leyenda_edades?: Array<{ label: string; desde: number; hasta: number }>
}

function cellNum(v: number | undefined | null): string {
  if (v === null || v === undefined) return ''
  return String(v)
}

export default function CuadroEdadView({ data }: { data: CuadroEdadData }) {
  const anios = data.anios ?? []
  const zonales = data.zonales ?? []

  return (
    <div className="cuadro-edad-wrap">
      <div className="cuadro-edad-title-row">
        <div className="cuadro-edad-title">{data.titulo}</div>
        <div className="cuadro-edad-dpto">{data.dpto}</div>
      </div>

      <div className="cuadro-edad-meta-row">
        <span className="cuadro-edad-meta-label">Actualización:</span>
        <span className="cuadro-edad-meta-value">{data.actualizacion}</span>
      </div>

      <div className="cuadro-edad-banner">{data.banner}</div>

      {zonales.map((z) => (
        <div key={z.titulo} className="cuadro-edad-zonal">
          <div className="cuadro-edad-zonal-head">
            <div className="cuadro-edad-zonal-title">{z.titulo}</div>
            <div className="cuadro-edad-zonal-right">
              <span>Parque Total</span>
              <span>Parque Falt/Exce</span>
              <span className="cuadro-edad-parque-actual">
                PARQUE Actual: <em>{data.fecha_parque}</em>
              </span>
            </div>
          </div>

          <div className="cuadro-edad-table-scroll">
            <table className="cuadro-edad-table">
              <thead>
                <tr>
                  <th className="col-n">Nº</th>
                  <th className="col-linea">Línea</th>
                  <th className="col-empresa">Empresa</th>
                  {anios.map((a) => (
                    <th key={a} className="col-anio">{a}</th>
                  ))}
                  <th className="col-tot">Parque Total</th>
                  <th className="col-falt">Parque Falt/Exce</th>
                  <th className="col-auth">Autoriz.(a)</th>
                  <th className="col-op">Operat.(b)</th>
                  <th className="col-res">Reserv.(c)</th>
                  <th className="col-dec">Declar.(d)</th>
                </tr>
              </thead>
              <tbody>
                {z.filas.map((f, i) => (
                  <tr key={`${z.titulo}-${i}`} className={f.match_ok === false ? 'sin-match' : undefined}>
                    <td className="col-n">{cellNum(f.n)}</td>
                    <td className="col-linea">{f.linea}</td>
                    <td className="col-empresa">{f.empresa}</td>
                    {(f.por_anio ?? []).map((c, ci) => (
                      <td key={ci} className="col-anio">{cellNum(c)}</td>
                    ))}
                    <td className="col-tot">{cellNum(f.parque_total)}</td>
                    <td className="col-falt">{cellNum(f.falt_exce)}</td>
                    <td className="col-auth">{cellNum(f.autoriz)}</td>
                    <td className="col-op">{cellNum(f.operat)}</td>
                    <td className="col-res">{cellNum(f.reserv)}</td>
                    <td className="col-dec">{cellNum(f.declar)}</td>
                  </tr>
                ))}
                <tr className="subtotal">
                  <td className="col-n" />
                  <td className="col-linea">{z.subtotal?.linea || 'Sub-total'}</td>
                  <td className="col-empresa" />
                  {(z.subtotal?.por_anio ?? []).map((c, ci) => (
                    <td key={ci} className="col-anio">{cellNum(c)}</td>
                  ))}
                  <td className="col-tot">{cellNum(z.subtotal?.parque_total)}</td>
                  <td className="col-falt">{cellNum(z.subtotal?.falt_exce)}</td>
                  <td className="col-auth">{cellNum(z.subtotal?.autoriz)}</td>
                  <td className="col-op">{cellNum(z.subtotal?.operat)}</td>
                  <td className="col-res">{cellNum(z.subtotal?.reserv)}</td>
                  <td className="col-dec">{cellNum(z.subtotal?.declar)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {data.totales && (
        <div className="cuadro-edad-table-scroll" style={{ marginTop: 8 }}>
          <table className="cuadro-edad-table">
            <tbody>
              <tr className="total">
                <td className="col-n" />
                <td className="col-linea">{data.totales.linea || 'Totales'}</td>
                <td className="col-empresa" />
                {(data.totales.por_anio ?? []).map((c, ci) => (
                  <td key={ci} className="col-anio">{cellNum(c)}</td>
                ))}
                <td className="col-tot">{cellNum(data.totales.parque_total)}</td>
                <td className="col-falt">{cellNum(data.totales.falt_exce)}</td>
                <td className="col-auth">{cellNum(data.totales.autoriz)}</td>
                <td className="col-op">{cellNum(data.totales.operat)}</td>
                <td className="col-res">{cellNum(data.totales.reserv)}</td>
                <td className="col-dec">{cellNum(data.totales.declar)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      <div className="cuadro-edad-leyenda">
        {(data.leyenda_edades ?? []).map((l) => (
          <div key={l.label} className="cuadro-edad-leyenda-item">
            <span className="flecha">◀</span>
            <strong>{l.label}</strong>
            <span className="rango">({l.desde}–{l.hasta})</span>
            <span className="flecha">▶</span>
          </div>
        ))}
      </div>
    </div>
  )
}
