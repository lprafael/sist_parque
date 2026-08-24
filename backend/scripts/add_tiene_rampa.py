"""Agrega buses.tiene_rampa si no existe."""
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
    ALTER TABLE registro_habilitacion.buses
    ADD COLUMN IF NOT EXISTS tiene_rampa BOOLEAN NOT NULL DEFAULT FALSE;
""")
print("Columna registro_habilitacion.buses.tiene_rampa agregada (o ya existía).")

cur.execute("""
    SELECT column_name, data_type, column_default, is_nullable
    FROM information_schema.columns
    WHERE table_schema = 'registro_habilitacion'
      AND table_name = 'buses'
      AND column_name = 'tiene_rampa';
""")
row = cur.fetchone()
print(" ", row)

cur.close()
conn.close()
sys.exit(0)
