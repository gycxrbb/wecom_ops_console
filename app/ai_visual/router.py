"""Route aggregator for ai-visual module."""
from fastapi import APIRouter

from app.route_helper import UnifiedResponseRoute
from .routers import jobs

router = APIRouter(
    prefix="/api/v1/ai-visual",
    tags=["ai-visual"],
    route_class=UnifiedResponseRoute,
)
router.include_router(jobs.router)
