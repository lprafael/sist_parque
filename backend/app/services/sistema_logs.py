"""
Auditoría central SIGPA (sistema.sistemas.id = 5).

- Logueos  → sistema.logs_acceso.sistema_id = 5
- Cambios  → sistema.logs_auditoria.sistema_id = 5
             (y espejo en registro_habilitacion.auditoria para la UI local)
"""
from __future__ import annotations

import contextvars
import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import SISTEMA_ID_PARQUE
from app.models import Auditoria, LogAcceso, LogAuditoriaSistema

_request_var: contextvars.ContextVar[Optional[Request]] = contextvars.ContextVar(
    "audit_request", default=None
)
_audit_written_var: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "audit_written", default=False
)

_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_SKIP_AUDIT_PREFIXES = (
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/refresh",
    "/api/v1/importador/preview",
    "/api/v1/importador/preview-empresas",
    "/api/v1/importador/upload-excel",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
)
_PATH_TABLA = re.compile(r"^/api/v1/([^/?]+)")
_PATH_ID = re.compile(r"/(\d+)(?:/|$|\?)")


def bind_request(request: Request) -> None:
    _request_var.set(request)
    _audit_written_var.set(False)


def current_request() -> Optional[Request]:
    return _request_var.get()


def _json_safe(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, bytes):
        return f"<bytes {len(obj)}>"
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v) for v in obj]
    return str(obj)


def client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    if request.client:
        return (request.client.host or "")[:45]
    return None


