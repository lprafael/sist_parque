import sys
import os
from datetime import date, datetime
from pathlib import Path

import psycopg2
import openpyxl
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "168.90.177.232"),
    "port":     int(os.getenv("DB_PORT", 2024)),
    "user":     os.getenv("DB_USER", "cid_admin_user"),
    "password": os.getenv("DB_PASSWORD", "vmtdmtcidccm"),
    "dbname":   os.getenv("DB_NAME", "bbdd-monitoreo-cid"),
    "sslmode":  "disable",
}
SCHEMA = "registro_habilitacion"

def parse_date(val):
    if val is None: return None
    if isinstance(val, (date, datetime)): return val.date() if isinstance(val, datetime) else val
    if isinstance(val, str):
        val = val.strip()
        if val in ("00/00/00", "", "N/A", "-", "None"): return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
            try: return datetime.strptime(val, fmt).date()
            except ValueError: continue
    return None

def main():
    excel_path = "excel.xlsx"
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb["General"]

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    print("Limpiando itv_bus, seguros_bus e historial_itv antes de importar...")
    cur.execute(f"DELETE FROM {SCHEMA}.itv_bus;")
    cur.execute(f"DELETE FROM {SCHEMA}.seguros_bus;")
    cur.execute(f"DELETE FROM {SCHEMA}.historial_itv;")

    # Pre-cargar mapa de RUAs y Chasis de la base de datos
    cur.execute(f"SELECT id_bus, rua, numero_chassis FROM {SCHEMA}.buses;")
    db_buses = cur.fetchall()
    
    rua_map = {}
    chassis_map = {}
    for id_b, rua_b, ch_b in db_buses:
        if rua_b: rua_map[str(rua_b).strip().upper()] = id_b
        if ch_b: chassis_map[str(ch_b).strip().upper()] = id_b

    stats = {"itv": 0, "seguros": 0, "errors": 0}

    # Recorrer exactamente las 1868 filas de buses (filas 7 a 1874)
    for row_idx in range(7, 1875):
        row = [ws.cell(row=row_idx, column=c).value for c in range(1, 20)]
        nro_orden    = row[0]
        marca_nom    = row[1]
        anio         = row[2]
        chassis      = row[3]
        rua          = row[4]
        seg_pas      = parse_date(row[8])
        seg_ter      = parse_date(row[9])
        tipo_carr    = row[11]
        marca_carr   = row[12]
        itv_ant      = parse_date(row[13])
        fecha_itv    = parse_date(row[14])
        venc_itv     = parse_date(row[15])
        sit_itv      = row[16]
        observacion  = row[18]

        rua_clean = str(rua).strip().upper() if rua else None
        chassis_clean = str(chassis).strip().upper() if chassis else None

        if not rua_clean and not chassis_clean:
            continue

        # 1. Bus Lookup or Create
        id_bus = None
        if rua_clean and rua_clean in rua_map:
            id_bus = rua_map[rua_clean]
        elif chassis_clean and chassis_clean in chassis_map:
            id_bus = chassis_map[chassis_clean]

        if not id_bus:
            rua_val = rua_clean or f"CHASSIS_{chassis_clean}"
            chassis_val = chassis_clean or f"RUA_{rua_clean}"
            try:
                cur.execute(f"""
                    INSERT INTO {SCHEMA}.buses (numero_orden, año, numero_chassis, rua, estado_bus)
                    VALUES (%s,%s,%s,%s,'ACTIVO')
                    RETURNING id_bus
                """, (nro_orden if isinstance(nro_orden, int) else None, anio if isinstance(anio, int) else 2000, chassis_val, rua_val))
                id_bus = cur.fetchone()[0]
                if rua_clean: rua_map[rua_clean] = id_bus
                if chassis_clean: chassis_map[chassis_clean] = id_bus
            except Exception as eb:
                cur.execute(f"SELECT id_bus FROM {SCHEMA}.buses WHERE rua = %s OR numero_chassis = %s", (rua_val, chassis_val))
                rb = cur.fetchone()
                if rb: id_bus = rb[0]

        if not id_bus:
            print(f"Row {row_idx}: could not find/create bus RUA={rua_clean}")
            continue

        # 2. ITV Bus — Upsert
        if venc_itv:
            sit_str = str(sit_itv).strip()[:20] if sit_itv else None
            obs_str = str(observacion).strip() if observacion else None
            try:
                cur.execute(f"""
                    INSERT INTO {SCHEMA}.itv_bus
                        (id_bus, fecha_itv, fecha_vencimiento, resultado_itv, observaciones)
                    VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT (id_bus) DO UPDATE SET
                        fecha_itv = EXCLUDED.fecha_itv,
                        fecha_vencimiento = EXCLUDED.fecha_vencimiento,
                        resultado_itv = EXCLUDED.resultado_itv,
                        observaciones = EXCLUDED.observaciones
                """, (id_bus, fecha_itv or venc_itv, venc_itv, sit_str, obs_str))
                stats["itv"] += 1
            except Exception as e_itv:
                stats["errors"] += 1
                print(f"Row {row_idx} ITV Error (RUA={rua_clean}, id_bus={id_bus}): {e_itv}")

        # 3. Seguros Bus
        for tipo, fecha_venc in [("PASAJEROS", seg_pas), ("TERCEROS", seg_ter)]:
            if fecha_venc:
                try:
                    cur.execute(f"""
                        INSERT INTO {SCHEMA}.seguros_bus
                            (id_bus, tipo_seguro, fecha_inicio, fecha_vencimiento, estado_seguro)
                        VALUES (%s,%s,%s,%s,'VIGENTE')
                    """, (id_bus, tipo, date.today(), fecha_venc))
                    stats["seguros"] += 1
                except Exception:
                    pass

    print("\n--- FINAL SUMMARY V4 ---")
    print(f"ITVs Processed : {stats['itv']}")
    print(f"Seguros Ins.   : {stats['seguros']}")
    print(f"Errors         : {stats['errors']}")

    cur.execute(f"SELECT count(*) FROM {SCHEMA}.itv_bus;")
    print(f"Verification DB count (itv_bus): {cur.fetchone()[0]}")
    cur.execute(f"SELECT count(*) FROM {SCHEMA}.seguros_bus;")
    print(f"Verification DB count (seguros_bus): {cur.fetchone()[0]}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
