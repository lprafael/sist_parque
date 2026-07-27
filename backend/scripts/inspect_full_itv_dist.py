import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "168.90.177.232"),
    port=int(os.getenv("DB_PORT", 2024)),
    user=os.getenv("DB_USER", "cid_admin_user"),
    password=os.getenv("DB_PASSWORD", "vmtdmtcidccm"),
    dbname=os.getenv("DB_NAME", "bbdd-monitoreo-cid"),
    sslmode="disable"
)
cur = conn.cursor()

cur.execute("SELECT count(*) FROM registro_habilitacion.itv_bus;")
print("Total rows in itv_bus:", cur.fetchone()[0])

cur.execute("SELECT extract(year from fecha_vencimiento) as yr, extract(month from fecha_vencimiento) as mo, count(*) FROM registro_habilitacion.itv_bus GROUP BY yr, mo ORDER BY yr, mo;")
print("Distribution by Year-Month in itv_bus:")
for r in cur.fetchall():
    print(f"  Año {int(r[0])} Mes {int(r[1]):02d}: {r[2]} buses")

cur.close()
conn.close()
