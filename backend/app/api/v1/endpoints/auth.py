from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.database import get_db
from app.core.security import (
    verify_password, create_access_token, create_refresh_token,
    decode_token, hash_password, get_current_user
)
from app.models import Usuario
from app.schemas import LoginRequest, TokenResponse, UsuarioOut, RefreshRequest

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Usuario).where(Usuario.username == body.username)
    )
    user: Usuario = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos"
        )
    if user.estado_usuario != "ACTIVO":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo. Contacte al administrador."
        )

    # Actualizar último acceso (naive datetime para asyncpg)
    await db.execute(
        update(Usuario)
        .where(Usuario.id_usuario == user.id_usuario)
        .values(ultimo_acceso=datetime.now(timezone.utc).replace(tzinfo=None))
    )
    await db.commit()

    token_data = {"sub": user.username, "rol": user.rol, "id": user.id_usuario}
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

    result = await db.execute(select(Usuario).where(Usuario.username == payload["sub"]))
    user: Usuario = result.scalar_one_or_none()
    if not user or user.estado_usuario != "ACTIVO":
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")

    token_data = {"sub": user.username, "rol": user.rol, "id": user.id_usuario}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        usuario=UsuarioOut.model_validate(user)
    )


@router.get("/me", response_model=UsuarioOut)
async def get_me(current_user: Usuario = Depends(get_current_user)):
    return current_user


@router.post("/logout")
async def logout():
    # JWT es stateless; el cliente elimina el token
    return {"message": "Sesión cerrada correctamente"}
