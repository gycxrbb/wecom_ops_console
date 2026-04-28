"""
安全防护压测脚本（高速优化版）
用法：python scripts/security_stress_test.py [BASE_URL]

默认目标：http://localhost:8000
测试内容：
  1. 登录暴力破解测试 — 验证 5 次失败后是否被锁定
  2. 登录接口限流测试 — 20 次/分钟
  3. 全局 API 限流测试 — 120 次/分钟
  4. 高并发洪水压测 — 50 线程 200 次请求
"""
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===================== 配置 =====================
BASE_URL = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8000'
API_PREFIX = f'{BASE_URL}/api'

# 连接池（关键：大幅提速）
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=200)
session.mount('http://', adapter)
session.mount('https://', adapter)

# 超时时长（短超时=压测更快）
TIMEOUT = 3

# ===================== 工具函数 =====================
def speed_request(method, url, json=None):
    """高速请求封装"""
    try:
        if method == 'GET':
            resp = session.get(url, timeout=TIMEOUT)
        else:
            resp = session.post(url, json=json, timeout=TIMEOUT)
        return resp.status_code, resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
    except Exception:
        return -1, {}


# ===================== 测试 1：暴力破解 =====================
def test_brute_force():
    print('=' * 60)
    print('🧪 测试 1：登录暴力破解防护')
    print('预期：5 次失败后锁定，返回 429/42900')
    print('=' * 60)

    url = f'{API_PREFIX}/v1/auth/login'
    lock_at = None

    for i in range(1, 10):
        code, data = speed_request('POST', url, json={
            'username': 'brute_test',
            'password': f'wrong_{i}'
        })

        c = data.get('code', code)
        msg = data.get('message', '')
        retry = data.get('data', {}).get('retry_after', '')

        if c in (429, 42900):
            if lock_at is None:
                lock_at = i
            status = '🔒 已锁定'
        elif c in (401, 40100):
            status = '❌ 密码错误'
        else:
            status = f'⚠️ 异常={c}'

        retry_info = f' 重试={retry}s' if retry else ''
        print(f' 第{i:2d}次 | {status} {msg}{retry_info}')

    print(f'\n✅ 结果：首次锁定在第 {lock_at} 次' if lock_at else '\n❌ 结果：未触发锁定')
    print()


# ===================== 测试 2：登录接口限流（20次/分钟）=====================
def test_login_rate_limit():
    print('=' * 60)
    print('🧪 测试 2：登录接口限流（20 次/分钟）')
    print('=' * 60)

    url = f'{API_PREFIX}/v1/auth/login'
    ok = 0
    block = 0
    limit_at = None

    def task():
        nonlocal ok, block, limit_at
        code, _ = speed_request('POST', url, json={'username': 'flood', 'password': '123'})
        if code in (429, 42900):
            block += 1
            if limit_at is None:
                limit_at = ok + block
        else:
            ok += 1

    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(task) for _ in range(35)]
        for f in futures:
            f.result()

    print(f' 正常：{ok} 次 | 限流：{block} 次')
    print(f' 首次限流在第 {limit_at} 次' if limit_at else '')
    print(f'  {"✅ 通过" if block > 0 else "❌ 未通过"}\n')


# ===================== 测试 3：全局 API 限流（120次/分钟）=====================
def test_global_rate_limit():
    print('=' * 60)
    print('🧪 测试 3：全局 API 限流（120 次/分钟）')
    print('=' * 60)

    url = f'{API_PREFIX}/v1/health'
    ok = 0
    block = 0

    def task():
        nonlocal ok, block
        code, _ = speed_request('GET', url)
        if code == 429:
            block += 1
        else:
            ok += 1

    with ThreadPoolExecutor(max_workers=30) as pool:
        futures = [pool.submit(task) for _ in range(150)]
        for f in futures:
            f.result()

    print(f' 正常：{ok} 次 | 限流：{block} 次')
    print(f'  {"✅ 通过" if block > 0 else "❌ 未通过"}\n')


# ===================== 测试 4：高并发洪水 =====================
def test_concurrent_flood():
    print('=' * 60)
    print('🧪 测试 4：高并发洪水（50线程 200次）')
    print('=' * 60)

    url = f'{API_PREFIX}/v1/health'
    ok = 0
    block = 0
    err = 0

    def task():
        nonlocal ok, block, err
        code, _ = speed_request('GET', url)
        if code == 200:
            ok += 1
        elif code == 429:
            block += 1
        else:
            err += 1

    with ThreadPoolExecutor(max_workers=50) as pool:
        futures = [pool.submit(task) for _ in range(200)]
        for f in futures:
            f.result()

    print(f' 成功：{ok} | 限流：{block} | 异常：{err}')
    print(f'  {"✅ 通过" if block > 0 else "❌ 未通过"}\n')


# ===================== 主流程 =====================
if __name__ == '__main__':
    print(f'\n🎯 压测目标：{BASE_URL}')
    print(f'⚠️  仅在测试环境执行！\n')

    test_brute_force()
    time.sleep(3)

    test_login_rate_limit()
    time.sleep(3)

    test_global_rate_limit()
    time.sleep(3)

    test_concurrent_flood()

    print('=' * 60)
    print('🏁 全部压测完成')
    print('=' * 60)