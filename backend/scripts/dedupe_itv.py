"""Elimina ITV duplicadas: misma (id_bus, fecha_itv, fecha_vencimiento).

Conserva la fila más antigua; si el grupo tenía alguna vigente, la conservada queda vigente.
"""
from __future__ import annotations

import asyncio
import os
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import delete, select

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.chdir(Path(__file__).resolve().parents[1])

from app.core.database import AsyncSessionLocal
from app.models import Bus, ItvBus


async def main():
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(ItvBus).where(
                    ItvBus.fecha_itv.is_not(None),
                    ItvBus.fecha_vencimiento.is_not(None),
                )
            )
        ).scalars().all()

        groups: dict[tuple, list[ItvBus]] = defaultdict(list)
        for r in rows:
            groups[(r.id_bus, r.fecha_itv, r.fecha_vencimiento)].append(r)

        to_delete: list[int] = []
        vigentes_ajustadas = 0
        grupos = 0
        for _, items in groups.items():
            if len(items) < 2:
                continue
            grupos += 1
            items.sort(
                key=lambda x: (
                    x.fecha_registro is None,
                    x.fecha_registro or x.fecha_itv,
                    x.id_itv,
                )
            )
            keep = items[0]
            any_vig = any(bool(i.es_vigente) for i in items)
            if any_vig and not keep.es_vigente:
                keep.es_vigente = True
                vigentes_ajustadas += 1
            for extra in items[1:]:
                if extra.resultado_itv and not keep.resultado_itv:
                    keep.resultado_itv = extra.resultado_itv
                if extra.centro_itv and not keep.centro_itv:
                    keep.centro_itv = extra.centro_itv
                to_delete.append(extra.id_itv)

        print(f"Grupos duplicados: {grupos}")
        print(f"A eliminar: {len(to_delete)}")
        if not to_delete:
            return

        await db.execute(delete(ItvBus).where(ItvBus.id_itv.in_(to_delete)))
        await db.commit()
        print(f"Eliminadas: {len(to_delete)} · Vigentes ajustadas: {vigentes_ajustadas}")

        bus = (
            await db.execute(select(Bus).where(Bus.rua == "BOO996"))
        ).scalar_one_or_none()
        if bus:
            itvs = (
                await db.execute(
                    select(ItvBus)
                    .where(ItvBus.id_bus == bus.id_bus)
                    .order_by(ItvBus.fecha_registro.desc())
                )
            ).scalars().all()
            print(f"BOO996 queda con {len(itvs)} ITV:")
            for i in itvs:
                print(
                    f"  id={i.id_itv} itv={i.fecha_itv} venc={i.fecha_vencimiento} "
                    f"vigente={i.es_vigente} reg={i.fecha_registro}"
                )


if __name__ == "__main__":
    asyncio.run(main())
