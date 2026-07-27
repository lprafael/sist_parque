"""
Empresas Operadoras de Transporte.
IMPORTANTE: public.eots es READ-ONLY (sistema CID).
Este módulo solo consulta esa tabla; nunca escribe en ella.
La asignación bus↔empresa se gestiona en registro_habilitacion.bus_empresa,
usando id_eot_vmt_hex como referencia a public.eots.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import Eot, BusEmpresa, Bus
from app.schemas import EotOut, BusEmpresaCreate, BusEmpresaOut

router = APIRouter(prefix="/empresas", tags=["Empresas (EOT)"])


# ============================================================
# CONSULTA DE EMPRESAS (READ-ONLY → public.eots)
# ============================================================

@router.get("", response_model=dict, summary="Listar empresas operadoras (fuente: public.eots)")
async def listar_empresas(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    solo_activas: bool = True,
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
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Retorna los buses asignados actualmente a la empresa indicada."""
    # Verificar que la empresa existe
    eot = (await db.execute(
        select(Eot).where(Eot.id_eot_vmt_hex == id_eot_vmt_hex)
    )).scalar_one_or_none()
    if not eot:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    q = (
        select(BusEmpresa)
        .where(BusEmpresa.id_eot == id_eot_vmt_hex)
    )
    if solo_activas:
        q = q.where(BusEmpresa.estado_asignacion == "ACTIVA")

    asignaciones = (await db.execute(q)).scalars().all()

    # Enriquecer con datos del bus
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
        })

    return {
        "empresa": EotOut.model_validate(eot),
        "total_buses": len(resultado),
        "buses": resultado
    }


# ============================================================
# ASIGNACIONES BUS ↔ EMPRESA (registro_habilitacion.bus_empresa)
# Escritura permitida aquí — pero solo referencia a EOTs existentes
# ============================================================

@router.post("/asignaciones", response_model=BusEmpresaOut, summary="Asignar bus a empresa")
async def asignar_bus_empresa(
    body: BusEmpresaCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles("ADMIN", "SUPERVISOR", "OPERADOR"))
):
    """
    Crea una asignación bus↔empresa en registro_habilitacion.bus_empresa.
    El campo id_eot debe corresponder a un id_eot_vmt_hex válido de public.eots.
    """
    # Verificar que la empresa existe en public.eots (read-only)
    eot = (await db.execute(
        select(Eot).where(Eot.id_eot_vmt_hex == body.id_eot)
    )).scalar_one_or_none()
    if not eot:
        raise HTTPException(
            status_code=400,
            detail=f"Empresa '{body.id_eot}' no encontrada en el catálogo de empresas (public.eots)"
        )

    # Verificar que el bus existe
    bus = (await db.execute(select(Bus).where(Bus.id_bus == body.id_bus))).scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus no encontrado")

    # Cerrar asignación activa anterior si existe
    asig_activa = (await db.execute(
        select(BusEmpresa).where(
            BusEmpresa.id_bus == body.id_bus,
            BusEmpresa.estado_asignacion == "ACTIVA"
        )
    )).scalar_one_or_none()

    if asig_activa:
        asig_activa.estado_asignacion = "CERRADA"
        asig_activa.fecha_fin_asignacion = body.fecha_asignacion

    nueva = BusEmpresa(**body.model_dump(), usuario_registro=user.username)
    db.add(nueva)
    await db.commit()
    await db.refresh(nueva)

    return BusEmpresaOut(
        **{c.name: getattr(nueva, c.name) for c in BusEmpresa.__table__.columns},
        empresa_nombre=eot.eot_nombre,
        empresa_lineas=eot.eot_linea,
    )


@router.get("/asignaciones/bus/{id_bus}", response_model=list[BusEmpresaOut], summary="Historial de asignaciones de un bus")
async def historial_asignaciones_bus(
    id_bus: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    asignaciones = (await db.execute(
        select(BusEmpresa)
        .where(BusEmpresa.id_bus == id_bus)
        .order_by(BusEmpresa.fecha_asignacion.desc())
    )).scalars().all()

    resultado = []
    for asig in asignaciones:
        eot = (await db.execute(
            select(Eot).where(Eot.id_eot_vmt_hex == asig.id_eot)
        )).scalar_one_or_none()
        resultado.append(BusEmpresaOut(
            **{c.name: getattr(asig, c.name) for c in BusEmpresa.__table__.columns},
            empresa_nombre=eot.eot_nombre if eot else None,
            empresa_lineas=eot.eot_linea if eot else None,
        ))
    return resultado
