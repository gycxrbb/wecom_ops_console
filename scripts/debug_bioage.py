import sys; sys.path.insert(0, '.')
from app.clients.crm_db import get_connection, return_connection

conn = get_connection()
try:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT code, value, unit, check_date "
            "FROM customer_report_items WHERE customer_id = 892 AND value IS NOT NULL "
            "ORDER BY code"
        )
        for r in cur.fetchall():
            print(r["code"], r["value"], r["unit"], r["check_date"])
finally:
    return_connection(conn)
