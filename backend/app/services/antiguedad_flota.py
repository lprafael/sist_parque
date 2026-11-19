"""Reglas de antigüedad de flota (Resolución GVMT N° 145/2026)."""
from __future__ import annotations

from datetime import date
from typing import Optional

# Art. 2°: no corresponde alta de unidades nuevas con más de 20 años.
TOPE_ANTIGUEDAD_ALTA_ANIOS = 20
RESOLUCION_GVMT_145 = "Resolución GVMT N° 145/2026 Art. 2°"


def antiguedad_anios(anio_fabricacion: int, anio_ref: Optional[int] = None) -> int:
    return (anio_ref or date.today().year) - int(anio_fabricacion)


def supera_tope_alta(anio_fabricacion: int, anio_ref: Optional[int] = None) -> bool:
    """True si la unidad supera el tope de 20 años para altas nuevas."""
    return antiguedad_anios(anio_fabricacion, anio_ref) > TOPE_ANTIGUEDAD_ALTA_ANIOS


def mensaje_alerta_alta(anio_fabricacion: int, anio_ref: Optional[int] = None) -> str:
    edad = antiguedad_anios(anio_fabricacion, anio_ref)
    return (
        f"Según {RESOLUCION_GVMT_145}, no corresponde el alta de unidades nuevas "
        f"con más de {TOPE_ANTIGUEDAD_ALTA_ANIOS} años de antigüedad. "
        f"Esta unidad tiene {edad} años (año/modelo {anio_fabricacion}). "
        "Si continúa, lo hace bajo su responsabilidad; confirme con "
        "confirmacion_antiguedad=true."
    )
