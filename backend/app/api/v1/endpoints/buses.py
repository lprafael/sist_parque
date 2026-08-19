from typing import Optional, List
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, text
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import Bus, Marca, TipoCarroceria, MarcaCarroceria, TipoServicio, ItvBus, BusEmpresa, Eot
from app.schemas import BusBajaIn, BusBajaOut, BusCreate, BusUpdate, BusOut, TipoServicioOut
from app.services.bus_baja import CAUSALES_BAJA, aplicar_baja_buses
from app.services.sistema_logs import registrar_auditoria

router = APIRouter(prefix="/buses", tags=["Buses"])


def calcular_estado_itv(vencimiento: Optional[date]) -> str:
    # Sin fecha = VENCIDA en la planilla (00/00/00), no "sin ITV".
    if not vencimiento:
        return "VENCIDO"
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
    numero_orden: Optional[int] = None,
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
            selectinload(Bus.tipo_servicio_rel),
        )
    )

    filters = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        filters.append(or_(
            Bus.rua.ilike(term),
            Bus.numero_chassis.ilike(term),
        ))
    if estado_bus:
        est = estado_bus.upper()
        # INACTIVO quedó como alias histórico; el parque no operativo está en BAJA
        if est == "INACTIVO":
            filters.append(Bus.estado_bus.in_(["INACTIVO", "BAJA"]))
        else:
            filters.append(Bus.estado_bus == est)
    if id_marca:
        filters.append(Bus.id_marca == id_marca)
    if numero_orden is not None:
        filters.append(Bus.numero_orden == numero_orden)
    if empresa:
        subq = (
            select(BusEmpresa.id_bus)
            .join(Eot, Eot.id_eot_vmt_hex == BusEmpresa.id_eot, isouter=True)
            .where(
                BusEmpresa.fecha_fin_asignacion.is_(None),
                or_(
                    BusEmpresa.id_eot == empresa,
                    Eot.id_eot_vmt_hex == empresa,
                    Eot.eot_nombre.ilike(f"%{empresa}%")
                )
            )
        )
        filters.append(Bus.id_bus.in_(subq))

    if filters:
        q = q.where(and_(*filters))

    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar()

    q = q.offset((page - 1) * page_size).limit(page_size).order_by(Bus.numero_orden)
    buses = (await db.execute(q)).scalars().all()

    # Enriquecer con ITV y Nombre de Empresa
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
            select(Eot.eot_nombre, BusEmpresa.id_eot)
            .join(BusEmpresa, BusEmpresa.id_eot == Eot.id_eot_vmt_hex)
            .where(BusEmpresa.id_bus == bus.id_bus, BusEmpresa.fecha_fin_asignacion.is_(None))
            .limit(1)
        )
        emp_res = (await db.execute(emp_q)).one_or_none()
        if emp_res:
            empresa_nombre = emp_res[0] if emp_res[0] else emp_res[1]
        else:
            emp_q_raw = select(BusEmpresa.id_eot).where(BusEmpresa.id_bus == bus.id_bus, BusEmpresa.fecha_fin_asignacion.is_(None)).limit(1)
            empresa_nombre = (await db.execute(emp_q_raw)).scalar_one_or_none()

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
            id_tipo_servicio=bus.id_tipo_servicio,
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
            tipo_servicio_nombre=bus.tipo_servicio_rel.nombre if bus.tipo_servicio_rel else None,
            empresa_actual=empresa_nombre,
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
        selectinload(Bus.tipo_servicio_rel),
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
        (a.id_eot for a in bus.asignaciones if a.fecha_fin_asignacion is None), None
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
        id_tipo_servicio=bus.id_tipo_servicio,
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
        tipo_servicio_nombre=bus.tipo_servicio_rel.nombre if bus.tipo_servicio_rel else None,
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

    if (body.estado_bus or "").upper() == "BAJA":
        raise HTTPException(
            status_code=400,
            detail="Para dar de baja use POST /buses/{id}/baja (motivo + cierre de asignación + ITV).",
        )

    bus = Bus(**body.model_dump())
    db.add(bus)
    await db.flush()

    await registrar_auditoria(
        db,
        accion="insert",
        tabla="buses",
        usuario=user,
        registro_id=bus.id_bus,
        datos_nuevos=body.model_dump(mode="json"),
        detalles=f"Alta de bus RUA={getattr(bus, 'rua', None)}",
    )
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
    nuevo_estado = (update_data.get("estado_bus") or "").upper()
    if nuevo_estado == "BAJA" and (bus.estado_bus or "").upper() != "BAJA":
        raise HTTPException(
            status_code=400,
            detail="La baja formal se hace en POST /buses/{id}/baja (motivo, cierra asignación e invalida ITV).",
        )
    for k, v in update_data.items():
        setattr(bus, k, v)

    await registrar_auditoria(
        db,
        accion="update",
        tabla="buses",
        usuario=user,
        registro_id=id_bus,
        datos_anteriores=old_data,
        datos_nuevos=update_data,
        detalles=f"Actualización de bus id={id_bus}",
    )
    await db.commit()
    return await obtener_bus(id_bus, db)


