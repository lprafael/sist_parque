from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_roles, hash_password, normalize_role, SISTEMA_ID_PARQUE
from app.models import Usuario, UsuarioSistemaRol, Rol
from app.schemas import UsuarioCreate, UsuarioUpdate, UsuarioOut
from app.services.sistema_logs import registrar_auditoria

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


def role_name_to_id(role_str: str) -> int:
    r = role_str.strip().lower()
    if r in ("admin", "administrador"):
        return 1
    if r in ("manager", "supervisor", "gerente"):
        return 2
    if r in ("user", "operador"):
        return 3
    if r in ("viewer", "consulta"):
        return 4
    return 3


def populate_user_role(u: Usuario):
    user_rol = None
    if u.username == 'admin':
        user_rol = 'ADMIN'
    else:
        for hab in getattr(u, 'habilitaciones_sistemas', []):
            if getattr(hab, 'sistema_id', None) == SISTEMA_ID_PARQUE and getattr(hab, 'activo', True):
                if getattr(hab, 'rol', None):
                    user_rol = getattr(hab.rol, 'nombre', None)
                break
    u.rol = normalize_role(user_rol or 'CONSULTA')


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
    """Listar solo usuarios habilitados en SIGPA (Parque Automotor, id_sistema=5)."""
    # Usuarios con habilitación activa en Parque (+ admin, que siempre tiene acceso)
    parque_ids = (
        select(UsuarioSistemaRol.usuario_id)
        .where(
            UsuarioSistemaRol.sistema_id == SISTEMA_ID_PARQUE,
            UsuarioSistemaRol.activo == True,
        )
    )

    q = select(Usuario).options(
        selectinload(Usuario.habilitaciones_sistemas).selectinload(UsuarioSistemaRol.rol)
    )
    filters = [
        or_(
            Usuario.username == "admin",
            Usuario.id.in_(parque_ids),
        )
    ]

    if search:
        filters.append(or_(
            Usuario.username.ilike(f"%{search}%"),
            Usuario.email.ilike(f"%{search}%"),
            Usuario.nombre_completo.ilike(f"%{search}%")
        ))
    if estado:
        is_active = estado.upper() == "ACTIVO"
        filters.append(Usuario.activo == is_active)

    q = q.where(*filters)

    # Filtro por rol en Parque (en SQL, no post-paginación)
    if rol:
        rol_norm = normalize_role(rol)
        rol_aliases = {
            "ADMIN": ["ADMIN", "Administrador", "admin", "administrador"],
            "SUPERVISOR": ["SUPERVISOR", "Manager", "manager", "supervisor", "gerente"],
            "OPERADOR": ["OPERADOR", "User", "user", "operador"],
            "CONSULTA": ["CONSULTA", "Viewer", "viewer", "consulta"],
        }
        aliases = rol_aliases.get(rol_norm, [rol_norm])
        rol_ids_q = select(Rol.id).where(or_(*[Rol.nombre.ilike(a) for a in aliases]))
        parque_rol_ids = (
            select(UsuarioSistemaRol.usuario_id)
            .where(
                UsuarioSistemaRol.sistema_id == SISTEMA_ID_PARQUE,
                UsuarioSistemaRol.activo == True,
                UsuarioSistemaRol.rol_id.in_(rol_ids_q),
            )
        )
        if rol_norm == "ADMIN":
            q = q.where(or_(Usuario.username == "admin", Usuario.id.in_(parque_rol_ids)))
        else:
            q = q.where(Usuario.id.in_(parque_rol_ids))

    # Conteo
    count_q = select(func.count()).select_from(q.order_by(None).subquery())
    total_res = await db.execute(count_q)
    total = total_res.scalar() or 0

    # Paginación
    q = q.order_by(Usuario.id.desc()).offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(q)
    usuarios = res.scalars().unique().all()

    items = []
    for u in usuarios:
        populate_user_role(u)
        items.append(UsuarioOut.model_validate(u))

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
async def crear_usuario(
    user_in: UsuarioCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_roles(["ADMIN"]))
):
    """Crear un nuevo usuario en el sistema centralizado."""
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
        hashed_password=hash_password(user_in.password),
        nombre_completo=user_in.nombre_completo,
        activo=True
    )
    db.add(usuario)
    await db.commit()
    await db.refresh(usuario)

    # Habilitación en id_sistema = 5
    rol_id = role_name_to_id(user_in.rol)
    hab = UsuarioSistemaRol(
        usuario_id=usuario.id,
        sistema_id=SISTEMA_ID_PARQUE,
        rol_id=rol_id,
        activo=True
    )
    db.add(hab)
    await registrar_auditoria(
        db,
        accion="insert",
        tabla="usuarios",
        usuario=admin,
        registro_id=usuario.id,
        datos_nuevos={
            "username": usuario.username,
            "email": usuario.email,
            "rol": user_in.rol,
            "sistema_id": SISTEMA_ID_PARQUE,
        },
        detalles=f"Alta de usuario {usuario.username} en SIGPA",
    )
    await db.commit()

    # Recargar con relaciones
    res_final = await db.execute(
        select(Usuario)
        .options(selectinload(Usuario.habilitaciones_sistemas).selectinload(UsuarioSistemaRol.rol))
        .where(Usuario.id == usuario.id)
    )
    user_final = res_final.scalar_one()
    populate_user_role(user_final)
    return UsuarioOut.model_validate(user_final)


@router.put("/{id_usuario}", response_model=UsuarioOut)
async def actualizar_usuario(
    id_usuario: int,
    user_in: UsuarioUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_roles(["ADMIN"]))
):
    """Actualizar datos o rol de un usuario."""
    res = await db.execute(
        select(Usuario)
        .options(selectinload(Usuario.habilitaciones_sistemas).selectinload(UsuarioSistemaRol.rol))
        .filter(Usuario.id == id_usuario)
    )
    usuario = res.scalar_one_or_none()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user_in.email:
        usuario.email = user_in.email
    if user_in.nombre_completo:
        usuario.nombre_completo = user_in.nombre_completo
    if user_in.estado_usuario:
        usuario.activo = user_in.estado_usuario.upper() == "ACTIVO"
    if user_in.password:
        usuario.hashed_password = hash_password(user_in.password)

    if user_in.rol:
        rol_id = role_name_to_id(user_in.rol)
        hab_exist = None
        for h in getattr(usuario, 'habilitaciones_sistemas', []):
            if getattr(h, 'sistema_id', None) == SISTEMA_ID_PARQUE:
                hab_exist = h
                break

        if hab_exist:
            hab_exist.rol_id = rol_id
            hab_exist.activo = True
        else:
            new_hab = UsuarioSistemaRol(
                usuario_id=usuario.id,
                sistema_id=SISTEMA_ID_PARQUE,
                rol_id=rol_id,
                activo=True
            )
            db.add(new_hab)

    await registrar_auditoria(
        db,
        accion="update",
        tabla="usuarios",
        usuario=admin,
        registro_id=id_usuario,
        datos_nuevos=user_in.model_dump(exclude_unset=True, exclude={"password"}),
        detalles=f"Actualización de usuario {usuario.username}",
    )
    await db.commit()

    res_final = await db.execute(
        select(Usuario)
        .options(selectinload(Usuario.habilitaciones_sistemas).selectinload(UsuarioSistemaRol.rol))
        .filter(Usuario.id == id_usuario)
    )
    user_final = res_final.scalar_one()
    populate_user_role(user_final)
    return UsuarioOut.model_validate(user_final)
