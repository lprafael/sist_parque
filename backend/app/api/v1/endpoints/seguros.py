from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import SeguroBus, CompaniaSeguro, TipoSeguro, Bus, Auditoria
from app.schemas import (
    SeguroBusCreate, SeguroBusUpdate, SeguroBusOut,
    CompaniaSeguroCreate, CompaniaSeguroOut, TipoSeguroOut
)

router = APIRouter(prefix="/seguros", tags=["Seguros"])


def estado_seguro(venc: date) -> tuple[str, int]:
    diff = (venc - date.today()).days
    if diff < 0:
        return "VENCIDO", diff
    elif diff <= 7:
        return "CRITICO", diff
    elif diff <= 30:
        return "POR_VENCER", diff
    return "VIGENTE", diff


# --- Compañías de seguros ---

@router.get("/companias", response_model=list[CompaniaSeguroOut])
async def listar_companias(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(CompaniaSeguro).where(CompaniaSeguro.activo == True).order_by(CompaniaSeguro.nombre))
    return result.scalars().all()


@router.post("/companias", response_model=CompaniaSeguroOut, status_code=status.HTTP_201_CREATED)
async def crear_compania(
    body: CompaniaSeguroCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_roles("ADMIN", "SUPERVISOR"))
):
    comp = CompaniaSeguro(**body.model_dump())
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@router.get("/tipos", response_model=list[TipoSeguroOut])
async def listar_tipos_seguro(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(TipoSeguro).where(TipoSeguro.activo == True).order_by(TipoSeguro.nombre)
    )
    return result.scalars().all()


# --- Seguros de buses ---

@router.get("", response_model=dict)
async def listar_seguros(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    id_bus: Optional[int] = None,
    tipo_seguro: Optional[str] = None,
    estado: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    q = select(SeguroBus)
    filters = []
    if id_bus:
        filters.append(SeguroBus.id_bus == id_bus)
    if tipo_seguro:
        filters.append(SeguroBus.tipo_seguro == tipo_seguro.upper())
    if filters:
        q = q.where(and_(*filters))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    seguros = (await db.execute(
        q.offset((page - 1) * page_size).limit(page_size).order_by(SeguroBus.fecha_vencimiento)
    )).scalars().all()

    items = []
    for seg in seguros:
        est, dias = estado_seguro(seg.fecha_vencimiento)
        if estado and est != estado.upper():
            continue
        # Nombre compañía / tipo
        comp = None
        if seg.id_compania:
            comp = (await db.execute(select(CompaniaSeguro.nombre).where(CompaniaSeguro.id_compania == seg.id_compania))).scalar_one_or_none()
        tipo_nombre = None
        if seg.id_tipo_seguro:
            tipo_nombre = (await db.execute(
                select(TipoSeguro.nombre).where(TipoSeguro.id_tipo_seguro == seg.id_tipo_seguro)
            )).scalar_one_or_none()
        items.append(SeguroBusOut(
            **{c.name: getattr(seg, c.name) for c in SeguroBus.__table__.columns},
            dias_para_vencer=dias,
            compania_nombre=comp,
            tipo_seguro_nombre=tipo_nombre or seg.tipo_seguro,
        ))

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("", response_model=SeguroBusOut, status_code=status.HTTP_201_CREATED)
async def crear_seguro(
    body: SeguroBusCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles("ADMIN", "SUPERVISOR", "OPERADOR"))
):
    bus = (await db.execute(select(Bus).where(Bus.id_bus == body.id_bus))).scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus no encontrado")

    data = body.model_dump()
    # Resolver id_tipo_seguro ↔ tipo_seguro (legado)
    if data.get("id_tipo_seguro") and not data.get("tipo_seguro"):
        nombre = (await db.execute(
            select(TipoSeguro.nombre).where(TipoSeguro.id_tipo_seguro == data["id_tipo_seguro"])
        )).scalar_one_or_none()
        if nombre:
            data["tipo_seguro"] = nombre
    elif data.get("tipo_seguro") and not data.get("id_tipo_seguro"):
        tid = (await db.execute(
            select(TipoSeguro.id_tipo_seguro).where(TipoSeguro.nombre == data["tipo_seguro"].upper())
        )).scalar_one_or_none()
        if tid:
            data["id_tipo_seguro"] = tid
            data["tipo_seguro"] = data["tipo_seguro"].upper()

    seg = SeguroBus(**data)
    db.add(seg)
    db.add(Auditoria(tabla_afectada="seguros_bus", id_registro=body.id_bus, accion="INSERT",
                     datos_nuevos=body.model_dump(mode="json"), usuario=user.username))
    await db.commit()
    await db.refresh(seg)
    est, dias = estado_seguro(seg.fecha_vencimiento)
    return SeguroBusOut(**{c.name: getattr(seg, c.name) for c in SeguroBus.__table__.columns}, dias_para_vencer=dias)


@router.put("/{id_seguro}", response_model=SeguroBusOut)
async def actualizar_seguro(
    id_seguro: int,
    body: SeguroBusUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles("ADMIN", "SUPERVISOR"))
):
    seg = (await db.execute(select(SeguroBus).where(SeguroBus.id_seguro == id_seguro))).scalar_one_or_none()
    if not seg:
        raise HTTPException(status_code=404, detail="Seguro no encontrado")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(seg, k, v)
    await db.commit()
    await db.refresh(seg)
    est, dias = estado_seguro(seg.fecha_vencimiento)
    return SeguroBusOut(**{c.name: getattr(seg, c.name) for c in SeguroBus.__table__.columns}, dias_para_vencer=dias)
