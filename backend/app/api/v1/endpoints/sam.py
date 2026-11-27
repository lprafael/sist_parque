"""Endpoints de dispositivos SAM y asignaciones SAM ↔ bus."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import (
    ORGANISMO_EPS,
    get_current_user,
    require_organismo,
    require_roles,
)
from app.models import Bus, DispositivoSam, SamBus
from app.schemas import DispositivoSamOut, SamBusAsignar, SamBusCerrar, SamBusOut
from app.services.sistema_logs import registrar_auditoria

router = APIRouter(prefix="/sam", tags=["SAM"])


def _sam_out(asig: SamBus, bus_rua: Optional[str] = None) -> SamBusOut:
    disp = asig.dispositivo
    return SamBusOut(
        id_asignacion_sam=asig.id_asignacion_sam,
        id_bus=asig.id_bus,
        id_sam=asig.id_sam,
        fecha_inicio=asig.fecha_inicio,
        fecha_fin=asig.fecha_fin,
        tipo_instalacion=asig.tipo_instalacion,
        motivo_asignacion=asig.motivo_asignacion,
        usuario_registro=asig.usuario_registro,
        fecha_registro=asig.fecha_registro,
        vigente=asig.fecha_fin is None,
        eps=disp.eps if disp else None,
        modelo_validador=disp.modelo_validador if disp else None,
        estado_sam=disp.estado if disp else None,
        bus_rua=bus_rua or (asig.bus.rua if asig.bus else None),
    )


def _dispositivo_out(
    d: DispositivoSam,
    id_bus_actual: Optional[int] = None,
    rua_bus_actual: Optional[str] = None,
) -> DispositivoSamOut:
    return DispositivoSamOut(
        id_sam_interno=d.id_sam_interno,
        id_sam=d.id_sam,
        eps=d.eps,
        modelo_validador=d.modelo_validador,
        numero_serie_hw=d.numero_serie_hw,
        estado=d.estado,
        fecha_alta=d.fecha_alta,
        observaciones=d.observaciones,
        asignado_actualmente=id_bus_actual is not None,
        id_bus_actual=id_bus_actual,
        rua_bus_actual=rua_bus_actual,
    )


@router.get("/dispositivos", response_model=dict)
async def listar_dispositivos(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    eps: Optional[str] = None,
    solo_disponibles: bool = False,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Lista dispositivos SAM del catálogo."""
    vigente_sq = (
        select(SamBus.id_sam, SamBus.id_bus)
        .where(SamBus.fecha_fin.is_(None))
        .subquery()
    )

    q = select(DispositivoSam, vigente_sq.c.id_bus).outerjoin(
        vigente_sq, vigente_sq.c.id_sam == DispositivoSam.id_sam
    )
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                DispositivoSam.id_sam.ilike(term),
                DispositivoSam.eps.ilike(term),
                DispositivoSam.numero_serie_hw.ilike(term),
            )
        )
    if eps:
        filters.append(DispositivoSam.eps.ilike(f"%{eps.strip()}%"))
    if solo_disponibles:
        filters.append(vigente_sq.c.id_bus.is_(None))
    if filters:
        q = q.where(and_(*filters))

    count_q = select(func.count()).select_from(q.order_by(None).subquery())
    total = (await db.execute(count_q)).scalar() or 0

    rows = (
        await db.execute(
            q.order_by(DispositivoSam.id_sam)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    bus_ids = {r[1] for r in rows if r[1] is not None}
    rua_map: dict[int, str] = {}
    if bus_ids:
        buses = (
            await db.execute(select(Bus.id_bus, Bus.rua).where(Bus.id_bus.in_(bus_ids)))
        ).all()
        rua_map = {b.id_bus: b.rua for b in buses}

    items = [
        _dispositivo_out(d, id_bus_actual=id_bus, rua_bus_actual=rua_map.get(id_bus) if id_bus else None)
        for d, id_bus in rows
    ]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/bus/{id_bus}", response_model=dict)
async def historial_sam_bus(
    id_bus: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Historial de asignaciones SAM de un bus (vigente primero)."""
    bus = (await db.execute(select(Bus).where(Bus.id_bus == id_bus))).scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus no encontrado")

    asignaciones = (
        await db.execute(
            select(SamBus)
            .options(selectinload(SamBus.dispositivo), selectinload(SamBus.bus))
            .where(SamBus.id_bus == id_bus)
            .order_by(SamBus.fecha_fin.isnot(None), SamBus.fecha_inicio.desc())
        )
    ).scalars().all()

    return {
        "id_bus": id_bus,
        "rua": bus.rua,
        "items": [_sam_out(a, bus_rua=bus.rua) for a in asignaciones],
    }


@router.get("/bus/{id_bus}/actual", response_model=Optional[SamBusOut])
async def sam_actual_bus(
    id_bus: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    bus = (await db.execute(select(Bus).where(Bus.id_bus == id_bus))).scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus no encontrado")

    asig = (
        await db.execute(
            select(SamBus)
            .options(selectinload(SamBus.dispositivo), selectinload(SamBus.bus))
            .where(SamBus.id_bus == id_bus, SamBus.fecha_fin.is_(None))
        )
    ).scalar_one_or_none()
    if not asig:
        return None
    return _sam_out(asig, bus_rua=bus.rua)


@router.post("/asignar", response_model=SamBusOut, status_code=status.HTTP_201_CREATED)
async def asignar_sam(
    body: SamBusAsignar,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_organismo(ORGANISMO_EPS)),
    _roles=Depends(require_roles("ADMIN", "SUPERVISOR", "OPERADOR")),
):
    """
    Asigna (o cambia) el dispositivo SAM de un bus.

    Solo INSERTA en sam_bus: el trigger trg_sam_bus_before_insert cierra
    automáticamente cualquier asignación vigente del mismo bus o del mismo SAM
    (fecha_fin = nueva fecha_inicio). Las exclusiones GiST impiden solapes.

    Solo usuarios del organismo EPS (id=4).
    """
    bus = (await db.execute(select(Bus).where(Bus.id_bus == body.id_bus))).scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus no encontrado")

    id_sam = body.id_sam.strip().lower()
    dispositivo = (
        await db.execute(select(DispositivoSam).where(DispositivoSam.id_sam == id_sam))
    ).scalar_one_or_none()
    if not dispositivo:
        raise HTTPException(status_code=404, detail="Dispositivo SAM no encontrado")

    fecha_inicio = body.fecha_inicio
    if fecha_inicio.tzinfo is not None:
        fecha_inicio = fecha_inicio.replace(tzinfo=None)

    tipo = (body.tipo_instalacion or "TITULAR").strip().upper() or "TITULAR"
    if tipo not in ("TITULAR", "AUXILIAR"):
        raise HTTPException(
            status_code=400,
            detail="tipo_instalacion inválido. Valores: TITULAR, AUXILIAR",
        )

    vigente_bus = (
        await db.execute(
            select(SamBus).where(SamBus.id_bus == body.id_bus, SamBus.fecha_fin.is_(None))
        )
    ).scalar_one_or_none()

    if vigente_bus and vigente_bus.id_sam == id_sam:
        raise HTTPException(
            status_code=409,
            detail="Este bus ya tiene asignado de forma vigente ese mismo SAM",
        )

    for prev in (
        vigente_bus,
        (
            await db.execute(
                select(SamBus).where(SamBus.id_sam == id_sam, SamBus.fecha_fin.is_(None))
            )
        ).scalar_one_or_none(),
    ):
        if prev and fecha_inicio <= prev.fecha_inicio:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"fecha_inicio ({fecha_inicio}) debe ser posterior al inicio "
                    f"de la asignación vigente ({prev.fecha_inicio})"
                ),
            )

    # El BEFORE INSERT cierra previas (bus y/o sam) con fecha_fin = fecha_inicio.
    nueva = SamBus(
        id_bus=body.id_bus,
        id_sam=id_sam,
        fecha_inicio=fecha_inicio,
        fecha_fin=None,
        tipo_instalacion=tipo,
        motivo_asignacion=body.motivo_asignacion,
        usuario_registro=user.username,
    )
    db.add(nueva)
    try:
        await db.flush()
    except Exception as exc:
        await db.rollback()
        msg = str(getattr(exc, "orig", exc))
        if "exclude_solapamiento" in msg or "ExclusionViolation" in type(exc).__name__:
            raise HTTPException(
                status_code=409,
                detail="Solapamiento de fechas: el bus o el SAM ya tienen una asignación en ese período.",
            ) from exc
        raise

    await registrar_auditoria(
        db,
        accion="insert",
        tabla="sam_bus",
        usuario=user,
        registro_id=nueva.id_asignacion_sam or body.id_bus,
        datos_nuevos={
            "id_bus": body.id_bus,
            "id_sam": id_sam,
            "fecha_inicio": str(fecha_inicio),
            "tipo_instalacion": tipo,
            "motivo_asignacion": body.motivo_asignacion,
        },
        detalles=f"Asignación SAM {id_sam} → bus={body.id_bus}",
    )
    await db.commit()

    asig = (
        await db.execute(
            select(SamBus)
            .options(selectinload(SamBus.dispositivo), selectinload(SamBus.bus))
            .where(SamBus.id_asignacion_sam == nueva.id_asignacion_sam)
        )
    ).scalar_one()
    return _sam_out(asig, bus_rua=bus.rua)


@router.post("/bus/{id_bus}/cerrar", response_model=SamBusOut)
async def cerrar_sam_bus(
    id_bus: int,
    body: SamBusCerrar,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_organismo(ORGANISMO_EPS)),
    _roles=Depends(require_roles("ADMIN", "SUPERVISOR", "OPERADOR")),
):
    """Cierra la asignación SAM vigente del bus sin reasignar otra."""
    bus = (await db.execute(select(Bus).where(Bus.id_bus == id_bus))).scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus no encontrado")

    vigente = (
        await db.execute(
            select(SamBus)
            .options(selectinload(SamBus.dispositivo), selectinload(SamBus.bus))
            .where(SamBus.id_bus == id_bus, SamBus.fecha_fin.is_(None))
        )
    ).scalar_one_or_none()
    if not vigente:
        raise HTTPException(status_code=404, detail="El bus no tiene SAM asignado actualmente")

    fecha_fin = body.fecha_fin
    if fecha_fin.tzinfo is not None:
        fecha_fin = fecha_fin.replace(tzinfo=None)

    if fecha_fin <= vigente.fecha_inicio:
        raise HTTPException(
            status_code=400,
            detail=(
                f"fecha_fin ({fecha_fin}) debe ser posterior a "
                f"fecha_inicio ({vigente.fecha_inicio})"
            ),
        )

    vigente.fecha_fin = fecha_fin
    if body.motivo_asignacion:
        nota = body.motivo_asignacion
        vigente.motivo_asignacion = (
            f"{vigente.motivo_asignacion}\n{nota}" if vigente.motivo_asignacion else nota
        )
    cierre = f"[cierre por {user.username}]"
    vigente.motivo_asignacion = (
        f"{vigente.motivo_asignacion} {cierre}" if vigente.motivo_asignacion else cierre
    )

    await registrar_auditoria(
        db,
        accion="update",
        tabla="sam_bus",
        usuario=user,
        registro_id=vigente.id_asignacion_sam,
        datos_nuevos={"fecha_fin": str(fecha_fin), "motivo": body.motivo_asignacion},
        detalles=f"Cierre SAM bus={id_bus}",
    )
    await db.commit()
    await db.refresh(vigente)
    return _sam_out(vigente, bus_rua=bus.rua)
