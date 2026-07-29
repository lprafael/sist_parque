from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import SeguroBus, CompaniaSeguro, TipoSeguro, Bus, Auditoria
from app.schemas import (
    SeguroBusCreate, SeguroBusUpdate, SeguroBusOut,
    CompaniaSeguroCreate, CompaniaSeguroOut, TipoSeguroOut
)

router = APIRouter(prefix="/seguros", tags=["Seguros"])


def estado_por_vencimiento(venc: date) -> tuple[str, int]:
    """Estado derivado de la fecha (no se guarda en DB)."""
    diff = (venc - date.today()).days
    if diff < 0:
        return "VENCIDO", diff
    elif diff <= 7:
        return "CRITICO", diff
    elif diff <= 30:
        return "POR_VENCER", diff
    return "VIGENTE", diff


def _seguro_out(seg: SeguroBus) -> SeguroBusOut:
    est, dias = estado_por_vencimiento(seg.fecha_vencimiento)
    return SeguroBusOut(
        id_seguro=seg.id_seguro,
        id_bus=seg.id_bus,
        id_tipo_seguro=seg.id_tipo_seguro,
        id_compania=seg.id_compania,
        numero_poliza=seg.numero_poliza,
        fecha_inicio=seg.fecha_inicio,
        fecha_vencimiento=seg.fecha_vencimiento,
        monto_cobertura=float(seg.monto_cobertura) if seg.monto_cobertura is not None else None,
        seguro_vigente=seg.seguro_vigente,
        observaciones=seg.observaciones,
        dias_para_vencer=dias,
        estado_calculado=est,
        compania_nombre=seg.compania.nombre if seg.compania else None,
        tipo_seguro_nombre=seg.tipo.nombre if seg.tipo else None,
        fecha_registro=seg.fecha_registro,
    )


# --- Compañías de seguros ---

@router.get("/companias", response_model=list[CompaniaSeguroOut])
async def listar_companias(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(CompaniaSeguro).where(CompaniaSeguro.activo == True).order_by(CompaniaSeguro.nombre)
    )
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
    id_tipo_seguro: Optional[int] = None,
    seguro_vigente: Optional[bool] = None,
    estado: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    q = (
        select(SeguroBus)
        .options(
            selectinload(SeguroBus.compania),
            selectinload(SeguroBus.tipo),
        )
    )
    filters = []
    if id_bus:
        filters.append(SeguroBus.id_bus == id_bus)
    if id_tipo_seguro:
        filters.append(SeguroBus.id_tipo_seguro == id_tipo_seguro)
    if seguro_vigente is not None:
        filters.append(SeguroBus.seguro_vigente == seguro_vigente)
    if filters:
        q = q.where(and_(*filters))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    seguros = (await db.execute(
        q.offset((page - 1) * page_size).limit(page_size).order_by(SeguroBus.fecha_vencimiento)
    )).scalars().all()

    items = []
    for seg in seguros:
        out = _seguro_out(seg)
        if estado and out.estado_calculado != estado.upper():
            continue
        items.append(out)

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

    tipo = (await db.execute(
        select(TipoSeguro).where(TipoSeguro.id_tipo_seguro == body.id_tipo_seguro)
    )).scalar_one_or_none()
    if not tipo:
        raise HTTPException(status_code=400, detail="id_tipo_seguro inválido")

    if body.id_compania:
        comp = (await db.execute(
            select(CompaniaSeguro).where(CompaniaSeguro.id_compania == body.id_compania)
        )).scalar_one_or_none()
        if not comp:
            raise HTTPException(status_code=400, detail="id_compania inválido")

    # Si se marca como vigente, desmarcar otros del mismo bus+tipo
    if body.seguro_vigente:
        otros = (await db.execute(
            select(SeguroBus).where(
                SeguroBus.id_bus == body.id_bus,
                SeguroBus.id_tipo_seguro == body.id_tipo_seguro,
                SeguroBus.seguro_vigente == True,
            )
        )).scalars().all()
        for o in otros:
            o.seguro_vigente = False

    seg = SeguroBus(**body.model_dump())
    db.add(seg)
    db.add(Auditoria(
        tabla_afectada="seguros_bus",
        id_registro=body.id_bus,
        accion="INSERT",
        datos_nuevos=body.model_dump(mode="json"),
        usuario=user.username,
    ))
    await db.commit()

    seg = (await db.execute(
        select(SeguroBus)
        .options(selectinload(SeguroBus.compania), selectinload(SeguroBus.tipo))
        .where(SeguroBus.id_seguro == seg.id_seguro)
    )).scalar_one()
    return _seguro_out(seg)


@router.put("/{id_seguro}", response_model=SeguroBusOut)
async def actualizar_seguro(
    id_seguro: int,
    body: SeguroBusUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles("ADMIN", "SUPERVISOR"))
):
    seg = (await db.execute(
        select(SeguroBus)
        .options(selectinload(SeguroBus.compania), selectinload(SeguroBus.tipo))
        .where(SeguroBus.id_seguro == id_seguro)
    )).scalar_one_or_none()
    if not seg:
        raise HTTPException(status_code=404, detail="Seguro no encontrado")

    data = body.model_dump(exclude_unset=True)
    if "id_tipo_seguro" in data and data["id_tipo_seguro"] is not None:
        tipo = (await db.execute(
            select(TipoSeguro).where(TipoSeguro.id_tipo_seguro == data["id_tipo_seguro"])
        )).scalar_one_or_none()
        if not tipo:
            raise HTTPException(status_code=400, detail="id_tipo_seguro inválido")

    if data.get("seguro_vigente") is True:
        id_tipo = data.get("id_tipo_seguro", seg.id_tipo_seguro)
        otros = (await db.execute(
            select(SeguroBus).where(
                SeguroBus.id_bus == seg.id_bus,
                SeguroBus.id_tipo_seguro == id_tipo,
                SeguroBus.seguro_vigente == True,
                SeguroBus.id_seguro != seg.id_seguro,
            )
        )).scalars().all()
        for o in otros:
            o.seguro_vigente = False

    for k, v in data.items():
        setattr(seg, k, v)

    await db.commit()
    await db.refresh(seg)
    seg = (await db.execute(
        select(SeguroBus)
        .options(selectinload(SeguroBus.compania), selectinload(SeguroBus.tipo))
        .where(SeguroBus.id_seguro == id_seguro)
    )).scalar_one()
    return _seguro_out(seg)
