import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.api.v1.endpoints.dashboard import distribucion_antiguedad_buses

async def main():
    async with AsyncSessionLocal() as db:
        res = await distribucion_antiguedad_buses(db=db, _=None)
        print("--- ENDPOINT /distribucion-antiguedad RESULT ---")
        print(f"Edad Promedio: {res['promedio_edad']} años")
        print(f"Total Buses Analizados: {res['total_buses']}")
        print(f"Total Categorías de Edad: {len(res['items'])}")
        print("\nMuestra 5 items:")
        for it in res['items'][:5]:
            print(" ", it)

if __name__ == "__main__":
    asyncio.run(main())
