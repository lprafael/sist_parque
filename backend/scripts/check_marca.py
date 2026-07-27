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
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_schema = 'registro_habilitacion' AND table_name = 'marca';
""")
print("Marca table columns:")
print(cur.fetchall())

cur.execute("""
    SELECT m.descripcion, count(b.id_bus) 
    FROM registro_habilitacion.buses b
    JOIN registro_habilitacion.marca m ON b.id_marca = m.id_marca
    WHERE b.estado_bus = 'ACTIVO'
    GROUP BY m.descripcion
    ORDER BY count(b.id_bus) DESC
    LIMIT 10;
""")
print("\nTop marcas in buses:")
print(cur.fetchall())
cur.close()
conn.close()
