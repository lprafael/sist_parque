"""Crea sistema.mensajes si no existe."""
import os
import sys

import psycopg2

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "168.90.177.232"),
    port=int(os.getenv("DB_PORT", 2024)),
    user=os.getenv("DB_USER", "cid_admin_user"),
    password=os.getenv("DB_PASSWORD", "vmtdmtcidccm"),
    dbname=os.getenv("DB_NAME", "bbdd-monitoreo-cid"),
    sslmode="disable",
)
conn.autocommit = True
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS sistema.mensajes (
    id          SERIAL PRIMARY KEY,
    id_usuario  INTEGER NOT NULL REFERENCES sistema.usuarios(id),
    id_sistema  INTEGER NOT NULL REFERENCES sistema.sistemas(id),
    tipo        VARCHAR(30) NOT NULL DEFAULT 'soporte',
    mensaje     TEXT NOT NULL,
    fecha       TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    entrante    BOOLEAN NOT NULL DEFAULT TRUE,
    leido       BOOLEAN NOT NULL DEFAULT FALSE,
    solucion    BOOLEAN NOT NULL DEFAULT FALSE,
    id_padre    INTEGER NULL REFERENCES sistema.mensajes(id)
);

CREATE INDEX IF NOT EXISTS ix_mensajes_id_usuario ON sistema.mensajes (id_usuario);
CREATE INDEX IF NOT EXISTS ix_mensajes_id_sistema ON sistema.mensajes (id_sistema);
CREATE INDEX IF NOT EXISTS ix_mensajes_leido ON sistema.mensajes (leido) WHERE leido = FALSE;
""")

cur.execute("""
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'sistema' AND table_name = 'mensajes'
ORDER BY ordinal_position;
""")
rows = cur.fetchall()
print("Tabla sistema.mensajes OK. Columnas:")
for r in rows:
    print(" ", r)

cur.close()
conn.close()
sys.exit(0)
