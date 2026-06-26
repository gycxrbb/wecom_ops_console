"""临时：检查客户 2699 的 L2 档案缓存状态。"""
import pymysql
from pymysql.cursors import DictCursor

conn = pymysql.connect(
    host="127.0.0.1", port=3306, user="root", password="255731xr",
    database="wecom_ops", charset="utf8mb4", cursorclass=DictCursor,
)
try:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT cache_key, crm_customer_id, generated_at, expires_at, stale_expires_at, last_hit_at, "
            "LENGTH(context_json) AS json_len, "
            "SUBSTRING(context_json, LOCATE('\"crm_status\"', context_json), 60) AS status_snippet "
            "FROM crm_ai_profile_cache WHERE crm_customer_id = %s",
            (2699,),
        )
        rows = cur.fetchall()
finally:
    conn.close()

print(f"[rows] count={len(rows)}")
for r in rows:
    print(r)
