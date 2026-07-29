"""
Empresas Operadoras de Transporte.
IMPORTANTE: public.eots es READ-ONLY (sistema CID).
Este módulo solo consulta esa tabla; nunca escribe en ella.
La asignación bus↔empresa se gestiona en registro_habilitacion.bus_empresa,
usando id_eot_vmt_hex como referencia a public.eots.

Reglas de vigencia:
- Asignación vigente ⇔ fecha_fin_asignacion IS NULL ∧ estado_asignacion = ACTIVA
- Un bus solo puede tener una asignación vigente (índice único parcial)
- fecha_fin null = el bus sigue asignado a esa EOT
"""
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import Eot, BusEmpresa, Bus
from app.schemas import (
    EotOut, BusEmpresaCreate, BusEmpresaBaja, BusEmpresaOut, MOTIVOS_ASIGNACION,
)

router = APIRouter(prefix="/empresas", tags=["Empresas (EOT)"])


def _periodos_solapan(
    inicio_a: date,
    fin_a: Optional[date],
    inicio_b: date,
    fin_b: Optional[date],
) -> bool:
    """True si los intervalos inclusivos [inicio, fin] se solapan (fin None = abierto)."""
    fin_a_eff = fin_a or date.max
    fin_b_eff = fin_b or date.max
    return inicio_a <= fin_b_eff and inicio_b <= fin_a_eff


async def _enriquecer_asignacion(db: AsyncSession, asig: BusEmpresa) -> BusEmpresaOut:
    eot = (await db.execute(
        select(Eot).where(Eot.id_eot_vmt_hex == asig.id_eot)
    )).scalar_one_or_none()
    return BusEmpresaOut(
        **{c.name: getattr(asig, c.name) for c in BusEmpresa.__table__.columns},
        empresa_nombre=eot.eot_nombre if eot else None,
        empresa_lineas=eot.eot_linea if eot else None,
    )


async def _assert_sin_solape(
    db: AsyncSession,
    id_bus: int,
    fecha_inicio: date,
    fecha_fin: Optional[date],
    excluir_id: Optional[int] = None,
) -> None:
    q = select(BusEmpresa).where(BusEmpresa.id_bus == id_bus)
    if excluir_id is not None:
        q = q.where(BusEmpresa.id_asignacion != excluir_id)
    existentes = (await db.execute(q)).scalars().all()
    for otra in existentes:
        if _periodos_solapan(
            fecha_inicio, fecha_fin,
            otra.fecha_asignacion, otra.fecha_fin_asignacion,
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"El periodo {fecha_inicio}–{fecha_fin or 'vigente'} se solapa con "
                    f"la asignación #{otra.id_asignacion} "
                    f"({otra.fecha_asignacion}–{otra.fecha_fin_asignacion or 'vigente'}, "
                    f"EOT {otra.id_eot})"
                ),
            )


# ============================================================
# CONSULTA DE EMPRESAS (READ-ONLY → public.eots)
# ============================================================

