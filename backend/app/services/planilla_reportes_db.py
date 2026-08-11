"""Reportes tipo planilla ITV calculados desde la base (no desde Excel)."""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import date
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Bus, BusEmpresa, Eot, EotLinea, ItvBus, Linea, Zona

HOY = date.today

# Catálogo de pestañas (como en el Excel ITV)
PESTANAS = [
    {"key": "cuadro_edad", "label": "CUADRO DE EDAD", "titulo": "Cuadro de edades del parque operativo"},
    {"key": "bajas", "label": "BAJAS", "titulo": "Parque automotor dado de baja"},
    {"key": "oper_reser_declar", "label": "BUSES OPER RESER Y DECLAR", "titulo": "Buses operativos, reserva y declarados"},
    {"key": "porcentaje_inclusivo", "label": "PORCENTAJE INCLUSIVO", "titulo": "Porcentaje de buses por tipo de servicio"},
    {"key": "graficos", "label": "GRAFICOS", "titulo": "Resumen global parque e ITV"},
    {"key": "porcentaje_itv", "label": "PORCENTAJE OPERATIVO ITV APROBA", "titulo": "ITV aprobada sobre buses declarados"},
    {"key": "porcentaje_resol", "label": "PORCENTAJE OPER RESOL SOBRE DEC", "titulo": "Declarado sobre operativo por resolución"},
    {"key": "cantidad_faltante", "label": "CANTIDAD FALTANTE", "titulo": "Faltantes sobre autorizado y operativo"},
    {"key": "buses_electricos", "label": "BUSES ELECTRICOS", "titulo": "Buses eléctricos por empresa"},
]

_MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _nat_key(s: str) -> list:
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", s or "")]


def _split_linea_tokens(raw: str) -> set[str]:
    s = _fold(raw)
    if not s:
        return set()
    parts = [p for p in re.split(r"[\s]+", s) if p and p != "Y"]
    tokens = set(parts)
    tokens.add(re.sub(r"\s+", "", s))
    m = re.fullmatch(r"ELECTRICO\s*(\d+)", s)
    if m:
        return {f"E{m.group(1)}", f"ELECTRICO{m.group(1)}", s}
    return tokens


def _label_lineas(numeros: list[str]) -> str:
    shorts: list[str] = []
    seen: set[str] = set()
    for n in sorted({(x or "").strip() for x in numeros if x}, key=_nat_key):
        m = re.fullmatch(r"(?i)electrico\s*(\d+)", n)
        label = f"E{m.group(1)}" if m else n
        if label not in seen:
            seen.add(label)
            shorts.append(label)
    if len(shorts) <= 2:
        return " Y ".join(shorts)
    return "-".join(shorts)


def _linea_match_eot_legacy(numero_linea: str, eot_linea: str) -> bool:
    """Cruza numero_linea con eots.eot_linea (legado, p.ej. '53-58-128')."""
    lin = _split_linea_tokens(numero_linea)
    eot = _split_linea_tokens(eot_linea)
    return bool(lin and eot and (lin & eot))


async def _explotacion_por_linea(
    db: AsyncSession,
    eots_by_id: dict[int, Eot],
    lineas: list[Linea],
) -> dict[int, list[Eot]]:
    """
    id_linea → EOTs que la explotan.
    Prioridad: public.eot_linea vigente; si está vacío, eots.eot_linea (texto).
    """
    hoy = HOY()
    res = await db.execute(select(EotLinea))
    vinculos = list(res.scalars().all())
    vigentes = [
        v for v in vinculos
        if v.fecha_fin is None or v.fecha_fin >= hoy
    ]
    out: dict[int, list[Eot]] = defaultdict(list)
    if vigentes:
        seen: set[tuple[int, int]] = set()
        for v in vigentes:
            eot = eots_by_id.get(v.eot_id)
            if not eot:
                continue
            key = (v.id_linea, eot.eot_id)
            if key in seen:
                continue
            seen.add(key)
            out[v.id_linea].append(eot)
        return out

    for lin in lineas:
        num = (lin.numero_linea or "").strip()
        if not num:
            continue
        for eot in eots_by_id.values():
            if _linea_match_eot_legacy(num, eot.eot_linea or ""):
                out[lin.id_linea].append(eot)
    return out


