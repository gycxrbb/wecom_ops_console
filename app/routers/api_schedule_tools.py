from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..security import get_current_user
from ..services.scheduler_service import schedule_service

router = APIRouter(prefix="/api/v1/schedules", tags=["schedule_tools"])


class SchedulePreviewBody(BaseModel):
    schedule_type: str = Field(default="once")
    run_at: str | None = None
    cron_expr: str | None = None
    timezone: str = Field(default="Asia/Shanghai")
    skip_weekends: bool = False
    skip_dates: list[str] = Field(default_factory=list)


@router.post("/preview-runs")
def preview_schedule_runs(body: SchedulePreviewBody, request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)

    job = models.Schedule(
        name="preview",
        title="preview",
        group_id=0,
        group_ids_json="[]",
        content_snapshot="{}",
        content="{}",
        variables="{}",
        msg_type="text",
        schedule_type=body.schedule_type or "once",
        run_at=datetime.fromisoformat(body.run_at) if body.run_at else None,
        cron_expr=(body.cron_expr or "").strip(),
        timezone=body.timezone or "Asia/Shanghai",
        skip_weekends=1 if body.skip_weekends else 0,
        skip_dates_json="[]" if not body.skip_dates else json.dumps(body.skip_dates, ensure_ascii=False),
        enabled=1,
        approval_required=0,
        status="approved",
    )

    next_runs = schedule_service.compute_next_runs(job, count=5)
    return {
        "next_runs": [item.isoformat() for item in next_runs],
        "next_run_at": next_runs[0].isoformat() if next_runs else None,
    }
