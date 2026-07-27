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

try:
    print("Executing DELETE FROM registro_habilitacion.itv_bus WHERE id_bus = 2482...")
    cur.execute("DELETE FROM registro_habilitacion.itv_bus WHERE id_bus = 2482;")
    print("Deleted rows count:", cur.rowcount)
    
    print("Executing INSERT INTO registro_habilitacion.itv_bus (id_bus, fecha_itv, fecha_vencimiento, resultado_itv) VALUES (2482, '2026-06-17', '2026-10-17', 'TOTAL')...")
    cur.execute("INSERT INTO registro_habilitacion.itv_bus (id_bus, fecha_itv, fecha_vencimiento, resultado_itv) VALUES (2482, '2026-06-17', '2026-10-17', 'TOTAL');")
    conn.commit()
    print("Commit successful!")
    
    cur.execute("SELECT * FROM registro_habilitacion.itv_bus WHERE id_bus = 2482;")
    print("After commit:", cur.fetchall())
except Exception as e:
    print("ERROR:", e)
    conn.rollback()

cur.close()
conn.close()