def _pct(num: float, den: float) -> Optional[float]:
    if not den:
        return None
    return round(num / den, 4)


def _empresa_label(eot: Eot) -> str:
    nom = (eot.eot_nombre or "").strip()
    lin = (eot.eot_linea or "").strip()
    if nom and lin:
        return f"{nom} - Línea {lin}"
    return nom or lin or (eot.id_eot_vmt_hex or str(eot.eot_id))


async def _eots_activas(db: AsyncSession) -> list[Eot]:
    """
    EOTs permisionarias activas en CID (situacion=1)
    O con parque vigente en registro_habilitacion (ej. ARAPOTI situacion=0).
    """
    eots_con_parque = (
        select(BusEmpresa.id_eot)
        .join(Bus, Bus.id_bus == BusEmpresa.id_bus)
        .where(
            BusEmpresa.fecha_fin_asignacion.is_(None),
            Bus.estado_bus == "ACTIVO",
            BusEmpresa.id_eot.is_not(None),
        )
        .distinct()
    )
    res = await db.execute(
        select(Eot)
        .where(
            and_(
                Eot.permisionario == True,
                or_(Eot.situacion == 1, Eot.id_eot_vmt_hex.in_(eots_con_parque)),
            )
        )
        .order_by(Eot.eot_nombre)
    )
    return list(res.scalars().all())


async def _buses_por_eot(db: AsyncSession, solo_activos: bool = True) -> dict[str, list[Bus]]:
    """id_eot_vmt_hex → buses con asignación vigente."""
    q = (
        select(BusEmpresa, Bus)
        .join(Bus, Bus.id_bus == BusEmpresa.id_bus)
        .where(BusEmpresa.fecha_fin_asignacion.is_(None))
        .options(
            selectinload(Bus.tipo_servicio_rel),
            selectinload(Bus.marca),
            selectinload(Bus.tipo_carroceria),
            selectinload(Bus.marca_carroceria),
        )
    )
    if solo_activos:
        q = q.where(Bus.estado_bus == "ACTIVO")
    rows = (await db.execute(q)).all()
    out: dict[str, list[Bus]] = defaultdict(list)
    for asig, bus in rows:
        if asig.id_eot:
            out[asig.id_eot].append(bus)
    return out


async def _itv_vigente_map(db: AsyncSession) -> dict[int, ItvBus]:
    res = await db.execute(select(ItvBus).where(ItvBus.es_vigente.is_(True)))
    return {itv.id_bus: itv for itv in res.scalars().all()}


def _tipo_nombre(bus: Bus) -> str:
    if bus.tipo_servicio_rel and bus.tipo_servicio_rel.nombre:
        return bus.tipo_servicio_rel.nombre.upper()
    return ""


def _es_diferencial(nombre: str) -> bool:
    return "DIFER" in nombre and "ELECTR" not in nombre


def _es_convencional(nombre: str) -> bool:
    return "CONVEN" in nombre


def _es_electrico(bus: Bus) -> bool:
    t = _tipo_nombre(bus)
    if "ELECTR" in t:
        return True
    comb = (bus.combustible or "").upper()
    return "ELECTR" in comb


def _fila_vacia(ncols: int) -> list[Any]:
    return [None] * ncols


