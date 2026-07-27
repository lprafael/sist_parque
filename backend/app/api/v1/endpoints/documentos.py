from typing import Optional, List
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import DocumentoBus, Bus
from app.schemas import DocumentoBusCreate, DocumentoBusOut

router = APIRouter(prefix="/documentos", tags=["Documentos"])


def calcular_estado_doc(vencimiento: Optional[date]) -> str:
    if not vencimiento:
        return "SIN_FECHA"
    today = date.today()
    diff = (vencimiento - today).days
    if diff < 0:
        return "VENCIDO"
    elif diff <= 30:
        return "POR_VENCER"
    return "VIGENTE"


@router.get("/bus/{id_bus}", response_model=List[DocumentoBusOut])
async def listar_documentos_bus(
    id_bus: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Listar todos los documentos de un vehículo."""
    res = await db.execute(
        select(DocumentoBus)
        .filter(DocumentoBus.id_bus == id_bus)
        .order_by(DocumentoBus.fecha_registro.desc())
    )
    docs = res.scalars().all()
    for d in docs:
        d.estado_documento = calcular_estado_doc(d.fecha_vencimiento)
    return docs


@router.post("", response_model=DocumentoBusOut, status_code=status.HTTP_201_CREATED)
async def crear_documento(
    doc_in: DocumentoBusCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles(["ADMIN", "SUPERVISOR", "OPERADOR"]))
):
    """Registrar un nuevo documento para un bus."""
    # Verificar bus
    res_bus = await db.execute(select(Bus).filter(Bus.id_bus == doc_in.id_bus))
    bus = res_bus.scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus no encontrado")

    doc = DocumentoBus(
        id_bus=doc_in.id_bus,
        tipo_documento=doc_in.tipo_documento,
        nombre_documento=doc_in.nombre_documento,
        fecha_emision=doc_in.fecha_emision,
        fecha_vencimiento=doc_in.fecha_vencimiento,
        estado_documento=calcular_estado_doc(doc_in.fecha_vencimiento),
        observaciones=doc_in.observaciones
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


@router.delete("/{id_documento}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_documento(
    id_documento: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles(["ADMIN", "SUPERVISOR"]))
):
    """Eliminar un documento registrado."""
    res = await db.execute(select(DocumentoBus).filter(DocumentoBus.id_documento == id_documento))
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    await db.delete(doc)
    await db.commit()
    return None
