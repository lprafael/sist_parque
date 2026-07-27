import asyncio
import os
import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.models import Bus, ItvBus
from sqlalchemy import select, func, and_

async def inspect_db():
    async with AsyncSessionLocal() as db:
        total_buses = (await db.execute(select(func.count()).select_from(Bus))).scalar()
        total_itv = (await db.execute(select(func.count()).select_from(ItvBus))).scalar()
        
        hoy = date.today()
        en_30 = hoy + timedelta(days=30)

        itv_vigente = (await db.execute(select(func.count()).select_from(ItvBus).where(ItvBus.fecha_vencimiento > en_30))).scalar()
        itv_por_vencer = (await db.execute(select(func.count()).select_from(ItvBus).where(
            and_(ItvBus.fecha_vencimiento >= hoy, ItvBus.fecha_vencimiento <= en_30)
        ))).scalar()
        itv_vencido = (await db.execute(select(func.count()).select_from(ItvBus).where(ItvBus.fecha_vencimiento < hoy))).scalar()

        print(f"Total Buses en DB: {total_buses}")
        print(f"Total Registros ITV en DB: {total_itv}")
        print(f"ITV Vigentes: {itv_vigente}")
        print(f"ITV Por Vencer (30d): {itv_por_vencer}")
        print(f"ITV Vencidos (< {hoy}): {itv_vencido}")

        # Sample 10 ITV rows
        res = await db.execute(select(ItvBus).limit(10))
        sample = res.scalars().all()
        print("\nMuestra 10 registros itv_bus:")
        for i in sample:
            print(f"  ID: {i.id_itv}, Bus: {i.id_bus}, Fecha ITV: {i.fecha_itv}, Vencimiento: {i.fecha_vencimiento}, Resultado: {i.resultado_itv}")

if __name__ == "__main__":
    asyncio.run(inspect_db())
