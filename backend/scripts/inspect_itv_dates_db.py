import psycopg2
import os
from datetime import date, timedelta

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "168.90.177.232"),
    port=int(os.getenv("DB_PORT", 2024)),
    user=os.getenv("DB_USER", "cid_admin_user"),
    password=os.getenv("DB_PASSWORD", "vmtdmtcidccm"),
    dbname=os.getenv("DB_NAME", "bbdd-monitoreo-cid"),
    sslmode="disable"
)
cur = conn.cursor()

hoy = date(2026, 7, 24)
en_30 = hoy + timedelta(days=30)

cur.execute("SELECT count(*) FROM registro_habilitacion.itv_bus;")
print("Total rows in itv_bus:", cur.fetchone()[0])

cur.execute("SELECT count(*) FROM registro_habilitacion.itv_bus WHERE fecha_vencimiento > %s;", (en_30,))
print("fecha_vencimiento > en_30 (after 2026-08-23):", cur.fetchone()[0])

cur.execute("SELECT count(*) FROM registro_habilitacion.itv_bus WHERE fecha_vencimiento >= %s AND fecha_vencimiento <= %s;", (hoy, en_30))
print("fecha_vencimiento between hoy and en_30:", cur.fetchone()[0])

cur.execute("SELECT count(*) FROM registro_habilitacion.itv_bus WHERE fecha_vencimiento < %s;", (hoy,))
print("fecha_vencimiento < hoy (before 2026-07-24):", cur.fetchone()[0])

cur.execute("SELECT min(fecha_vencimiento), max(fecha_vencimiento) FROM registro_habilitacion.itv_bus;")
print("Min/Max fecha_vencimiento in itv_bus:", cur.fetchone())

cur.execute("SELECT extract(year from fecha_vencimiento) as yr, extract(month from fecha_vencimiento) as mo, count(*) FROM registro_habilitacion.itv_bus GROUP BY yr, mo ORDER BY yr, mo;")
print("\nDistribution by Year-Month:")
for r in cur.fetchall():
    print(f"  Year {int(r[0])} Month {int(r[1])}: {r[2]} buses")

cur.close()
conn.close()
