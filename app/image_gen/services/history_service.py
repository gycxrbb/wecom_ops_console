"""生图历史 + 审计接入。

存储上传(七牛,同步 httpx)和历史落库(SQLAlchemy)都放线程池执行(asyncio.to_thread),
不阻塞事件循环 —— 生图期间不卡其他请求。写操作各自用独立 SessionLocal(MySQL 连接用完即还,
不长时间占用连接池)。审计走 invocation_audit(scene_key=image_gen),fire-and-forget。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.crm_profile.services.invocation_audit import (
    fail_invocation,
    finish_invocation,
    start_invocation,
    write_step,
)
from app.database import SessionLocal
from app.services.storage.base import UploadPayload
from app.services.storage.facade import storage_facade

from ..models import ImageGenHistory

_log = logging.getLogger(__name__)

SCENE_KEY = "image_gen"
STAGE_GENERATION = "visual_generation"
STEP_KIND = "visual_generation"


def new_record_id() -> str:
    return uuid.uuid4().hex


async def write_success(
    *,
    record_id: str,
    operator_user_id: int | None,
    customer_id: int | None,
    mode: str,
    prompt: str,
    params: dict[str, Any],
    model: str,
    provider_name: str,
    image_bytes: bytes,
    gen_ms: int,
    audit_call_id: str | None,
) -> str:
    """七牛存储 + 历史落库，全部在线程池执行(不阻塞 loop)，独立 Session。返回 public_url。

    记录 gen_ms / storage_ms 分摊到 params_json.timing 并打日志，便于定位耗时来源。
    """

    def _do() -> str:
        db = SessionLocal()
        try:
            t0 = time.perf_counter()
            result = storage_facade.upload(
                UploadPayload(
                    content=image_bytes,
                    filename=f"{record_id}.png",
                    mime_type="image/png",
                    object_key=f"image_gen/{record_id}.png",
                )
            )
            storage_ms = int((time.perf_counter() - t0) * 1000)
            params_with_timing = {**params, "timing": {"gen_ms": gen_ms, "storage_ms": storage_ms}}
            row = ImageGenHistory(
                record_id=record_id,
                operator_user_id=operator_user_id,
                customer_id=customer_id,
                mode=mode,
                prompt=prompt,
                params_json=json.dumps(params_with_timing, ensure_ascii=False),
                model=model,
                provider_name=provider_name,
                latency_ms=gen_ms + storage_ms,
                status="success",
                storage_provider=result.provider,
                storage_key=result.object_key,
                public_url=result.public_url,
                audit_call_id=audit_call_id,
            )
            db.add(row)
            db.commit()
            _log.info(
                "image_gen timing: gen=%dms storage=%dms total=%dms provider=%s model=%s size=%s",
                gen_ms,
                storage_ms,
                gen_ms + storage_ms,
                provider_name,
                model,
                params.get("size"),
            )
            return result.public_url
        finally:
            db.close()

    return await asyncio.to_thread(_do)


async def write_failure(
    *,
    record_id: str,
    operator_user_id: int | None,
    customer_id: int | None,
    mode: str,
    prompt: str,
    params: dict[str, Any],
    model: str,
    provider_name: str,
    error_code: str,
    error_message: str,
    gen_ms: int,
    audit_call_id: str | None,
) -> None:
    def _do() -> None:
        db = SessionLocal()
        try:
            row = ImageGenHistory(
                record_id=record_id,
                operator_user_id=operator_user_id,
                customer_id=customer_id,
                mode=mode,
                prompt=prompt,
                params_json=json.dumps(params, ensure_ascii=False),
                model=model,
                provider_name=provider_name,
                latency_ms=gen_ms,
                status="failed",
                error_code=error_code,
                error_message=(error_message or "")[:2000],
                audit_call_id=audit_call_id,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

    await asyncio.to_thread(_do)


def list_history(
    db: Session,
    *,
    customer_id: int | None = None,
    mode: str | None = None,
    status: str | None = None,
    operator_user_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ImageGenHistory], int]:
    q = db.query(ImageGenHistory)
    if customer_id is not None:
        q = q.filter(ImageGenHistory.customer_id == customer_id)
    if mode:
        q = q.filter(ImageGenHistory.mode == mode)
    if status:
        q = q.filter(ImageGenHistory.status == status)
    if operator_user_id is not None:
        q = q.filter(ImageGenHistory.operator_user_id == operator_user_id)
    total = q.count()
    rows = (
        q.order_by(ImageGenHistory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return rows, total


def get_history(db: Session, record_id: str) -> ImageGenHistory | None:
    return db.query(ImageGenHistory).filter(ImageGenHistory.record_id == record_id).first()


def start_audit(
    *, call_id: str, operator_user_id: int | None, customer_id: int | None, mode: str
) -> None:
    try:
        start_invocation(
            call_id,
            execution_mode="single_turn",
            local_user_id=operator_user_id,
            crm_customer_id=customer_id,
            entry_scene=f"image_gen_{mode}",
            scene_key=SCENE_KEY,
        )
    except Exception:
        _log.debug("image_gen start_invocation failed (ignored)", exc_info=True)


def finish_audit(
    *,
    call_id: str,
    model: str,
    provider_name: str,
    latency_ms: int,
    prompt_chars: int,
    status: str,
    error_code: str | None = None,
) -> None:
    try:
        if status == "success":
            write_step(
                call_id,
                0,
                STEP_KIND,
                name="image_generation",
                status="success",
                model=model,
                latency_ms=latency_ms,
                output_json=json.dumps(
                    {"provider": provider_name, "prompt_chars": prompt_chars}, ensure_ascii=False
                ),
            )
            finish_invocation(
                call_id,
                primary_model=model,
                primary_provider=provider_name,
                latency_ms=latency_ms,
                step_count=1,
            )
        else:
            fail_invocation(
                call_id,
                STAGE_GENERATION,
                error_code or "image_gen_failed",
                latency_ms=latency_ms,
            )
    except Exception:
        _log.debug("image_gen finish audit failed (ignored)", exc_info=True)
