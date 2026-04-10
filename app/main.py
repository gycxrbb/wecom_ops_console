from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from .config import STATIC_DIR, UPLOAD_DIR, FRONTEND_DIR, DATA_DIR, settings
from .database import Base, engine, SessionLocal
from .routers.auth import router as auth_router
from .routers.pages import router as pages_router
from .routers.api import router as api_router
from .schema_migrations import ensure_schedule_schema, ensure_asset_folders_schema, ensure_plan_schema, ensure_user_profile_schema
from .routers.api_folders import router as folders_router
from .routers.api_operation_plans import router as operation_plans_router
from .routers.api_profile import router as profile_router
from .routers.api_schedule_tools import router as schedule_tools_router
from .routers.api_permissions import router as permissions_router
from .services.seed import seed_all
from .services.scheduler_service import schedule_service
import hashlib

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine, checkfirst=True)
    ensure_schedule_schema(engine)
    ensure_asset_folders_schema(engine)
    ensure_plan_schema(engine)
    ensure_user_profile_schema(engine)
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()
    schedule_service.start()
    schedule_service.sync_from_db()
    yield
    schedule_service.shutdown()

app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.app_secret_key)


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
