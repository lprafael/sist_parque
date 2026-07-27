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
conn.autocommit = True
cur = conn.cursor()

print("Eliminando referencias en tablas dependientes (alertas, seguros_bus, historial_itv, bus_empresa, etc.)...")
cur.execute("DELETE FROM registro_habilitacion.alertas WHERE id_bus NOT IN (SELECT id_bus FROM registro_habilitacion.itv_bus);")
cur.execute("DELETE FROM registro_habilitacion.seguros_bus WHERE id_bus NOT IN (SELECT id_bus FROM registro_habilitacion.itv_bus);")
cur.execute("DELETE FROM registro_habilitacion.historial_itv WHERE id_bus NOT IN (SELECT id_bus FROM registro_habilitacion.itv_bus);")
cur.execute("DELETE FROM registro_habilitacion.bus_empresa WHERE id_bus NOT IN (SELECT id_bus FROM registro_habilitacion.itv_bus);")

print("Eliminando buses que no están en la planilla oficial 2026...")
cur.execute("DELETE FROM registro_habilitacion.buses WHERE id_bus NOT IN (SELECT id_bus FROM registro_habilitacion.itv_bus);")
deleted_count = cur.rowcount
print(f"Buses huerfanos/obsoletos eliminados: {deleted_count}")

cur.execute("SELECT count(*) FROM registro_habilitacion.buses;")
total_buses = cur.fetchone()[0]
print(f"Total Buses en DB despues de la purga: {total_buses}")

cur.close()
conn.close()