@router.get("", response_model=dict, summary="Listar empresas operadoras (fuente: public.eots)")
async def listar_empresas(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    solo_activas: bool = True,
    solo_permisionarias: Optional[bool] = Query(None, description="Filtrar empresas permisionarias (true/false)"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """
    Lista todas las empresas de public.eots.
    Solo lectura — no permite crear, editar ni eliminar empresas.
    """
    q = select(Eot)
    filters = []
    if search:
        filters.append(Eot.eot_nombre.ilike(f"%{search}%"))
    if solo_activas:
        filters.append(Eot.situacion == 1)   # 1 = activa en el CID
    if solo_permisionarias is not None:
        filters.append(Eot.permisionario == solo_permisionarias)
    if filters:
        q = q.where(and_(*filters))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    empresas = (
        await db.execute(q.offset((page - 1) * page_size).limit(page_size).order_by(Eot.eot_nombre))
    ).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [EotOut.model_validate(e) for e in empresas]
    }


@router.get("/{id_eot_vmt_hex}", response_model=EotOut, summary="Detalle de una empresa")
async def obtener_empresa(
    id_eot_vmt_hex: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    eot = (await db.execute(
        select(Eot).where(Eot.id_eot_vmt_hex == id_eot_vmt_hex)
    )).scalar_one_or_none()
    if not eot:
        raise HTTPException(status_code=404, detail=f"Empresa con id_eot_vmt_hex='{id_eot_vmt_hex}' no encontrada")
    return EotOut.model_validate(eot)


@router.get("/{id_eot_vmt_hex}/buses", summary="Buses asignados a una empresa")
async def buses_de_empresa(
    id_eot_vmt_hex: str,
    solo_activas: bool = True,
    a_fecha: Optional[date] = Query(
        None,
        description="Si se indica, retorna buses asignados a esa EOT en esa fecha (consulta temporal)",
    ),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Retorna los buses asignados a la empresa (vigentes, o en una fecha histórica)."""
    eot = (await db.execute(
        select(Eot).where(Eot.id_eot_vmt_hex == id_eot_vmt_hex)
    )).scalar_one_or_none()
    if not eot:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    q = select(BusEmpresa).where(BusEmpresa.id_eot == id_eot_vmt_hex)

    if a_fecha is not None:
        q = q.where(
            BusEmpresa.fecha_asignacion <= a_fecha,
            or_(
                BusEmpresa.fecha_fin_asignacion.is_(None),
                BusEmpresa.fecha_fin_asignacion >= a_fecha,
            ),
        )
    elif solo_activas:
        q = q.where(BusEmpresa.fecha_fin_asignacion.is_(None))

    asignaciones = (await db.execute(q.order_by(BusEmpresa.fecha_asignacion.desc()))).scalars().all()

    resultado = []
    for asig in asignaciones:
        bus = (await db.execute(select(Bus).where(Bus.id_bus == asig.id_bus))).scalar_one_or_none()
        resultado.append({
            "id_asignacion": asig.id_asignacion,
            "id_bus": asig.id_bus,
            "rua": bus.rua if bus else None,
            "numero_chassis": bus.numero_chassis if bus else None,
            "año": bus.año if bus else None,
            "estado_bus": bus.estado_bus if bus else None,
            "fecha_asignacion": asig.fecha_asignacion,
            "fecha_fin_asignacion": asig.fecha_fin_asignacion,
            "estado_asignacion": asig.estado_asignacion,
            "motivo": asig.motivo,
        })

    return {
        "empresa": EotOut.model_validate(eot),
        "a_fecha": a_fecha.isoformat() if a_fecha else None,
        "total_buses": len(resultado),
        "buses": resultado,
    }


# ============================================================
# ASIGNACIONES BUS ↔ EMPRESA (registro_habilitacion.bus_empresa)
# ============================================================

@router.post("/asignaciones", response_model=BusEmpresaOut, summary="Alta o transferencia de bus a EOT")
async def asignar_bus_empresa(
    body: BusEmpresaCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles("ADMIN", "SUPERVISOR", "OPERADOR"))
):
    """
    Crea una asignación vigente bus↔EOT.
    Si el bus ya tiene asignación vigente, la cierra (transferencia) con fecha_fin = fecha_asignacion.
    """
    eot = (await db.execute(
        select(Eot).where(Eot.id_eot_vmt_hex == body.id_eot)
    )).scalar_one_or_none()
    if not eot:
        raise HTTPException(
            status_code=400,
            detail=f"Empresa '{body.id_eot}' no encontrada en el catálogo de empresas (public.eots)"
        )

    bus = (await db.execute(select(Bus).where(Bus.id_bus == body.id_bus))).scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus no encontrado")
    if bus.estado_bus and bus.estado_bus.upper() in ("BAJA", "INACTIVO", "INACTIVA"):
        raise HTTPException(status_code=400, detail=f"El bus está en estado '{bus.estado_bus}' y no puede asignarse")

    asig_activa = (await db.execute(
        select(BusEmpresa).where(
            BusEmpresa.id_bus == body.id_bus,
            BusEmpresa.fecha_fin_asignacion.is_(None),
        )
    )).scalar_one_or_none()

    if asig_activa and asig_activa.id_eot == body.id_eot:
        raise HTTPException(
            status_code=409,
            detail="El bus ya está asignado de forma vigente a esa misma EOT",
        )

    if body.motivo and body.motivo.upper() not in MOTIVOS_ASIGNACION:
        raise HTTPException(
            status_code=400,
            detail=f"motivo inválido. Valores: {', '.join(MOTIVOS_ASIGNACION)}",
        )

    motivo = (body.motivo or ("TRANSFERENCIA" if asig_activa else "ALTA")).upper()

    if asig_activa:
        if body.fecha_asignacion < asig_activa.fecha_asignacion:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"fecha_asignacion ({body.fecha_asignacion}) no puede ser anterior "
                    f"al inicio de la asignación vigente ({asig_activa.fecha_asignacion})"
                ),
            )
        # Último día en la EOT anterior = día previo al inicio en la nueva
        fin_prev = body.fecha_asignacion - timedelta(days=1)
        if fin_prev < asig_activa.fecha_asignacion:
            fin_prev = asig_activa.fecha_asignacion
        asig_activa.estado_asignacion = "CERRADA"
        asig_activa.fecha_fin_asignacion = fin_prev
        if not asig_activa.motivo:
            asig_activa.motivo = "TRANSFERENCIA"

    # Validar solape contra historial (la vigente ya quedó con fecha_fin)
    await _assert_sin_solape(db, body.id_bus, body.fecha_asignacion, None)

    nueva = BusEmpresa(
        id_bus=body.id_bus,
        id_eot=body.id_eot,
        fecha_asignacion=body.fecha_asignacion,
        fecha_fin_asignacion=None,
        estado_asignacion="ACTIVA",
        motivo=motivo,
        observaciones=body.observaciones,
        usuario_registro=user.username,
    )
    db.add(nueva)
    await db.commit()
    await db.refresh(nueva)

    return await _enriquecer_asignacion(db, nueva)


@router.post("/asignaciones/baja", response_model=BusEmpresaOut, summary="Baja de bus en EOT (sin reasignar)")
async def baja_bus_empresa(
    body: BusEmpresaBaja,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles("ADMIN", "SUPERVISOR", "OPERADOR"))
):
    """
    Cierra la asignación vigente del bus sin crear otra.
    El bus queda sin EOT hasta un nuevo alta/transferencia.
    motivo: BAJA | SUSPENSION.
    """
    motivo = body.motivo.upper()
    if motivo not in ("BAJA", "SUSPENSION"):
        raise HTTPException(status_code=400, detail="motivo de baja debe ser BAJA o SUSPENSION")

    asig_activa = (await db.execute(
        select(BusEmpresa).where(
            BusEmpresa.id_bus == body.id_bus,
            BusEmpresa.fecha_fin_asignacion.is_(None),
        )
    )).scalar_one_or_none()
    if not asig_activa:
        raise HTTPException(status_code=404, detail="El bus no tiene asignación vigente a ninguna EOT")

    if body.fecha_fin < asig_activa.fecha_asignacion:
        raise HTTPException(
            status_code=400,
            detail=(
                f"fecha_fin ({body.fecha_fin}) no puede ser anterior "
                f"a fecha_asignacion ({asig_activa.fecha_asignacion})"
            ),
        )

    asig_activa.fecha_fin_asignacion = body.fecha_fin
    asig_activa.estado_asignacion = "CERRADA"
    asig_activa.motivo = motivo
    if body.observaciones:
        nota = body.observaciones
        asig_activa.observaciones = (
            f"{asig_activa.observaciones}\n{nota}" if asig_activa.observaciones else nota
        )
    # Auditoría ligera en observaciones de cierre vía usuario
    cierre = f"[cierre por {user.username}]"
    asig_activa.observaciones = (
        f"{asig_activa.observaciones} {cierre}" if asig_activa.observaciones else cierre
    )

    await db.commit()
    await db.refresh(asig_activa)
    return await _enriquecer_asignacion(db, asig_activa)


@router.get("/asignaciones/sin-empresa", summary="Buses sin asignación vigente a ninguna EOT")
async def buses_sin_empresa(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Lista buses que no tienen fila vigente en bus_empresa."""
    sub_vigentes = (
        select(BusEmpresa.id_bus)
        .where(BusEmpresa.fecha_fin_asignacion.is_(None))
        .scalar_subquery()
    )
    q = select(Bus).where(Bus.id_bus.notin_(sub_vigentes))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    buses = (
        await db.execute(
            q.order_by(Bus.rua).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id_bus": b.id_bus,
                "rua": b.rua,
                "numero_chassis": b.numero_chassis,
                "estado_bus": b.estado_bus,
                "año": b.año,
            }
            for b in buses
        ],
    }


@router.get("/asignaciones/bus/{id_bus}", response_model=list[BusEmpresaOut], summary="Historial de asignaciones de un bus")
async def historial_asignaciones_bus(
    id_bus: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    asignaciones = (await db.execute(
        select(BusEmpresa)
        .where(BusEmpresa.id_bus == id_bus)
        .order_by(BusEmpresa.fecha_asignacion.desc(), BusEmpresa.id_asignacion.desc())
    )).scalars().all()

    return [await _enriquecer_asignacion(db, asig) for asig in asignaciones]