async def reporte_cuadro_edad(db: AsyncSession) -> dict:
    """
    Replica el layout de la hoja Excel «CUADRO DE EDAD» con datos vivos:
    public.zonas → public.lineas → empresa explotadora (eot_linea / eots.eot_linea).
    """
    hoy = HOY()
    anio_actual = hoy.year
    anios = list(range(2006, anio_actual + 2))
    buses_map = await _buses_por_eot(db, solo_activos=True)
    eots = list((await db.execute(select(Eot))).scalars().all())
    eots_by_id = {e.eot_id: e for e in eots if e.eot_id is not None}

    zonas = list((await db.execute(select(Zona).order_by(Zona.id_zona))).scalars().all())
    lineas = list((await db.execute(
        select(Linea).where(Linea.id_zona.is_not(None)).order_by(Linea.numero_linea)
    )).scalars().all())
    lineas_por_zona: dict[int, list[Linea]] = defaultdict(list)
    for lin in lineas:
        if lin.id_zona is not None:
            lineas_por_zona[lin.id_zona].append(lin)

    explotacion = await _explotacion_por_linea(db, eots_by_id, lineas)

    headers = [
        "Nº", "Línea", "Empresa",
        *[str(a) for a in anios],
        "Parque Total", "Parque Falt/Exce",
        "Autoriz.(a)", "Operat.(b)", "Reserv.(c)", "Declar.(d)",
    ]
    ncols = len(headers)

    def build_data_row(n: Optional[int], linea_label: str, eot: Optional[Eot]) -> dict[str, Any]:
        buses = buses_map.get(eot.id_eot_vmt_hex, []) if eot and eot.id_eot_vmt_hex else []
        counts = {a: 0 for a in anios}
        for b in buses:
            if isinstance(b.año, int) and b.año in counts:
                counts[b.año] += 1
            elif isinstance(b.año, int) and b.año < anios[0]:
                counts[anios[0]] += 1
        parque_total = sum(counts.values())
        autoriz = int(eot.autorizado or 0) if eot else 0
        operat = int(eot.operativo or 0) if eot else 0
        reserv = int(eot.reserva or 0) if eot else 0
        declar = parque_total
        falt = parque_total - autoriz
        return {
            "tipo": "data",
            "n": n,
            "linea": linea_label,
            "empresa": ((eot.eot_nombre or "").strip() if eot else "—"),
            "por_anio": [counts[a] for a in anios],
            "parque_total": parque_total,
            "falt_exce": falt,
            "autoriz": autoriz,
            "operat": operat,
            "reserv": reserv,
            "declar": declar,
            "id_eot": eot.id_eot_vmt_hex if eot else None,
            "match_ok": eot is not None,
        }

    def sum_rows(filas_data: list[dict]) -> dict[str, Any]:
        por_anio = [sum(f["por_anio"][i] for f in filas_data) for i in range(len(anios))]
        parque = sum(f["parque_total"] for f in filas_data)
        autoriz = sum(f["autoriz"] for f in filas_data)
        return {
            "tipo": "subtotal",
            "n": None,
            "linea": "Sub-total",
            "empresa": "",
            "por_anio": por_anio,
            "parque_total": parque,
            "falt_exce": parque - autoriz,
            "autoriz": autoriz,
            "operat": sum(f["operat"] for f in filas_data),
            "reserv": sum(f["reserv"] for f in filas_data),
            "declar": parque,
        }

    def row_to_cells(row: dict[str, Any]) -> list[Any]:
        return [
            row.get("n"),
            row.get("linea"),
            row.get("empresa"),
            *row.get("por_anio", []),
            row.get("parque_total"),
            row.get("falt_exce"),
            row.get("autoriz"),
            row.get("operat"),
            row.get("reserv"),
            row.get("declar"),
        ]

    zonales_out: list[dict[str, Any]] = []
    all_data: list[dict[str, Any]] = []
    filas_grid: list[list[Any]] = []
    row_kinds: list[str] = []

    titulo = f"CUADRO DE EDADES DE LAS UNIDADES DE TRANSPORTE DEL AREA METROPOLITANA - AÑO {anio_actual}"
    actualizacion = f"{_MESES_ES[hoy.month - 1]}-{str(anio_actual)[2:]}"
    fecha_parque = hoy.strftime("%d-%m-%y")

    # Encabezado global (para Excel / filas)
    filas_grid.append([titulo] + [None] * (ncols - 2) + ["DPTO DE REGISTRO Y HABILITACIÓN"])
    row_kinds.append("title")
    filas_grid.append([None, "Actualización:", actualizacion] + [None] * (ncols - 3))
    row_kinds.append("meta")
    filas_grid.append(["PARQUE OPERATIVO DE EMPRESAS"] + [None] * (ncols - 1))
    row_kinds.append("banner")

    n_seq = 0
    for z in zonas:
        filas_data: list[dict[str, Any]] = []
        grupos: dict[int, dict[str, Any]] = {}
        sin_eot: list[Linea] = []
        for lin in lineas_por_zona.get(z.id_zona, []):
            eots_lin = explotacion.get(lin.id_linea) or []
            if not eots_lin:
                sin_eot.append(lin)
                continue
            for eot in eots_lin:
                g = grupos.setdefault(eot.eot_id, {"eot": eot, "lineas": []})
                g["lineas"].append(lin)

        for g in sorted(grupos.values(), key=lambda x: _nat_key((x["eot"].eot_nombre or ""))):
            n_seq += 1
            label = _label_lineas([ln.numero_linea or "" for ln in g["lineas"]])
            filas_data.append(build_data_row(n_seq, label, g["eot"]))
        for lin in sin_eot:
            n_seq += 1
            filas_data.append(build_data_row(n_seq, (lin.numero_linea or "—").strip(), None))

        titulo_zonal = z.nombre or f"Zonal {z.id_zona}"
        if z.descripcion:
            titulo_zonal = f"{titulo_zonal} ({z.descripcion})"

        # Cabecera de zonal
        z_header = _fila_vacia(ncols)
        z_header[1] = titulo_zonal
        z_header[3 + len(anios)] = "Parque Total"
        z_header[4 + len(anios)] = "Parque Falt/Exce"
        z_header[5 + len(anios)] = "PARQUE Actual:"
        z_header[7 + len(anios)] = fecha_parque
        filas_grid.append(z_header)
        row_kinds.append("zonal")

        # Headers columnas (Parque Total / Falt van en la fila zonal, no aquí)
        col_header = headers.copy()
        for i in range(3 + len(anios), 5 + len(anios)):
            col_header[i] = None
        filas_grid.append(col_header)
        row_kinds.append("col_header")

        for fr in filas_data:
            filas_grid.append(row_to_cells(fr))
            row_kinds.append("data")
            all_data.append(fr)

        sub = sum_rows(filas_data) if filas_data else sum_rows([])
        filas_grid.append(row_to_cells(sub))
        row_kinds.append("subtotal")

        zonales_out.append({
            "titulo": titulo_zonal,
            "id_zona": z.id_zona,
            "filas": filas_data,
            "subtotal": sub,
        })

    # Totales generales
    total = sum_rows(all_data)
    total["linea"] = "Totales"
    total["tipo"] = "total"
    filas_grid.append(_fila_vacia(ncols))
    row_kinds.append("blank")
    filas_grid.append(row_to_cells(total))
    row_kinds.append("total")

    # Leyenda edades
    filas_grid.append(_fila_vacia(ncols))
    row_kinds.append("blank")
    leyenda = _fila_vacia(ncols)
    # 2006-2012 = cols index 3..9, 2013-2019, 2020-fin
    leyenda[3] = "14 a 20 Años"
    leyenda[3 + 7] = "7 a 13 Años"
    leyenda[3 + 14] = "0 a 6 Años"
    filas_grid.append(leyenda)
    row_kinds.append("leyenda")

    return {
        "key": "cuadro_edad",
        "layout": "cuadro_edad_zonal",
        "hoja": "CUADRO DE EDAD",
        "titulo": titulo,
        "nota": f"Actualización: {actualizacion}",
        "dpto": "DPTO DE REGISTRO Y HABILITACIÓN",
        "banner": "PARQUE OPERATIVO DE EMPRESAS",
        "actualizacion": actualizacion,
        "fecha_parque": fecha_parque,
        "anio": anio_actual,
        "anios": anios,
        "headers": headers,
        "zonales": zonales_out,
        "totales": total,
        "leyenda_edades": [
            {"label": "14 a 20 Años", "desde": 2006, "hasta": 2012},
            {"label": "7 a 13 Años", "desde": 2013, "hasta": 2019},
            {"label": "0 a 6 Años", "desde": 2020, "hasta": anios[-1]},
        ],
        "total_filas": len(all_data),
        "filas": filas_grid,
        "row_kinds": row_kinds,
        "fuente": "public.zonas + public.lineas + public.eots",
        "fecha": hoy.isoformat(),
    }


