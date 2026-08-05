from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, SISTEMA_ID_PARQUE
from app.models import Mensaje, Usuario
from app.schemas import MensajeCreate, MensajeOut

router = APIRouter(prefix="/mensajes", tags=["Mensajes"])


@router.post("", response_model=MensajeOut, status_code=201)
async def crear_mensaje(
    body: MensajeCreate,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Registra un mensaje de feedback del usuario autenticado (entrante)."""
    row = Mensaje(
        id_usuario=user.id,
        id_sistema=SISTEMA_ID_PARQUE,
        tipo=body.tipo,
        mensaje=body.mensaje,
        entrante=True,
        leido=False,
        solucion=False,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return MensajeOut.model_validate(row)
