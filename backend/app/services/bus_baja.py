"""Baja formal de un bus: estado BAJA + cierra asignación + invalida ITV.

Misma semántica que la hoja BAJAS del importador. El flujo de /buses
agrega causal, normativa y auditoría; el importador sigue llamando
sin enriquecer observaciones para no cambiar su comportamiento.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bus, BusEmpresa, ItvBus
from app.services.sistema_logs import registrar_auditoria

CAUSALES_BAJA = (
    "ANTIGUEDAD_20",
    "SOLICITUD_EMPRESA",
    "ACCIDENTE",
    "INCENDIO",
    "ITV_VENCIDA",
    "RESOLUCION",
    "OTRO",
)

CAUSAL_LABEL = {
    "ANTIGUEDAD_20": "Antigüedad +20 años",
    "SOLICITUD_EMPRESA": "Solicitud de la empresa",
    "ACCIDENTE": "Accidente / siniestro",
    "INCENDIO": "Incendio",
    "ITV_VENCIDA": "ITV vencida",
    "RESOLUCION": "Resolución / MEU",
    "OTRO": "Otro",
}


def _nota_formal(
    *,
    causal: Optional[str],
    observaciones: Optional[str],
    usuario: Optional[str],
) -> str:
    partes: list[str] = ["BAJA FORMAL"]
    if causal:
        partes.append(f"causal={CAUSAL_LABEL.get(causal, causal)}")
    if observaciones and observaciones.strip():
        partes.append(observaciones.strip())
    if usuario:
        partes.append(f"[cierre por {usuario}]")
    return " | ".join(partes)


async def aplicar_baja_buses(
    db: AsyncSession,
    buses: list[Bus],
    *,
    fecha_baja: date,
    motivo_asignacion: str = "BAJA",
    causal: Optional[str] = None,
    normativa: Optional[str] = None,
    observaciones: Optional[str] = None,
    usuario: Optional[str] = None,
    enriquecer_asig: bool = False,
    auditar: bool = False,
) -> dict:
    """Pasa buses a BAJA, cierra asignación vigente e invalida ITV vigente.

    Omite los que ya están en BAJA. No crea asignación si no había una.
    """
    candidatos = [b for b in buses if (b.estado_bus or "").upper() != "BAJA"]
    if not candidatos:
        return {
            "buses_baja": 0,
            "asignaciones_cerradas": 0,
            "itv_invalidadas": 0,
            "ids": [],
        }

    id_set = {b.id_bus for b in candidatos}
    previos = {b.id_bus: b.estado_bus for b in candidatos}
    for b in candidatos:
        b.estado_bus = "BAJA"

    asig_res = await db.execute(
        select(BusEmpresa).where(
            BusEmpresa.id_bus.in_(id_set),
            BusEmpresa.fecha_fin_asignacion.is_(None),
        )
    )
    asignaciones = list(asig_res.scalars().all())
    nota = _nota_formal(causal=causal, observaciones=observaciones, usuario=usuario) if enriquecer_asig else None
    for asig in asignaciones:
        asig.fecha_fin_asignacion = fecha_baja
        asig.estado_asignacion = "CERRADA"
        if not asig.motivo or enriquecer_asig:
            asig.motivo = motivo_asignacion
        if enriquecer_asig and normativa:
            asig.normativa = normativa
        if nota:
            asig.observaciones = (
                f"{asig.observaciones}\n{nota}" if asig.observaciones else nota
            )

    itv_res = await db.execute(
        select(ItvBus).where(ItvBus.id_bus.in_(id_set), ItvBus.es_vigente.is_(True))
    )
    itvs = list(itv_res.scalars().all())
    for itv in itvs:
        itv.es_vigente = False

    if auditar and usuario:
        for b in candidatos:
            await registrar_auditoria(
                db,
                accion="update",
                tabla="buses",
                usuario=usuario,
                registro_id=b.id_bus,
                datos_anteriores={"estado_bus": previos.get(b.id_bus)},
                datos_nuevos={
                    "estado_bus": "BAJA",
                    "fecha_baja": fecha_baja.isoformat(),
                    "causal": causal,
                    "normativa": normativa,
                    "observaciones": observaciones,
                    "asignacion_cerrada": any(a.id_bus == b.id_bus for a in asignaciones),
                    "itv_invalidadas": sum(1 for i in itvs if i.id_bus == b.id_bus),
                },
                detalles=f"Baja formal de bus id={b.id_bus} causal={causal}",
            )

    return {
        "buses_baja": len(candidatos),
        "asignaciones_cerradas": len(asignaciones),
        "itv_invalidadas": len(itvs),
        "ids": sorted(id_set),
    }
