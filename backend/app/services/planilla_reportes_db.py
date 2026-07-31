"""Reportes tipo planilla ITV calculados desde la base (no desde Excel)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Optional

from sqlalchemy import and_, func, select
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
    res = await db.execute(
        select(Eot)
        .where(and_(Eot.situacion == 1, Eot.permisionario == True))
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


async def reporte_cuadro_edad(db: AsyncSession) -> dict:
    eots = await _eots_activas(db)
    buses_map = await _buses_por_eot(db, solo_activos=True)
    anio_actual = HOY().year
    anios = list(range(2006, anio_actual + 2))
    headers = ["Nº", "Línea", "Empresa", *[str(a) for a in anios], "Total"]
    rows: list[list[Any]] = []
    n = 0
    for eot in eots:
        hex_id = eot.id_eot_vmt_hex
        if not hex_id:
            continue
        buses = buses_map.get(hex_id, [])
        if not buses:
            continue
        n += 1
        counts = {a: 0 for a in anios}
        for b in buses:
            if isinstance(b.año, int) and b.año in counts:
                counts[b.año] += 1
        total = sum(counts.values())
        rows.append([
            n,
            (eot.eot_linea or "").strip() or "—",
            (eot.eot_nombre or "").strip() or "—",
            *[counts[a] for a in anios],
            total,
        ])
    # fila total
    if rows:
        totales = [""] * 3 + [sum(r[i] for r in rows) for i in range(3, 3 + len(anios) + 1)]
        totales[0] = ""
        totales[1] = ""
        totales[2] = "TOTAL"
        rows.append(totales)
    return _pack("cuadro_edad", headers, rows, f"Actualización: {HOY().isoformat()}")


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
