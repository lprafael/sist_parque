"""
Normalización schema registro_habilitacion:

1) tipos_bus          ← valores de buses.tipo_servicio (CONVENCIONAL, DIFERENCIADO, ...)
2) tipos_seguro       ← valores de seguros_bus.tipo_seguro (PASAJEROS, TERCEROS)
3) documentos_eot     ← documentación de parque por EOT (HABILITACION / AUMENTO / DISMINUCION)
4) bus_empresa.normativa (TEXT)

Notas:
- companias_seguros y tipos_carroceria YA existen como catálogos normalizados.
- Hoy companias_seguros está vacía y seguros_bus.id_compania es NULL en todos los registros
  (el import Excel no traía compañía). La FK ya está lista para cuando se carguen compañías.
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
        # ── 1. tipos_bus ──────────────────────────────────────
        print("1. Crear catálogo tipos_bus...")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.tipos_bus (
                id_tipo_bus SERIAL PRIMARY KEY,
                nombre      VARCHAR(100) NOT NULL UNIQUE,
                descripcion VARCHAR(200),
                activo      BOOLEAN DEFAULT TRUE
            );
        """)

        cur.execute(f"""
            ALTER TABLE {SCHEMA}.buses
            ADD COLUMN IF NOT EXISTS id_tipo_bus INTEGER
            REFERENCES {SCHEMA}.tipos_bus(id_tipo_bus);
        """)

        print("   Poblar tipos_bus desde buses.tipo_servicio...")
        cur.execute(f"""
            INSERT INTO {SCHEMA}.tipos_bus (nombre)
            SELECT DISTINCT UPPER(TRIM(tipo_servicio))
            FROM {SCHEMA}.buses
            WHERE tipo_servicio IS NOT NULL AND TRIM(tipo_servicio) <> ''
            ON CONFLICT (nombre) DO NOTHING;
        """)
        # Defaults útiles si la tabla está vacía
        cur.execute(f"""
            INSERT INTO {SCHEMA}.tipos_bus (nombre, descripcion) VALUES
                ('CONVENCIONAL', 'Servicio convencional'),
                ('DIFERENCIADO', 'Servicio diferenciado')
            ON CONFLICT (nombre) DO NOTHING;
        """)

        print("   Asignar id_tipo_bus en buses...")
        cur.execute(f"""
            UPDATE {SCHEMA}.buses b
            SET id_tipo_bus = t.id_tipo_bus
            FROM {SCHEMA}.tipos_bus t
            WHERE b.tipo_servicio IS NOT NULL
              AND UPPER(TRIM(b.tipo_servicio)) = t.nombre
              AND (b.id_tipo_bus IS DISTINCT FROM t.id_tipo_bus);
        """)

        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS ix_buses_id_tipo_bus
            ON {SCHEMA}.buses (id_tipo_bus);
        """)

        # ── 2. tipos_seguro ───────────────────────────────────
        print("2. Crear catálogo tipos_seguro...")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.tipos_seguro (
                id_tipo_seguro SERIAL PRIMARY KEY,
                nombre         VARCHAR(50) NOT NULL UNIQUE,
                descripcion    VARCHAR(200),
                activo         BOOLEAN DEFAULT TRUE
            );
        """)

        cur.execute(f"""
            ALTER TABLE {SCHEMA}.seguros_bus
            ADD COLUMN IF NOT EXISTS id_tipo_seguro INTEGER
            REFERENCES {SCHEMA}.tipos_seguro(id_tipo_seguro);
        """)

        print("   Poblar tipos_seguro...")
        cur.execute(f"""
            INSERT INTO {SCHEMA}.tipos_seguro (nombre, descripcion) VALUES
                ('PASAJEROS', 'Seguro de pasajeros'),
                ('TERCEROS',  'Seguro a terceros')
            ON CONFLICT (nombre) DO NOTHING;
        """)
        cur.execute(f"""
            INSERT INTO {SCHEMA}.tipos_seguro (nombre)
            SELECT DISTINCT UPPER(TRIM(tipo_seguro))
            FROM {SCHEMA}.seguros_bus
            WHERE tipo_seguro IS NOT NULL AND TRIM(tipo_seguro) <> ''
            ON CONFLICT (nombre) DO NOTHING;
        """)

        print("   Asignar id_tipo_seguro en seguros_bus...")
        cur.execute(f"""
            UPDATE {SCHEMA}.seguros_bus s
            SET id_tipo_seguro = t.id_tipo_seguro
            FROM {SCHEMA}.tipos_seguro t
            WHERE s.tipo_seguro IS NOT NULL
              AND UPPER(TRIM(s.tipo_seguro)) = t.nombre
              AND (s.id_tipo_seguro IS DISTINCT FROM t.id_tipo_seguro);
        """)

        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS ix_seguros_bus_id_tipo_seguro
            ON {SCHEMA}.seguros_bus (id_tipo_seguro);
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS ix_seguros_bus_id_compania
            ON {SCHEMA}.seguros_bus (id_compania);
        """)

        # ── 3. documentos_eot ─────────────────────────────────
        print("3. Crear tabla documentos_eot...")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.documentos_eot (
                id_documento_eot  SERIAL PRIMARY KEY,
                id_eot            VARCHAR(255) NOT NULL,  -- public.eots.id_eot_vmt_hex
                tipo_documento    VARCHAR(30)  NOT NULL,  -- HABILITACION | AUMENTO | DISMINUCION
                numero_resolucion VARCHAR(100),
                nombre_documento  VARCHAR(200),
                fecha_emision     DATE,
                fecha_vigencia    DATE,
                cantidad_buses    INTEGER,                -- opcional: tamaño de parque referido
                archivo_url       VARCHAR(500),
                observaciones     TEXT,
                usuario_registro  VARCHAR(100),
                fecha_registro    TIMESTAMP DEFAULT NOW(),
                CONSTRAINT chk_documentos_eot_tipo CHECK (
                    tipo_documento IN ('HABILITACION', 'AUMENTO', 'DISMINUCION')
                )
            );
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS ix_documentos_eot_id_eot
            ON {SCHEMA}.documentos_eot (id_eot);
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS ix_documentos_eot_tipo
            ON {SCHEMA}.documentos_eot (tipo_documento);
        """)

        # ── 4. normativa en bus_empresa ───────────────────────
        print("4. Agregar columna normativa a bus_empresa...")
        cur.execute(f"""
            ALTER TABLE {SCHEMA}.bus_empresa
            ADD COLUMN IF NOT EXISTS normativa TEXT;
        """)

        conn.commit()

        # ── Verificación ─────────────────────────────────────
        cur.execute(f"SELECT id_tipo_bus, nombre FROM {SCHEMA}.tipos_bus ORDER BY 1")
        print("tipos_bus:", cur.fetchall())
        cur.execute(f"SELECT id_tipo_seguro, nombre FROM {SCHEMA}.tipos_seguro ORDER BY 1")
        print("tipos_seguro:", cur.fetchall())
        cur.execute(f"""
            SELECT COUNT(*) FILTER (WHERE id_tipo_bus IS NOT NULL),
                   COUNT(*)
            FROM {SCHEMA}.buses
        """)
        print("buses con id_tipo_bus / total:", cur.fetchone())
        cur.execute(f"""
            SELECT COUNT(*) FILTER (WHERE id_tipo_seguro IS NOT NULL),
                   COUNT(*)
            FROM {SCHEMA}.seguros_bus
        """)
        print("seguros con id_tipo_seguro / total:", cur.fetchone())
        cur.execute(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema=%s AND table_name='bus_empresa' AND column_name='normativa'
        """, (SCHEMA,))
        print("bus_empresa.normativa:", cur.fetchone())
        cur.execute(f"""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema=%s AND table_name='documentos_eot'
        """, (SCHEMA,))
        print("documentos_eot existe:", cur.fetchone()[0] == 1)
        print("OK migración normalización")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()
