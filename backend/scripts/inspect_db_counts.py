import asyncio
import os
import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.models import Bus, ItvBus, SeguroBus
from sqlalchemy import select, func, and_

async def inspect():
    async with AsyncSessionLocal() as db:
        buses_cnt = (await db.execute(select(func.count()).select_from(Bus))).scalar()
        itv_cnt = (await db.execute(select(func.count()).select_from(ItvBus))).scalar()
        seguros_cnt = (await db.execute(select(func.count()).select_from(SeguroBus))).scalar()

        print(f"Total Buses: {buses_cnt}")
        print(f"Total Registros ITV: {itv_cnt}")
        print(f"Total Seguros: {seguros_cnt}")

        # Check year distribution of fecha_vencimiento in ItvBus
        res = await db.execute(select(ItvBus.fecha_vencimiento))
        dates = res.scalars().all()
        
        years = {}
        vencidos = 0
        vigentes = 0
        hoy = date.today()

        for d in dates:
            if d:
                yr = d.year
                years[yr] = years.get(yr, 0) + 1
                if d < hoy:
                    vencidos += 1
                else:
                    vigentes += 1

        print(f"\nDistribución por año en DB (itv_bus.fecha_vencimiento):")
        for yr, c in sorted(years.items()):
            print(f"  Año {yr}: {c} registros")
        print(f"\nResumen para la fecha de hoy ({hoy}):")
        print(f"  ITV Vencidos (< {hoy}): {vencidos}")
        print(f"  ITV Vigentes (>= {hoy}): {vigentes}")

if __name__ == "__main__":
    asyncio.run(inspect())
