from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.core.database import get_db
from app.core.security import get_current_user, require_roles, hash_password
from app.models import Usuario
from app.schemas import UsuarioCreate, UsuarioUpdate, UsuarioOut

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.get("", response_model=dict)
async def listar_usuarios(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    rol: Optional[str] = None,
    estado: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles(["ADMIN", "SUPERVISOR"]))
):
    """Listar usuarios del sistema con paginación y filtros."""
    q = select(Usuario)
    filters = []

    if search:
        filters.append(or_(
            Usuario.username.ilike(f"%{search}%"),
            Usuario.email.ilike(f"%{search}%"),
            Usuario.nombre_completo.ilike(f"%{search}%")
        ))
    if rol:
        filters.append(Usuario.rol == rol.upper())
    if estado:
        filters.append(Usuario.estado_usuario == estado.upper())

    if filters:
        q = q.where(*filters)

    # Conteo
    count_q = select(func.count()).select_from(q.subquery())
    total_res = await db.execute(count_q)
    total = total_res.scalar() or 0

    # Paginación
    q = q.order_by(Usuario.id_usuario.desc()).offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(q)
    usuarios = res.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [UsuarioOut.model_validate(u) for u in usuarios]
    }


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
async def crear_usuario(
    user_in: UsuarioCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_roles(["ADMIN"]))
):
    """Crear un nuevo usuario en el sistema."""
    # Verificar si username o email existen
    res = await db.execute(
        select(Usuario).where(
            or_(Usuario.username == user_in.username, Usuario.email == user_in.email)
        )
    )
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nombre de usuario o correo electrónico ya registrado"
        )

    usuario = Usuario(
        username=user_in.username,
        email=user_in.email,
        password_hash=hash_password(user_in.password),
        nombre_completo=user_in.nombre_completo,
        rol=user_in.rol.upper(),
        estado_usuario="ACTIVO"
    )
    db.add(usuario)
    await db.commit()
    await db.refresh(usuario)
    return usuario


@router.put("/{id_usuario}", response_model=UsuarioOut)
async def actualizar_usuario(
    id_usuario: int,
    user_in: UsuarioUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_roles(["ADMIN"]))
):
    """Actualizar datos o rol de un usuario."""
    res = await db.execute(select(Usuario).filter(Usuario.id_usuario == id_usuario))
    usuario = res.scalar_one_or_none()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user_in.email:
        usuario.email = user_in.email
    if user_in.nombre_completo:
        usuario.nombre_completo = user_in.nombre_completo
    if user_in.rol:
        usuario.rol = user_in.rol.upper()
    if user_in.estado_usuario:
        usuario.estado_usuario = user_in.estado_usuario.upper()
    if user_in.password:
        usuario.password_hash = hash_password(user_in.password)

    await db.commit()
    await db.refresh(usuario)
    return usuario