def user_agent(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    return request.headers.get("user-agent")


def _identity(usuario: Any) -> tuple[Optional[int], str]:
    if usuario is None:
        return None, "anonimo"
    if isinstance(usuario, str):
        return None, usuario or "anonimo"
    uid = getattr(usuario, "id", None)
    name = getattr(usuario, "username", None) or "anonimo"
    return uid, name


def _norm_accion(accion: str) -> str:
    raw = (accion or "update").strip().lower()
    aliases = {
        "insert": "insert",
        "create": "insert",
        "update": "update",
        "put": "update",
        "patch": "update",
        "delete": "delete",
        "baja": "update",
        "import": "import",
        "importar": "import",
    }
    return aliases.get(raw, raw[:50] or "update")


async def ensure_logs_schema(db: Optional[AsyncSession] = None) -> None:
    """Garantiza sistema_id en logs_auditoria (entornos que aún no lo tienen)."""
    sql = text(
        "ALTER TABLE sistema.logs_auditoria "
        "ADD COLUMN IF NOT EXISTS sistema_id INTEGER"
    )
    if db is not None:
        await db.execute(sql)
        await db.commit()
        return
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(sql)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            print(f"[AUDIT] No se pudo asegurar sistema_id en logs_auditoria: {exc}")


async def registrar_acceso(
    db: AsyncSession,
    *,
    username: str,
    accion: str,
    exitoso: bool,
    usuario_id: Optional[int] = None,
    request: Optional[Request] = None,
    detalles: Optional[dict] = None,
) -> None:
    req = request or current_request()
    db.add(LogAcceso(
        usuario_id=usuario_id,
        username=(username or "anonimo")[:50],
        accion=accion[:50],
        ip_address=client_ip(req),
        user_agent=user_agent(req),
        exitoso=exitoso,
        detalles=_json_safe(detalles) if detalles else None,
        sistema_id=SISTEMA_ID_PARQUE,
        fecha=datetime.utcnow(),
    ))


async def registrar_auditoria(
    db: AsyncSession,
    *,
    accion: str,
    tabla: str,
    usuario: Any = None,
    registro_id: Optional[int] = None,
    datos_anteriores: Any = None,
    datos_nuevos: Any = None,
    detalles: Optional[str] = None,
    request: Optional[Request] = None,
    espejo_local: bool = True,
) -> None:
    req = request or current_request()
    uid, username = _identity(usuario)
    accion_norm = _norm_accion(accion)
    db.add(LogAuditoriaSistema(
        usuario_id=uid,
        username=username[:100],
        accion=accion_norm,
        tabla=(tabla or "desconocida")[:100],
        registro_id=registro_id,
        datos_anteriores=_json_safe(datos_anteriores),
        datos_nuevos=_json_safe(datos_nuevos),
        ip_address=client_ip(req),
        user_agent=user_agent(req),
        fecha=datetime.utcnow(),
        detalles=(detalles or "")[:2000] or None,
        sistema_id=SISTEMA_ID_PARQUE,
    ))
    if espejo_local:
        local_accion = {
            "insert": "INSERT",
            "update": "UPDATE",
            "delete": "DELETE",
            "import": "IMPORT",
        }.get(accion_norm, accion_norm.upper()[:20])
        db.add(Auditoria(
            tabla_afectada=(tabla or "desconocida")[:100],
            id_registro=registro_id,
            accion=local_accion,
            datos_anteriores=_json_safe(datos_anteriores),
            datos_nuevos=_json_safe(datos_nuevos),
            usuario=username[:100],
        ))
    _audit_written_var.set(True)


def _tabla_desde_path(path: str) -> str:
    m = _PATH_TABLA.match(path)
    return (m.group(1) if m else path.strip("/") or "api")[:100]


def _id_desde_path(path: str) -> Optional[int]:
    m = _PATH_ID.search(path)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _accion_http(method: str, path: str) -> str:
    p = path.lower()
    if "import" in p or "sincronizar" in p or "cargar" in p or "upload" in p:
        return "import"
    if "/baja" in p:
        return "update"
    return {"POST": "insert", "PUT": "update", "PATCH": "update", "DELETE": "delete"}.get(
        method.upper(), "update"
    )


def _usuario_desde_jwt(request: Request) -> tuple[Optional[int], str]:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None, "anonimo"
    try:
        from jose import jwt
        from app.core.config import settings

        payload = jwt.decode(
            auth.split(" ", 1)[1],
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        uid = payload.get("user_id") or payload.get("id")
        try:
            uid = int(uid) if uid is not None else None
        except (TypeError, ValueError):
            uid = None
        return uid, (payload.get("sub") or "anonimo")
    except Exception:
        return None, "anonimo"


async def auditar_request_http(request: Request, status_code: int, body: Any = None) -> None:
    """Fallback: registra mutaciones HTTP que el endpoint no auditó en detalle."""
    if _audit_written_var.get():
        return
    if request.method.upper() not in _MUTATING:
        return
    if status_code >= 400:
        return
    path = request.url.path or ""
    if any(path.startswith(p) or path == p for p in _SKIP_AUDIT_PREFIXES):
        return

    uid, username = _usuario_desde_jwt(request)
    tabla = _tabla_desde_path(path)
    registro_id = _id_desde_path(path)
    datos = body
    if isinstance(body, (bytes, bytearray)):
        if request.headers.get("content-type", "").startswith("multipart/"):
            datos = {"multipart": True, "bytes": len(body)}
        else:
            try:
                datos = json.loads(body.decode("utf-8") or "null")
            except Exception:
                datos = {"raw": body[:500].decode("utf-8", errors="replace")}
    if isinstance(datos, dict):
        datos = {k: v for k, v in datos.items() if k.lower() not in {"password", "hashed_password", "token"}}

    async with AsyncSessionLocal() as session:
        try:
            await registrar_auditoria(
                session,
                accion=_accion_http(request.method, path),
                tabla=tabla,
                usuario=type("U", (), {"id": uid, "username": username})(),
                registro_id=registro_id,
                datos_nuevos=datos,
                detalles=f"{request.method} {path} → {status_code}",
                request=request,
                espejo_local=False,
            )
            await session.commit()
        except Exception as exc:
            await session.rollback()
            print(f"[AUDIT] No se pudo registrar logs_auditoria: {exc}")
