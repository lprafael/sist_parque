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
DATA_START = 7

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

def upsert_catalogo(cur, tabla, campo, valor):
    if not valor or str(valor).strip() == "": return None
    valor = str(valor).strip()[:100]
    pk = "id_marca" if tabla == "marcas" else \
         "id_marca_carroceria" if tabla == "marcas_carroceria" else "id_tipo"
    cur.execute(f"SELECT {pk} FROM {SCHEMA}.{tabla} WHERE {campo} = %s", (valor,))
    row = cur.fetchone()
    if row: return row[0]
    cur.execute(f"INSERT INTO {SCHEMA}.{tabla} ({campo}) VALUES (%s) RETURNING {pk}", (valor,))
    return cur.fetchone()[0]

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

    stats = {"buses_updated": 0, "buses_created": 0, "itv": 0, "seguros": 0, "itv_errors": 0}

    for row_idx, row in enumerate(ws.iter_rows(min_row=DATA_START, values_only=True), start=DATA_START):
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

        # 1. Catálogos
        id_marca      = upsert_catalogo(cur, "marcas", "nombre", marca_nom)
        id_marca_carr = upsert_catalogo(cur, "marcas_carroceria", "nombre", marca_carr)
        id_tipo_carr  = None
        if tipo_carr:
            desc = str(tipo_carr).strip()[:100]
            cur.execute(f"SELECT id_tipo FROM {SCHEMA}.tipos_carroceria WHERE descripcion = %s", (desc,))
            r = cur.fetchone()
            if r: id_tipo_carr = r[0]
            else:
                cur.execute(f"INSERT INTO {SCHEMA}.tipos_carroceria (descripcion) VALUES (%s) RETURNING id_tipo", (desc,))
                id_tipo_carr = cur.fetchone()[0]

        # 2. Bus Lookup or Create
        id_bus = None
        if rua_clean and rua_clean in rua_map:
            id_bus = rua_map[rua_clean]
        elif chassis_clean and chassis_clean in chassis_map:
            id_bus = chassis_map[chassis_clean]

        if id_bus:
            cur.execute(f"""
                UPDATE {SCHEMA}.buses
                SET numero_orden=%s, id_marca=%s, año=%s, id_tipo_carroceria=%s,
                    id_marca_carroceria=%s, fecha_modificacion=NOW()
                WHERE id_bus=%s
            """, (nro_orden if isinstance(nro_orden, int) else None, id_marca, anio if isinstance(anio, int) else 2000, id_tipo_carr, id_marca_carr, id_bus))
            stats["buses_updated"] += 1
        else:
            rua_val = rua_clean or f"CHASSIS_{chassis_clean}"
            chassis_val = chassis_clean or f"RUA_{rua_clean}"
            try:
                cur.execute(f"""
                    INSERT INTO {SCHEMA}.buses
                        (numero_orden, id_marca, año, numero_chassis, rua,
                         id_tipo_carroceria, id_marca_carroceria, estado_bus)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,'ACTIVO')
                    RETURNING id_bus
                """, (nro_orden if isinstance(nro_orden, int) else None, id_marca, anio if isinstance(anio, int) else 2000, chassis_val, rua_val, id_tipo_carr, id_marca_carr))
                id_bus = cur.fetchone()[0]
                stats["buses_created"] += 1
                if rua_clean: rua_map[rua_clean] = id_bus
                if chassis_clean: chassis_map[chassis_clean] = id_bus
            except Exception as e_c:
                cur.execute(f"SELECT id_bus FROM {SCHEMA}.buses WHERE rua = %s OR numero_chassis = %s", (rua_val, chassis_val))
                rb = cur.fetchone()
                if rb: id_bus = rb[0]

        if not id_bus:
            continue

        # 3. ITV
        if venc_itv:
            sit_str = str(sit_itv).strip()[:20] if sit_itv else None
            obs_str = str(observacion).strip() if observacion else None
            try:
                cur.execute(f"""
                    INSERT INTO {SCHEMA}.itv_bus
                        (id_bus, fecha_itv, fecha_vencimiento, resultado_itv, observaciones)
                    VALUES (%s,%s,%s,%s,%s)
                """, (id_bus, fecha_itv or venc_itv, venc_itv, sit_str, obs_str))
                stats["itv"] += 1

                if itv_ant:
                    try:
                        cur.execute(f"""
                            INSERT INTO {SCHEMA}.historial_itv
                                (id_bus, fecha_vencimiento_anterior, fecha_itv_actual, fecha_vencimiento_actual)
                            VALUES (%s,%s,%s,%s)
                        """, (id_bus, itv_ant, fecha_itv or venc_itv, venc_itv))
                    except Exception:
                        pass
            except Exception as e_itv:
                stats["itv_errors"] += 1
                if stats["itv_errors"] <= 5:
                    print(f"ITV Error Row {row_idx} (RUA={rua_clean}): {e_itv}")

        # 4. Seguros
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

    print("\n--- FINAL SUMMARY V2 ---")
    print(f"Buses Updated : {stats['buses_updated']}")
    print(f"Buses Created : {stats['buses_created']}")
    print(f"ITVs Inserted : {stats['itv']}")
    print(f"ITV Errors    : {stats['itv_errors']}")
    print(f"Seguros Ins.  : {stats['seguros']}")

    cur.execute(f"SELECT count(*) FROM {SCHEMA}.itv_bus;")
    print(f"Final Count in itv_bus: {cur.fetchone()[0]}")
    cur.execute(f"SELECT count(*) FROM {SCHEMA}.seguros_bus;")
    print(f"Final Count in seguros_bus: {cur.fetchone()[0]}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
