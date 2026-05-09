"""CRM Customer 360 Profile HTTP endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from ..config import settings
from ..route_helper import UnifiedResponseRoute
from .routers import customers, profile, ai_config

router = APIRouter(
    prefix="/api/v1/crm-customers",
    tags=["crm-customers"],
    route_class=UnifiedResponseRoute,
)

router.include_router(customers.router)
router.include_router(profile.router)
router.include_router(ai_config.router)

# AI Coach endpoints (only when ai_coach_enabled)
_ai_coach_enabled = settings.ai_coach_enabled or (bool(settings.ai_api_key) and settings.crm_profile_enabled)

if _ai_coach_enabled:
    from .routers import ai_coach, ai_attachment, ai_feedback_admin
    router.include_router(ai_coach.router)
    router.include_router(ai_attachment.router)
    router.include_router(ai_feedback_admin.router)