async def reporte_bajas(db: AsyncSession) -> dict:
    """Buses con estado INACTIVO — listado estilo planilla de bajas."""
    itv_map = await _itv_vigente_map(db)

    q = (
        select(Bus)
        .where(Bus.estado_bus == "INACTIVO")
        .options(
            selectinload(Bus.marca),
            selectinload(Bus.tipo_carroceria),
            selectinload(Bus.marca_carroceria),
        )
        .order_by(Bus.numero_orden.nullslast(), Bus.id_bus)
    )
    buses = list((await db.execute(q)).scalars().all())

    # Última asignación (cualquier motivo) para mostrar empresa
    emp_map: dict[int, str] = {}
    if buses:
        ids = [b.id_bus for b in buses]
        asig_q = await db.execute(
            select(BusEmpresa, Eot)
            .outerjoin(Eot, Eot.id_eot_vmt_hex == BusEmpresa.id_eot)
            .where(BusEmpresa.id_bus.in_(ids))
            .order_by(BusEmpresa.fecha_asignacion.desc())
        )
        for asig, eot in asig_q.all():
            if asig.id_bus not in emp_map:
                emp_map[asig.id_bus] = _empresa_label(eot) if eot else (asig.id_eot or "—")

    headers = [
        "Nº", "Nº Orden", "Marca", "Año", "Chasis", "RUA",
        "Tipo carrocería", "Marca carrocería",
        "Fecha ITV", "Vencimiento ITV", "Situación ITV", "Empresa",
    ]
    rows: list[list[Any]] = []
    for n, bus in enumerate(buses, 1):
        itv = itv_map.get(bus.id_bus)
        sit = None
        if itv:
            sit = "APROBADA" if itv.fecha_vencimiento >= HOY() else "VENCIDA"
        rows.append([
            n,
            bus.numero_orden,
            bus.marca.nombre if bus.marca else "—",
            bus.año,
            bus.numero_chassis,
            bus.rua,
            bus.tipo_carroceria.descripcion if bus.tipo_carroceria else "—",
            bus.marca_carroceria.nombre if bus.marca_carroceria else "—",
            itv.fecha_itv.isoformat() if itv and itv.fecha_itv else "—",
            itv.fecha_vencimiento.isoformat() if itv and itv.fecha_vencimiento else "—",
            sit or "—",
            emp_map.get(bus.id_bus, "—"),
        ])
    return _pack("bajas", headers, rows, f"Buses INACTIVO · {HOY().isoformat()}")


