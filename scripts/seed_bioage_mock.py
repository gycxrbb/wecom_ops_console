"""一次性脚本：为 customer_id=892 插入模拟血生化指标数据。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.clients.crm_db import get_connection, return_connection

rows = [
    ('albumin',    '白蛋白',        42.5,  'g/L',    '40-55',   'blood'),
    ('creatinine', '肌酐',          58.0,  'umol/L', '41-81',   'blood'),
    ('alp',        '碱性磷酸酶',     85.0,  'U/L',    '35-104',  'blood'),
    ('hscrp',      '超敏C反应蛋白',   1.8,   'mg/L',   '0-3',     'blood'),
    ('tc',         '总胆固醇',       5.6,   'mmol/L', '2.8-5.7', 'blood'),
]

conn = get_connection()
try:
    with conn.cursor() as cur:
        for code, name, value, unit, normal_range, category in rows:
            cur.execute(
                "INSERT INTO customer_report_items "
                "(report_id, customer_id, check_date, category, code, name, value, unit, normal_range, flag, created_at) "
                "VALUES (78, 892, '2026-04-25', %s, %s, %s, %s, %s, %s, 0, NOW())",
                (category, code, name, value, unit, normal_range),
            )
        conn.commit()
        print(f"Inserted {len(rows)} rows")

        cur.execute(
            "SELECT code, value, unit FROM customer_report_items "
            "WHERE customer_id = 892 AND code IN ('hba1c','albumin','creatinine','alp','hscrp','tc') "
            "AND check_date = '2026-04-25' GROUP BY code, value, unit"
        )
        print("--- verification ---")
        for r in cur.fetchall():
            print(r["code"], r["value"], r["unit"])
finally:
    return_connection(conn)
