import asyncio
import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def test():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT count(*), min(fecha_vencimiento), max(fecha_vencimiento) FROM registro_habilitacion.itv_bus;"))
        print("asyncpg raw query result:", res.fetchone())

        res2 = await session.execute(text("SELECT fecha_vencimiento, count(*) FROM registro_habilitacion.itv_bus GROUP BY fecha_vencimiento ORDER BY fecha_vencimiento LIMIT 10;"))
        print("asyncpg dates sample:", res2.fetchall())

if __name__ == "__main__":
    asyncio.run(test())
