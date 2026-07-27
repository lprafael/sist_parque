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
total_itv = cur.fetchone()[0]

cur.execute("SELECT count(*) FROM registro_habilitacion.buses;")
total_buses = cur.fetchone()[0]

print(f"Total Buses en DB: {total_buses}")
print(f"Total Registros ITV en DB: {total_itv}")

cur.execute("SELECT b.id_bus, b.rua, i.fecha_itv, i.fecha_vencimiento FROM registro_habilitacion.buses b LEFT JOIN registro_habilitacion.itv_bus i ON b.id_bus = i.id_bus LIMIT 15;")
print("\nMuestra 15 buses con sus ITVs:")
for r in cur.fetchall():
    print(" ", r)

cur.close()
conn.close()
