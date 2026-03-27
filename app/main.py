from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from .config import STATIC_DIR, settings
from .database import Base, engine, SessionLocal
from .routers.auth import router as auth_router
from .routers.pages import router as pages_router
from .routers.api import router as api_router
from .services.seed import seed_all
from .services.scheduler_service import schedule_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
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
app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')
app.include_router(auth_router)
app.include_router(pages_router)
app.include_router(api_router)
