from typing import Optional, List
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, text
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import Bus, Marca, TipoCarroceria, MarcaCarroceria, ItvBus, BusEmpresa
from app.schemas import BusCreate, BusUpdate, BusOut
from app.models import Auditoria
import json

router = APIRouter(prefix="/buses", tags=["Buses"])


def calcular_estado_itv(vencimiento: Optional[date]) -> str:
    if not vencimiento:
        return "SIN_ITV"
    today = date.today()
    diff = (vencimiento - today).days
    if diff < 0:
        return "VENCIDO"
    elif diff <= 15:
        return "CRITICO"
    elif diff <= 30:
        return "POR_VENCER"
    return "VIGENTE"


@router.get("", response_model=dict)
async def listar_buses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    estado_bus: Optional[str] = None,
    estado_itv: Optional[str] = None,
    id_marca: Optional[int] = None,
    empresa: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Listado paginado de buses con joins a marcas, ITV vigente y empresa actual."""
    # Base query con joins
    q = (
        select(Bus)
        .options(
            selectinload(Bus.marca),
            selectinload(Bus.tipo_carroceria),
            selectinload(Bus.marca_carroceria),
        )
    )

    filters = []
    if search:
        filters.append(or_(
            Bus.rua.ilike(f"%{search}%"),
            Bus.numero_chassis.ilike(f"%{search}%"),
        ))
    if estado_bus:
        filters.append(Bus.estado_bus == estado_bus.upper())
    if id_marca:
        filters.append(Bus.id_marca == id_marca)

    if filters:
        q = q.where(and_(*filters))

    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar()

    q = q.offset((page - 1) * page_size).limit(page_size).order_by(Bus.numero_orden)
    buses = (await db.execute(q)).scalars().all()

    # Enriquecer con ITV
    items = []
    for bus in buses:
        itv_q = (
            select(ItvBus)
            .where(ItvBus.id_bus == bus.id_bus)
            .order_by(ItvBus.fecha_vencimiento.desc())
            .limit(1)
        )
        itv = (await db.execute(itv_q)).scalar_one_or_none()

        emp_q = (
            select(BusEmpresa.id_eot)
            .where(BusEmpresa.id_bus == bus.id_bus, BusEmpresa.estado_asignacion == "ACTIVA")
            .limit(1)
        )
        empresa_actual = (await db.execute(emp_q)).scalar_one_or_none()

        venc = itv.fecha_vencimiento if itv else None
        estado = calcular_estado_itv(venc)

        if estado_itv and estado != estado_itv.upper():
            continue

        out = BusOut(
            id_bus=bus.id_bus,
            numero_orden=bus.numero_orden,
            id_marca=bus.id_marca,
            año=bus.año,
            numero_chassis=bus.numero_chassis,
            rua=bus.rua,
            id_tipo_carroceria=bus.id_tipo_carroceria,
            id_marca_carroceria=bus.id_marca_carroceria,
            capacidad_pasajeros=bus.capacidad_pasajeros,
            combustible=bus.combustible,
            cilindrada=bus.cilindrada,
            color=bus.color,
            estado_bus=bus.estado_bus,
            fecha_registro=bus.fecha_registro,
            fecha_modificacion=bus.fecha_modificacion,
            marca_nombre=bus.marca.nombre if bus.marca else None,
            tipo_carroceria_nombre=bus.tipo_carroceria.descripcion if bus.tipo_carroceria else None,
            marca_carroceria_nombre=bus.marca_carroceria.nombre if bus.marca_carroceria else None,
            empresa_actual=empresa_actual,
            itv_vencimiento=venc,
            itv_estado=estado,
        )
        items.append(out)

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/{id_bus}", response_model=BusOut)
async def obtener_bus(
    id_bus: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    q = select(Bus).options(
        selectinload(Bus.marca),
        selectinload(Bus.tipo_carroceria),
        selectinload(Bus.marca_carroceria),
        selectinload(Bus.itv_registros),
        selectinload(Bus.seguros),
        selectinload(Bus.documentos),
        selectinload(Bus.asignaciones),
        selectinload(Bus.alertas),
    ).where(Bus.id_bus == id_bus)
    bus = (await db.execute(q)).scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus no encontrado")

    itv = sorted(bus.itv_registros, key=lambda x: x.fecha_vencimiento, reverse=True)
    venc = itv[0].fecha_vencimiento if itv else None
    empresa_act = next(
        (a.id_eot for a in bus.asignaciones if a.estado_asignacion == "ACTIVA"), None
    )

    return BusOut(
        id_bus=bus.id_bus,
        numero_orden=bus.numero_orden,
        id_marca=bus.id_marca,
        año=bus.año,
        numero_chassis=bus.numero_chassis,
        rua=bus.rua,
        id_tipo_carroceria=bus.id_tipo_carroceria,
        id_marca_carroceria=bus.id_marca_carroceria,
        capacidad_pasajeros=bus.capacidad_pasajeros,
        combustible=bus.combustible,
        cilindrada=bus.cilindrada,
        color=bus.color,
        estado_bus=bus.estado_bus,
        fecha_registro=bus.fecha_registro,
        fecha_modificacion=bus.fecha_modificacion,
        marca_nombre=bus.marca.nombre if bus.marca else None,
        tipo_carroceria_nombre=bus.tipo_carroceria.descripcion if bus.tipo_carroceria else None,
        marca_carroceria_nombre=bus.marca_carroceria.nombre if bus.marca_carroceria else None,
        empresa_actual=empresa_act,
        itv_vencimiento=venc,
        itv_estado=calcular_estado_itv(venc),
    )


@router.post("", response_model=BusOut, status_code=status.HTTP_201_CREATED)
async def crear_bus(
    body: BusCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles("ADMIN", "SUPERVISOR", "OPERADOR"))
):
    # Verificar duplicado
    dup = await db.execute(
        select(Bus).where(or_(Bus.rua == body.rua, Bus.numero_chassis == body.numero_chassis))
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="RUA o Nº Chassis ya registrado")

    bus = Bus(**body.model_dump())
    db.add(bus)
    await db.flush()

    # Auditoría
    db.add(Auditoria(
        tabla_afectada="buses",
        id_registro=bus.id_bus,
        accion="INSERT",
        datos_nuevos=body.model_dump(mode="json"),
        usuario=user.username
    ))
    await db.commit()
    await db.refresh(bus)
    return await obtener_bus(bus.id_bus, db)


@router.put("/{id_bus}", response_model=BusOut)
async def actualizar_bus(
    id_bus: int,
    body: BusUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles("ADMIN", "SUPERVISOR", "OPERADOR"))
):
    bus = (await db.execute(select(Bus).where(Bus.id_bus == id_bus))).scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus no encontrado")

    old_data = {c.name: getattr(bus, c.name) for c in Bus.__table__.columns}
    update_data = body.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(bus, k, v)

    db.add(Auditoria(
        tabla_afectada="buses",
        id_registro=id_bus,
        accion="UPDATE",
        datos_anteriores=old_data,
        datos_nuevos=update_data,
        usuario=user.username
    ))
    await db.commit()
    return await obtener_bus(id_bus, db)


@router.delete("/{id_bus}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_bus(
    id_bus: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles("ADMIN"))
):
    bus = (await db.execute(select(Bus).where(Bus.id_bus == id_bus))).scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus no encontrado")

    db.add(Auditoria(
        tabla_afectada="buses",
        id_registro=id_bus,
        accion="DELETE",
        datos_anteriores={"rua": bus.rua, "chassis": bus.numero_chassis},
        usuario=user.username
    ))
    await db.delete(bus)
    await db.commit()


@router.get("/catalogo/marcas")
async def listar_marcas(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Marca).order_by(Marca.nombre))
    return result.scalars().all()


@router.get("/catalogo/tipos-carroceria")
async def listar_tipos_carroceria(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(TipoCarroceria).order_by(TipoCarroceria.descripcion))
    return result.scalars().all()


@router.get("/catalogo/marcas-carroceria")
async def listar_marcas_carroceria(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(MarcaCarroceria).order_by(MarcaCarroceria.nombre))
    return result.scalars().all()
