"""Zona horaria operativa del sistema: Paraguay (Asunción)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

TZ_ASUNCION = ZoneInfo("America/Asuncion")
TZ_UTC = timezone.utc


def now_utc() -> datetime:
    """Instante actual en UTC (aware)."""
    return datetime.now(TZ_UTC)


def now_utc_naive() -> datetime:
    """UTC sin tzinfo, para columnas DateTime naive."""
    return now_utc().replace(tzinfo=None)


def now_asuncion() -> datetime:
    """Instante actual en America/Asuncion (aware)."""
    return datetime.now(TZ_ASUNCION)


def to_asuncion(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Convierte un datetime a America/Asuncion.
    Si viene naive, se asume UTC (así se guardan logs/auditoría).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_UTC)
    return dt.astimezone(TZ_ASUNCION)


def to_asuncion_iso(dt: Optional[datetime]) -> Optional[str]:
    """ISO 8601 con offset de Asunción (ej. 2026-11-23T10:20:00-03:00)."""
    local = to_asuncion(dt)
    return local.isoformat() if local else None
