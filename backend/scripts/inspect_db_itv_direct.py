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
print("Total rows in registro_habilitacion.itv_bus:", cur.fetchone()[0])

cur.execute("SELECT count(*) FROM registro_habilitacion.buses;")
print("Total rows in registro_habilitacion.buses:", cur.fetchone()[0])

cur.execute("SELECT count(*) FROM registro_habilitacion.seguros_bus;")
print("Total rows in registro_habilitacion.seguros_bus:", cur.fetchone()[0])

cur.execute("SELECT fecha_vencimiento, count(*) FROM registro_habilitacion.itv_bus GROUP BY fecha_vencimiento ORDER BY count(*) DESC LIMIT 15;")
print("\nTop 15 fecha_vencimiento in itv_bus:")
for r in cur.fetchall():
    print(" ", r)

cur.close()
conn.close()
