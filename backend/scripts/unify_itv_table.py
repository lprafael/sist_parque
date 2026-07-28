import psycopg2
import os

SCHEMA = "registro_habilitacion"

def run_unification():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "168.90.177.232"),
        port=int(os.getenv("DB_PORT", 2024)),
        user=os.getenv("DB_USER", "cid_admin_user"),
        password=os.getenv("DB_PASSWORD", "vmtdmtcidccm"),
        dbname=os.getenv("DB_NAME", "bbdd-monitoreo-cid"),
        sslmode="disable"
    )
    cur = conn.cursor()

    print("1. Añadiendo columna es_vigente a itv_bus...")
    cur.execute(f"ALTER TABLE {SCHEMA}.itv_bus ADD COLUMN IF NOT EXISTS es_vigente BOOLEAN DEFAULT TRUE;")

    print("2. Ajustando vigencia para mantener sólo la última ITV por bus como es_vigente = TRUE...")
    cur.execute(f"UPDATE {SCHEMA}.itv_bus SET es_vigente = FALSE;")
    cur.execute(f"""
        WITH latest AS (
            SELECT id_itv, ROW_NUMBER() OVER (PARTITION BY id_bus ORDER BY fecha_vencimiento DESC, id_itv DESC) as rn
            FROM {SCHEMA}.itv_bus
        )
        UPDATE {SCHEMA}.itv_bus
        SET es_vigente = TRUE
        WHERE id_itv IN (SELECT id_itv FROM latest WHERE rn = 1);
    """)

    print("3. Creando índice único parcial para garantizar la consistencia de datos...")
    cur.execute(f"""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_itv_bus_vigente_unico 
        ON {SCHEMA}.itv_bus (id_bus) 
        WHERE (es_vigente = TRUE);
    """)

    print("4. Eliminando la tabla redundante historial_itv...")
    cur.execute(f"DROP TABLE IF EXISTS {SCHEMA}.historial_itv CASCADE;")

    conn.commit()

    # Verificación
    cur.execute(f"SELECT count(*) FROM {SCHEMA}.itv_bus WHERE es_vigente = TRUE;")
    cnt_vigentes = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM {SCHEMA}.itv_bus;")
    cnt_total = cur.fetchone()[0]

    print("Migracion completada con exito.")
    print(f"   Total registros en itv_bus: {cnt_total}")
    print(f"   Registros vigentes (es_vigente=TRUE): {cnt_vigentes}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    run_unification()
