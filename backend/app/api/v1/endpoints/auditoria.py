from typing import Optional, List
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.core.database import get_db
from app.core.security import require_roles
from app.models import Auditoria
from app.schemas import AuditoriaOut

router = APIRouter(prefix="/auditoria", tags=["Auditoría"])


@router.get("", response_model=dict)
async def listar_auditoria(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tabla: Optional[str] = None,
    accion: Optional[str] = None,
    usuario: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_roles(["ADMIN", "SUPERVISOR"]))
):
    """Consulta paginada del log de auditoría del sistema."""
    q = select(Auditoria)
    filters = []

    if tabla:
        filters.append(Auditoria.tabla_afectada.ilike(f"%{tabla}%"))
    if accion:
        filters.append(Auditoria.accion == accion.upper())
    if usuario:
        filters.append(Auditoria.usuario.ilike(f"%{usuario}%"))

    if filters:
        q = q.where(*filters)

    # Conteo
    count_q = select(func.count()).select_from(q.subquery())
    total_res = await db.execute(count_q)
    total = total_res.scalar() or 0

    # Paginación
    q = q.order_by(Auditoria.fecha_accion.desc()).offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(q)
    logs = res.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [AuditoriaOut.model_validate(log) for log in logs]
    }
