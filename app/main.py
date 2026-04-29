from contextlib import asynccontextmanager
import asyncio
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from .config import STATIC_DIR, UPLOAD_DIR, FRONTEND_DIR, DATA_DIR, settings
from .database import Base, engine, SessionLocal
from .middleware.ip_rate_limit import IPRateLimitMiddleware, cleanup_buckets as _cleanup_ip_buckets
from .routers.auth import router as auth_router
from .routers.pages import router as pages_router
from .routers.api import router as api_router
from .schema_migrations import ensure_schedule_schema, ensure_asset_folders_schema, ensure_plan_schema, ensure_user_profile_schema, ensure_external_docs_schema, ensure_rag_schema, ensure_speech_category_schema
from .routers.api_folders import router as folders_router
from .routers.api_operation_plans import router as operation_plans_router
from .routers.api_profile import router as profile_router
from .routers.api_schedule_tools import router as schedule_tools_router
from .routers.api_permissions import router as permissions_router
from .routers.api_sop import router as sop_router
from .routers.api_system_docs import router as system_docs_router
from .routers.api_crm_groups import router as crm_groups_router
from .routers.api_crm_points import router as crm_points_router
from .routers.api_speech_templates import router as speech_templates_router
from .routers.api_external_docs import router as external_docs_router
from .routers.api_rag import router as rag_router
from .services.seed import seed_all
from .services.scheduler_service import schedule_service
import hashlib

_log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine, checkfirst=True)
    ensure_schedule_schema(engine)
    ensure_asset_folders_schema(engine)
    ensure_plan_schema(engine)
    ensure_user_profile_schema(engine)
    ensure_external_docs_schema(engine)
    ensure_rag_schema(engine)
    ensure_speech_category_schema(engine)
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()
    schedule_service.start()
    schedule_service.sync_from_db()

    # AI client warmup: pre-establish TLS/TCP connections
    asyncio.create_task(_ai_warmup())
    asyncio.create_task(_ai_keepalive_loop())
    asyncio.create_task(_ip_rate_limit_cleanup_loop())
    if settings.crm_profile_enabled:
        asyncio.create_task(_crm_profile_cache_cleanup_loop())
        asyncio.create_task(_crm_profile_cache_refresh_loop())

    yield
    try:
        from .clients.ai_chat_client import _close_client
        await _close_client()
    except Exception:
        pass
    schedule_service.shutdown()


async def _ai_warmup():
    """Warm up AI client connections on startup."""
    try:
        from .clients.ai_chat_client import _get_client
        client = await _get_client()
        if settings.ai_provider == 'deepseek' and settings.deepseek_api_key:
            url = settings.deepseek_base_url
        else:
            url = settings.ai_base_url or 'https://aihubmix.com/v1'
        await client.head(url, timeout=3.0)
        _log.info('AI client warmup done')
    except Exception:
        pass


async def _ai_keepalive_loop():
    """Periodic HEAD request to keep AI connections alive."""
    while True:
        await asyncio.sleep(60)
        try:
            from .clients.ai_chat_client import _get_client
            client = await _get_client()
            if settings.ai_provider == 'deepseek' and settings.deepseek_api_key:
                url = settings.deepseek_base_url
            else:
                url = settings.ai_base_url
            await client.head(url, timeout=5.0)
        except Exception:
            pass


async def _crm_profile_cache_cleanup_loop():
    """Periodically clean expired CRM AI profile L2 snapshots."""
    while True:
        try:
            from .crm_profile.services.profile_context_cache import cleanup_expired_profile_cache
            deleted = await asyncio.get_event_loop().run_in_executor(None, cleanup_expired_profile_cache)
            if deleted:
                _log.info("CRM AI profile cache cleanup deleted %s expired snapshots", deleted)
        except Exception:
            _log.exception("CRM AI profile cache cleanup failed")
        await asyncio.sleep(6 * 60 * 60)


async def _crm_profile_cache_refresh_loop():
    """Periodically refresh L2 cache entries that are about to expire."""
    while True:
        await asyncio.sleep(30 * 60)  # every 30 min
        try:
            from .crm_profile.services.profile_context_cache import refresh_expiring_cache_entries
            refreshed = await asyncio.get_event_loop().run_in_executor(None, refresh_expiring_cache_entries)
            if refreshed:
                _log.info("CRM AI profile cache refreshed %s expiring entries", refreshed)
        except Exception:
            _log.exception("CRM profile cache refresh failed")

async def _ip_rate_limit_cleanup_loop():
    """定期清理 IP 限流桶过期记录，防止内存泄漏。"""
    while True:
        await asyncio.sleep(300)
        try:
            _cleanup_ip_buckets()
        except Exception:
            pass

app = FastAPI(title=settings.app_name, lifespan=lifespan)

# ── 安全默认值检查 ──
_INSECURE_SECRETS = {'change-me', 'your-256-bit-secret-key-change-me'}
if settings.app_secret_key in _INSECURE_SECRETS:
    _log.warning('⚠️  APP_SECRET_KEY 仍为默认值，请在 .env 中设置一个强随机密钥！')
if settings.jwt_secret_key in _INSECURE_SECRETS:
    _log.warning('⚠️  JWT_SECRET_KEY 仍为默认值，请在 .env 中设置一个独立的强随机密钥！')

app.add_middleware(SessionMiddleware, secret_key=settings.app_secret_key)
app.add_middleware(IPRateLimitMiddleware)

# ── CORS ──
_cors_origins = [o.strip() for o in settings.cors_allowed_origins.split(',') if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )


# === GitHub Webhook 自动部署 ===
WEBHOOK_SECRET = settings.app_secret_key  # 复用 APP_SECRET_KEY 作为签名密钥
DEPLOY_TRIGGER = DATA_DIR / 'deploy.trigger'

@app.post('/webhook/deploy')
async def github_webhook(request: Request):
    # 简单鉴权：通过 query parameter 传 key
    key = request.query_params.get('key', '')
    expected_key = hashlib.sha256(WEBHOOK_SECRET.encode()).hexdigest()[:16]
    if key != expected_key:
        return {"error": "unauthorized"}

    # 写触发文件，由主机 cron 检测并执行部署
    DEPLOY_TRIGGER.write_text('triggered')
    return {"status": "deploy triggered"}


app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')
app.mount('/uploads', StaticFiles(directory=str(UPLOAD_DIR)), name='uploads')
app.include_router(auth_router)
app.include_router(pages_router)
app.include_router(api_router)
app.include_router(folders_router)
app.include_router(operation_plans_router)
app.include_router(profile_router)
app.include_router(schedule_tools_router)
app.include_router(permissions_router)
app.include_router(sop_router)
app.include_router(system_docs_router)
app.include_router(crm_groups_router)
app.include_router(crm_points_router)
app.include_router(speech_templates_router)
app.include_router(external_docs_router)
app.include_router(rag_router)

if settings.crm_profile_enabled:
    from .crm_profile import router as crm_profile_router, init_models
    init_models()
    app.include_router(crm_profile_router)

# Vue SPA 前端（必须在所有 API 路由之后 mount）
if FRONTEND_DIR.exists():
    from fastapi.responses import FileResponse
    import os

    @app.get('/{full_path:path}')
    async def serve_spa(full_path: str):
        file_path = FRONTEND_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIR / 'index.html'))
