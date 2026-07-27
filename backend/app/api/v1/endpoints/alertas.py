from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import Alerta, Bus
from app.schemas import AlertaOut, AlertaAtender

router = APIRouter(prefix="/alertas", tags=["Alertas"])


@router.get("", response_model=dict)
async def listar_alertas(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    estado: Optional[str] = None,       # PENDIENTE, ATENDIDA, IGNORADA
    prioridad: Optional[str] = None,    # ALTA, MEDIA, BAJA
    tipo_alerta: Optional[str] = None,  # ITV, SEGURO_PASAJEROS, etc.
    id_bus: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    q = select(Alerta)
    filters = []
    if estado:
        filters.append(Alerta.estado_alerta == estado.upper())
    if prioridad:
        filters.append(Alerta.prioridad == prioridad.upper())
    if tipo_alerta:
        filters.append(Alerta.tipo_alerta == tipo_alerta.upper())
    if id_bus:
        filters.append(Alerta.id_bus == id_bus)
    if filters:
        q = q.where(and_(*filters))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    alertas = (await db.execute(
        q.offset((page - 1) * page_size).limit(page_size)
         .order_by(
             Alerta.prioridad.desc(),   # ALTA primero
             Alerta.fecha_alerta.asc()
         )
    )).scalars().all()

    items = []
    for al in alertas:
        bus_rua = None
        if al.id_bus:
            bus_rua = (await db.execute(select(Bus.rua).where(Bus.id_bus == al.id_bus))).scalar_one_or_none()
        items.append(AlertaOut(
            **{c.name: getattr(al, c.name) for c in Alerta.__table__.columns},
            bus_rua=bus_rua
        ))

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.put("/{id_alerta}/atender", response_model=AlertaOut)
async def atender_alerta(
    id_alerta: int,
    body: AlertaAtender,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles("ADMIN", "SUPERVISOR", "OPERADOR"))
):
    """Marca una alerta como atendida."""
    al = (await db.execute(select(Alerta).where(Alerta.id_alerta == id_alerta))).scalar_one_or_none()
    if not al:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alerta no encontrada")

    al.estado_alerta = "ATENDIDA"
    al.fecha_atencion = datetime.now(timezone.utc)
    al.usuario_atencion = body.usuario_atencion
    if body.observacion:
        al.descripcion = (al.descripcion or "") + f"\n[Atendida]: {body.observacion}"

    await db.commit()
    return AlertaOut(**{c.name: getattr(al, c.name) for c in Alerta.__table__.columns})


@router.put("/{id_alerta}/ignorar", response_model=AlertaOut)
async def ignorar_alerta(
    id_alerta: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles("ADMIN", "SUPERVISOR"))
):
    al = (await db.execute(select(Alerta).where(Alerta.id_alerta == id_alerta))).scalar_one_or_none()
    if not al:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    al.estado_alerta = "IGNORADA"
    al.usuario_atencion = user.username
    await db.commit()
    return AlertaOut(**{c.name: getattr(al, c.name) for c in Alerta.__table__.columns})


@router.delete("/limpiar-todas")
async def limpiar_todas_alertas(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Elimina todas las alertas de la base de datos."""
    from sqlalchemy import delete
    await db.execute(delete(Alerta))
    await db.commit()
    return {"message": "Todas las alertas han sido eliminadas correctamente."}

