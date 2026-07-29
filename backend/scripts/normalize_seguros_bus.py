"""
Normaliza seguros_bus:
- elimina columna texto tipo_seguro (usar solo id_tipo_seguro → tipos_seguro)
- reemplaza estado_seguro (VARCHAR) por seguro_vigente (BOOLEAN)
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
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Asegurar catálogo y FK id_tipo_seguro
        print("1. Asegurar tipos_seguro + id_tipo_seguro...")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.tipos_seguro (
                id_tipo_seguro SERIAL PRIMARY KEY,
                nombre         VARCHAR(50) NOT NULL UNIQUE,
                descripcion    VARCHAR(200),
                activo         BOOLEAN DEFAULT TRUE
            );
        """)
        cur.execute(f"""
            INSERT INTO {SCHEMA}.tipos_seguro (nombre, descripcion) VALUES
                ('PASAJEROS', 'Seguro de pasajeros'),
                ('TERCEROS',  'Seguro a terceros')
            ON CONFLICT (nombre) DO NOTHING;
        """)
        cur.execute(f"""
            ALTER TABLE {SCHEMA}.seguros_bus
            ADD COLUMN IF NOT EXISTS id_tipo_seguro INTEGER
            REFERENCES {SCHEMA}.tipos_seguro(id_tipo_seguro);
        """)

        # Rellenar id_tipo_seguro desde tipo_seguro si aún existe la columna texto
        cur.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema=%s AND table_name='seguros_bus' AND column_name='tipo_seguro'
        """, (SCHEMA,))
        if cur.fetchone():
            print("2. Migrar tipo_seguro texto -> id_tipo_seguro...")
            cur.execute(f"""
                INSERT INTO {SCHEMA}.tipos_seguro (nombre)
                SELECT DISTINCT UPPER(TRIM(tipo_seguro))
                FROM {SCHEMA}.seguros_bus
                WHERE tipo_seguro IS NOT NULL AND TRIM(tipo_seguro) <> ''
                ON CONFLICT (nombre) DO NOTHING;
            """)
            cur.execute(f"""
                UPDATE {SCHEMA}.seguros_bus s
                SET id_tipo_seguro = t.id_tipo_seguro
                FROM {SCHEMA}.tipos_seguro t
                WHERE s.tipo_seguro IS NOT NULL
                  AND UPPER(TRIM(s.tipo_seguro)) = t.nombre
                  AND s.id_tipo_seguro IS NULL;
            """)
            cur.execute(f"""
                SELECT COUNT(*) FILTER (WHERE id_tipo_seguro IS NULL), COUNT(*)
                FROM {SCHEMA}.seguros_bus
            """)
            sin_fk, total = cur.fetchone()
            print(f"   sin id_tipo_seguro: {sin_fk} / {total}")
            if sin_fk and sin_fk > 0:
                raise RuntimeError(
                    f"Hay {sin_fk} seguros sin id_tipo_seguro; no se puede dropear tipo_seguro"
                )

            print("3. Eliminar columna tipo_seguro...")
            cur.execute(f"ALTER TABLE {SCHEMA}.seguros_bus DROP COLUMN tipo_seguro;")
        else:
            print("2-3. Columna tipo_seguro ya no existe")

        # seguro_vigente
        print("4. Agregar seguro_vigente...")
        cur.execute(f"""
            ALTER TABLE {SCHEMA}.seguros_bus
            ADD COLUMN IF NOT EXISTS seguro_vigente BOOLEAN;
        """)

        cur.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema=%s AND table_name='seguros_bus' AND column_name='estado_seguro'
        """, (SCHEMA,))
        if cur.fetchone():
            print("5. Poblar seguro_vigente desde estado_seguro / fecha_vencimiento...")
            cur.execute(f"""
                UPDATE {SCHEMA}.seguros_bus
                SET seguro_vigente = CASE
                    WHEN UPPER(COALESCE(estado_seguro, '')) = 'VIGENTE' THEN TRUE
                    WHEN fecha_vencimiento >= CURRENT_DATE THEN TRUE
                    ELSE FALSE
                END
                WHERE seguro_vigente IS NULL;
            """)
            print("6. Eliminar columna estado_seguro...")
            cur.execute(f"ALTER TABLE {SCHEMA}.seguros_bus DROP COLUMN estado_seguro;")
        else:
            print("5-6. estado_seguro ya no existe; completar nulls de seguro_vigente...")
            cur.execute(f"""
                UPDATE {SCHEMA}.seguros_bus
                SET seguro_vigente = (fecha_vencimiento >= CURRENT_DATE)
                WHERE seguro_vigente IS NULL;
            """)

        cur.execute(f"""
            ALTER TABLE {SCHEMA}.seguros_bus
            ALTER COLUMN seguro_vigente SET DEFAULT TRUE;
        """)
        cur.execute(f"""
            ALTER TABLE {SCHEMA}.seguros_bus
            ALTER COLUMN seguro_vigente SET NOT NULL;
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS ix_seguros_bus_seguro_vigente
            ON {SCHEMA}.seguros_bus (seguro_vigente);
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS ix_seguros_bus_id_tipo_seguro
            ON {SCHEMA}.seguros_bus (id_tipo_seguro);
        """)

        # Opcional: NOT NULL en id_tipo_seguro si todos tienen valor
        cur.execute(f"""
            SELECT COUNT(*) FILTER (WHERE id_tipo_seguro IS NULL) FROM {SCHEMA}.seguros_bus
        """)
        if cur.fetchone()[0] == 0:
            cur.execute(f"""
                ALTER TABLE {SCHEMA}.seguros_bus
                ALTER COLUMN id_tipo_seguro SET NOT NULL;
            """)
            print("7. id_tipo_seguro NOT NULL")

        conn.commit()

        cur.execute(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name='seguros_bus'
            ORDER BY ordinal_position
        """, (SCHEMA,))
        print("=== seguros_bus columns ===")
        for r in cur.fetchall():
            print(r)

        cur.execute(f"""
            SELECT seguro_vigente, COUNT(*)
            FROM {SCHEMA}.seguros_bus
            GROUP BY 1 ORDER BY 1
        """)
        print("seguro_vigente counts:", cur.fetchall())
        print("OK normalize_seguros_bus")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()
