# 登录安全与 DDoS 防护调查报告

> **调查日期**: 2026-04-28
> **调查范围**: 登录暴力破解防护、API 层面安全、DDoS 防护

---

## 一、登录暴力破解防护：现状

### 1.1 已有防护

系统已实现 **基于 IP + 用户名的滑动窗口限流**，代码位于 `app/services/login_rate_limiter.py`：

| 参数 | 值 | 含义 |
|------|----|------|
| `MAX_ATTEMPTS` | 5 | 窗口内最大失败次数 |
| `WINDOW_SECONDS` | 900 (15 分钟) | 滑动窗口长度 |
| `LOCKOUT_SECONDS` | 900 (15 分钟) | 锁定时长 |

**工作流程**：
1. 用户登录前，调用 `rate_limiter.check(client_ip, username)` 检查是否被锁定
2. 登录失败 → `rate_limiter.record_failure(client_ip, username)` 记录
3. 登录成功 → `rate_limiter.reset(client_ip, username)` 清空记录
4. 15 分钟内同一 IP + 用户名累计失败 5 次 → 锁定 15 分钟

**密码安全**：
- 前端到后端：密码经 **RSA 加密** 传输（每次启动生成临时密钥对）
- 数据库存储：密码使用 **PBKDF2-SHA256（29000 轮）** 哈希，且使用 `hmac.compare_digest` 做时间安全比较

### 1.2 存在的薄弱点

#### 薄弱点 1（中等）：旧登录入口 `/login` 无暴力破解防护

系统存在 **两个登录入口**：

| 入口 | 文件 | 暴力破解防护 |
|------|------|-------------|
| `POST /api/v1/auth/login` | `app/routers/api.py` L42 | ✅ 有 `rate_limiter` |
| `POST /login` | `app/routers/auth.py` L10 | ❌ **无任何防护** |

`/login` 是旧的 Form-based 登录入口，直接调用 `authenticate()` 后设置 session，**完全没有调用 `rate_limiter`**。攻击者可以绕过 `/api/v1/auth/login` 的限流，直接对 `/login` 进行暴力破解。

#### 薄弱点 2（中等）：限流状态为进程内内存

```python
_attempts: dict[str, list[float]] = defaultdict(list)
```

- 进程重启后限流记录清空
- 多 worker 进程不共享（当前单进程部署影响小）
- 攻击者只需等待部署/重启即可重置计数

#### 薄弱点 3（低）：限流维度仅 IP + 用户名

- 攻击者可以用**不同用户名**穷举同一 IP，不触发锁定（但只要目标用户名固定仍有效）
- 缺少**纯 IP 维度**限流：同一 IP 大量尝试不同用户名不会被拦截

#### 薄弱点 4（低）：登录成功后 reset 清空所有记录

`rate_limiter.reset()` 在登录成功后清空该 IP+用户名 的所有失败记录。攻击者如果知道正确密码，可以在锁定期间用正确密码登录一次来重置计数，然后继续爆破其他账号。不过实际场景中如果攻击者已知正确密码，爆破本身意义不大。

---

## 二、JWT / 会话安全

### 2.1 JWT 配置

| 项目 | 值 | 评估 |
|------|----|------|
| 算法 | HS256 | ✅ 标准 |
| Access Token 有效期 | 1440 分钟（24 小时） | ⚠️ 偏长，建议 1-2 小时 |
| Refresh Token 有效期 | 7 天 | ✅ 合理 |
| Secret Key | 配置项 `jwt_secret_key` | ⚠️ 默认值为弱密钥（已有启动警告） |

### 2.2 安全默认值检查

`app/main.py` L116-121 已实现启动时检查弱密钥并打印警告：

```python
_INSECURE_SECRETS = {'change-me', 'your-256-bit-secret-key-change-me'}
if settings.app_secret_key in _INSECURE_SECRETS:
    _log.warning('⚠️  APP_SECRET_KEY 仍为默认值...')
if settings.jwt_secret_key in _INSECURE_SECRETS:
    _log.warning('⚠️  JWT_SECRET_KEY 仍为默认值...')
```

**但仅打印警告，不阻止启动**。如果生产环境忘记配置 `.env`，系统将以弱密钥运行。

### 2.3 Session 安全

- 使用 Starlette `SessionMiddleware`，密钥为 `app_secret_key`
- Session 数据存储在客户端 Cookie 中（签名但未加密）

---

## 三、DDoS 防护评估

### 3.1 当前架构

```
浏览器 → Nginx(:8080/443) → Docker(:8000) FastAPI
```

### 3.2 Nginx 层

