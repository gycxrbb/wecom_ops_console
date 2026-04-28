"""
登录接口压测脚本
目标：https://api.crm.habitility.cn/sys/userLogin
功能：
1. 暴力破解测试（失败锁定检测）
2. 高频请求限流测试
3. 高并发洪水压测
"""
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# 目标接口
URL = "https://api.crm.habitility.cn/sys/userLogin"

# 连接池优化（提速关键）
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=50,
    pool_maxsize=200,
    max_retries=0
)
session.mount("https://", adapter)
TIMEOUT = 3

# 请求头（模拟真实浏览器）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json"
}

# ===================== 高速请求 =====================
def send_request(username="test", password="wrong"):
    try:
        resp = session.post(
            URL,
            json={"username": username, "password": password},
            headers=HEADERS,
            timeout=TIMEOUT
        )
        return resp.status_code, resp.json()
    except Exception as e:
        return -1, {"error": str(e)}

# ===================== 1. 暴力破解测试 =====================
def test_brute_force():
    print("=" * 60)
    print("测试1：暴力破解（失败锁定）")
    print("=" * 60)
    lock_at = None

    for i in range(1, 12):
        code, data = send_request(password=f"wrong_{i}")
        errcode = data.get("errcode", code)
        errmsg = data.get("errmsg", "")

        if errcode in (429, 42900, -2):
            status = "🔒 已限流/锁定"
            if lock_at is None:
                lock_at = i
        else:
            status = "❌ 失败"

        print(f"第{i:2d}次 | {status} | code={errcode} | {errmsg}")

    print(f"\n结果：首次锁定 = 第{lock_at}次" if lock_at else "结果：未触发锁定\n")

# ===================== 2. 高频限流测试 =====================
def test_rate_limit():
    print("=" * 60)
    print("测试2：高频请求限流")
    print("=" * 60)
    success = 0
    blocked = 0
    limit_at = None
    total = 4000

    def task():
        nonlocal success, blocked, limit_at
        code, data = send_request()
        errcode = data.get("errcode", code)
        if errcode in (429, 42900, -2):
            blocked += 1
            if limit_at is None:
                limit_at = success + blocked
        else:
            success += 1

    with ThreadPoolExecutor(max_workers=20) as pool:
        [pool.submit(task) for _ in range(total)]
    print(f"成功：{success} | 被限流：{blocked}")
    print(f"首次限流在第{limit_at}次" if limit_at else "无限流")
    print(f"{'✅ 限流生效' if blocked>0 else '❌ 限流未生效'}\n")

# ===================== 3. 高并发洪水测试 =====================
def test_concurrent():
    print("=" * 60)
    print("测试3：高并发洪水（50线程 200次）")
    print("=" * 60)
    success = 0
    blocked = 0
    error = 0

    def task():
        nonlocal success, blocked, error
        code, data = send_request()
        errcode = data.get("errcode", code)
        if errcode in (429, 42900, -2):
            blocked +=1
        elif code == 200:
            success +=1
        else:
            error +=1

    with ThreadPoolExecutor(max_workers=50) as pool:
        [pool.submit(task) for _ in range(2000)]
    print(f"成功：{success} | 限流：{blocked} | 错误：{error}")
    print(f"{'✅ 防护有效' if blocked>0 else '❌ 无防护'}\n")

# ===================== 主入口 =====================
if __name__ == "__main__":
    print(f"🎯 压测目标：{URL}")
    print("⚠️  仅用于授权测试环境\n")

    test_brute_force()
    time.sleep(2)
    test_rate_limit()
    time.sleep(2)
    test_concurrent()

    print("=" * 60)
    print("🏁 压测完成")
    print("=" * 60)