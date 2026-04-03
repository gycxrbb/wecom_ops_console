from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from .config import STATIC_DIR, settings
from .database import Base, engine, SessionLocal
from .routers.auth import router as auth_router
from .routers.pages import router as pages_router
from .routers.api import router as api_router
from .schema_migrations import ensure_schedule_schema, ensure_asset_folders_schema, ensure_plan_schema
from .routers.api_folders import router as folders_router
from .routers.api_operation_plans import router as operation_plans_router
from .services.seed import seed_all

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schedule_schema(engine)
    ensure_asset_folders_schema(engine)
    ensure_plan_schema(engine)
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()
    yield

app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.app_secret_key)
app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')
app.include_router(auth_router)
app.include_router(pages_router)
app.include_router(api_router)
app.include_router(folders_router)
app.include_router(operation_plans_router)
