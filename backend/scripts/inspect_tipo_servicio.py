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

# Buscar columnas con "tipo" o "servicio" en todas las tablas de registro_habilitacion
cur.execute("""
    SELECT table_schema, table_name, column_name, data_type
    FROM information_schema.columns
    WHERE column_name ILIKE '%tipo%servicio%' OR column_name ILIKE '%servicio%'
    ORDER BY table_schema, table_name, column_name;
""")
print("Columnas con 'servicio':")
for row in cur.fetchall():
    print(" ", row)

# También buscar en la tabla de buses del auxiliar o buses
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'registro_habilitacion' AND table_name = 'auxiliar'
    ORDER BY ordinal_position;
""")
print("\nColumnas de registro_habilitacion.auxiliar:")
for row in cur.fetchall():
    print(" ", row)

# Verificar en public.eots
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'eots'
    ORDER BY ordinal_position;
""")
print("\nColumnas de public.eots:")
for row in cur.fetchall():
    print(" ", row)

cur.close()
conn.close()
