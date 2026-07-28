"""直出生图编排：选供应商 → 生图 → 存七牛 → 记历史 → 审计。

生成(httpx async,await 期间不阻塞事件循环) + 存储/落库(线程池 asyncio.to_thread)，
全程不卡其他请求。providers 由调用方预先加载并**在生成前释放 DB 连接**(避免数分钟生图期间
占用连接池)。计时：gen_ms(纯生成)与 storage_ms(七牛+落库)分摊记录，便于定位瓶颈。
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from .history_service import (
    finish_audit,
    new_record_id,
    start_audit,
    write_failure,
    write_success,
)
from .image_client import ImageGenerationError, edit_with_provider, generate_with_provider
from .provider_chain import NoProviderConfigured, ProviderConfig

_log = logging.getLogger(__name__)


@dataclass
class DirectResult:
    record_id: str
    provider_name: str
    model: str
    image_bytes: bytes
    public_url: str
    latency_ms: int
    metadata: dict


async def orchestrate_direct(
    *,
    operator_user_id: int | None,
    customer_id: int | None,
    prompt: str,
    providers: list[ProviderConfig],
    model: str | None = None,
    size: str = "auto",
    n: int = 1,
    quality: str = "auto",
) -> DirectResult:
    if not providers:
        raise NoProviderConfigured("没有可用的生图供应商，请联系管理员配置")

    record_id = new_record_id()
    params = {"size": size, "n": n, "quality": quality, "requested_model": model}
    start_audit(
        call_id=record_id,
        operator_user_id=operator_user_id,
        customer_id=customer_id,
        mode="direct",
    )

    started = time.perf_counter()
    last_error: Exception | None = None
    last_provider = providers[0]
    for provider in providers:
        last_provider = provider
        try:
            image_bytes, meta = await generate_with_provider(
                provider, prompt=prompt, model=model, size=size, n=n, quality=quality
            )
            gen_ms = int((time.perf_counter() - started) * 1000)
            # 存储七牛 + 历史放后台 fire-and-forget，不阻塞响应（前端用 b64 显示图，url 由后台填入历史行）。
            # 否则大图(9MB+)七牛上传慢/重试时，前端要干等几分钟才看到图。
            asyncio.create_task(write_success(
                record_id=record_id,
                operator_user_id=operator_user_id,
                customer_id=customer_id,
                mode="direct",
                prompt=prompt,
                params=params,
                model=meta["model"],
                provider_name=provider.name,
                image_bytes=image_bytes,
                gen_ms=gen_ms,
                audit_call_id=record_id,
            ))
            finish_audit(
                call_id=record_id,
                model=meta["model"],
                provider_name=provider.name,
                latency_ms=gen_ms,
                prompt_chars=meta.get("prompt_chars", 0),
                status="success",
            )
            return DirectResult(
                record_id=record_id,
                provider_name=provider.name,
                model=meta["model"],
                image_bytes=image_bytes,
                public_url="",
                latency_ms=gen_ms,
                metadata=meta,
            )
        except ImageGenerationError as exc:
            last_error = exc
            _log.warning(
                "image_gen provider %s failed (%s): %s",
                provider.name,
                exc.error_code,
                exc,
            )
            continue  # P0 单供应商仅一轮；P1 加 _is_failover_eligible 仅对基础设施错误切换

    gen_ms = int((time.perf_counter() - started) * 1000)
    err = last_error or RuntimeError("image generation failed")
    code = getattr(err, "error_code", "image_gen_failed")
    await write_failure(
        record_id=record_id,
        operator_user_id=operator_user_id,
        customer_id=customer_id,
        mode="direct",
        prompt=prompt,
        params=params,
        model=model or last_provider.default_model,
        provider_name=last_provider.name,
        error_code=code,
        error_message=str(err),
        gen_ms=gen_ms,
        audit_call_id=record_id,
    )
    finish_audit(
        call_id=record_id,
        model=model or last_provider.default_model,
        provider_name=last_provider.name,
        latency_ms=gen_ms,
        prompt_chars=len(prompt),
        status="failed",
        error_code=code,
    )
    raise err


async def orchestrate_edit(
    *,
    operator_user_id: int | None,
    customer_id: int | None,
    prompt: str,
    providers: list[ProviderConfig],
    images: list[tuple[str, bytes, str]],
    model: str | None = None,
    size: str = "1024x1024",
    n: int = 1,
    mask: tuple[str, bytes, str] | None = None,
) -> DirectResult:
    """参考图编辑编排（直出同步）：选供应商 → /images/edits → 存七牛 → 记历史 → 审计。"""
    if not providers:
        raise NoProviderConfigured("没有可用的生图供应商，请联系管理员配置")

    record_id = new_record_id()
    params = {
        "size": size, "n": n, "requested_model": model, "mode": "edit",
        "ref_images": len(images), "has_mask": mask is not None,
    }
    start_audit(
        call_id=record_id, operator_user_id=operator_user_id,
        customer_id=customer_id, mode="edit",
    )

    started = time.perf_counter()
    last_error: Exception | None = None
    last_provider = providers[0]
    for provider in providers:
        last_provider = provider
        try:
            image_bytes, meta = await edit_with_provider(
                provider, prompt=prompt, images=images, model=model, size=size, n=n, mask=mask,
            )
            gen_ms = int((time.perf_counter() - started) * 1000)
            # 存储七牛 + 历史放后台，不阻塞响应（同 orchestrate_direct）
            asyncio.create_task(write_success(
                record_id=record_id, operator_user_id=operator_user_id, customer_id=customer_id,
                mode="edit", prompt=prompt, params=params, model=meta["model"],
                provider_name=provider.name, image_bytes=image_bytes, gen_ms=gen_ms, audit_call_id=record_id,
            ))
            finish_audit(
                call_id=record_id, model=meta["model"], provider_name=provider.name,
                latency_ms=gen_ms, prompt_chars=meta.get("prompt_chars", 0), status="success",
            )
            return DirectResult(
                record_id=record_id, provider_name=provider.name, model=meta["model"],
                image_bytes=image_bytes, public_url="", latency_ms=gen_ms, metadata=meta,
            )
        except ImageGenerationError as exc:
            last_error = exc
            _log.warning("image_gen edit provider %s failed (%s): %s", provider.name, exc.error_code, exc)
            continue

    gen_ms = int((time.perf_counter() - started) * 1000)
    err = last_error or RuntimeError("image edit failed")
    code = getattr(err, "error_code", "image_gen_failed")
    await write_failure(
        record_id=record_id, operator_user_id=operator_user_id, customer_id=customer_id,
        mode="edit", prompt=prompt, params=params, model=model or last_provider.default_model,
        provider_name=last_provider.name, error_code=code, error_message=str(err),
        gen_ms=gen_ms, audit_call_id=record_id,
    )
    finish_audit(
        call_id=record_id, model=model or last_provider.default_model,
        provider_name=last_provider.name, latency_ms=gen_ms, prompt_chars=len(prompt),
        status="failed", error_code=code,
    )
    raise err
