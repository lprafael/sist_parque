import psycopg2
import asyncio
import asyncpg
import os

DB_HOST = "168.90.177.232"
DB_PORT = 2024
DB_USER = "cid_admin_user"
DB_PASS = "vmtdmtcidccm"
DB_NAME = "bbdd-monitoreo-cid"

# 1. psycopg2
conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, dbname=DB_NAME, sslmode="disable")
cur = conn.cursor()
cur.execute("SELECT count(*) FROM registro_habilitacion.itv_bus;")
count_psycopg = cur.fetchone()[0]
cur.close()
conn.close()

# 2. asyncpg
async def check_asyncpg():
    conn_a = await asyncpg.connect(user=DB_USER, password=DB_PASS, database=DB_NAME, host=DB_HOST, port=DB_PORT)
    row = await conn_a.fetchrow("SELECT count(*) FROM registro_habilitacion.itv_bus;")
    await conn_a.close()
    return row[0]

count_asyncpg = asyncio.run(check_asyncpg())

print(f"Count via psycopg2: {count_psycopg}")
print(f"Count via asyncpg:  {count_asyncpg}")