async def reporte_oper_reser_declar(db: AsyncSession) -> dict:
    eots = await _eots_activas(db)
    buses_map = await _buses_por_eot(db, solo_activos=True)
    headers = [
        "Nº", "Empresa",
        "Operativa declarada", "Reserva declarada", "Total declarado",
        "Diferencial", "Convencional", "Eléctrico",
        "Total difer.", "Total conven.",
    ]
    rows = []
    n = 0
    for eot in eots:
        hex_id = eot.id_eot_vmt_hex
        if not hex_id:
            continue
        buses = buses_map.get(hex_id, [])
        op_dec = eot.operativo_declarado if eot.operativo_declarado is not None else len(buses)
        res_dec = eot.reserva_declarada or 0
        dif = sum(1 for b in buses if _es_diferencial(_tipo_nombre(b)))
        conv = sum(1 for b in buses if _es_convencional(_tipo_nombre(b)))
        elec = sum(1 for b in buses if _es_electrico(b))
        n += 1
        rows.append([
            n,
            _empresa_label(eot),
            op_dec,
            res_dec,
            (op_dec or 0) + (res_dec or 0),
            dif,
            conv,
            elec,
            dif + elec,
            conv,
        ])
    return _pack("oper_reser_declar", headers, rows, f"Fecha: {HOY().isoformat()}")


async def reporte_porcentaje_inclusivo(db: AsyncSession) -> dict:
    """Sin flag inclusivo en DB: muestra distribución por tipo de servicio."""
    eots = await _eots_activas(db)
    buses_map = await _buses_por_eot(db, solo_activos=True)
    headers = [
        "Empresa", "Operativo resolución",
        "Diferencial", "Convencional", "Eléctrico",
        "% Diferencial", "% Convencional", "% Eléctrico",
    ]
    rows = []
    for eot in eots:
        hex_id = eot.id_eot_vmt_hex
        if not hex_id:
            continue
        buses = buses_map.get(hex_id, [])
        operativo = eot.operativo or len(buses) or 0
        if not buses and not operativo:
            continue
        dif = sum(1 for b in buses if _es_diferencial(_tipo_nombre(b)))
        conv = sum(1 for b in buses if _es_convencional(_tipo_nombre(b)))
        elec = sum(1 for b in buses if _es_electrico(b))
        base = len(buses) or 1
        rows.append([
            _empresa_label(eot),
            operativo,
            dif,
            conv,
            elec,
            _pct(dif, base),
            _pct(conv, base),
            _pct(elec, base),
        ])
    return _pack(
        "porcentaje_inclusivo",
        headers,
        rows,
        f"Fecha: {HOY().isoformat()} · Nota: sin marcador inclusivo (*) en DB; se muestra tipo de servicio",
    )


