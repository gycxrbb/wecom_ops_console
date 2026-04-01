from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.orm import Session
from ..database import SessionLocal
from .. import models
from ..security import json_loads

class ScheduleService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def sync_from_db(self):
        self.scheduler.remove_all_jobs()
        db = SessionLocal()
        try:
            jobs = db.query(models.Schedule).filter(models.Schedule.enabled == 1, models.Schedule.schedule_type.in_(['once', 'cron'])).all()
            for job in jobs:
                self.add_or_update_job(job)
        finally:
            db.close()

    def add_or_update_job(self, job: models.Schedule):
        aps_id = f'job-{job.id}'
        try:
            self.scheduler.remove_job(aps_id)
        except Exception:
            pass
        if not job.enabled:
            return
        if job.approval_required and job.status != 'approved':
            return
        if job.schedule_type == 'once' and job.run_at:
            trigger = DateTrigger(run_date=job.run_at)
        elif job.schedule_type == 'cron' and job.cron_expr:
            minute, hour, day, month, day_of_week = job.cron_expr.strip().split()[:5]
            trigger = CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week, timezone=job.timezone)
        else:
            return
        self.scheduler.add_job(execute_job, trigger=trigger, id=aps_id, args=[job.id], replace_existing=True, misfire_grace_time=60)

schedule_service = ScheduleService()

async def execute_job(job_id: int):
    from ..routers.api import perform_job_send
    db: Session = SessionLocal()
    try:
        job = db.query(models.Schedule).filter(models.Schedule.id == job_id).first()
        if not job or not job.enabled:
            return
        now = datetime.now(ZoneInfo(job.timezone or 'Asia/Shanghai'))
        skip_dates = set(json_loads(job.skip_dates_json, []))
        if job.skip_weekends and now.weekday() >= 5:
            return
        if now.strftime('%Y-%m-%d') in skip_dates:
            return
        await perform_job_send(db, job, run_mode='scheduled')
        if job.schedule_type == 'once':
            job.enabled = False
            job.status = 'completed'
            db.commit()
    finally:
        db.close()
