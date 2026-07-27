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

cur.execute("SELECT count(*), min(fecha_vencimiento), max(fecha_vencimiento) FROM registro_habilitacion.itv_bus;")
print("itv_bus:", cur.fetchone())

cur.execute("SELECT count(*), min(fecha_vencimiento), max(fecha_vencimiento) FROM registro_habilitacion.seguros_bus;")
print("seguros_bus:", cur.fetchone())

cur.execute("SELECT count(*) FROM registro_habilitacion.buses;")
print("buses count:", cur.fetchone())

cur.execute("SELECT fecha_vencimiento, count(*) FROM registro_habilitacion.itv_bus GROUP BY fecha_vencimiento ORDER BY fecha_vencimiento LIMIT 20;")
print("First 20 vencimiento dates in itv_bus:", cur.fetchall())

cur.close()
conn.close()
