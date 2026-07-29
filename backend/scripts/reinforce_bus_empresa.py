"""
Refuerza registro_habilitacion.bus_empresa para el historial N:N bus↔EOT:
- columna motivo
- sincroniza estado_asignacion con fecha_fin_asignacion
- cierra duplicados vigentes (deja uno por bus)
- índice único parcial: un solo vigente por bus
- índice por EOT vigentes
"""
import os
import psycopg2

SCHEMA = "registro_habilitacion"


def run():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "168.90.177.232"),
        port=int(os.getenv("DB_PORT", 2024)),
        user=os.getenv("DB_USER", "cid_admin_user"),
        password=os.getenv("DB_PASSWORD", "vmtdmtcidccm"),
        dbname=os.getenv("DB_NAME", "bbdd-monitoreo-cid"),
        sslmode="disable",
    )
    cur = conn.cursor()

    print("1. Columna motivo...")
    cur.execute(f"""
        ALTER TABLE {SCHEMA}.bus_empresa
        ADD COLUMN IF NOT EXISTS motivo VARCHAR(30);
    """)

    print("2. Sincronizar estado <-> fecha_fin...")
    cur.execute(f"""
        UPDATE {SCHEMA}.bus_empresa
        SET estado_asignacion = 'ACTIVA',
            fecha_fin_asignacion = NULL
        WHERE fecha_fin_asignacion IS NULL
          AND COALESCE(estado_asignacion, '') <> 'ACTIVA';
    """)
    cur.execute(f"""
        UPDATE {SCHEMA}.bus_empresa
        SET estado_asignacion = 'CERRADA'
        WHERE fecha_fin_asignacion IS NOT NULL
          AND COALESCE(estado_asignacion, '') <> 'CERRADA';
    """)

    print("3. Cerrar duplicados vigentes (conservar el mas reciente por bus)...")
    cur.execute(f"""
        WITH ranked AS (
            SELECT id_asignacion,
                   ROW_NUMBER() OVER (
                       PARTITION BY id_bus
                       ORDER BY fecha_asignacion DESC, id_asignacion DESC
                   ) AS rn
            FROM {SCHEMA}.bus_empresa
            WHERE fecha_fin_asignacion IS NULL
        )
        UPDATE {SCHEMA}.bus_empresa be
        SET estado_asignacion = 'CERRADA',
            fecha_fin_asignacion = CURRENT_DATE,
            motivo = COALESCE(be.motivo, 'BAJA'),
            observaciones = CONCAT_WS(
                E'\\n',
                be.observaciones,
                '[auto] cerrado por migracion: multiples vigentes'
            )
        FROM ranked r
        WHERE be.id_asignacion = r.id_asignacion
          AND r.rn > 1;
    """)
    print(f"   Duplicados cerrados: {cur.rowcount}")

    print("4. Motivo por defecto en vigentes sin motivo...")
    cur.execute(f"""
        UPDATE {SCHEMA}.bus_empresa
        SET motivo = 'ALTA'
        WHERE fecha_fin_asignacion IS NULL
          AND motivo IS NULL;
    """)

    print("5. Indice unico parcial (un vigente por bus)...")
    cur.execute(f"""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_bus_empresa_vigente
        ON {SCHEMA}.bus_empresa (id_bus)
        WHERE fecha_fin_asignacion IS NULL;
    """)

    print("6. Indice EOT vigentes...")
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS ix_bus_empresa_eot_vigente
        ON {SCHEMA}.bus_empresa (id_eot)
        WHERE fecha_fin_asignacion IS NULL;
    """)

    conn.commit()

    cur.execute(f"""
        SELECT
            COUNT(*) FILTER (WHERE fecha_fin_asignacion IS NULL) AS vigentes,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE motivo IS NOT NULL) AS con_motivo
        FROM {SCHEMA}.bus_empresa;
    """)
    vigentes, total, con_motivo = cur.fetchone()
    print("Migracion OK.")
    print(f"   Total: {total} | Vigentes: {vigentes} | Con motivo: {con_motivo}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    run()
