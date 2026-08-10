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

from app.models import Bus, BusEmpresa, Eot, ItvBus

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

# Orden y zonales del Excel ITV → hoja CUADRO DE EDAD (match por tokens de nombre)
ZONALES_CUADRO_EDAD: list[dict[str, Any]] = [
    {
        "titulo": "Zonal 1 (San Lorenzo - Capiatá - J.A.Saldívar)",
        "empresas": [
            {"n": 1, "linea": "12 Y 43", "empresa": "Magno SA", "match": ["MAGNO"]},
            {"n": 2, "linea": "19", "empresa": "Gonzalez Quiñonez SRL", "match": ["GONZALEZ", "QUINONEZ"]},
            {"n": 3, "linea": "45-50-56", "empresa": "La Sanlorenzana S.A. de Transporte y T.", "match": ["SANLORENZANA"]},
            {"n": 4, "linea": "53-58-128", "empresa": "Capiatá S.R.L.", "match": ["CAPIATA"]},
            {"n": None, "linea": "E1,E2 Y E3", "empresa": "ARAPOTI", "match": ["ARAPOTI"]},
            {"n": 5, "linea": "10-21 y 96", "empresa": "Aldana S.A.", "match": ["ALDANA"]},
        ],
    },
    {
        "titulo": "Zonal 2 (M.R. Alonso - Limpio - Bajo Chaco)",
        "empresas": [
            {"n": 6, "linea": "5 CH.", "empresa": "La Chaqueña S.A.T.C.", "match": ["CHAQUENA"]},
            {"n": 7, "linea": "34", "empresa": "Ciudad de Limpio S.R.L.", "match": ["CIUDAD", "LIMPIO"]},
            {"n": 8, "linea": "36", "empresa": "Campo Limpio S.A.", "match": ["CAMPO", "LIMPIO"]},
            {"n": 9, "linea": "40", "empresa": "ADUSA", "match": ["USUARIOS"]},
            {"n": 10, "linea": "35", "empresa": "EL BUS S.A.", "match": ["EL BUS"]},
            {"n": 11, "linea": "44", "empresa": "XIMEX S.A.", "match": ["XIMEX"]},
            {"n": 12, "linea": "101-A-102", "empresa": "Coop. Puerto Elseño Ko Che Ltda.", "match": ["ELSE"]},
            {"n": 13, "linea": "101-B", "empresa": "Puerto Falcon SACI", "match": ["FALCON"]},
        ],
    },
    {
        "titulo": "Zonal 3 (Luque - Areguá)",
        "empresas": [
            {"n": 14, "linea": "5", "empresa": "Ciudad de Luque S.R.L.", "match": ["CIUDAD", "LUQUE"]},
            {"n": 15, "linea": "11 y 203", "empresa": "Grupo Bene S.A.", "match": ["GRUPO", "BENE"]},
            {"n": 16, "linea": "28", "empresa": "Gral. Aquino S.R.L.", "match": ["AQUINO"]},
            {"n": 17, "linea": "30", "empresa": "Vanguardia S.A.C.I.", "match": ["VANGUARDIA"]},
            {"n": 18, "linea": "49 y 220", "empresa": "La Limpeña S.R.L.", "match": ["LIMPENA"]},
            {"n": 19, "linea": "110", "empresa": "Cerro Koi S.A.", "match": ["CERRO", "KOI"]},
            {"n": 20, "linea": "111", "empresa": "Aregüeña S.A.", "match": ["AREGUE"]},
        ],
    },
    {
        "titulo": "Zonal 4 (Fernando de la Mora)",
        "empresas": [],
    },
    {
        "titulo": "Zonal 5 (Ñemb., V. Elisa, S. Antonio, Ytor., Guaram.)",
        "empresas": [
            {"n": 21, "linea": "15-1-2-3-4 Y 47", "empresa": "Automotores Guaraní S.R.L.", "match": ["GUARANI"]},
            {"n": 22, "linea": "88", "empresa": "La Lomita S.A.", "match": ["LOMITA"]},
            {"n": 23, "linea": "18 - 26 y 52", "empresa": "Lince S.R.L.", "match": ["LINCE"]},
            {"n": 24, "linea": "38", "empresa": "Mariscal López S.R.L.", "match": ["MARISCAL"]},
            {"n": 25, "linea": "54", "empresa": "G.M. de T y T S.R.L.", "match": ["GM T"]},
        ],
    },
    {
        "titulo": "Zonal 6 (Lambaré)",
        "empresas": [
            {"n": 30, "linea": "48-51 Y 85", "empresa": "San Isidro S.R.L.", "match": ["SAN ISIDRO"]},
            {"n": 31, "linea": "8 y 31", "empresa": "De la Conquista S.A.", "match": ["CONQUISTA"]},
            {"n": 32, "linea": "23-24 Y 33", "empresa": "TTL Lambaré S.A.", "match": ["TTL"]},
            {"n": 33, "linea": "41", "empresa": "1° de diciembre S.R.L.", "match": ["DICIEMBRE"]},
        ],
    },
    {
        "titulo": "Zonal 7 (ACECOR)",
        "empresas": [
            {"n": 34, "linea": "165 y 27", "empresa": "Ñandutí S.A.", "match": ["ANDUTI"]},
            {"n": 35, "linea": "232", "empresa": "Ciudad de Villeta", "match": ["VILLETA"]},
            {"n": 36, "linea": "454", "empresa": "3 de febrero S.A.", "match": ["FEBRERO"]},
            {"n": 37, "linea": "187", "empresa": "San José Obrero S.A.", "match": ["OBRERO"]},
            {"n": 38, "linea": "233", "empresa": "16 de Noviembre S.R.L.", "match": ["NOVIEMBRE"]},
            {"n": 39, "linea": "242", "empresa": "Ypacarai S.A.", "match": ["YPACARAI"]},
        ],
    },
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


def _match_eot(eots: list[Eot], tokens: list[str]) -> Optional[Eot]:
    toks = [_fold(t) for t in tokens if t]
    if not toks:
        return None
    best: Optional[Eot] = None
    best_score = -1
    for eot in eots:
        nom = _fold(eot.eot_nombre or "")
        if not nom:
            continue
        if all(t in nom for t in toks):
            score = sum(len(t) for t in toks) * 10 - abs(len(nom) - sum(len(t) for t in toks))
            if score > best_score:
                best_score = score
                best = eot
    return best


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


async def _eots_para_cuadro(db: AsyncSession) -> list[Eot]:
    """EOTs candidatas al cuadro (permisionarias o con parque / situacion activa)."""
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
        select(Eot).where(
            or_(
                Eot.permisionario == True,
                Eot.situacion == 1,
                Eot.id_eot_vmt_hex.in_(eots_con_parque),
            )
        )
    )
    return list(res.scalars().all())


