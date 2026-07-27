import psycopg2
import os
from datetime import date

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "168.90.177.232"),
    port=int(os.getenv("DB_PORT", 2024)),
    user=os.getenv("DB_USER", "cid_admin_user"),
    password=os.getenv("DB_PASSWORD", "vmtdmtcidccm"),
    dbname=os.getenv("DB_NAME", "bbdd-monitoreo-cid"),
    sslmode="disable"
)
cur = conn.cursor()

cur.execute("""
    SELECT año, count(*) 
    FROM registro_habilitacion.buses 
    WHERE estado_bus = 'ACTIVO' AND año IS NOT NULL AND año > 1970
    GROUP BY año 
    ORDER BY año ASC;
""")
rows = cur.fetchall()

current_year = date.today().year

print("Distribución de buses por año y antigüedad:")
total_buses = 0
total_edad = 0

for anio, cnt in rows:
    antiguedad = current_year - anio
    total_buses += cnt
    total_edad += (antiguedad * cnt)
    print(f"  Año {anio} ({antiguedad} años de antigüedad): {cnt} buses")

promedio = total_edad / total_buses if total_buses > 0 else 0
print(f"\nEdad promedio del parque automotor: {promedio:.1f} años ({total_buses} buses analizados)")

cur.close()
conn.close()