根据 `deploy-guide.md` 中的 Nginx 配置，**未发现任何 `limit_req` / `limit_conn` 配置**。当前 Nginx 仅做反向代理和 HTTPS 终结，**没有请求频率限制**。

### 3.3 应用层

| 防护项 | 状态 |
|--------|------|
| 全局 API 限流中间件（如 slowapi） | ❌ 未安装 |
| 请求体大小限制 | ⚠️ Nginx 配置了 `client_max_body_size 100m`，FastAPI 未配置 |
| 安全响应头（X-Frame-Options 等） | ❌ 未配置 |
| CORS | ✅ 有，但 `cors_allowed_origins` 留空时不启用 |
| Webhook 端点鉴权 | ⚠️ `/webhook/deploy` 用简单 query param 校验 |

### 3.4 DDoS 风险评估

| 攻击面 | 风险级别 | 说明 |
|--------|---------|------|
| **登录接口洪水攻击** | 🔴 高 | `/login` 完全无限流，`/api/v1/auth/login` 仅限流失败请求，成功的正常请求无限制 |
| **API 接口洪水攻击** | 🔴 高 | 所有 API 无全局频率限制，大量请求可耗尽服务器资源 |
| **文件上传攻击** | 🟡 中 | 100MB 上传限制 + 无频率限制 = 可通过大量大文件上传耗尽磁盘/带宽 |
| **AI 接口滥用** | 🟡 中 | AI 对话接口调用外部 API 有成本，无频率限制可导致账单激增 |
| **部署 Webhook** | 🟢 低 | 有简单鉴权，但可被暴力穷举 key |

### 3.5 核心结论

**系统目前没有任何 DDoS 防护能力**。单进程 uvicorn 在面对并发攻击时非常脆弱，所有保护都依赖 Nginx，但 Nginx 也未配置任何限流规则。

---

## 四、各项总评

| 安全项 | 评分 | 说明 |
|--------|------|------|
| 密码存储 | ✅ 良好 | PBKDF2-SHA256 29000 轮 + 时间安全比较 |
| 密码传输 | ✅ 良好 | RSA 加密 + HTTPS |
| 登录暴力破解防护 | ⚠️ 部分 | 主入口有，旧入口 `/login` 缺失 |
| JWT 安全 | ⚠️ 部分 | 有效期偏长，弱密钥仅警告不阻断 |
| API 全局限流 | ❌ 缺失 | 无 slowapi 或类似中间件 |
| Nginx 限流 | ❌ 缺失 | 无 limit_req / limit_conn |
| 安全响应头 | ❌ 缺失 | 无 X-Frame-Options / CSP / HSTS 等 |
| DDoS 防护 | ❌ 缺失 | 应用层和 Nginx 层均无防护 |

---

## 五、建议优先级

### P0（建议立即修复）

1. **旧登录入口加暴力破解防护** — `/login` 路由添加 `rate_limiter` 调用，与 `/api/v1/auth/login` 一致
2. **Nginx 添加 `limit_req`** — 至少对登录和 API 接口做基本频率限制

### P1（建议近期处理）

3. **添加纯 IP 维度限流** — 同一 IP 短时间内大量请求（不管用户名）直接封锁
4. **缩短 JWT Access Token 有效期** — 从 24 小时改为 1-2 小时，依赖 Refresh Token 续期
5. **添加安全响应头** — `X-Frame-Options`、`X-Content-Type-Options`、`Strict-Transport-Security`

### P2（建议长期规划）

6. **引入 slowapi 或类似全局 API 限流** — 对高频调用的 API 接口加限流
7. **限流状态迁移至 Redis** — 利用已有的 Redis 实例，实现跨进程、跨重启的持久化限流
8. **添加登录验证码** — 连续失败 3 次后要求验证码
9. **接入云 WAF / CDN** — 在 Nginx 前增加一层 DDoS 防护

---

## 六、相关文件清单

| 文件 | 作用 |
|------|------|
| `app/services/login_rate_limiter.py` | 登录暴力破解防护（滑动窗口限流） |
| `app/routers/api.py` L42-85 | API 登录入口（有防护） |
| `app/routers/auth.py` L10-23 | 旧 Form 登录入口（**无防护**） |
| `app/security.py` | RSA 加密、JWT、密码哈希、认证逻辑 |
| `app/password_utils.py` | PBKDF2-SHA256 密码哈希实现 |
| `app/main.py` L114-134 | CORS、Session 中间件、弱密钥检查 |
| `deploy-guide.md` L249-290 | Nginx 配置（无限流规则） |