def _fila_vacia(ncols: int) -> list[Any]:
    return [None] * ncols


async def reporte_cuadro_edad(db: AsyncSession) -> dict:
    """
    Replica el layout de la hoja Excel «CUADRO DE EDAD»:
    título, zonales, años 2006…, Parque Total / Falt-Exce y PARQUE Actual.
    """
    hoy = HOY()
    anio_actual = hoy.year
    anios = list(range(2006, anio_actual + 2))
    buses_map = await _buses_por_eot(db, solo_activos=True)
    eots = await _eots_para_cuadro(db)
    used_ids: set[str] = set()

    headers = [
        "Nº", "Línea", "Empresa",
        *[str(a) for a in anios],
        "Parque Total", "Parque Falt/Exce",
        "Autoriz.(a)", "Operat.(b)", "Reserv.(c)", "Declar.(d)",
    ]
    ncols = len(headers)

    def build_data_row(spec: dict, eot: Optional[Eot]) -> dict[str, Any]:
        buses = buses_map.get(eot.id_eot_vmt_hex, []) if eot and eot.id_eot_vmt_hex else []
        if eot and eot.id_eot_vmt_hex:
            used_ids.add(eot.id_eot_vmt_hex)
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
        # Declar.(d) = parque contado por año (como en la planilla)
        declar = parque_total
        falt = parque_total - autoriz
        por_anio = [counts[a] for a in anios]
        return {
            "tipo": "data",
            "n": spec.get("n"),
            "linea": spec.get("linea") or ((eot.eot_linea or "").strip() if eot else ""),
            "empresa": spec.get("empresa") or ((eot.eot_nombre or "").strip() if eot else "—"),
            "por_anio": por_anio,
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

    for z in ZONALES_CUADRO_EDAD:
        filas_data: list[dict[str, Any]] = []
        for spec in z["empresas"]:
            eot = _match_eot(eots, spec.get("match") or [])
            filas_data.append(build_data_row(spec, eot))

        # Cabecera de zonal
        z_header = _fila_vacia(ncols)
        z_header[1] = z["titulo"]
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
            "titulo": z["titulo"],
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
        "fuente": "registro_habilitacion + public.eots",
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
