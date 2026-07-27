from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Bus, ItvBus, SeguroBus, Alerta, Eot, BusEmpresa
from app.schemas import KpiDashboard

router = APIRouter(prefix="/dashboard", tags=["Dashboard & KPIs"])

HOY = date.today


@router.get("/kpis", response_model=KpiDashboard)
async def obtener_kpis(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    hoy = date.today()
    en_30 = hoy + timedelta(days=30)

    # Buses
    total_buses   = (await db.execute(select(func.count()).select_from(Bus))).scalar()
    buses_activos = (await db.execute(select(func.count()).select_from(Bus).where(Bus.estado_bus == "ACTIVO"))).scalar()



    # ITV — toma el último ITV por bus
    itv_vigente    = (await db.execute(select(func.count()).select_from(ItvBus).where(ItvBus.fecha_vencimiento > en_30))).scalar()
    itv_por_vencer = (await db.execute(select(func.count()).select_from(ItvBus).where(
        and_(ItvBus.fecha_vencimiento >= hoy, ItvBus.fecha_vencimiento <= en_30)
    ))).scalar()
    itv_vencido    = (await db.execute(select(func.count()).select_from(ItvBus).where(ItvBus.fecha_vencimiento < hoy))).scalar()

    # Seguros
    seg_vigentes   = (await db.execute(select(func.count()).select_from(SeguroBus).where(SeguroBus.fecha_vencimiento > en_30))).scalar()
    seg_por_vencer = (await db.execute(select(func.count()).select_from(SeguroBus).where(
        and_(SeguroBus.fecha_vencimiento >= hoy, SeguroBus.fecha_vencimiento <= en_30)
    ))).scalar()
    seg_vencidos   = (await db.execute(select(func.count()).select_from(SeguroBus).where(SeguroBus.fecha_vencimiento < hoy))).scalar()

    # Alertas
    alertas_criticas   = (await db.execute(select(func.count()).select_from(Alerta).where(
        and_(Alerta.estado_alerta == "PENDIENTE", Alerta.prioridad == "ALTA")
    ))).scalar()
    alertas_pendientes = (await db.execute(select(func.count()).select_from(Alerta).where(Alerta.estado_alerta == "PENDIENTE"))).scalar()

    # Empresas permisionarias activas
    total_empresas = (await db.execute(select(func.count()).select_from(Eot).where(
        and_(Eot.situacion == 1, Eot.permisionario == True)
    ))).scalar()


    return KpiDashboard(
        total_buses=total_buses,
        buses_activos=buses_activos,
        buses_inactivos=total_buses - buses_activos,
        itv_vigente=itv_vigente,
        itv_por_vencer=itv_por_vencer,
        itv_vencido=itv_vencido,
        seguros_vigentes=seg_vigentes,
        seguros_por_vencer=seg_por_vencer,
        seguros_vencidos=seg_vencidos,
        alertas_criticas=alertas_criticas,
        alertas_pendientes=alertas_pendientes,
        total_empresas=total_empresas,
    )


@router.get("/vencimientos-proximos")
async def vencimientos_proximos(
    dias: int = 30,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Timeline de vencimientos en los próximos N días (ITV + seguros)."""
    hoy = date.today()
    limite = hoy + timedelta(days=dias)

    # ITV
    itv_q = await db.execute(
        select(ItvBus, Bus.rua, Bus.numero_orden)
        .join(Bus, Bus.id_bus == ItvBus.id_bus)
        .where(and_(ItvBus.fecha_vencimiento >= hoy, ItvBus.fecha_vencimiento <= limite))
        .order_by(ItvBus.fecha_vencimiento)
    )
    itv_rows = itv_q.all()

    # Seguros
    seg_q = await db.execute(
        select(SeguroBus, Bus.rua, Bus.numero_orden)
        .join(Bus, Bus.id_bus == SeguroBus.id_bus)
        .where(and_(SeguroBus.fecha_vencimiento >= hoy, SeguroBus.fecha_vencimiento <= limite))
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
    for seg, rua, orden in seg_rows:
        diff = (seg.fecha_vencimiento - hoy).days
        items.append({
            "tipo": f"SEGURO_{seg.tipo_seguro}",
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
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Cantidad de buses activos por empresa operadora."""
    result = await db.execute(
        select(
            BusEmpresa.id_eot,
            func.count(BusEmpresa.id_bus).label("total_buses")
        )
        .where(BusEmpresa.estado_asignacion == "ACTIVA")
        .group_by(BusEmpresa.id_eot)
        .order_by(func.count(BusEmpresa.id_bus).desc())
    )
    rows = result.all()

    items = []
    for id_eot, total in rows:
        eot = (await db.execute(select(Eot.eot_nombre, Eot.eot_linea).where(Eot.id_eot_vmt_hex == id_eot))).one_or_none()
        items.append({
            "id_eot": id_eot,
            "empresa": eot.eot_nombre if eot else id_eot,
            "lineas": eot.eot_linea.strip() if eot else "",
            "total_buses": total,
        })
    return items


@router.get("/distribucion-antiguedad")
async def distribucion_antiguedad_buses(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Distribución de buses por años de antigüedad y cálculo de la edad promedio."""
    current_year = date.today().year

    result = await db.execute(
        select(Bus.año, func.count(Bus.id_bus).label("cantidad"))
        .where(and_(Bus.estado_bus == "ACTIVO", Bus.año.isnot(None), Bus.año > 1970))
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
        "items": items,
    }


@router.get("/distribucion-tipo-servicio")
async def distribucion_tipo_servicio(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Distribución de buses por Tipo de Servicio."""
    
    result = await db.execute(
        select(Bus.tipo_servicio, func.count(Bus.id_bus).label("cantidad"))
        .where(Bus.estado_bus == "ACTIVO")
        .group_by(Bus.tipo_servicio)
    )
    rows = result.all()

    items = []
    for tipo_servicio, cnt in rows:
        items.append({
            "name": tipo_servicio if tipo_servicio else "SIN ESPECIFICAR",
            "value": cnt,
        })

    return items


@router.get("/distribucion-marcas")
async def distribucion_marcas(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Distribución de buses por Marca (Top 10)."""
    from app.models import Marca
    
    result = await db.execute(
        select(Marca.nombre, func.count(Bus.id_bus).label("cantidad"))
        .join(Marca, Bus.id_marca == Marca.id_marca)
        .where(Bus.estado_bus == "ACTIVO")
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

