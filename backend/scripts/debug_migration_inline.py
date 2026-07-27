import openpyxl
import psycopg2
import os
from datetime import date, datetime

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "168.90.177.232"),
    "port":     int(os.getenv("DB_PORT", 2024)),
    "user":     os.getenv("DB_USER", "cid_admin_user"),
    "password": os.getenv("DB_PASSWORD", "vmtdmtcidccm"),
    "dbname":   os.getenv("DB_NAME", "bbdd-monitoreo-cid"),
    "sslmode":  "disable",
}
SCHEMA = "registro_habilitacion"

conn = psycopg2.connect(**DB_CONFIG)
conn.autocommit = False
cur = conn.cursor()

def parse_date(val):
    if val is None: return None
    if isinstance(val, (date, datetime)): return val.date() if isinstance(val, datetime) else val
    return None

wb = openpyxl.load_workbook("excel.xlsx", data_only=True)
ws = wb["General"]

print("Running DEBUG migration on 10 rows...")
for r in range(7, 17):
    row = [ws.cell(row=r, column=c).value for c in range(1, 20)]
    rua = row[4]
    chassis = row[3]
    venc_itv = parse_date(row[15])
    fecha_itv = parse_date(row[14])
    sit_itv = row[16]
    
    rua_clean = str(rua).strip().upper() if rua else f"CHASSIS_{chassis}"
    
    # 1. Bus ID
    cur.execute(f"SELECT id_bus FROM {SCHEMA}.buses WHERE rua = %s", (rua_clean,))
    res = cur.fetchone()
    id_bus = res[0] if res else None
    
    print(f"Row {r} (RUA={rua_clean}): id_bus={id_bus}, venc_itv={venc_itv}")
    
    if id_bus and venc_itv:
        sit_str = str(sit_itv).strip()[:20] if sit_itv else None
        print(f"  Executing INSERT INTO {SCHEMA}.itv_bus (id_bus={id_bus}, venc={venc_itv})...")
        cur.execute(f"""
            INSERT INTO {SCHEMA}.itv_bus
                (id_bus, fecha_itv, fecha_vencimiento, resultado_itv)
            VALUES (%s,%s,%s,%s)
        """, (id_bus, fecha_itv or venc_itv, venc_itv, sit_str))
        print("  Insert executed. Rowcount:", cur.rowcount)
        
        for tipo, fecha_venc in [("PASAJEROS", parse_date(row[8])), ("TERCEROS", parse_date(row[9]))]:
            if fecha_venc:
                cur.execute(f"""
                    INSERT INTO {SCHEMA}.seguros_bus
                        (id_bus, tipo_seguro, fecha_inicio, fecha_vencimiento, estado_seguro)
                    VALUES (%s,%s,%s,%s,'VIGENTE')
                """, (id_bus, tipo, date.today(), fecha_venc))

conn.commit()
print("COMMITTED!")

cur.execute(f"SELECT count(*) FROM {SCHEMA}.itv_bus;")
print("Count in itv_bus after commit:", cur.fetchone()[0])

cur.execute(f"SELECT count(*) FROM {SCHEMA}.seguros_bus;")
print("Count in seguros_bus after commit:", cur.fetchone()[0])

cur.close()
conn.close()
