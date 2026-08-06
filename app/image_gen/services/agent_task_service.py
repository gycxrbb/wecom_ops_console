"""agent 生图任务化：提交(INSERT running) → 后台 asyncio 生图+存储+UPDATE → 查询。

复用 orchestrate_direct(write_history=False，只生图不落库)、storage_facade(七牛)、ImageGenHistory(任务表)。
落库两阶段：提交时 INSERT running 行(同步 await，保证轮询一定能查到)；后台跑完 UPDATE 成 success/failed。
与画廊 write_success(一次性 INSERT) 完全隔离——画廊同步路径不受影响。

进程重启时，在途的 asyncio task 丢失，启动由 cleanup_image_gen_running_rows 把残留 running 行标 failed。
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any

from app.database import SessionLocal
from app.services.storage.base import UploadPayload
from app.services.storage.facade import storage_facade

from ..models import ImageGenHistory
from .direct_orchestrator import DirectResult, orchestrate_direct
from .history_service import new_record_id
from .image_client import ImageGenerationError
from .provider_chain import NoProviderConfigured, ProviderConfig

_log = logging.getLogger(__name__)


async def submit_agent_image_task(
    *,
    operator_user_id: int | None,
    customer_id: int | None,
    prompt: str,
    providers: list[ProviderConfig],
    model: str | None = None,
    size: str = "auto",
    n: int = 1,
    quality: str = "auto",
) -> str:
    """提交 agent 生图任务：INSERT running 行 + 派后台 task。返回 task_id(=record_id)。"""
    record_id = new_record_id()
    params_json = json.dumps(
        {"size": size, "n": n, "quality": quality, "requested_model": model}, ensure_ascii=False
    )

    def _insert() -> None:
        db = SessionLocal()
        try:
            db.add(ImageGenHistory(
                record_id=record_id,
                operator_user_id=operator_user_id,
                customer_id=customer_id,
                mode="agent",
                prompt=prompt,
                params_json=params_json,
                model=model or "",
                status="running",
            ))
            db.commit()
        finally:
            db.close()

    await asyncio.to_thread(_insert)
    asyncio.create_task(_run_agent_image_task(
        record_id=record_id,
        operator_user_id=operator_user_id,
        customer_id=customer_id,
        prompt=prompt,
        providers=providers,
        model=model,
        size=size,
        n=n,
        quality=quality,
    ))
    return record_id


async def _run_agent_image_task(
    *,
    record_id: str,
    operator_user_id: int | None,
    customer_id: int | None,
    prompt: str,
    providers: list[ProviderConfig],
    model: str | None,
    size: str,
    n: int,
    quality: str,
) -> None:
    """后台执行：生图 → 七牛上传 → UPDATE running 行为 success/failed。"""
    started = time.perf_counter()
    try:
        result = await orchestrate_direct(
            operator_user_id=operator_user_id,
            customer_id=customer_id,
            prompt=prompt,
            providers=providers,
            model=model,
            size=size,
            n=n,
            quality=quality,
            record_id=record_id,
            write_history=False,
        )
        await _finalize_success(
            record_id=record_id,
            result=result,
            gen_ms=result.latency_ms,
            size=size,
            n=n,
            quality=quality,
            requested_model=model,
        )
    except (ImageGenerationError, NoProviderConfigured) as exc:
        await _finalize_failure(
            record_id=record_id,
            error_code=getattr(exc, "error_code", "image_gen_failed"),
            error_message=str(exc),
            gen_ms=int((time.perf_counter() - started) * 1000),
        )
    except Exception as exc:
        _log.exception("image_gen agent task %s unexpected error", record_id)
        await _finalize_failure(
            record_id=record_id,
            error_code="image_gen_failed",
            error_message=str(exc),
            gen_ms=int((time.perf_counter() - started) * 1000),
        )


async def _finalize_success(
    *,
    record_id: str,
    result: DirectResult,
    gen_ms: int,
    size: str,
    n: int,
    quality: str,
    requested_model: str | None,
) -> None:
    # 1. 先 UPDATE success（带 b64，前端轮询到 success 立刻显示图），不等七牛存储
    image_b64 = base64.b64encode(result.image_bytes).decode("ascii")

    def _mark_success() -> None:
        db = SessionLocal()
        try:
            params_with_timing = {
                "size": size, "n": n, "quality": quality, "requested_model": requested_model,
                "timing": {"gen_ms": gen_ms, "storage_ms": 0},
            }
            db.query(ImageGenHistory).filter(
                ImageGenHistory.record_id == record_id,
                ImageGenHistory.status == "running",
            ).update(
                {
                    "status": "success",
                    "model": result.model,
                    "provider_name": result.provider_name,
                    "latency_ms": gen_ms,
                    "params_json": json.dumps(params_with_timing, ensure_ascii=False),
                    "image_b64": image_b64,
                    "error_code": "",
                    "error_message": "",
                },
                synchronize_session=False,
            )
            db.commit()
            _log.info(
                "image_gen agent task %s success (b64 ready, storage background): gen=%dms provider=%s model=%s",
                record_id, gen_ms, result.provider_name, result.model,
            )
        finally:
            db.close()

    await asyncio.to_thread(_mark_success)

    # 2. 七牛存储后台 fire-and-forget，完成后 UPDATE url（前端不依赖 url 显示，b64 已就绪）
    asyncio.create_task(_upload_and_update_url_after_success(
        record_id=record_id, image_bytes=result.image_bytes, gen_ms=gen_ms,
        size=size, n=n, quality=quality, requested_model=requested_model,
    ))


async def _upload_and_update_url_after_success(
    *,
    record_id: str,
    image_bytes: bytes,
    gen_ms: int,
    size: str,
    n: int,
    quality: str,
    requested_model: str | None,
) -> None:
    """后台：上传七牛 + UPDATE url/storage 字段。失败仅告警（b64 已落库，前端显示不受影响）。"""
    def _do() -> None:
        db = SessionLocal()
        try:
            t0 = time.perf_counter()
            storage_result = storage_facade.upload(
                UploadPayload(
                    content=image_bytes,
                    filename=f"{record_id}.png",
                    mime_type="image/png",
                    object_key=f"image_gen/{record_id}.png",
                )
            )
            storage_ms = int((time.perf_counter() - t0) * 1000)
            params_with_timing = {
                "size": size, "n": n, "quality": quality, "requested_model": requested_model,
                "timing": {"gen_ms": gen_ms, "storage_ms": storage_ms},
            }
            db.query(ImageGenHistory).filter(
                ImageGenHistory.record_id == record_id,
                ImageGenHistory.status == "success",
            ).update(
                {
                    "latency_ms": gen_ms + storage_ms,
                    "params_json": json.dumps(params_with_timing, ensure_ascii=False),
                    "storage_provider": storage_result.provider,
                    "storage_key": storage_result.object_key,
                    "public_url": storage_result.public_url,
                },
                synchronize_session=False,
            )
            db.commit()
            _log.info(
                "image_gen agent task %s storage done: storage=%dms url=%s",
                record_id, storage_ms, storage_result.public_url,
            )
        except Exception:
            _log.warning("image_gen agent task %s background storage failed", record_id, exc_info=True)
        finally:
            db.close()

    await asyncio.to_thread(_do)


async def _finalize_failure(*, record_id: str, error_code: str, error_message: str, gen_ms: int) -> None:
    def _do() -> None:
        db = SessionLocal()
        try:
            db.query(ImageGenHistory).filter(
                ImageGenHistory.record_id == record_id,
                ImageGenHistory.status == "running",
            ).update(
                {
                    "status": "failed",
                    "error_code": error_code,
                    "error_message": (error_message or "")[:2000],
                    "latency_ms": gen_ms,
                },
                synchronize_session=False,
            )
            db.commit()
        finally:
            db.close()

    await asyncio.to_thread(_do)


async def get_agent_image_task(record_id: str) -> dict[str, Any] | None:
    """轮询查询单个任务，返回裸 JSON {task_id, status, data?, error?}。行不存在返回 None。"""
    def _do() -> ImageGenHistory | None:
        db = SessionLocal()
        try:
            return db.query(ImageGenHistory).filter(ImageGenHistory.record_id == record_id).first()
        finally:
            db.close()

    row = await asyncio.to_thread(_do)
    return _serialize_task(row) if row else None


def _serialize_task(row: ImageGenHistory) -> dict[str, Any]:
    task: dict[str, Any] = {"task_id": row.record_id, "status": row.status}
    if row.status == "success":
        task["data"] = [{
            "b64_json": row.image_b64 or "",
            "url": row.public_url or "",
            "record_id": row.record_id,
        }]
    elif row.status == "failed":
        task["error"] = {
            "code": row.error_code or "image_gen_failed",
            "message": row.error_message or "生图失败",
        }
    return task
