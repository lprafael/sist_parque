import psycopg2
import os

SCHEMA = "registro_habilitacion"

def test_consistency():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "168.90.177.232"),
        port=int(os.getenv("DB_PORT", 2024)),
        user=os.getenv("DB_USER", "cid_admin_user"),
        password=os.getenv("DB_PASSWORD", "vmtdmtcidccm"),
        dbname=os.getenv("DB_NAME", "bbdd-monitoreo-cid"),
        sslmode="disable"
    )
    cur = conn.cursor()

    # Obtener el primer id_bus existente
    cur.execute(f"SELECT id_bus FROM {SCHEMA}.itv_bus WHERE es_vigente = TRUE LIMIT 1;")
    bus_id = cur.fetchone()[0]

    print(f"Probando restricción de consistencia para id_bus={bus_id}...")

    # Intentar insertar una segunda ITV con es_vigente = TRUE (debe fallar por la Unique Index parcial)
    try:
        cur.execute(f"""
            INSERT INTO {SCHEMA}.itv_bus (id_bus, fecha_itv, fecha_vencimiento, resultado_itv, es_vigente)
            VALUES ({bus_id}, '2026-01-01', '2026-12-31', 'TOTAL', TRUE);
        """)
        conn.commit()
        print("ERROR: La insercion duplicada vigente debio ser rechazada por el indice unico pero paso.")
    except psycopg2.Error as e:
        conn.rollback()
        print("EXITO: La base de datos rechazo correctamente la ITV duplicada con es_vigente=TRUE.")
        print("Detalle de la restriccion violada:", str(e).strip().split('\n')[0])

    cur.close()
    conn.close()

if __name__ == "__main__":
    test_consistency()
