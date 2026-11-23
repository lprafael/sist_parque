from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Bus, ItvBus, SeguroBus, TipoSeguro, TipoServicio, Alerta, Eot, BusEmpresa
from app.schemas import KpiDashboard

router = APIRouter(prefix="/dashboard", tags=["Dashboard & KPIs"])


def _buses_ids_de_eot(id_eot: str):
    """Subquery de buses con asignación vigente a la EOT."""
    return (
        select(BusEmpresa.id_bus)
        .where(
            BusEmpresa.fecha_fin_asignacion.is_(None),
            BusEmpresa.id_eot == id_eot,
        )
    )


def _bus_filter(id_eot: Optional[str]):
    """Condición opcional: Bus.id_bus ∈ asignación vigente de la EOT."""
    if not id_eot:
        return None
    return Bus.id_bus.in_(_buses_ids_de_eot(id_eot))


@router.get("/kpis", response_model=KpiDashboard)
async def obtener_kpis(
    id_eot: Optional[str] = Query(None, description="Filtrar por id_eot_vmt_hex de la empresa"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    hoy = date.today()
    en_30 = hoy + timedelta(days=30)
    bus_f = _bus_filter(id_eot)

    # Buses
    total_q = select(func.count()).select_from(Bus)
    activos_q = select(func.count()).select_from(Bus).where(Bus.estado_bus == "ACTIVO")
    if bus_f is not None:
        total_q = total_q.where(bus_f)
        activos_q = activos_q.where(bus_f)
    total_buses = (await db.execute(total_q)).scalar()
    buses_activos = (await db.execute(activos_q)).scalar()

    # ITV — alineado a planilla: APROBADA = fecha >= hoy; VENCIDA = fecha < hoy o sin ITV.
    # itv_vigente (= APROBADA) incluye "por vencer" (igual que seguros vigentes).
    # itv_por_vencer es subconjunto (vence en ≤30 días).
    itv_base = [ItvBus.es_vigente == True]
    if bus_f is not None:
        itv_base.append(ItvBus.id_bus.in_(_buses_ids_de_eot(id_eot)))

    itv_vigente = (await db.execute(select(func.count()).select_from(ItvBus).where(
        and_(*itv_base, ItvBus.fecha_vencimiento >= hoy)
    ))).scalar() or 0
    itv_por_vencer = (await db.execute(select(func.count()).select_from(ItvBus).where(
        and_(*itv_base, ItvBus.fecha_vencimiento >= hoy, ItvBus.fecha_vencimiento <= en_30)
    ))).scalar() or 0
    itv_vencido_fecha = (await db.execute(select(func.count()).select_from(ItvBus).where(
        and_(*itv_base, ItvBus.fecha_vencimiento < hoy)
    ))).scalar() or 0

    sin_itv_conds = [
        Bus.estado_bus == "ACTIVO",
        ~Bus.id_bus.in_(select(ItvBus.id_bus).where(ItvBus.es_vigente == True)),
    ]
    if bus_f is not None:
        sin_itv_conds.append(bus_f)
    itv_sin_fecha = (await db.execute(
        select(func.count()).select_from(Bus).where(and_(*sin_itv_conds))
    )).scalar() or 0
    itv_vencido = itv_vencido_fecha + itv_sin_fecha

    # Seguros — separados por tipo (PASAJEROS / TERCEROS).
    # Solo la póliza con seguro_vigente de buses ACTIVO (histórico excluido).
    # Vigente = fecha >= hoy; por vencer ⊆ vigente (≤30 días); vencido = fecha < hoy.
    async def _count_seguro_tipo(nombre_tipo: str, *extra_conds):
        tipo_id_sq = select(TipoSeguro.id_tipo_seguro).where(
            func.upper(TipoSeguro.nombre) == nombre_tipo.upper()
        )
        bus_activos_sq = select(Bus.id_bus).where(Bus.estado_bus == "ACTIVO")
        if bus_f is not None:
            bus_activos_sq = bus_activos_sq.where(bus_f)
        return (await db.execute(
            select(func.count()).select_from(SeguroBus).where(
                and_(
                    SeguroBus.seguro_vigente.is_(True),
                    SeguroBus.id_tipo_seguro.in_(tipo_id_sq),
                    SeguroBus.id_bus.in_(bus_activos_sq),
                    *extra_conds,
                )
            )
        )).scalar() or 0

    seg_pas_vig = await _count_seguro_tipo("PASAJEROS", SeguroBus.fecha_vencimiento >= hoy)
    seg_pas_por = await _count_seguro_tipo(
        "PASAJEROS",
        SeguroBus.fecha_vencimiento >= hoy,
        SeguroBus.fecha_vencimiento <= en_30,
    )
    seg_pas_ven = await _count_seguro_tipo("PASAJEROS", SeguroBus.fecha_vencimiento < hoy)

    seg_ter_vig = await _count_seguro_tipo("TERCEROS", SeguroBus.fecha_vencimiento >= hoy)
    seg_ter_por = await _count_seguro_tipo(
        "TERCEROS",
        SeguroBus.fecha_vencimiento >= hoy,
        SeguroBus.fecha_vencimiento <= en_30,
    )
    seg_ter_ven = await _count_seguro_tipo("TERCEROS", SeguroBus.fecha_vencimiento < hoy)

    # Alertas
    alerta_conds_crit = [Alerta.estado_alerta == "PENDIENTE", Alerta.prioridad == "ALTA"]
    alerta_conds_pend = [Alerta.estado_alerta == "PENDIENTE"]
    if bus_f is not None:
        alerta_conds_crit.append(Alerta.id_bus.in_(_buses_ids_de_eot(id_eot)))
        alerta_conds_pend.append(Alerta.id_bus.in_(_buses_ids_de_eot(id_eot)))

    alertas_criticas = (await db.execute(select(func.count()).select_from(Alerta).where(
        and_(*alerta_conds_crit)
    ))).scalar()
    alertas_pendientes = (await db.execute(select(func.count()).select_from(Alerta).where(
        and_(*alerta_conds_pend)
    ))).scalar()

    # Empresas permisionarias activas (con filtro: 1 si la EOT existe y califica)
    if id_eot:
        total_empresas = (await db.execute(select(func.count()).select_from(Eot).where(
            and_(
                Eot.id_eot_vmt_hex == id_eot,
                Eot.situacion == 1,
                Eot.permisionario == True,
            )
        ))).scalar()
    else:
        total_empresas = (await db.execute(select(func.count()).select_from(Eot).where(
            and_(Eot.situacion == 1, Eot.permisionario == True)
        ))).scalar()

    # Parque: tipo de servicio + rampa (solo buses ACTIVO)
    tipo_join_conds = [Bus.id_tipo_servicio == TipoServicio.id_tipo_servicio, Bus.estado_bus == "ACTIVO"]
    if bus_f is not None:
        tipo_join_conds.append(bus_f)

    tipo_rows = (await db.execute(
        select(TipoServicio.id_tipo_servicio, TipoServicio.nombre, func.count(Bus.id_bus))
        .outerjoin(Bus, and_(*tipo_join_conds))
        .where(TipoServicio.activo == True)
        .group_by(TipoServicio.id_tipo_servicio, TipoServicio.nombre)
    )).all()

    tipo_map: dict[str, tuple] = {}
    for tid, nombre, cnt in tipo_rows:
        key = (nombre or "").strip().upper()
        tipo_map[key] = (tid, int(cnt or 0))

    id_conv, buses_convencional = tipo_map.get("CONVENCIONAL", (None, 0))
    id_dif, buses_diferenciado = tipo_map.get("DIFERENCIADO", (None, 0))
    id_elec, buses_electrico = tipo_map.get("ELECTRICO", (None, 0))

    rampa_conds = [Bus.estado_bus == "ACTIVO", Bus.tiene_rampa.is_(True)]
    if bus_f is not None:
        rampa_conds.append(bus_f)
    buses_con_rampa = (await db.execute(
        select(func.count()).select_from(Bus).where(and_(*rampa_conds))
    )).scalar() or 0

    return KpiDashboard(
        total_buses=total_buses,
        buses_activos=buses_activos,
        buses_inactivos=total_buses - buses_activos,
        itv_vigente=itv_vigente,
        itv_por_vencer=itv_por_vencer,
        itv_vencido=itv_vencido,
        itv_sin_vigente=itv_sin_fecha,
        seguros_pasajeros_vigentes=seg_pas_vig,
        seguros_pasajeros_por_vencer=seg_pas_por,
        seguros_pasajeros_vencidos=seg_pas_ven,
        seguros_terceros_vigentes=seg_ter_vig,
        seguros_terceros_por_vencer=seg_ter_por,
        seguros_terceros_vencidos=seg_ter_ven,
        alertas_criticas=alertas_criticas,
        alertas_pendientes=alertas_pendientes,
        total_empresas=total_empresas,
        buses_convencional=buses_convencional,
        buses_diferenciado=buses_diferenciado,
        buses_electrico=buses_electrico,
        buses_con_rampa=buses_con_rampa,
        id_tipo_convencional=id_conv,
        id_tipo_diferenciado=id_dif,
        id_tipo_electrico=id_elec,
    )


@router.get("/vencimientos-proximos")
async def vencimientos_proximos(
    dias: int = 30,
    id_eot: Optional[str] = Query(None, description="Filtrar por id_eot_vmt_hex de la empresa"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Timeline de vencimientos en los próximos N días (ITV + seguros)."""
    hoy = date.today()
    limite = hoy + timedelta(days=dias)
    bus_f = _bus_filter(id_eot)

    itv_conds = [ItvBus.fecha_vencimiento >= hoy, ItvBus.fecha_vencimiento <= limite]
    if bus_f is not None:
        itv_conds.append(bus_f)

    itv_q = await db.execute(
        select(ItvBus, Bus.rua, Bus.numero_orden)
        .join(Bus, Bus.id_bus == ItvBus.id_bus)
        .where(and_(*itv_conds))
        .order_by(ItvBus.fecha_vencimiento)
    )
    itv_rows = itv_q.all()

    seg_conds = [
        SeguroBus.seguro_vigente == True,
        SeguroBus.fecha_vencimiento >= hoy,
        SeguroBus.fecha_vencimiento <= limite,
    ]
    if bus_f is not None:
        seg_conds.append(bus_f)

    seg_q = await db.execute(
        select(SeguroBus, Bus.rua, Bus.numero_orden, TipoSeguro.nombre)
        .join(Bus, Bus.id_bus == SeguroBus.id_bus)
        .join(TipoSeguro, TipoSeguro.id_tipo_seguro == SeguroBus.id_tipo_seguro)
        .where(and_(*seg_conds))
        .order_by(SeguroBus.fecha_vencimiento)
    )
    seg_rows = seg_q.all()

    items = []
    for itv, rua, orden in itv_rows:
        diff = (itv.fecha_vencimiento - hoy).days
        items.append({
            "tipo": "ITV",
            "id_bus": itv.id_bus,
            "rua": rua,
            "numero_orden": orden,
            "fecha_vencimiento": itv.fecha_vencimiento,
            "dias_restantes": diff,
            "prioridad": "ALTA" if diff <= 7 else ("MEDIA" if diff <= 15 else "BAJA"),
        })
    for seg, rua, orden, tipo_nombre in seg_rows:
        diff = (seg.fecha_vencimiento - hoy).days
        items.append({
            "tipo": f"SEGURO_{tipo_nombre}",
            "id_bus": seg.id_bus,
            "rua": rua,
            "numero_orden": orden,
            "fecha_vencimiento": seg.fecha_vencimiento,
            "dias_restantes": diff,
            "prioridad": "ALTA" if diff <= 7 else ("MEDIA" if diff <= 15 else "BAJA"),
        })

    items.sort(key=lambda x: x["fecha_vencimiento"])
    return {"dias_consultados": dias, "total": len(items), "items": items}


@router.get("/distribucion-empresas")
async def distribucion_por_empresa(
    id_eot: Optional[str] = Query(None, description="Filtrar por id_eot_vmt_hex de la empresa"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Cantidad de buses activos por empresa operadora."""
    q = (
        select(
            BusEmpresa.id_eot,
            func.count(BusEmpresa.id_bus).label("total_buses")
        )
        .where(BusEmpresa.fecha_fin_asignacion.is_(None))
    )
    if id_eot:
        q = q.where(BusEmpresa.id_eot == id_eot)
    q = q.group_by(BusEmpresa.id_eot).order_by(func.count(BusEmpresa.id_bus).desc())

    result = await db.execute(q)
    rows = result.all()

    items = []
    for eid, total in rows:
        eot = (await db.execute(
            select(Eot.eot_nombre, Eot.eot_linea).where(Eot.id_eot_vmt_hex == eid)
        )).one_or_none()
        items.append({
            "id_eot": eid,
            "empresa": eot.eot_nombre if eot else eid,
            "lineas": eot.eot_linea.strip() if eot and eot.eot_linea else "",
            "total_buses": total,
        })
    return items


def _conds_antiguedad(id_eot: Optional[str], anio_ref: int):
    """Buses activos con año/modelo válido (excluye futuros → evita edades negativas)."""
    bus_f = _bus_filter(id_eot)
    conds = [
        Bus.estado_bus == "ACTIVO",
        Bus.año.isnot(None),
        Bus.año > 1970,
        Bus.año <= anio_ref,
    ]
    if bus_f is not None:
        conds.append(bus_f)
    return conds


def _mediana_desde_grupos(grupos: list[tuple[int, int]]) -> Optional[float]:
    """Mediana ponderada: grupos = [(edad, cantidad), ...] ordenados por edad."""
    total = sum(c for _, c in grupos)
    if total <= 0:
        return None
    objetivo = (total + 1) / 2
    acum = 0
    for edad, cnt in grupos:
        acum += cnt
        if acum >= objetivo:
            return float(edad)
    return float(grupos[-1][0]) if grupos else None


@router.get("/distribucion-antiguedad")
async def distribucion_antiguedad_buses(
    id_eot: Optional[str] = Query(None, description="Filtrar por id_eot_vmt_hex de la empresa"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Distribución de buses por años de antigüedad y cálculo de la edad promedio."""
    current_year = date.today().year
    conds = _conds_antiguedad(id_eot, current_year)

    result = await db.execute(
        select(Bus.año, func.count(Bus.id_bus).label("cantidad"))
        .where(and_(*conds))
        .group_by(Bus.año)
        .order_by(Bus.año.asc())
    )
    rows = result.all()

    items = []
    total_buses = 0
    suma_edades = 0

    for anio, cnt in rows:
        antiguedad = current_year - anio
        total_buses += cnt
        suma_edades += (antiguedad * cnt)
        items.append({
            "anio": anio,
            "antiguedad": antiguedad,
            "label": f"{antiguedad} año{'s' if antiguedad != 1 else ''} ({anio})",
            "cantidad": cnt,
        })

    promedio_edad = round(suma_edades / total_buses, 1) if total_buses > 0 else 0.0

    return {
        "promedio_edad": promedio_edad,
        "total_buses": total_buses,
        "anio_referencia": current_year,
        "items": items,
    }


@router.get("/analisis-antiguedad")
async def analisis_antiguedad_parque(
    id_eot: Optional[str] = Query(None, description="Filtrar por id_eot_vmt_hex de la empresa"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Análisis detallado de antigüedad del parque activo:
    año de referencia del promedio, extremos, tramos, umbrales normativos y muestra.
    """
    anio_ref = date.today().year
    conds = _conds_antiguedad(id_eot, anio_ref)

    result = await db.execute(
        select(Bus.año, func.count(Bus.id_bus).label("cantidad"))
        .where(and_(*conds))
        .group_by(Bus.año)
        .order_by(Bus.año.asc())
    )
    rows = result.all()

    items = []
    total_buses = 0
    suma_edades = 0
    grupos_edad: list[tuple[int, int]] = []

    for anio, cnt in rows:
        edad = anio_ref - int(anio)
        total_buses += cnt
        suma_edades += edad * cnt
        grupos_edad.append((edad, cnt))
        items.append({
            "anio": anio,
            "antiguedad": edad,
            "label": f"{edad} año{'s' if edad != 1 else ''} ({anio})",
            "cantidad": cnt,
        })

    if total_buses == 0:
        return {
            "anio_referencia": anio_ref,
            "total_buses": 0,
            "promedio_edad": 0,
            "mediana_edad": None,
            "moda": None,
            "anio_desde": None,
            "anio_hasta": None,
            "mas_antiguos": None,
            "mas_nuevos": None,
            "tramos": [],
            "umbrales": {},
            "distribucion": [],
            "top_por_cantidad": [],
            "empresas_mas_antiguas": [],
            "muestra_mas_antiguos": [],
        }

    promedio = round(suma_edades / total_buses, 1)
    mediana = _mediana_desde_grupos(grupos_edad)
    moda_item = max(items, key=lambda x: x["cantidad"])
    anio_desde = items[0]["anio"]
    anio_hasta = items[-1]["anio"]
    mas_antiguos = items[0]  # menor año = más viejo
    mas_nuevos = items[-1]

    def _tramo(label: str, lo: int, hi: Optional[int]) -> dict:
        cant = sum(
            it["cantidad"]
            for it in items
            if it["antiguedad"] >= lo and (hi is None or it["antiguedad"] <= hi)
        )
        return {
            "label": label,
            "edad_desde": lo,
            "edad_hasta": hi,
            "cantidad": cant,
            "porcentaje": round(100 * cant / total_buses, 1),
        }

    tramos = [
        _tramo("0 a 6 años", 0, 6),
        _tramo("7 a 13 años", 7, 13),
        _tramo("14 a 20 años", 14, 20),
        _tramo("Más de 20 años", 21, None),
    ]

    def _umbral(pred) -> dict:
        cant = sum(it["cantidad"] for it in items if pred(it["antiguedad"]))
        return {"cantidad": cant, "porcentaje": round(100 * cant / total_buses, 1)}

    umbrales = {
        "hasta_15": {
            "descripcion": "Hasta 15 años (tope general Ley 7617)",
            **_umbral(lambda e: e <= 15),
        },
        "mas_de_15": {
            "descripcion": "Más de 15 años",
            **_umbral(lambda e: e > 15),
        },
        "hasta_20": {
            "descripcion": "Hasta 20 años (tope habitual de altas)",
            **_umbral(lambda e: e <= 20),
        },
        "mas_de_20": {
            "descripcion": "Más de 20 años (alerta GVMT 145/2026 Art. 2°)",
            **_umbral(lambda e: e > 20),
        },
        "igual_21": {
            "descripcion": "Exactamente 21 años (excepción 2027 GVMT 145)",
            **_umbral(lambda e: e == 21),
        },
    }

    top_por_cantidad = sorted(items, key=lambda x: x["cantidad"], reverse=True)[:10]

    # Empresas con flota más antigua (solo si no hay filtro EOT)
    empresas_mas_antiguas = []
    if not id_eot:
        emp_q = (
            select(
                Eot.eot_nombre,
                BusEmpresa.id_eot,
                func.count(Bus.id_bus).label("total"),
                func.avg(anio_ref - Bus.año).label("promedio"),
                func.max(anio_ref - Bus.año).label("edad_max"),
                func.min(Bus.año).label("anio_min"),
            )
            .join(BusEmpresa, BusEmpresa.id_bus == Bus.id_bus)
            .join(Eot, Eot.id_eot_vmt_hex == BusEmpresa.id_eot, isouter=True)
            .where(
                and_(
                    *conds,
                    BusEmpresa.fecha_fin_asignacion.is_(None),
                )
            )
            .group_by(Eot.eot_nombre, BusEmpresa.id_eot)
            .having(func.count(Bus.id_bus) >= 5)
            .order_by(func.avg(anio_ref - Bus.año).desc())
            .limit(10)
        )
        emp_rows = (await db.execute(emp_q)).all()
        for nombre, eot_id, total, prom, edad_max, anio_min in emp_rows:
            empresas_mas_antiguas.append({
                "empresa": nombre or eot_id or "Sin nombre",
                "id_eot": eot_id,
                "total_buses": total,
                "promedio_edad": round(float(prom or 0), 1),
                "edad_max": int(edad_max or 0),
                "anio_mas_antiguo": int(anio_min) if anio_min else None,
            })

    # Muestra de buses más antiguos (con empresa vigente)
    emp_activa = (
        select(
            BusEmpresa.id_bus.label("id_bus"),
            func.coalesce(Eot.eot_nombre, BusEmpresa.id_eot).label("empresa"),
        )
        .outerjoin(Eot, Eot.id_eot_vmt_hex == BusEmpresa.id_eot)
        .where(BusEmpresa.fecha_fin_asignacion.is_(None))
        .subquery()
    )
    muestra_q = (
        select(
            Bus.id_bus,
            Bus.rua,
            Bus.año,
            Bus.numero_orden,
            emp_activa.c.empresa,
        )
        .outerjoin(emp_activa, emp_activa.c.id_bus == Bus.id_bus)
        .where(and_(*conds))
        .order_by(Bus.año.asc(), Bus.rua.asc())
        .limit(25)
    )
    muestra_mas_antiguos = [
        {
            "id_bus": id_bus,
            "rua": rua,
            "numero_orden": nro,
            "anio": anio,
            "antiguedad": anio_ref - int(anio),
            "empresa": empresa,
        }
        for id_bus, rua, anio, nro, empresa in (await db.execute(muestra_q)).all()
    ]

    return {
        "anio_referencia": anio_ref,
        "total_buses": total_buses,
        "promedio_edad": promedio,
        "mediana_edad": mediana,
        "moda": {
            "anio": moda_item["anio"],
            "antiguedad": moda_item["antiguedad"],
            "cantidad": moda_item["cantidad"],
        },
        "anio_desde": anio_desde,
        "anio_hasta": anio_hasta,
        "mas_antiguos": {
            "anio": mas_antiguos["anio"],
            "antiguedad": mas_antiguos["antiguedad"],
            "cantidad": mas_antiguos["cantidad"],
        },
        "mas_nuevos": {
            "anio": mas_nuevos["anio"],
            "antiguedad": mas_nuevos["antiguedad"],
            "cantidad": mas_nuevos["cantidad"],
        },
        "tramos": tramos,
        "umbrales": umbrales,
        "distribucion": items,
        "top_por_cantidad": top_por_cantidad,
        "empresas_mas_antiguas": empresas_mas_antiguas,
        "muestra_mas_antiguos": muestra_mas_antiguos,
    }


@router.get("/distribucion-tipo-servicio")
async def distribucion_tipo_servicio(
    id_eot: Optional[str] = Query(None, description="Filtrar por id_eot_vmt_hex de la empresa"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Distribución de buses por Tipo de Servicio."""
    bus_f = _bus_filter(id_eot)

    join_conds = [Bus.id_tipo_servicio == TipoServicio.id_tipo_servicio, Bus.estado_bus == "ACTIVO"]
    if bus_f is not None:
        join_conds.append(bus_f)

    result = await db.execute(
        select(TipoServicio.nombre, func.count(Bus.id_bus).label("cantidad"))
        .join(Bus, and_(*join_conds))
        .group_by(TipoServicio.nombre)
    )
    rows = result.all()

    items = []
    for nombre, cnt in rows:
        items.append({
            "name": nombre if nombre else "SIN ESPECIFICAR",
            "value": cnt,
        })

    sin_conds = [Bus.estado_bus == "ACTIVO", Bus.id_tipo_servicio.is_(None)]
    if bus_f is not None:
        sin_conds.append(bus_f)
    sin = (await db.execute(
        select(func.count()).select_from(Bus).where(*sin_conds)
    )).scalar() or 0
    if sin:
        items.append({"name": "SIN ESPECIFICAR", "value": sin})

    return items


@router.get("/distribucion-marcas")
async def distribucion_marcas(
    id_eot: Optional[str] = Query(None, description="Filtrar por id_eot_vmt_hex de la empresa"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Distribución de buses por Marca (Top 10)."""
    from app.models import Marca

    bus_f = _bus_filter(id_eot)
    conds = [Bus.estado_bus == "ACTIVO"]
    if bus_f is not None:
        conds.append(bus_f)

    result = await db.execute(
        select(Marca.nombre, func.count(Bus.id_bus).label("cantidad"))
        .join(Marca, Bus.id_marca == Marca.id_marca)
        .where(and_(*conds))
        .group_by(Marca.nombre)
        .order_by(func.count(Bus.id_bus).desc())
        .limit(10)
    )
    rows = result.all()

    items = []
    for marca_nombre, cnt in rows:
        items.append({
            "name": marca_nombre if marca_nombre else "SIN ESPECIFICAR",
            "value": cnt,
        })

    return items
