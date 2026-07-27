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

# Distribución de buses por Tipo de Servicio desde la tabla auxiliar
cur.execute("""
    SELECT "Tipo de Servicio", count(*)
    FROM registro_habilitacion.auxiliar
    WHERE "Tipo de Servicio" IS NOT NULL AND "Tipo de Servicio" != ''
    GROUP BY "Tipo de Servicio"
    ORDER BY count(*) DESC;
""")
print("Distribución de buses por Tipo de Servicio:")
for row in cur.fetchall():
    print(" ", row)

cur.close()
conn.close()