async def reporte_graficos(db: AsyncSession) -> dict:
    buses_map = await _buses_por_eot(db, solo_activos=True)
    itv_map = await _itv_vigente_map(db)
    all_buses: list[Bus] = []
    for lst in buses_map.values():
        all_buses.extend(lst)
    # dedupe
    by_id = {b.id_bus: b for b in all_buses}
    all_buses = list(by_id.values())

    dif = sum(1 for b in all_buses if _es_diferencial(_tipo_nombre(b)))
    conv = sum(1 for b in all_buses if _es_convencional(_tipo_nombre(b)))
    elec = sum(1 for b in all_buses if _es_electrico(b))
    total = len(all_buses) or 1

    itv_ok = 0
    itv_venc = 0
    sin_itv = 0
    for b in all_buses:
        itv = itv_map.get(b.id_bus)
        if not itv:
            sin_itv += 1
        elif itv.fecha_vencimiento >= HOY():
            itv_ok += 1
        else:
            itv_venc += 1

    headers = ["Concepto", "Cantidad", "%"]
    rows = [
        ["ELÉCTRICOS", elec, _pct(elec, total)],
        ["BUSES DIFERENCIALES", dif, _pct(dif, total)],
        ["BUSES CONVENCIONALES", conv, _pct(conv, total)],
        ["TOTAL PARQUE ACTIVO", len(all_buses), 1],
        ["", "", ""],
        ["BUSES ITV APROBADO / VIGENTE", itv_ok, _pct(itv_ok, total)],
        ["BUSES ITV VENCIDO", itv_venc, _pct(itv_venc, total)],
        ["BUSES SIN ITV", sin_itv, _pct(sin_itv, total)],
    ]
    return _pack("graficos", headers, rows, f"Fecha: {HOY().isoformat()}")


async def reporte_porcentaje_itv(db: AsyncSession) -> dict:
    eots = await _eots_activas(db)
    buses_map = await _buses_por_eot(db, solo_activos=True)
    itv_map = await _itv_vigente_map(db)
    headers = [
        "Nº", "Empresa", "Autorizado", "Operativo", "Reserva",
        "Buses declarados", "Con ITV vigente", "% sobre declarados",
    ]
    rows = []
    n = 0
    for eot in eots:
        hex_id = eot.id_eot_vmt_hex
        if not hex_id:
            continue
        buses = buses_map.get(hex_id, [])
        declarado = eot.operativo_declarado if eot.operativo_declarado is not None else len(buses)
        itv_ok = sum(
            1 for b in buses
            if (itv := itv_map.get(b.id_bus)) and itv.fecha_vencimiento >= HOY()
        )
        n += 1
        rows.append([
            n,
            _empresa_label(eot),
            eot.autorizado,
            eot.operativo,
            eot.reserva,
            declarado,
            itv_ok,
            _pct(itv_ok, declarado or 0),
        ])
    return _pack("porcentaje_itv", headers, rows, f"Fecha: {HOY().isoformat()}")


async def reporte_porcentaje_resol(db: AsyncSession) -> dict:
    eots = await _eots_activas(db)
    buses_map = await _buses_por_eot(db, solo_activos=True)
    headers = [
        "Nº", "Empresa", "Autorizado", "Operativo", "Reserva",
        "Declarado oper.", "Declarado reserva", "Total declarado",
        "Faltante 75%", "% declarado / operativo",
    ]
    rows = []
    n = 0
    for eot in eots:
        hex_id = eot.id_eot_vmt_hex
        if not hex_id:
            continue
        buses = buses_map.get(hex_id, [])
        op = eot.operativo or 0
        op_dec = eot.operativo_declarado if eot.operativo_declarado is not None else len(buses)
        res_dec = eot.reserva_declarada or 0
        total_dec = (op_dec or 0) + (res_dec or 0)
        umbral = round(op * 0.75, 2) if op else 0
        faltante = max(0, umbral - total_dec) if op else 0
        n += 1
        rows.append([
            n,
            _empresa_label(eot),
            eot.autorizado,
            op,
            eot.reserva,
            op_dec,
            res_dec,
            total_dec,
            faltante,
            _pct(total_dec, op),
        ])
    return _pack("porcentaje_resol", headers, rows, f"Fecha: {HOY().isoformat()}")