@router.post("/{id_bus}/baja", response_model=BusBajaOut)
async def dar_de_baja_bus(
    id_bus: int,
    body: BusBajaIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles("ADMIN", "SUPERVISOR", "OPERADOR")),
):
    """Baja formal: estado BAJA, cierra asignación vigente e invalida ITV vigente."""
    bus = (await db.execute(select(Bus).where(Bus.id_bus == id_bus))).scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus no encontrado")
    if (bus.estado_bus or "").upper() == "BAJA":
        raise HTTPException(status_code=409, detail="El bus ya está dado de baja")

    if body.causal == "OTRO" and not (body.causal_detalle or "").strip():
        raise HTTPException(status_code=400, detail="Indique el detalle de la causal (OTRO)")

    asig_activa = (
        await db.execute(
            select(BusEmpresa).where(
                BusEmpresa.id_bus == id_bus,
                BusEmpresa.fecha_fin_asignacion.is_(None),
            )
        )
    ).scalar_one_or_none()
    if asig_activa and body.fecha_baja < asig_activa.fecha_asignacion:
        raise HTTPException(
            status_code=400,
            detail=(
                f"fecha_baja ({body.fecha_baja}) no puede ser anterior "
                f"al inicio de la asignación vigente ({asig_activa.fecha_asignacion})"
            ),
        )

    nota = " | ".join(
        p.strip()
        for p in (body.causal_detalle, body.observaciones)
        if p and p.strip()
    )

    applied = await aplicar_baja_buses(
        db,
        [bus],
        fecha_baja=body.fecha_baja,
        motivo_asignacion="BAJA",
        causal=body.causal,
        normativa=body.normativa,
        observaciones=nota or None,
        usuario=user.username,
        enriquecer_asig=True,
        auditar=True,
    )
    await db.commit()
    out = await obtener_bus(id_bus, db)
    return BusBajaOut(
        id_bus=id_bus,
        estado_bus=out.estado_bus,
        fecha_baja=body.fecha_baja,
        causal=body.causal,
        asignacion_cerrada=applied["asignaciones_cerradas"] > 0,
        itv_invalidadas=applied["itv_invalidadas"],
        bus=out,
    )


@router.delete("/{id_bus}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_bus(
    id_bus: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles("ADMIN"))
):
    bus = (await db.execute(select(Bus).where(Bus.id_bus == id_bus))).scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus no encontrado")

    await registrar_auditoria(
        db,
        accion="delete",
        tabla="buses",
        usuario=user,
        registro_id=id_bus,
        datos_anteriores={"rua": bus.rua, "chassis": bus.numero_chassis},
        detalles=f"Eliminación de bus RUA={bus.rua}",
    )
    await db.delete(bus)
    await db.commit()


@router.get("/catalogo/numeros-orden")
async def listar_numeros_orden(
    q: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Devuelve pares {numero_orden, rua} para el autocomplete del filtro."""
    stmt = (
        select(Bus.numero_orden, Bus.rua)
        .where(Bus.numero_orden.isnot(None))
        .order_by(Bus.numero_orden)
        .limit(200)
    )
    if q and q.strip():
        try:
            n = int(q.strip())
            stmt = stmt.where(Bus.numero_orden == n)
        except ValueError:
            stmt = stmt.where(Bus.rua.ilike(f"%{q.strip()}%"))
    rows = (await db.execute(stmt)).all()
    return [{"numero_orden": r[0], "rua": r[1]} for r in rows]


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


@router.get("/catalogo/causales-baja")
async def listar_causales_baja(_=Depends(get_current_user)):
    from app.services.bus_baja import CAUSAL_LABEL
    return [{"codigo": k, "label": CAUSAL_LABEL[k]} for k in CAUSALES_BAJA]


@router.get("/catalogo/tipos-servicio", response_model=list[TipoServicioOut])
async def listar_tipos_servicio(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(TipoServicio).where(TipoServicio.activo == True).order_by(TipoServicio.nombre)
    )
    return result.scalars().all()
