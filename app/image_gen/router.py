"""路由聚合。

两个子路由器职责不同，刻意分开：
- api_router：统一响应格式（UnifiedResponseRoute），供 Vue 后台调用（providers/history）
- proxy_router：裸 JSON / OpenAI 兼容，供 React gpt_image_playground 调用（不包装，否则 React 客户端无法解析）
"""
from fastapi import APIRouter

from app.route_helper import UnifiedResponseRoute

from .routers import agent as agent_router
from .routers import history as history_router
from .routers import prompts as prompts_router
from .routers import providers as providers_router
from .routers import proxy as proxy_router

router = APIRouter()

unified_api = APIRouter(
    prefix="/api/v1/image-gen",
    tags=["image-gen"],
    route_class=UnifiedResponseRoute,
)
unified_api.include_router(providers_router.router)
unified_api.include_router(history_router.router)

raw_proxy = APIRouter(
    prefix="/api/image-gen/v1",
    tags=["image-gen-proxy"],
)
raw_proxy.include_router(proxy_router.router)

# agent 辅助端点（playground fetch 调用，裸 JSON，不包装）：customer-profile / history-callback
raw_api = APIRouter(
    prefix="/api/v1/image-gen",
    tags=["image-gen-agent"],
)
raw_api.include_router(agent_router.router)
raw_api.include_router(prompts_router.router)

router.include_router(unified_api)
router.include_router(raw_proxy)
router.include_router(raw_api)
