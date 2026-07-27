from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import ItvBus, HistorialItv, Bus, Auditoria
from app.schemas import ItvBusCreate, ItvBusUpdate, ItvBusOut, HistorialItvOut

router = APIRouter(prefix="/itv", tags=["ITV - Inspección Técnica"])


def estado_itv(venc: Optional[date]) -> tuple[str, Optional[int]]:
    if not venc:
        return "SIN_ITV", None
    diff = (venc - date.today()).days
    if diff < 0:
        estado = "VENCIDO"
    elif diff <= 7:
        estado = "CRITICO"
    elif diff <= 30:
        estado = "POR_VENCER"
    else:
        estado = "VIGENTE"
    return estado, diff


@router.get("", response_model=dict)
async def listar_itv(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    id_bus: Optional[int] = None,
    estado: Optional[str] = None,
    vence_antes_de: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    q = select(ItvBus)
    filters = []
    if id_bus:
        filters.append(ItvBus.id_bus == id_bus)
    if vence_antes_de:
        filters.append(ItvBus.fecha_vencimiento <= vence_antes_de)
    if filters:
        q = q.where(and_(*filters))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    itv_list = (
        await db.execute(q.offset((page - 1) * page_size).limit(page_size).order_by(ItvBus.fecha_vencimiento))
    ).scalars().all()

    items = []
    for itv in itv_list:
        est, dias = estado_itv(itv.fecha_vencimiento)
        if estado and est != estado.upper():
            continue
        items.append(ItvBusOut(
            **{c.name: getattr(itv, c.name) for c in ItvBus.__table__.columns},
            dias_para_vencer=dias,
            estado_itv=est
        ))

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/{id_itv}", response_model=ItvBusOut)
async def obtener_itv(id_itv: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    itv = (await db.execute(select(ItvBus).where(ItvBus.id_itv == id_itv))).scalar_one_or_none()
    if not itv:
        raise HTTPException(status_code=404, detail="Registro ITV no encontrado")
    est, dias = estado_itv(itv.fecha_vencimiento)
    return ItvBusOut(**{c.name: getattr(itv, c.name) for c in ItvBus.__table__.columns}, dias_para_vencer=dias, estado_itv=est)


@router.post("", response_model=ItvBusOut, status_code=status.HTTP_201_CREATED)
async def registrar_itv(
    body: ItvBusCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles("ADMIN", "SUPERVISOR", "OPERADOR"))
):
    # Verificar que el bus existe
    bus = (await db.execute(select(Bus).where(Bus.id_bus == body.id_bus))).scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus no encontrado")

    # Guardar ITV anterior en historial (evitando duplicados idénticos)
    itv_ant = (await db.execute(
        select(ItvBus).where(ItvBus.id_bus == body.id_bus).order_by(ItvBus.fecha_vencimiento.desc()).limit(1)
    )).scalar_one_or_none()

    if itv_ant:
        diff = (body.fecha_vencimiento - itv_ant.fecha_vencimiento).days
        hist_dup = (await db.execute(
            select(HistorialItv).where(
                and_(
                    HistorialItv.id_bus == body.id_bus,
                    HistorialItv.fecha_vencimiento_anterior == itv_ant.fecha_vencimiento,
                    HistorialItv.fecha_itv_actual == body.fecha_itv,
                    HistorialItv.fecha_vencimiento_actual == body.fecha_vencimiento
                )
            )
        )).scalar_one_or_none()

        if not hist_dup:
            db.add(HistorialItv(
                id_bus=body.id_bus,
                fecha_vencimiento_anterior=itv_ant.fecha_vencimiento,
                fecha_itv_actual=body.fecha_itv,
                fecha_vencimiento_actual=body.fecha_vencimiento,
                diferencia_dias=diff
            ))

    itv = ItvBus(**body.model_dump())
    db.add(itv)
    db.add(Auditoria(tabla_afectada="itv_bus", id_registro=body.id_bus, accion="INSERT",
                     datos_nuevos=body.model_dump(mode="json"), usuario=user.username))
    await db.commit()
    await db.refresh(itv)
    est, dias = estado_itv(itv.fecha_vencimiento)
    return ItvBusOut(**{c.name: getattr(itv, c.name) for c in ItvBus.__table__.columns}, dias_para_vencer=dias, estado_itv=est)


@router.put("/{id_itv}", response_model=ItvBusOut)
async def actualizar_itv(
    id_itv: int,
    body: ItvBusUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles("ADMIN", "SUPERVISOR"))
):
    itv = (await db.execute(select(ItvBus).where(ItvBus.id_itv == id_itv))).scalar_one_or_none()
    if not itv:
        raise HTTPException(status_code=404, detail="Registro ITV no encontrado")

    update_data = body.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(itv, k, v)
    await db.commit()
    await db.refresh(itv)
    est, dias = estado_itv(itv.fecha_vencimiento)
    return ItvBusOut(**{c.name: getattr(itv, c.name) for c in ItvBus.__table__.columns}, dias_para_vencer=dias, estado_itv=est)


@router.get("/historial/{id_bus}", response_model=list[HistorialItvOut])
async def historial_itv_bus(id_bus: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    hist = (await db.execute(
        select(HistorialItv).where(HistorialItv.id_bus == id_bus).order_by(HistorialItv.fecha_registro.desc())
    )).scalars().all()
    return hist
