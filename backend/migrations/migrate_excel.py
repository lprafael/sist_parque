"""
Script de migración robusta e independiente por registro (ITV Excel → PostgreSQL)
"""
import sys
import os
import argparse
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

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
HEADER_ROW = 6
DATA_START  = 7


def parse_date(val):
    if val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val.date() if isinstance(val, datetime) else val
    if isinstance(val, str):
        val = val.strip()
        if val in ("00/00/00", "", "N/A", "-", "None"):
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
    return None


def upsert_catalogo(cur, tabla, campo, valor):
    if not valor or str(valor).strip() == "":
        return None
    valor = str(valor).strip()[:100]
    pk = "id_marca" if tabla == "marcas" else \
         "id_marca_carroceria" if tabla == "marcas_carroceria" else "id_tipo"
    cur.execute(f"SELECT {pk} FROM {SCHEMA}.{tabla} WHERE {campo} = %s", (valor,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(f"INSERT INTO {SCHEMA}.{tabla} ({campo}) VALUES (%s) RETURNING {pk}", (valor,))
    return cur.fetchone()[0]


def main(excel_path: str):
    print(f"Leyendo archivo Excel: {excel_path}")
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb["General"]

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    print("Limpiando registros antiguos de itv_bus, seguros_bus e historial_itv...")
    cur.execute(f"DELETE FROM {SCHEMA}.itv_bus;")
    cur.execute(f"DELETE FROM {SCHEMA}.seguros_bus;")
    cur.execute(f"DELETE FROM {SCHEMA}.historial_itv;")
    conn.commit()

    stats = {"buses": 0, "itv": 0, "seguros": 0, "asignaciones": 0, "errores": 0, "omitidos": 0}

    for row_idx, row in enumerate(ws.iter_rows(min_row=DATA_START, values_only=True), start=DATA_START):
        nro_orden    = row[0]
        marca_nom    = row[1]
        anio         = row[2]
        chassis      = row[3]
        rua          = row[4]
        pod_rtd      = row[5]
        docs         = row[6]
        habilitacion = parse_date(row[7])
        seg_pas      = parse_date(row[8])
        seg_ter      = parse_date(row[9])
        tipo_serv    = row[10]
        tipo_carr    = row[11]
        marca_carr   = row[12]
        itv_ant      = parse_date(row[13])
        fecha_itv    = parse_date(row[14])
        venc_itv     = parse_date(row[15])
        sit_itv      = row[16]
        empresa_lin  = row[17]
        observacion  = row[18]

        rua_clean = str(rua).strip().upper() if rua else None
        chassis_clean = str(chassis).strip().upper() if chassis else None

        if not rua_clean and not chassis_clean:
            stats["omitidos"] += 1
            continue

        id_bus = None

        # --- A. BUSES ---
        try:
            id_marca      = upsert_catalogo(cur, "marcas", "nombre", marca_nom)
            id_marca_carr = upsert_catalogo(cur, "marcas_carroceria", "nombre", marca_carr)
            id_tipo_carr  = None
            if tipo_carr:
                desc = str(tipo_carr).strip()[:100]
                cur.execute(f"SELECT id_tipo FROM {SCHEMA}.tipos_carroceria WHERE descripcion = %s", (desc,))
                r = cur.fetchone()
                if r:
                    id_tipo_carr = r[0]
                else:
                    cur.execute(f"INSERT INTO {SCHEMA}.tipos_carroceria (descripcion) VALUES (%s) RETURNING id_tipo", (desc,))
                    id_tipo_carr = cur.fetchone()[0]

            if rua_clean:
                cur.execute(f"SELECT id_bus FROM {SCHEMA}.buses WHERE rua = %s", (rua_clean,))
                r = cur.fetchone()
                if r: id_bus = r[0]

            if not id_bus and chassis_clean:
                cur.execute(f"SELECT id_bus FROM {SCHEMA}.buses WHERE numero_chassis = %s", (chassis_clean,))
                r = cur.fetchone()
                if r: id_bus = r[0]

            if id_bus:
                cur.execute(f"""
                    UPDATE {SCHEMA}.buses
                    SET numero_orden=%s, id_marca=%s, año=%s, id_tipo_carroceria=%s,
                        id_marca_carroceria=%s, fecha_modificacion=NOW()
                    WHERE id_bus=%s
                """, (nro_orden if isinstance(nro_orden, int) else None, id_marca, anio if isinstance(anio, int) else 2000, id_tipo_carr, id_marca_carr, id_bus))
            else:
                rua_final = rua_clean or f"CHASSIS_{chassis_clean}"
                chassis_final = chassis_clean or f"RUA_{rua_clean}"
                cur.execute(f"""
                    INSERT INTO {SCHEMA}.buses
                        (numero_orden, id_marca, año, numero_chassis, rua,
                         id_tipo_carroceria, id_marca_carroceria, estado_bus)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,'ACTIVO')
                    ON CONFLICT DO NOTHING
                    RETURNING id_bus
                """, (nro_orden if isinstance(nro_orden, int) else None, id_marca, anio if isinstance(anio, int) else 2000, chassis_final, rua_final, id_tipo_carr, id_marca_carr))
                r = cur.fetchone()
                if r:
                    id_bus = r[0]
                else:
                    cur.execute(f"SELECT id_bus FROM {SCHEMA}.buses WHERE rua = %s OR numero_chassis = %s", (rua_final, chassis_final))
                    res_b = cur.fetchone()
                    if res_b: id_bus = res_b[0]
            
            stats["buses"] += 1
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"   [Error Bus Fila {row_idx} RUA={rua_clean}]: {e}")
            stats["errores"] += 1
            continue

        if not id_bus:
            continue

        # --- B. ITV BUS ---
        if venc_itv:
            try:
                sit_str = str(sit_itv).strip()[:20] if sit_itv else None
                obs_str = str(observacion).strip() if observacion else None
                cur.execute(f"""
                    INSERT INTO {SCHEMA}.itv_bus
                        (id_bus, fecha_itv, fecha_vencimiento, resultado_itv, observaciones)
                    VALUES (%s,%s,%s,%s,%s)
                """, (id_bus, fecha_itv or venc_itv, venc_itv, sit_str, obs_str))
                stats["itv"] += 1

                if itv_ant:
                    cur.execute(f"""
                        INSERT INTO {SCHEMA}.historial_itv
                            (id_bus, fecha_vencimiento_anterior, fecha_itv_actual, fecha_vencimiento_actual)
                        VALUES (%s,%s,%s,%s)
                    """, (id_bus, itv_ant, fecha_itv or venc_itv, venc_itv))

                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"   [Error ITV Fila {row_idx} RUA={rua_clean}]: {e}")

        # --- C. SEGUROS BUS ---
        try:
            for tipo, fecha_venc in [("PASAJEROS", seg_pas), ("TERCEROS", seg_ter)]:
                if fecha_venc:
                    cur.execute(f"""
                        INSERT INTO {SCHEMA}.seguros_bus
                            (id_bus, tipo_seguro, fecha_inicio, fecha_vencimiento, estado_seguro)
                        VALUES (%s,%s,%s,%s,'VIGENTE')
                    """, (id_bus, tipo, date.today(), fecha_venc))
                    stats["seguros"] += 1
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"   [Error Seguros Fila {row_idx} RUA={rua_clean}]: {e}")

        # --- D. ASIGNACIÓN EMPRESA ---
        if empresa_lin:
            try:
                empresa_str = str(empresa_lin).strip()
                cur.execute(
                    "SELECT id_eot_vmt_hex FROM public.eots WHERE eot_nombre ILIKE %s LIMIT 1",
                    (empresa_str.split(" - ")[0].strip() + "%",)
                )
                eot_row = cur.fetchone()
                if eot_row:
                    id_eot = eot_row[0]
                    cur.execute(f"""
                        SELECT id_asignacion FROM {SCHEMA}.bus_empresa
                        WHERE id_bus=%s AND id_eot=%s AND estado_asignacion='ACTIVA'
                    """, (id_bus, id_eot))
                    if not cur.fetchone():
                        cur.execute(f"""
                            INSERT INTO {SCHEMA}.bus_empresa
                                (id_bus, id_eot, fecha_asignacion, estado_asignacion, observaciones)
                            VALUES (%s,%s,%s,'ACTIVA',%s)
                        """, (id_bus, id_eot, date.today(), empresa_lin))
                        stats["asignaciones"] += 1
                conn.commit()
            except Exception as e:
                conn.rollback()

    cur.close()
    conn.close()

    print("\n================ MIGRACIÓN ISOLADA FINALIZADA CON ÉXITO ================")
    print(f"   Buses Procesados    : {stats['buses']}")
    print(f"   Registros ITV       : {stats['itv']}")
    print(f"   Pólizas de Seguros  : {stats['seguros']}")
    print(f"   Asignaciones Empresa: {stats['asignaciones']}")
    print(f"   Filas Omitidas      : {stats['omitidos']}")
    print(f"   Errores Bus         : {stats['errores']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrar datos ITV desde Excel a PostgreSQL")
    parser.add_argument("--file", required=True, help="Ruta al archivo .xlsx")
    args = parser.parse_args()
    main(args.file)
