import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import psycopg2

conn = psycopg2.connect(
    host='168.90.177.232',
    port=2024,
    user='cid_admin_user',
    password='vmtdmtcidccm',
    dbname='bbdd-monitoreo-cid',
    sslmode='disable'
)
cur = conn.cursor()

# Estructura de public.eots
cur.execute("""
    SELECT column_name, data_type, is_nullable, character_maximum_length
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'eots'
    ORDER BY ordinal_position;
""")
cols = cur.fetchall()
print("=== ESTRUCTURA: public.eots ===")
for col in cols:
    name, dtype, nullable, maxlen = col
    len_str = f'({maxlen})' if maxlen else ''
    print(f"  {name}: {dtype}{len_str} {'NULL' if nullable=='YES' else 'NOT NULL'}")

# Sample data
cur.execute("SELECT * FROM public.eots LIMIT 5;")
rows = cur.fetchall()
colnames = [desc[0] for desc in cur.description]
print(f"\n=== MUESTRA DE DATOS (5 filas) ===")
print("COLUMNAS:", colnames)
for r in rows:
    print(r)

# Count
cur.execute("SELECT COUNT(*) FROM public.eots;")
total = cur.fetchone()[0]
print(f"\nTotal registros: {total}")

# Check if there are other related tables in public schema that reference eots
cur.execute("""
    SELECT tc.table_name, kcu.column_name, ccu.table_name AS foreign_table, ccu.column_name AS foreign_column
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND ccu.table_name = 'eots'
    LIMIT 20;
""")
fks = cur.fetchall()
print(f"\n=== FK que apuntan a eots ===")
for fk in fks:
    print(f"  {fk[0]}.{fk[1]} -> eots.{fk[3]}")

conn.close()