async def reporte_cantidad_faltante(db: AsyncSession) -> dict:
    eots = await _eots_activas(db)
    buses_map = await _buses_por_eot(db, solo_activos=True)
    headers = [
        "Nº", "Empresa", "Autorizado", "Operativo", "Reserva",
        "Declarado oper.", "Declarado reserva", "Total declarado",
        "Faltante autorizado", "Faltante operativo",
        "% autorizado", "% operativo",
    ]
    rows = []
    n = 0
    for eot in eots:
        hex_id = eot.id_eot_vmt_hex
        if not hex_id:
            continue
        buses = buses_map.get(hex_id, [])
        aut = eot.autorizado or 0
        op = eot.operativo or 0
        op_dec = eot.operativo_declarado if eot.operativo_declarado is not None else len(buses)
        res_dec = eot.reserva_declarada or 0
        total_dec = (op_dec or 0) + (res_dec or 0)
        n += 1
        rows.append([
            n,
            _empresa_label(eot),
            aut,
            op,
            eot.reserva,
            op_dec,
            res_dec,
            total_dec,
            max(0, aut - total_dec),
            max(0, op - total_dec),
            _pct(total_dec, aut),
            _pct(total_dec, op),
        ])
    return _pack("cantidad_faltante", headers, rows, f"Fecha: {HOY().isoformat()}")


async def reporte_buses_electricos(db: AsyncSession) -> dict:
    eots = await _eots_activas(db)
    buses_map = await _buses_por_eot(db, solo_activos=True)
    headers = [
        "Empresa", "Autorizado por resolución", "Eléctricos", "% eléctricos",
    ]
    rows = []
    for eot in eots:
        hex_id = eot.id_eot_vmt_hex
        if not hex_id:
            continue
        buses = buses_map.get(hex_id, [])
        elec = sum(1 for b in buses if _es_electrico(b))
        aut = eot.autorizado or 0
        rows.append([
            _empresa_label(eot),
            aut,
            elec,
            _pct(elec, aut or len(buses) or 1),
        ])
    return _pack("buses_electricos", headers, rows, f"Fecha: {HOY().isoformat()}")


def _pack(key: str, headers: list[str], rows: list[list[Any]], nota: str) -> dict:
    meta = next((p for p in PESTANAS if p["key"] == key), {"label": key, "titulo": key})
    # Convertir a grilla tipo Excel: fila título + headers + data
    filas: list[list[Any]] = [
        [meta["titulo"]],
        [nota],
        [],
        headers,
        *rows,
    ]
    return {
        "key": key,
        "hoja": meta["label"],
        "titulo": meta["titulo"],
        "nota": nota,
        "headers": headers,
        "total_filas": len(rows),
        "filas": filas,
        "fuente": "registro_habilitacion + public.eots",
        "fecha": HOY().isoformat(),
    }


HANDLERS = {
    "cuadro_edad": reporte_cuadro_edad,
    "bajas": reporte_bajas,
    "oper_reser_declar": reporte_oper_reser_declar,
    "porcentaje_inclusivo": reporte_porcentaje_inclusivo,
    "graficos": reporte_graficos,
    "porcentaje_itv": reporte_porcentaje_itv,
    "porcentaje_resol": reporte_porcentaje_resol,
    "cantidad_faltante": reporte_cantidad_faltante,
    "buses_electricos": reporte_buses_electricos,
}


async def obtener_reporte(db: AsyncSession, key: str) -> dict:
    handler = HANDLERS.get(key)
    if not handler:
        raise KeyError(f"Reporte desconocido: {key}")
    return await handler(db)
