from datetime import datetime, timedelta, timezone
from typing import Optional, List, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models import Usuario, UsuarioSistemaRol, Rol

bearer_scheme = HTTPBearer()

# ID del sistema en la tabla sistema.sistemas (SIGPA - Parque Automotor)
SISTEMA_ID_PARQUE = 5

_pwd_context = None


def get_pwd_context():
    global _pwd_context
    if _pwd_context is None:
        try:
            _pwd_context = CryptContext(
                schemes=["bcrypt"],
                deprecated="auto",
                bcrypt__ident="2b"
            )
            _pwd_context.hash("init")
        except Exception:
            _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return _pwd_context


def _truncate_password(password: str) -> str:
    if not isinstance(password, str):
        return password
    password_bytes = password.encode('utf-8')
    if len(password_bytes) <= 72:
        return password
    truncated = password_bytes[:72]
    while truncated and (truncated[-1] & 0x80) and not (truncated[-1] & 0x40):
        truncated = truncated[:-1]
    return truncated.decode('utf-8', errors='ignore')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    plain_password = _truncate_password(plain_password)
    try:
        plain_bytes = plain_password.encode('utf-8')[:72]
        hashed_bytes = hashed_password.encode('utf-8')
        if bcrypt.checkpw(plain_bytes, hashed_bytes):
            return True
    except Exception:
        pass

    try:
        ctx = get_pwd_context()
        return ctx.verify(plain_password, hashed_password)
    except Exception:
        return False


def hash_password(password: str) -> str:
    password = _truncate_password(password)
    ctx = get_pwd_context()
    return ctx.hash(password)


def get_password_hash(password: str) -> str:
    return hash_password(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


def normalize_role(role_name: Optional[str]) -> str:
    if not role_name:
        return "CONSULTA"
    r = role_name.strip().lower()
    if r in ("admin", "administrador"):
        return "ADMIN"
    if r in ("manager", "supervisor", "gerente"):
        return "SUPERVISOR"
    if r in ("user", "operador"):
        return "OPERADOR"
    if r in ("viewer", "consulta"):
        return "CONSULTA"
    return role_name.upper()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    payload = decode_token(credentials.credentials)
    username: str = payload.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    result = await db.execute(
        select(Usuario)
        .options(
            selectinload(Usuario.habilitaciones_sistemas).selectinload(UsuarioSistemaRol.rol),
            selectinload(Usuario.organismo)
        )
        .where(Usuario.username == username)
    )
    user = result.scalar_one_or_none()
    if not user or not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo"
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no tiene permisos habilitados en este sistema."
        )

    user.rol = normalize_role(user_rol or 'ADMIN')
    user.rol_raw = user_rol
    return user


def require_roles(*roles: Union[str, List[str]]):
    """
    Decorator de roles.
    Ejemplos de uso:
    - Depends(require_roles('ADMIN', 'SUPERVISOR'))
    - Depends(require_roles(['ADMIN', 'SUPERVISOR']))
    """
    flat_roles = []
    for r in roles:
        if isinstance(r, list):
            flat_roles.extend(r)
        else:
            flat_roles.append(r)
    normalized_allowed = [normalize_role(str(x)) for x in flat_roles]
    raw_allowed = [str(x).strip().lower() for x in flat_roles]

    async def checker(current_user: Usuario = Depends(get_current_user)) -> Usuario:
        user_role_norm = normalize_role(getattr(current_user, 'rol', ''))
        user_role_raw = str(getattr(current_user, 'rol_raw', '') or '').strip().lower()

        if user_role_norm not in normalized_allowed and user_role_raw not in raw_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Roles permitidos: {', '.join(normalized_allowed)}"
            )
        return current_user

    return checker
