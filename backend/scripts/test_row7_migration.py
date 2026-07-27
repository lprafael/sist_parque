import psycopg2
import openpyxl
import os
from datetime import datetime, date

wb = openpyxl.load_workbook("excel.xlsx", data_only=True)
ws = wb["General"]

row = [ws.cell(row=7, column=c).value for c in range(1, 20)]

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "168.90.177.232"),
    port=int(os.getenv("DB_PORT", 2024)),
    user=os.getenv("DB_USER", "cid_admin_user"),
    password=os.getenv("DB_PASSWORD", "vmtdmtcidccm"),
    dbname=os.getenv("DB_NAME", "bbdd-monitoreo-cid"),
    sslmode="disable"
)
cur = conn.cursor()

def parse_date(val):
    if val is None: return None
    if isinstance(val, (date, datetime)): return val.date() if isinstance(val, datetime) else val
    return None

try:
    print("Testing Row 7 migration step-by-step...")
    id_bus = 2037
    fecha_itv = parse_date(row[14])
    venc_itv = parse_date(row[15])
    itv_ant = parse_date(row[13])
    sit_itv = row[16]
    observacion = row[18]
    seg_pas = parse_date(row[8])
    seg_ter = parse_date(row[9])

    print("Step 1: Insert ITV...")
    sit_str = str(sit_itv).strip()[:20] if sit_itv else None
    obs_str = str(observacion).strip() if observacion else None
    cur.execute("INSERT INTO registro_habilitacion.itv_bus (id_bus, fecha_itv, fecha_vencimiento, resultado_itv, observaciones) VALUES (%s,%s,%s,%s,%s)", (id_bus, fecha_itv or venc_itv, venc_itv, sit_str, obs_str))
    print("Step 1 OK")

    print("Step 2: Insert Historial...")
    if itv_ant:
        cur.execute("INSERT INTO registro_habilitacion.historial_itv (id_bus, fecha_vencimiento_anterior, fecha_itv_actual, fecha_vencimiento_actual) VALUES (%s,%s,%s,%s)", (id_bus, itv_ant, fecha_itv or venc_itv, venc_itv))
    print("Step 2 OK")

    print("Step 3: Insert Seguros...")
    for tipo, fecha_venc in [("PASAJEROS", seg_pas), ("TERCEROS", seg_ter)]:
        if fecha_venc:
            cur.execute("INSERT INTO registro_habilitacion.seguros_bus (id_bus, tipo_seguro, fecha_inicio, fecha_vencimiento, estado_seguro) VALUES (%s,%s,%s,%s,'VIGENTE')", (id_bus, tipo, date.today(), fecha_venc))
    print("Step 3 OK")

    conn.commit()
    print("ALL STEPS OK & COMMITTED!")
except Exception as e:
    print("TEST FAILED WITH ERROR:", e)
    conn.rollback()

cur.close()
conn.close()
