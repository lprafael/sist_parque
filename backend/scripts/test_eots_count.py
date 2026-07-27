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

cur.execute("SELECT count(*) FROM public.eots WHERE situacion = 1;")
total_sit_1 = cur.fetchone()[0]

cur.execute("SELECT count(*) FROM public.eots WHERE situacion = 1 AND permisionario = true;")
total_permisionarios = cur.fetchone()[0]

print(f"Empresas con situacion = 1: {total_sit_1}")
print(f"Empresas con situacion = 1 Y permisionario = true: {total_permisionarios}")

cur.close()
conn.close()
