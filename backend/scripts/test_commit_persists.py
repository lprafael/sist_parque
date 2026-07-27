import psycopg2
import os

conn1 = psycopg2.connect(
    host=os.getenv("DB_HOST", "168.90.177.232"),
    port=int(os.getenv("DB_PORT", 2024)),
    user=os.getenv("DB_USER", "cid_admin_user"),
    password=os.getenv("DB_PASSWORD", "vmtdmtcidccm"),
    dbname=os.getenv("DB_NAME", "bbdd-monitoreo-cid"),
    sslmode="disable"
)
cur1 = conn1.cursor()

# Get sample bus
cur1.execute("SELECT id_bus FROM registro_habilitacion.buses LIMIT 1;")
bus_id = cur1.fetchone()[0]

print(f"Test Bus ID: {bus_id}")
cur1.execute("INSERT INTO registro_habilitacion.itv_bus (id_bus, fecha_itv, fecha_vencimiento, resultado_itv) VALUES (%s, '2026-06-01', '2026-12-01', 'TEST') RETURNING id_itv;", (bus_id,))
new_id = cur1.fetchone()[0]
print(f"Inserted row ID: {new_id} in Conn 1")
conn1.commit()
print("Conn 1 committed.")
cur1.close()
conn1.close()

# Separate Connection
conn2 = psycopg2.connect(
    host=os.getenv("DB_HOST", "168.90.177.232"),
    port=int(os.getenv("DB_PORT", 2024)),
    user=os.getenv("DB_USER", "cid_admin_user"),
    password=os.getenv("DB_PASSWORD", "vmtdmtcidccm"),
    dbname=os.getenv("DB_NAME", "bbdd-monitoreo-cid"),
    sslmode="disable"
)
cur2 = conn2.cursor()
cur2.execute("SELECT count(*), max(id_itv) FROM registro_habilitacion.itv_bus;")
print("Conn 2 Query Result:", cur2.fetchone())
cur2.close()
conn2.close()
