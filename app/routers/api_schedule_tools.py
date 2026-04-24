from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..security import get_current_user
from ..services.scheduler_service import schedule_service
from ..route_helper import _dt

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
        "next_runs": [_dt(item) for item in next_runs],
        "next_run_at": _dt(next_runs[0]) if next_runs else None,
    }


@router.get("/calendar")
def get_schedule_calendar(
    group_id: int | None = None,
    days: int = 14,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """返回未来 N 天的定时任务日历视图数据。"""
    get_current_user(request, db)
    tz = ZoneInfo("Asia/Shanghai")
    now = datetime.now(tz)
    end_date = now + timedelta(days=days)

    query = db.query(models.Schedule).filter(
        models.Schedule.enabled == 1,
        models.Schedule.schedule_type.in_(["once", "cron"]),
    )

    if group_id:
        query = query.filter(models.Schedule.group_ids_json.contains(str(group_id)))

    jobs = query.order_by(models.Schedule.run_at).all()

    calendar: dict[str, list[dict]] = {}

    for i in range(days):
        d = (now + timedelta(days=i)).strftime("%Y-%m-%d")
        calendar[d] = []

    for job in jobs:
        next_runs = schedule_service.compute_next_runs(job, count=days * 2)
        for run_time in next_runs:
            run_local = run_time.astimezone(tz)
            date_key = run_local.strftime("%Y-%m-%d")
            if date_key in calendar:
                entry = {
                    "id": job.id,
                    "title": job.title,
                    "run_at": run_local.strftime('%Y-%m-%d %H:%M:%S'),
                    "msg_type": job.msg_type,
                    "schedule_type": job.schedule_type,
                    "status": job.status,
                }
                # avoid duplicates
                if not any(e["id"] == job.id and e["run_at"] == entry["run_at"] for e in calendar[date_key]):
                    calendar[date_key].append(entry)

    # sort each day by run_at
    for d in calendar:
        calendar[d].sort(key=lambda x: x["run_at"])

    return {"days": calendar, "total_jobs": len(jobs)}
