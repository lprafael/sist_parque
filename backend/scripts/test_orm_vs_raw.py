import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.models import ItvBus, Bus, SeguroBus
from sqlalchemy import select, func, text

async def main():
    async with AsyncSessionLocal() as db:
        cnt_itv_orm = (await db.execute(select(func.count()).select_from(ItvBus))).scalar()
        print("ORM count ItvBus:", cnt_itv_orm)

        cnt_itv_raw = (await db.execute(text("SELECT count(*) FROM registro_habilitacion.itv_bus"))).scalar()
        print("RAW SQL count itv_bus:", cnt_itv_raw)

        cnt_seg_orm = (await db.execute(select(func.count()).select_from(SeguroBus))).scalar()
        print("ORM count SeguroBus:", cnt_seg_orm)

        cnt_seg_raw = (await db.execute(text("SELECT count(*) FROM registro_habilitacion.seguros_bus"))).scalar()
        print("RAW SQL count seguros_bus:", cnt_seg_raw)

if __name__ == "__main__":
    asyncio.run(main())
