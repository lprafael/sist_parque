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

# Buses con ITV en itv_bus son los 1.865 buses activos de la planilla oficial
cur.execute("""
    UPDATE registro_habilitacion.buses 
    SET estado_bus = 'INACTIVO' 
    WHERE id_bus NOT IN (SELECT id_bus FROM registro_habilitacion.itv_bus);
""")
print("Buses no presentes en la planilla oficial marcados como INACTIVO:", cur.rowcount)

cur.execute("""
    UPDATE registro_habilitacion.buses 
    SET estado_bus = 'ACTIVO' 
    WHERE id_bus IN (SELECT id_bus FROM registro_habilitacion.itv_bus);
""")
print("Buses de la planilla oficial marcados como ACTIVO:", cur.rowcount)

cur.execute("SELECT estado_bus, count(*) FROM registro_habilitacion.buses GROUP BY estado_bus;")
print("\nResumen final de estado_bus en DB:")
for r in cur.fetchall():
    print(" ", r)

cur.close()
conn.close()
