# AI 对话迁移 — 企微后端改动实施计划

> 目标：让企微后端能识别 CRM 前端发来的 JWT token，使 CRM 前端能直接调用企微 AI 对话接口。
> 改动范围：仅企微后端（本仓库），不涉及 CRM 前端代码。

---

## 改动总览

| 文件 | 改动 | 行数估计 |
|---|---|---|
| `app/config.py` | 新增 4 个 CRM token 配置项 | ~4 行 |
| `app/security.py` | `get_current_user` 增加 CRM JWT fallback | ~25 行 |
| `app/services/crm_admin_auth.py` | 新增 `get_or_create_user_by_crm_admin_id` | ~20 行 |

不需要改动：
- 路由层（AI 接口签名不变）
- AI 服务层（业务逻辑不变）
- 数据库模型（`users.crm_admin_id` 已存在）

---

## 步骤 1：config.py — 新增 CRM token 配置

在 `app/config.py` 的 `Settings` 类中，紧跟现有 `crm_admin_*` 字段之后新增：

```python
# CRM JWT token fallback（供 CRM 前端直连 AI 接口）
crm_jwt_secret_key: str = ''                                # CRM 后端 APP_PUBLIC_KEY
crm_token_strict_redis_check: bool = False                  # 是否强制 Redis token 比对
```

.env 新增：

```env
CRM_JWT_SECRET_KEY=123456
CRM_TOKEN_STRICT_REDIS_CHECK=false
```

说明：
- `crm_jwt_secret_key` 对应 CRM 后端的 `APP_PUBLIC_KEY`，用于验证 CRM 签发的 JWT 签名
- `crm_token_strict_redis_check` 开发期关闭，生产环境建议开启

---

## 步骤 2：crm_admin_auth.py — 新增按 crm_admin_id 获取/创建用户

在现有文件末尾新增函数：

```python
def get_or_create_user_by_crm_admin_id(db: Session, crm_admin_id: int) -> models.User | None:
    """根据 crm_admin_id 查找本地用户，不存在则从 CRM DB 同步创建。"""
    user = db.query(models.User).filter(
        models.User.crm_admin_id == crm_admin_id,
        models.User.status == 1,
    ).first()
    if user:
        return user

    # 本地不存在，尝试从 CRM DB 拉取并同步
    if not crm_admin_auth_enabled():
        return None

    try:
        admins = fetch_all_crm_admins()
    except CrmAdminAuthUnavailable:
        return None

    admin = next((a for a in admins if int(a.get("id") or 0) == crm_admin_id), None)
    if not admin:
        return None

    return sync_crm_admin_to_local(db, admin)
```

逻辑：
1. 按 `crm_admin_id` 查本地 users 表
2. 找到 → 直接返回
3. 找不到且 CRM DB 可用 → 从 CRM 数据库拉取该管理员信息 → 调用现有 `sync_crm_admin_to_local` 创建
4. 创建的用户角色为 `coach`，权限为 `{}`（由 `sync_crm_admin_to_local` 已有逻辑处理）

---

## 步骤 3：security.py — get_current_user 增加 CRM JWT fallback

在 `get_current_user` 函数中，企微 JWT 解析失败后、session fallback 之前，插入 CRM token fallback：

```python
def get_current_user(request: Request, db: Session):
    user_id = None

    # 1. 企微 JWT Bearer token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            user_id = payload.get("sub")
        except PyJWTError:
            pass

        # 2. CRM JWT fallback（企微 JWT 解析失败时尝试）
        if not user_id and settings.crm_jwt_secret_key:
            user = _try_crm_token_fallback(token, db)
            if user:
                return user

    # 3. Session fallback
    if not user_id:
        user_id = request.session.get('user_id')

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')

    user = db.query(models.User).filter(models.User.id == int(user_id), models.User.status == 1).first()
    if not user:
        if 'user_id' in request.session:
            request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
    return user


def _try_crm_token_fallback(token: str, db: Session):
    """尝试用 CRM JWT 密钥解析 token，成功则映射到本地用户。"""
    from .services.crm_admin_auth import get_or_create_user_by_crm_admin_id

    try:
        payload = jwt.decode(token, settings.crm_jwt_secret_key, algorithms=['HS256'])
    except PyJWTError:
        return None

    crm_admin_id = payload.get("id")
    if not crm_admin_id:
        return None

    return get_or_create_user_by_crm_admin_id(db, int(crm_admin_id))
```

关键点：
- CRM JWT payload 字段是 `id`（不是企微的 `sub`）
- 先走企微 JWT，失败后才走 CRM JWT，不影响现有认证
- `crm_jwt_secret_key` 为空时直接跳过，无需配置即不影响原有行为
- 自动创建的本地用户带 `crm_admin_id`，后续 CRM 请求可直接命中

---

## 验证步骤

1. 在 `.env` 中配置 `CRM_JWT_SECRET_KEY=123456`（CRM 后端的 APP_PUBLIC_KEY）
2. 重启企微后端
3. 用 CRM 后端签发一个测试 token：

```python
import jwt
token = jwt.sign({"id": 1}, "123456", algorithm="HS256")
```

4. 用该 token 调用企微 AI 接口：

```bash
curl -H "Authorization: Bearer <crm_test_token>" \
     http://localhost:8000/api/v1/crm-customers/892/ai/config
```

5. 确认：
   - 返回 200 + AI 配置数据
   - 后端日志无报错
   - 本地 users 表自动创建了 `crm_admin_id=1` 的用户
   - 企微原有登录 token 仍然正常可用

---

## 生产部署注意

1. `CRM_TOKEN_STRICT_REDIS_CHECK` 建议生产改为 `true`
2. 企微后端需能访问 CRM Redis（`mfg-crm:sys:token:{userId}`）
3. Redis 比对逻辑作为 known gap，如暂不具备条件需在部署文档中标明
