from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import (
    verify_password, create_access_token, create_refresh_token,
    decode_token, get_current_user, normalize_role, SISTEMA_ID_PARQUE
)
from app.models import Usuario, UsuarioSistemaRol
from app.schemas import LoginRequest, TokenResponse, UsuarioOut, RefreshRequest
from app.services.sistema_logs import registrar_acceso

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Usuario)
        .options(
            selectinload(Usuario.habilitaciones_sistemas).selectinload(UsuarioSistemaRol.rol),
            selectinload(Usuario.organismo)
        )
        .where(Usuario.username == body.username)
    )
    user: Usuario = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        await registrar_acceso(
            db,
            username=body.username,
            accion="login_failed",
            exitoso=False,
            usuario_id=user.id if user else None,
            request=request,
            detalles={"motivo": "credenciales_incorrectas"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

    if not user.activo:
        await registrar_acceso(
            db,
            username=user.username,
            accion="login_failed",
            exitoso=False,
            usuario_id=user.id,
            request=request,
            detalles={"motivo": "usuario_inactivo"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo"
        )

    # Determinar rol en id_sistema = 5
    user_rol = None
    if user.username == 'admin':
        user_rol = 'ADMIN'
    else:
        for hab in getattr(user, 'habilitaciones_sistemas', []):
            if getattr(hab, 'sistema_id', None) == SISTEMA_ID_PARQUE and getattr(hab, 'activo', True):
                if getattr(hab, 'rol', None):
                    user_rol = getattr(hab.rol, 'nombre', None)
                break

    if not user_rol and user.username != 'admin':
        await registrar_acceso(
            db,
            username=user.username,
            accion="login_failed",
            exitoso=False,
            usuario_id=user.id,
            request=request,
            detalles={"motivo": "sin_permiso_sigpa", "sistema_id": SISTEMA_ID_PARQUE},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no tiene permisos habilitados en este sistema."
        )

    norm_role = normalize_role(user_rol or 'ADMIN')
    user.rol = norm_role

    # Actualizar último acceso y registrar log (sistema_id = 5 SIGPA)
    user.ultimo_acceso = datetime.now(timezone.utc).replace(tzinfo=None)
    await registrar_acceso(
        db,
        username=user.username,
        accion="login",
        exitoso=True,
        usuario_id=user.id,
        request=request,
        detalles={"rol": norm_role},
    )
    await db.commit()

    token_data = {"sub": user.username, "role": norm_role, "rol": norm_role, "user_id": user.id, "id": user.id}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        usuario=UsuarioOut.model_validate(user)
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Token de refresh inválido")

    result = await db.execute(
        select(Usuario)
        .options(
            selectinload(Usuario.habilitaciones_sistemas).selectinload(UsuarioSistemaRol.rol),
            selectinload(Usuario.organismo)
        )
        .where(Usuario.username == payload["sub"])
    )
    user: Usuario = result.scalar_one_or_none()
    if not user or not user.activo:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")

    user_rol = None
    if user.username == 'admin':
        user_rol = 'ADMIN'
    else:
        for hab in getattr(user, 'habilitaciones_sistemas', []):
            if getattr(hab, 'sistema_id', None) == SISTEMA_ID_PARQUE and getattr(hab, 'activo', True):
                if getattr(hab, 'rol', None):
                    user_rol = getattr(hab.rol, 'nombre', None)
                break

    if not user_rol and user.username != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no tiene permisos habilitados en este sistema."
        )

    norm_role = normalize_role(user_rol or 'ADMIN')
    user.rol = norm_role

    token_data = {"sub": user.username, "role": norm_role, "rol": norm_role, "user_id": user.id, "id": user.id}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        usuario=UsuarioOut.model_validate(user)
    )


@router.get("/me", response_model=UsuarioOut)
async def get_me(current_user: Usuario = Depends(get_current_user)):
    return current_user


@router.post("/logout")
async def logout(
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await registrar_acceso(
        db,
        username=current_user.username,
        accion="logout",
        exitoso=True,
        usuario_id=current_user.id,
        request=request,
    )
    await db.commit()
    return {"message": "Sesión cerrada correctamente"}
