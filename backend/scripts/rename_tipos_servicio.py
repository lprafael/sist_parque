"""
Renombra tipos_bus → tipos_servicio y limpia buses:
- tabla tipos_bus → tipos_servicio
- PK id_tipo_bus → id_tipo_servicio
- buses.id_tipo_bus → buses.id_tipo_servicio
- elimina buses.tipo_servicio (texto legado)
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
        # ¿Existe tipos_bus?
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema=%s AND table_name='tipos_bus'
        """, (SCHEMA,))
        tiene_tipos_bus = cur.fetchone() is not None

        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema=%s AND table_name='tipos_servicio'
        """, (SCHEMA,))
        tiene_tipos_servicio = cur.fetchone() is not None

        if tiene_tipos_bus and not tiene_tipos_servicio:
            print("1. Renombrar tabla tipos_bus -> tipos_servicio...")
            cur.execute(f"ALTER TABLE {SCHEMA}.tipos_bus RENAME TO tipos_servicio;")
            cur.execute(f"""
                ALTER TABLE {SCHEMA}.tipos_servicio
                RENAME COLUMN id_tipo_bus TO id_tipo_servicio;
            """)
            # Sequence rename if exists
            cur.execute("""
                SELECT pg_get_serial_sequence(%s, 'id_tipo_servicio')
            """, (f"{SCHEMA}.tipos_servicio",))
            seq = cur.fetchone()[0]
            if seq:
                cur.execute(f"ALTER SEQUENCE {seq} RENAME TO tipos_servicio_id_tipo_servicio_seq;")
                print(f"   sequence renombrada: {seq}")
        elif not tiene_tipos_servicio:
            print("1. Crear tipos_servicio (no existia tipos_bus)...")
            cur.execute(f"""
                CREATE TABLE {SCHEMA}.tipos_servicio (
                    id_tipo_servicio SERIAL PRIMARY KEY,
                    nombre           VARCHAR(100) NOT NULL UNIQUE,
                    descripcion      VARCHAR(200),
                    activo           BOOLEAN DEFAULT TRUE
                );
            """)
            cur.execute(f"""
                INSERT INTO {SCHEMA}.tipos_servicio (nombre, descripcion) VALUES
                    ('CONVENCIONAL', 'Servicio convencional'),
                    ('DIFERENCIADO', 'Servicio diferenciado')
                ON CONFLICT (nombre) DO NOTHING;
            """)
        else:
            print("1. tipos_servicio ya existe")

        # FK / columna en buses
        cur.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema=%s AND table_name='buses' AND column_name='id_tipo_bus'
        """, (SCHEMA,))
        if cur.fetchone():
            print("2. Renombrar buses.id_tipo_bus -> id_tipo_servicio...")
            # Drop old FK if any, rename column, recreate FK
            cur.execute(f"""
                SELECT conname FROM pg_constraint
                WHERE conrelid = '{SCHEMA}.buses'::regclass
                  AND contype = 'f'
                  AND pg_get_constraintdef(oid) ILIKE '%%id_tipo_bus%%'
            """)
            for (conname,) in cur.fetchall():
                cur.execute(f'ALTER TABLE {SCHEMA}.buses DROP CONSTRAINT "{conname}";')
                print(f"   drop FK {conname}")

            cur.execute(f"""
                ALTER TABLE {SCHEMA}.buses
                RENAME COLUMN id_tipo_bus TO id_tipo_servicio;
            """)
            cur.execute(f"""
                ALTER TABLE {SCHEMA}.buses
                ADD CONSTRAINT buses_id_tipo_servicio_fkey
                FOREIGN KEY (id_tipo_servicio)
                REFERENCES {SCHEMA}.tipos_servicio(id_tipo_servicio);
            """)
            cur.execute(f"DROP INDEX IF EXISTS {SCHEMA}.ix_buses_id_tipo_bus;")
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS ix_buses_id_tipo_servicio
                ON {SCHEMA}.buses (id_tipo_servicio);
            """)
        else:
            cur.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema=%s AND table_name='buses' AND column_name='id_tipo_servicio'
            """, (SCHEMA,))
            if not cur.fetchone():
                print("2. Agregar buses.id_tipo_servicio...")
                cur.execute(f"""
                    ALTER TABLE {SCHEMA}.buses
                    ADD COLUMN id_tipo_servicio INTEGER
                    REFERENCES {SCHEMA}.tipos_servicio(id_tipo_servicio);
                """)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS ix_buses_id_tipo_servicio
                    ON {SCHEMA}.buses (id_tipo_servicio);
                """)
            else:
                print("2. buses.id_tipo_servicio ya existe")

        # Rellenar FK desde tipo_servicio texto si aún existe
        cur.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema=%s AND table_name='buses' AND column_name='tipo_servicio'
        """, (SCHEMA,))
        if cur.fetchone():
            print("3. Completar id_tipo_servicio desde tipo_servicio texto...")
            cur.execute(f"""
                INSERT INTO {SCHEMA}.tipos_servicio (nombre)
                SELECT DISTINCT UPPER(TRIM(tipo_servicio))
                FROM {SCHEMA}.buses
                WHERE tipo_servicio IS NOT NULL AND TRIM(tipo_servicio) <> ''
                ON CONFLICT (nombre) DO NOTHING;
            """)
            cur.execute(f"""
                UPDATE {SCHEMA}.buses b
                SET id_tipo_servicio = t.id_tipo_servicio
                FROM {SCHEMA}.tipos_servicio t
                WHERE b.tipo_servicio IS NOT NULL
                  AND UPPER(TRIM(b.tipo_servicio)) = t.nombre
                  AND b.id_tipo_servicio IS NULL;
            """)
            cur.execute(f"""
                SELECT COUNT(*) FILTER (WHERE id_tipo_servicio IS NULL), COUNT(*)
                FROM {SCHEMA}.buses
            """)
            sin_fk, total = cur.fetchone()
            print(f"   sin id_tipo_servicio: {sin_fk} / {total}")

            print("4. Eliminar columna buses.tipo_servicio...")
            cur.execute(f"ALTER TABLE {SCHEMA}.buses DROP COLUMN tipo_servicio;")
        else:
            print("3-4. Columna tipo_servicio ya no existe")

        conn.commit()

        cur.execute(f"SELECT id_tipo_servicio, nombre FROM {SCHEMA}.tipos_servicio ORDER BY 1")
        print("tipos_servicio:", cur.fetchall())
        cur.execute(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema=%s AND table_name='buses'
              AND column_name IN ('tipo_servicio','id_tipo_bus','id_tipo_servicio')
            ORDER BY 1
        """, (SCHEMA,))
        print("buses cols relevantes:", [r[0] for r in cur.fetchall()])
        print("OK rename_tipos_servicio")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()
