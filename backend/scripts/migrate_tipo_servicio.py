import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "168.90.177.232"),
    port=int(os.getenv("DB_PORT", 2024)),
    user=os.getenv("DB_USER", "cid_admin_user"),
    password=os.getenv("DB_PASSWORD", "vmtdmtcidccm"),
    dbname=os.getenv("DB_NAME", "bbdd-monitoreo-cid"),
    sslmode="disable"
)
conn.autocommit = True
cur = conn.cursor()

# 1. Agregar la columna tipo_servicio a la tabla buses
print("Agregando columna tipo_servicio a la tabla buses...")
cur.execute("""
    ALTER TABLE registro_habilitacion.buses 
    ADD COLUMN IF NOT EXISTS tipo_servicio VARCHAR(50);
""")
print("  Columna agregada (o ya existía).")

# 2. Migrar los datos desde auxiliar, normalizando las variantes con (*)
print("Migrando datos de Tipo de Servicio desde auxiliar -> buses...")
cur.execute("""
    UPDATE registro_habilitacion.buses b
    SET tipo_servicio = CASE
        WHEN UPPER(TRIM(a."Tipo de Servicio")) LIKE 'CONVENCIONAL%'  THEN 'CONVENCIONAL'
        WHEN UPPER(TRIM(a."Tipo de Servicio")) LIKE 'DIFERENCIADO%'  THEN 'DIFERENCIADO'
        ELSE UPPER(TRIM(a."Tipo de Servicio"))
    END
    FROM registro_habilitacion.auxiliar a
    WHERE b.rua = a."RUA"
      AND a."Tipo de Servicio" IS NOT NULL
      AND a."Tipo de Servicio" != '';
""")
updated = cur.rowcount
print(f"  Buses actualizados con tipo_servicio: {updated}")

# 3. Verificar la distribución resultante
cur.execute("""
    SELECT tipo_servicio, count(*) 
    FROM registro_habilitacion.buses 
    WHERE tipo_servicio IS NOT NULL
    GROUP BY tipo_servicio 
    ORDER BY count(*) DESC;
""")
print("\nDistribución final en buses:")
for row in cur.fetchall():
    print(" ", row)

cur.close()
conn.close()
