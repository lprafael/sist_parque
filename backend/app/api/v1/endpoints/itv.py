from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import ItvBus, Bus
from app.services.sistema_logs import registrar_auditoria
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
    solo_vigentes: bool = Query(True, description="Si es True, sólo retorna los registros de ITV vigentes"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    q = select(ItvBus)
    filters = []
    if solo_vigentes:
        filters.append(ItvBus.es_vigente == True)
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

    # Si se registra una ITV marcada como vigente (default True), marcar las ITVs previas de ese bus como no vigentes
    if body.es_vigente:
        await db.execute(
            update(ItvBus)
            .where(ItvBus.id_bus == body.id_bus)
            .values(es_vigente=False)
        )

    itv = ItvBus(**body.model_dump())
    db.add(itv)
    await db.flush()
    await registrar_auditoria(
        db,
        accion="insert",
        tabla="itv_bus",
        usuario=user,
        registro_id=itv.id_itv or body.id_bus,
        datos_nuevos=body.model_dump(mode="json"),
        detalles=f"Alta ITV bus={body.id_bus}",
    )
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

    # Si se actualiza es_vigente a True, asegurar que otras ITVs del bus pasen a False
    if update_data.get("es_vigente") is True:
        await db.execute(
            update(ItvBus)
            .where(and_(ItvBus.id_bus == itv.id_bus, ItvBus.id_itv != id_itv))
            .values(es_vigente=False)
        )

    for k, v in update_data.items():
        setattr(itv, k, v)
    await registrar_auditoria(
        db,
        accion="update",
        tabla="itv_bus",
        usuario=user,
        registro_id=id_itv,
        datos_nuevos=update_data,
        detalles=f"Actualización ITV id={id_itv}",
    )
    await db.commit()
    await db.refresh(itv)
    est, dias = estado_itv(itv.fecha_vencimiento)
    return ItvBusOut(**{c.name: getattr(itv, c.name) for c in ItvBus.__table__.columns}, dias_para_vencer=dias, estado_itv=est)


@router.get("/historial/{id_bus}", response_model=list[HistorialItvOut])
async def historial_itv_bus(id_bus: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    # Orden cronológico por vencimiento, luego registro (para deduplicar fechas iguales)
    records = (await db.execute(
        select(ItvBus)
        .where(ItvBus.id_bus == id_bus)
        .order_by(ItvBus.fecha_vencimiento.asc(), ItvBus.fecha_registro.asc(), ItvBus.id_itv.asc())
    )).scalars().all()

    # Una fila por (fecha_itv, fecha_vencimiento): conservar la más antigua
    seen_keys: set[tuple] = set()
    unique: list[ItvBus] = []
    for rec in records:
        key = (rec.fecha_itv, rec.fecha_vencimiento)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique.append(rec)

    historial = []
    for idx, rec in enumerate(unique):
        prev_venc = unique[idx - 1].fecha_vencimiento if idx > 0 else None
        diff_days = (rec.fecha_itv - prev_venc).days if prev_venc and rec.fecha_itv else None

        historial.append(HistorialItvOut(
            id_historial=rec.id_itv,
            id_bus=rec.id_bus,
            fecha_vencimiento_anterior=prev_venc,
            fecha_itv_actual=rec.fecha_itv,
            fecha_vencimiento_actual=rec.fecha_vencimiento,
            diferencia_dias=diff_days,
            observaciones=rec.observaciones,
            fecha_registro=rec.fecha_registro
        ))

    return list(reversed(historial))
