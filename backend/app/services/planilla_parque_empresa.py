"""Planillas del parque por empresa.

Dos variantes (sin columna POD/RTD):
- operativa  → subsidio: solo buses con ITV (excluye vencidas / sin fecha)
- empresa    → informes: todos los buses activos + pie de resumen ITV
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Auxiliar,
    Bus,
    BusEmpresa,
    DocumentoBus,
    Eot,
    ItvBus,
    SeguroBus,
    TipoSeguro,
)

HOY = date.today
ModoPlanilla = Literal["operativa", "empresa"]

HEADERS_OPERATIVA = [
    "N° DE ORDEN",
    "MARCA",
    "AÑO",
    "N° CHASSIS",
    "RUA",
    "DOCUMENTOS",
    "HABILITACIÓN",
    "SEGURO PASAJEROS",
    "SEGURO TERCEROS",
    "TIPO DE SERVICIO",
    "TIPO DE CARROCERIA",
    "MARCA DE CARROCERIA",
    "FECHA DE IVENCIMIENTO DEL ITV ANTERIOR",
    "FECHA DE ITV",
    "VENCIMIENTO DE ITV",
    "SITUACION DE ITV aprobada",
    "EMPRESA - LINEA",
]

HEADERS_EMPRESA = [
    "N° DE ORDEN",
    "MARCA",
    "AÑO",
    "N° CHASSIS",
    "RUA",
    "DOCUMENTOS",
    "HABILITACIÓN",
    "SEGURO PASAJEROS",
    "SEGURO TERCEROS",
    "TIPO DE SERVICIO",
    "TIPO DE CARROCERIA",
    "MARCA DE CARROCERIA",
    "FECHA DE ITV",
    "VENCIMIENTO DE ITV",
    "SITUACION DE ITV aprobada o vencida",
    "EMPRESA - LINEA",
]


def _headers(modo: ModoPlanilla) -> list[str]:
    return HEADERS_OPERATIVA if modo == "operativa" else HEADERS_EMPRESA


def _ncols(modo: ModoPlanilla) -> int:
    return len(_headers(modo))


def _empresa_label(eot: Eot) -> str:
    nom = (eot.eot_nombre or "").strip()
    lin = (eot.eot_linea or "").strip()
    if nom and lin:
        return f"{nom} - Línea {lin}"
    return nom or lin or (eot.id_eot_vmt_hex or str(eot.eot_id))


def _sheet_name(eot: Eot, modo: ModoPlanilla) -> str:
    lin = (eot.eot_linea or "").strip()
    nom = (eot.eot_nombre or "").strip()
    prefix = "OP " if modo == "operativa" else "EMP "
    raw = f"{prefix}{lin} {nom}" if lin else f"{prefix}{nom}"
    cleaned = re.sub(r'[\[\]:*?/\\]', " ", raw).strip()
    return (cleaned or "Empresa")[:31]


def _tipo_servicio_label(bus: Bus) -> str:
    base = (bus.tipo_servicio_rel.nombre if bus.tipo_servicio_rel else "") or ""
    base = base.strip().upper()
    if not base:
        return ""
    if bus.tiene_rampa and "(*)" not in base:
        return f"{base} (*)"
    return base


def _tipo_sort_key(label: str) -> tuple[int, int, str]:
    s = label.upper()
    has_star = 1 if "(*)" in s else 0
    core = s.replace(" (*)", "").strip()
    if "CONVEN" in core:
        return (0, has_star, label)
    if "DIFER" in core and "ELECTR" not in core:
        return (1, has_star, label)
    if "ELECTR" in core:
        return (2, 0, label)
    return (3, has_star, label)


def _fmt_fecha(val: Optional[date]) -> Any:
    return val if val else None


def _es_convencional(label: str) -> bool:
    return "CONVEN" in label.upper()


def _es_diferencial(label: str) -> bool:
    s = label.upper()
    return "DIFER" in s and "ELECTR" not in s


def _es_electrico(label: str) -> bool:
    return "ELECTR" in label.upper()


async def _eots_con_parque(db: AsyncSession, ids: Optional[list[str]] = None) -> list[Eot]:
    q = (
        select(Eot)
        .where(Eot.permisionario.is_(True))
        .order_by(Eot.eot_nombre)
    )
    if ids:
        q = q.where(Eot.id_eot_vmt_hex.in_(ids))
    eots = list((await db.execute(q)).scalars().all())
    if ids:
        order = {h: i for i, h in enumerate(ids)}
        eots.sort(key=lambda e: order.get(e.id_eot_vmt_hex or "", 9999))
    return eots


async def _buses_por_eot(db: AsyncSession) -> dict[str, list[Bus]]:
    q = (
        select(BusEmpresa, Bus)
        .join(Bus, Bus.id_bus == BusEmpresa.id_bus)
        .where(
            BusEmpresa.fecha_fin_asignacion.is_(None),
            Bus.estado_bus == "ACTIVO",
        )
        .options(
            selectinload(Bus.marca),
            selectinload(Bus.tipo_carroceria),
            selectinload(Bus.marca_carroceria),
            selectinload(Bus.tipo_servicio_rel),
        )
    )
    out: dict[str, list[Bus]] = {}
    for asig, bus in (await db.execute(q)).all():
        if asig.id_eot:
            out.setdefault(asig.id_eot, []).append(bus)
    return out


async def _auxiliar_por_rua(db: AsyncSession) -> dict[str, Auxiliar]:
    rows = (await db.execute(select(Auxiliar))).scalars().all()
    return {r.RUA: r for r in rows if r.RUA}


async def _itv_por_bus(db: AsyncSession) -> dict[int, list[ItvBus]]:
    rows = list(
        (await db.execute(select(ItvBus).order_by(ItvBus.fecha_vencimiento.desc()))).scalars().all()
    )
    out: dict[int, list[ItvBus]] = {}
    for itv in rows:
        out.setdefault(itv.id_bus, []).append(itv)
    return out


async def _seguros_por_bus(db: AsyncSession) -> dict[int, dict[str, SeguroBus]]:
    tipo_rows = (await db.execute(select(TipoSeguro))).scalars().all()
    tipo_by_id = {t.id_tipo_seguro: (t.nombre or "").upper() for t in tipo_rows}
    rows = (
        await db.execute(select(SeguroBus).where(SeguroBus.seguro_vigente.is_(True)))
    ).scalars().all()
    out: dict[int, dict[str, SeguroBus]] = {}
    for seg in rows:
        nombre = tipo_by_id.get(seg.id_tipo_seguro, "")
        if not nombre:
            continue
        out.setdefault(seg.id_bus, {})[nombre] = seg
    return out


async def _docs_por_bus(db: AsyncSession) -> dict[int, dict[str, DocumentoBus]]:
    rows = (await db.execute(select(DocumentoBus))).scalars().all()
    out: dict[int, dict[str, DocumentoBus]] = {}
    for doc in rows:
        tipo = (doc.tipo_documento or "").upper()
        if not tipo:
            continue
        out.setdefault(doc.id_bus, {})[tipo] = doc
    return out


def _doc_estado(doc: Optional[DocumentoBus], fallback: Optional[str] = None) -> str:
    if doc and doc.estado_documento:
        return doc.estado_documento
    if fallback:
        return fallback
    if doc and doc.fecha_vencimiento:
        return "VIGENTE" if doc.fecha_vencimiento >= HOY() else "VENCIDO"
    return ""


def _itv_info(
    itvs: list[ItvBus],
    aux: Optional[Auxiliar],
) -> dict[str, Any]:
    """Resuelve fechas y situación ITV. Sin fechas → VENCIDA (como planilla empresa oficial)."""
    vigente = next((i for i in itvs if i.es_vigente), None)
    if not vigente and itvs:
        vigente = itvs[0]

    anterior = None
    if vigente and len(itvs) > 1:
        for itv in itvs:
            if itv.id_itv != vigente.id_itv:
                anterior = itv
                break

    fecha_itv = vigente.fecha_itv if vigente else (aux.fecha_de_itv if aux else None)
    venc_itv = vigente.fecha_vencimiento if vigente else (aux.vencimiento_de_itv if aux else None)
    itv_ant = (
        anterior.fecha_vencimiento if anterior
        else (aux.fecha_de_vencimiento_del_itv_anterior if aux else None)
    )

    tiene_fechas = bool(fecha_itv or venc_itv)
    if not tiene_fechas:
        # Como en PARQUE EMPRESA: sin fechas → 00/00/00 y VENCIDA
        situacion = "VENCIDA"
        resultado = ""
    else:
        resultado = (
            (vigente.resultado_itv if vigente and vigente.resultado_itv else None)
            or (aux.situacion_de_itv_aprobada if aux else "")
            or "TOTAL"
        )
        # Con fechas de ITV se cuenta como APROBADA (pie oficial Aldana: 127 aprobadas / 2 vencidas)
        situacion = "APROBADA"

    return {
        "fecha_itv": fecha_itv,
        "venc_itv": venc_itv,
        "itv_ant": itv_ant,
        "resultado": resultado,
        "situacion": situacion,
        "tiene_fechas": tiene_fechas,
    }


def _fila_bus(
    bus: Bus,
    empresa_linea: str,
    aux: Optional[Auxiliar],
    itvs: list[ItvBus],
    seguros: dict[str, SeguroBus],
    docs: dict[str, DocumentoBus],
    modo: ModoPlanilla,
) -> tuple[list[Any], dict[str, Any]]:
    itv = _itv_info(itvs, aux)

    seg_pas = seguros.get("PASAJEROS")
    seg_ter = seguros.get("TERCEROS")
    seg_pas_fecha = seg_pas.fecha_vencimiento if seg_pas else (aux.seguro_pasajeros if aux else None)
    seg_ter_fecha = seg_ter.fecha_vencimiento if seg_ter else (aux.seguro_terceros if aux else None)

    hab_doc = docs.get("HABILITACION")
    hab_fecha = (
        hab_doc.fecha_vencimiento if hab_doc and hab_doc.fecha_vencimiento
        else (aux.habilitacion if aux else None)
    )
    docs_txt = (aux.documentos if aux and aux.documentos else "") or _doc_estado(docs.get("DOCUMENTOS"))

    base = [
        bus.numero_orden,
        bus.marca.nombre if bus.marca else (aux.marca if aux else ""),
        bus.año,
        bus.numero_chassis,
        bus.rua,
        docs_txt,
        _fmt_fecha(hab_fecha),
        _fmt_fecha(seg_pas_fecha),
        _fmt_fecha(seg_ter_fecha),
        _tipo_servicio_label(bus) or (aux.tipo_de_servicio if aux else ""),
        bus.tipo_carroceria.descripcion if bus.tipo_carroceria else (aux.tipo_de_carroceria if aux else ""),
        bus.marca_carroceria.nombre if bus.marca_carroceria else (aux.marca_de_carroceria if aux else ""),
    ]

    if modo == "operativa":
        row = base + [
            _fmt_fecha(itv["itv_ant"]),
            _fmt_fecha(itv["fecha_itv"]),
            _fmt_fecha(itv["venc_itv"]),
            itv["resultado"] or "TOTAL",
            empresa_linea,
        ]
    else:
        # Planilla empresa: sin fechas → "00/00/00" y VENCIDA
        fecha_itv_val: Any = _fmt_fecha(itv["fecha_itv"]) if itv["tiene_fechas"] else "00/00/00"
        venc_val: Any = _fmt_fecha(itv["venc_itv"]) if itv["tiene_fechas"] else "00/00/00"
        row = base + [
            fecha_itv_val,
            venc_val,
            itv["situacion"],
            empresa_linea,
        ]

    return row, itv


def _conteo_tipos(filas: list[list[Any]], idx_tipo: int) -> dict[str, int]:
    counts = {"conv": 0, "conv_inc": 0, "dif": 0, "dif_inc": 0, "elec": 0}
    for row in filas:
        label = str(row[idx_tipo] or "")
        if _es_electrico(label):
            counts["elec"] += 1
        elif _es_diferencial(label):
            if "(*)" in label:
                counts["dif_inc"] += 1
            else:
                counts["dif"] += 1
        elif _es_convencional(label):
            if "(*)" in label:
                counts["conv_inc"] += 1
            else:
                counts["conv"] += 1
    return counts


def _fila_vacia(ncols: int) -> list[Any]:
    return [None] * ncols


def _cel(row: list[Any], col: int, val: Any) -> None:
    if 0 <= col < len(row):
        row[col] = val


def _fin_mes_anterior(ref: date) -> date:
    return ref.replace(day=1) - timedelta(days=1)


def _encabezado(ncols: int, hoy: date) -> tuple[list[list[Any]], list[str]]:
    grid: list[list[Any]] = []
    kinds: list[str] = []
    titulo = _fila_vacia(ncols)
    _cel(titulo, 0, "Planilla de ITV - Actualizado al ")
    _cel(titulo, 5, hoy)
    _cel(titulo, ncols - 1, "PPASITV")
    grid.append(titulo)
    kinds.append("title")

    r4 = _fila_vacia(ncols)
    _cel(r4, 0, "Planilla del Parque Automotor")
    grid.append(r4)
    kinds.append("subtitle")

    r5 = _fila_vacia(ncols)
    _cel(r5, 0, "Planilla para Inspección Técnica Vehicular")
    grid.append(r5)
    kinds.append("subtitle")
    return grid, kinds


def _pie_comun_izq(
    ncols: int,
    eot: Eot,
    empresa_linea: str,
    hoy: date,
    autoriz: int,
    operat: int,
    reserva: int,
    op_dec: int,
    res_dec: int,
    total_declarado: int,
) -> list[list[Any]]:
    """Bloque izquierdo del pie (autorizado / operativo / declarado)."""
    C_D, C_E, C_F, C_G, C_I = 3, 4, 5, 6, 8
    C_EMP = ncols - 1
    filas: list[list[Any]] = []

    pie1 = _fila_vacia(ncols)
    _cel(pie1, 11 if ncols > 12 else 10, empresa_linea)
    _cel(pie1, C_EMP, empresa_linea)
    filas.append(pie1)

    pie2 = _fila_vacia(ncols)
    _cel(pie2, C_D, "ACTUALIZACIÓN:")
    _cel(pie2, C_E, hoy)
    _cel(pie2, C_F, "POD")
    _cel(pie2, C_G, "Parque Operativo Declarado")
    _cel(pie2, C_EMP, empresa_linea)
    filas.append(pie2)

    pie3 = _fila_vacia(ncols)
    _cel(pie3, C_D, "IMPRESIÓN")
    _cel(pie3, C_E, hoy)
    _cel(pie3, C_F, "RTD")
    _cel(pie3, C_G, "Reserva Técnica Declarada")
    _cel(pie3, C_EMP, empresa_linea)
    filas.append(pie3)

    # Fila vacía de fechas mes (operativa la completa; empresa deja empresa-linea)
    pie4 = _fila_vacia(ncols)
    _cel(pie4, C_EMP, empresa_linea)
    filas.append(pie4)

    resol = "según Resolución GVMT N° 44/2025 es de: "
    for label, val in [
        (f"Parque Autorizado {resol}", autoriz),
        (f"Parque Operativo {resol}", operat),
        (f"Reserva Técnica {resol}", reserva),
    ]:
        r = _fila_vacia(ncols)
        _cel(r, C_F, label)
        _cel(r, C_G, val)
        _cel(r, C_I, "buses")
        _cel(r, C_EMP, empresa_linea)
        filas.append(r)

    pie_op = _fila_vacia(ncols)
    _cel(pie_op, C_F, "Parque Operativo Declarado:")
    _cel(pie_op, C_G, op_dec)
    _cel(pie_op, 7, "Declarado")
    _cel(pie_op, C_I, "buses")
    _cel(pie_op, C_EMP, empresa_linea)
    filas.append(pie_op)

    pie_rt = _fila_vacia(ncols)
    _cel(pie_rt, C_F, "Reserva Técnica Declarada:")
    _cel(pie_rt, C_G, res_dec)
    _cel(pie_rt, 7, total_declarado)
    _cel(pie_rt, C_EMP, empresa_linea)
    filas.append(pie_rt)

    return filas


def _armar_filas_hoja(
    eot: Eot,
    buses: list[Bus],
    aux_map: dict[str, Auxiliar],
    itv_map: dict[int, list[ItvBus]],
    seg_map: dict[int, dict[str, SeguroBus]],
    doc_map: dict[int, dict[str, DocumentoBus]],
    modo: ModoPlanilla,
) -> tuple[list[list[Any]], list[str], dict[str, Any]]:
    hoy = HOY()
    headers = _headers(modo)
    ncols = len(headers)
    empresa_linea = _empresa_label(eot)

    filas_data: list[list[Any]] = []
    itv_stats = {"aprobadas": 0, "rechazadas": 0, "vencidas": 0, "sin_itv": 0}

    for bus in buses:
        row, itv = _fila_bus(
            bus,
            empresa_linea,
            aux_map.get(bus.rua),
            itv_map.get(bus.id_bus, []),
            seg_map.get(bus.id_bus, {}),
            doc_map.get(bus.id_bus, {}),
            modo,
        )
        # Operativa (subsidio): solo buses con ITV (fechas presentes)
        if modo == "operativa" and not itv["tiene_fechas"]:
            continue

        filas_data.append(row)
        if itv["situacion"] == "APROBADA":
            itv_stats["aprobadas"] += 1
        elif itv["situacion"] == "VENCIDA":
            itv_stats["vencidas"] += 1
        else:
            itv_stats["sin_itv"] += 1

    idx_tipo = headers.index("TIPO DE SERVICIO")
    idx_orden = headers.index("N° DE ORDEN")
    filas_data.sort(
        key=lambda r: (
            _tipo_sort_key(str(r[idx_tipo] or "")),
            r[idx_orden] if isinstance(r[idx_orden], int) else 999999,
            str(r[idx_orden] or ""),
        )
    )

    tipos = _conteo_tipos(filas_data, idx_tipo)
    total = len(filas_data)
    autoriz = int(eot.autorizado or 0)
    operat = int(eot.operativo or 0)
    reserva = int(eot.reserva or 0)
    op_dec = int(eot.operativo_declarado if eot.operativo_declarado is not None else total)
    res_dec = int(eot.reserva_declarada or 0)
    total_dec = op_dec + res_dec
    conv_total = tipos["conv"] + tipos["conv_inc"]
    dif_total = tipos["dif"] + tipos["dif_inc"]
    mes_anterior = _fin_mes_anterior(hoy)

    grid, row_kinds = _encabezado(ncols, hoy)
    grid.append(list(headers))
    row_kinds.append("col_header")

    for row in filas_data:
        grid.append(row)
        row_kinds.append("data")

    grid.append(_fila_vacia(ncols))
    row_kinds.append("blank")

    pie_izq = _pie_comun_izq(
        ncols, eot, empresa_linea, hoy,
        autoriz, operat, reserva, op_dec, res_dec, total_dec,
    )

    C_EMP = ncols - 1
    C_M = 12 if ncols > 13 else 11

    if modo == "operativa":
        # Completar bloque derecho: mes actual / anterior + tipos de servicio
        C_MES_ACT = ncols - 3
        C_MES_ANT = ncols - 2
        # pie_izq[2] = IMPRESIÓN → agregar Mes actual/anterior
        _cel(pie_izq[2], C_MES_ACT, "Mes actual")
        _cel(pie_izq[2], C_MES_ANT, "Mes anterior")
        _cel(pie_izq[3], C_MES_ACT, f"(al {hoy.strftime('%d/%m/%Y')})")
        _cel(pie_izq[3], C_MES_ANT, f"(al {mes_anterior.strftime('%d/%m/%Y')})")

        # filas 4-7 del pie_izq = autorizado/operativo/reserva/op_dec
        _cel(pie_izq[4], C_M, "SERVICIO ELECTRICO DIFER.")
        _cel(pie_izq[4], C_MES_ACT, tipos["elec"])
        _cel(pie_izq[4], C_MES_ANT, tipos["elec"])

        _cel(pie_izq[5], C_M, "SERVICIO DIFERENCIAL")
        _cel(pie_izq[5], C_MES_ACT, dif_total)
        _cel(pie_izq[5], C_MES_ANT, dif_total)

        _cel(pie_izq[6], C_M, "SERVICIO CONVENCIONAL")
        _cel(pie_izq[6], C_MES_ACT, conv_total)
        _cel(pie_izq[6], C_MES_ANT, conv_total)

        _cel(pie_izq[7], C_M, "TOTAL BUSES")
        _cel(pie_izq[7], C_MES_ACT, total)
        _cel(pie_izq[7], C_MES_ANT, total)

        for r in pie_izq:
            grid.append(r)
            row_kinds.append("footer")

        pie_end = _fila_vacia(ncols)
        _cel(pie_end, C_EMP, empresa_linea)
        grid.append(pie_end)
        row_kinds.append("footer")
    else:
        # Planilla empresa: bloque derecho = resumen ITV
        C_VAL = ncols - 2  # columna P en oficial de 17 cols
        # pie_izq[2] IMPRESIÓN → TOTAL APROBADAS
        _cel(pie_izq[2], C_M, "TOTAL APROBADAS ITV")
        _cel(pie_izq[2], C_VAL, itv_stats["aprobadas"])

        # pie_izq[3] → TOTAL RECHAZADAS
        _cel(pie_izq[3], C_M, "TOTAL RECHAZADAS")
        _cel(pie_izq[3], C_VAL, itv_stats["rechazadas"] or None)

        _cel(pie_izq[4], C_M, "TOTAL VENCIDAS")
        _cel(pie_izq[4], C_VAL, itv_stats["vencidas"])

        _cel(pie_izq[5], C_M, "TOTAL SIN ITV")
        _cel(pie_izq[5], C_VAL, itv_stats["sin_itv"] or None)

        pct = round(total / operat, 4) if operat else None
        _cel(pie_izq[6], C_M, "% OPERATIVO")
        _cel(pie_izq[6], C_M + 1, pct)

        _cel(pie_izq[7], C_M, "TOTAL DE UNIDADES")
        _cel(pie_izq[7], C_VAL, total)

        for r in pie_izq:
            grid.append(r)
            row_kinds.append("footer")

    meta = {
        "empresa": empresa_linea,
        "id_eot": eot.id_eot_vmt_hex,
        "modo": modo,
        "total_buses": total,
        "autorizado": autoriz,
        "operativo": operat,
        "reserva": reserva,
        "operativo_declarado": op_dec,
        "reserva_declarada": res_dec,
        "tipos": tipos,
        "itv_stats": itv_stats,
    }
    return grid, row_kinds, meta


async def listar_empresas_parque(db: AsyncSession) -> list[dict[str, Any]]:
    eots = await _eots_con_parque(db)
    buses_map = await _buses_por_eot(db)
    out: list[dict[str, Any]] = []
    for eot in eots:
        hex_id = eot.id_eot_vmt_hex
        if not hex_id:
            continue
        n = len(buses_map.get(hex_id, []))
        if n == 0:
            continue
        out.append({
            "id_eot": hex_id,
            "nombre": eot.eot_nombre,
            "linea": eot.eot_linea,
            "label": _empresa_label(eot),
            "total_buses": n,
            "sheet_name": _sheet_name(eot, "empresa"),
        })
    return out


async def generar_planillas_parque(
    db: AsyncSession,
    ids_eot: Optional[list[str]] = None,
    modo: ModoPlanilla = "empresa",
) -> list[dict[str, Any]]:
    """Genera grillas por empresa. modo=operativa|empresa."""
    if modo not in ("operativa", "empresa"):
        modo = "empresa"

    eots = await _eots_con_parque(db, ids=ids_eot)
    buses_map = await _buses_por_eot(db)
    aux_map = await _auxiliar_por_rua(db)
    itv_map = await _itv_por_bus(db)
    seg_map = await _seguros_por_bus(db)
    doc_map = await _docs_por_bus(db)

    hoy = HOY()
    planillas: list[dict[str, Any]] = []
    headers = _headers(modo)

    for eot in eots:
        hex_id = eot.id_eot_vmt_hex
        if not hex_id:
            continue
        buses = buses_map.get(hex_id, [])
        if not buses:
            continue
        filas, kinds, meta = _armar_filas_hoja(
            eot, buses, aux_map, itv_map, seg_map, doc_map, modo,
        )
        if meta["total_buses"] == 0:
            continue
        titulo_modo = "Operativa (subsidio)" if modo == "operativa" else "Empresa (informes)"
        planillas.append({
            "key": "planilla_parque",
            "layout": f"planilla_parque_{modo}",
            "hoja": _sheet_name(eot, modo),
            "titulo": f"Planilla {titulo_modo} — {_empresa_label(eot)}",
            "headers": headers,
            "filas": filas,
            "row_kinds": kinds,
            "fecha": hoy.isoformat(),
            "fuente": "registro_habilitacion + public.eots",
            **meta,
        })

    return planillas
