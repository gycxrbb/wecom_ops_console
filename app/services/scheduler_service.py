from __future__ import annotations
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.orm import Session
from ..database import SessionLocal
from .. import models
from ..security import json_loads

logger = logging.getLogger(__name__)

class ScheduleService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone='Asia/Shanghai')

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info('Scheduler started')

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info('Scheduler shut down')

    def sync_from_db(self):
        self.scheduler.remove_all_jobs()
        db = SessionLocal()
        try:
            jobs = db.query(models.Schedule).filter(models.Schedule.enabled == 1, models.Schedule.schedule_type.in_(['once', 'cron'])).all()
            logger.info(f'Syncing {len(jobs)} enabled schedule(s) from DB')
            for job in jobs:
                self.add_or_update_job(job)
                job.next_run_at = self.compute_next_run_at(job)
                logger.info(f'Job {job.id} ({job.title}): next_run_at={job.next_run_at}')
            db.commit()
            registered = self.scheduler.get_jobs()
            logger.info(f'Scheduler has {len(registered)} registered job(s)')
        finally:
            db.close()

    def _build_trigger(self, job: models.Schedule):
        if not job.enabled:
            return None
        if job.approval_required and job.status != 'approved':
            return None
        if job.schedule_type == 'cron' and job.cron_expr:
            parts = job.cron_expr.strip().split()
            if len(parts) < 5:
                return None
            minute, hour, day, month, day_of_week = parts[:5]
            timezone = ZoneInfo(job.timezone or 'Asia/Shanghai')
            return CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week, timezone=timezone)
        return None

    def _is_valid_fire_time(self, job: models.Schedule, fire_time: datetime) -> bool:
        skip_dates = set(json_loads(job.skip_dates_json, []))
        local_time = fire_time.astimezone(ZoneInfo(job.timezone or 'Asia/Shanghai'))
        if job.skip_weekends and local_time.weekday() >= 5:
            return False
        if local_time.strftime('%Y-%m-%d') in skip_dates:
            return False
        return True

    def compute_next_runs(self, job: models.Schedule, count: int = 5) -> list[datetime]:
        if not job.enabled:
            return []
        if job.approval_required and job.status != 'approved':
            return []
        if job.schedule_type == 'once':
            now = datetime.now(ZoneInfo(job.timezone or 'Asia/Shanghai'))
            run_at_local = job.run_at.replace(tzinfo=ZoneInfo(job.timezone or 'Asia/Shanghai'))
            if not job.run_at or run_at_local < now:
                return []
            return [job.run_at] if self._is_valid_fire_time(job, job.run_at.replace(tzinfo=ZoneInfo(job.timezone or 'Asia/Shanghai'))) else []

        trigger = self._build_trigger(job)
        if not trigger:
            return []

        timezone = ZoneInfo(job.timezone or 'Asia/Shanghai')
        cursor = datetime.now(timezone)
        previous = None
        results: list[datetime] = []
        attempts = 0

        while len(results) < count and attempts < count * 20:
            next_fire = trigger.get_next_fire_time(previous, cursor)
            if not next_fire:
                break
            previous = next_fire
            cursor = next_fire
            attempts += 1
            if self._is_valid_fire_time(job, next_fire):
                results.append(next_fire)

        return results

    def compute_next_run_at(self, job: models.Schedule) -> datetime | None:
        runs = self.compute_next_runs(job, count=1)
        return runs[0] if runs else None

    def add_or_update_job(self, job: models.Schedule):
        aps_id = f'job-{job.id}'
        try:
            self.scheduler.remove_job(aps_id)
        except Exception:
            pass
        if not job.enabled:
            job.next_run_at = None
            logger.debug(f'Job {job.id} skipped: disabled')
            return
        if job.approval_required and job.status != 'approved':
            job.next_run_at = None
            logger.debug(f'Job {job.id} skipped: pending approval')
            return
        if job.schedule_type == 'once' and job.run_at:
            tz = ZoneInfo(job.timezone or 'Asia/Shanghai')
            run_at_local = job.run_at.replace(tzinfo=tz)
            if run_at_local < datetime.now(tz):
                logger.info(f'Job {job.id} skipped: run_at {run_at_local} is in the past')
                job.next_run_at = None
                return
            trigger = DateTrigger(run_date=run_at_local)
        elif job.schedule_type == 'cron' and job.cron_expr:
            trigger = self._build_trigger(job)
        else:
            job.next_run_at = None
            logger.debug(f'Job {job.id} skipped: no valid trigger config')
            return
        scheduled_job = self.scheduler.add_job(execute_job, trigger=trigger, id=aps_id, args=[job.id], replace_existing=True, misfire_grace_time=300)
        job.next_run_at = scheduled_job.next_run_time
        logger.info(f'Job {job.id} registered: type={job.schedule_type} next_run={scheduled_job.next_run_time}')

schedule_service = ScheduleService()

async def execute_job(job_id: int):
    from ..routers.api import perform_job_send
    db: Session = SessionLocal()
    try:
        job = db.query(models.Schedule).filter(models.Schedule.id == job_id).first()
        if not job or not job.enabled:
            logger.warning(f'Job {job_id} skipped: not found or disabled')
            return
        now = datetime.now(ZoneInfo(job.timezone or 'Asia/Shanghai'))
        skip_dates = set(json_loads(job.skip_dates_json, []))
        if job.skip_weekends and now.weekday() >= 5:
            logger.info(f'Job {job_id} skipped: weekend')
            return
        if now.strftime('%Y-%m-%d') in skip_dates:
            logger.info(f'Job {job_id} skipped: skip date')
            return
        logger.info(f'Executing job {job_id} ({job.title}) at {now.isoformat()}')
        await perform_job_send(db, job, run_mode='scheduled')
        if job.schedule_type == 'once':
            job.enabled = False
            job.status = 'completed'
        job.next_run_at = schedule_service.compute_next_run_at(job)
        db.commit()
        logger.info(f'Job {job_id} executed successfully')
    except Exception as e:
        logger.error(f'Job {job_id} execution failed: {e}', exc_info=True)
        try:
            job = db.query(models.Schedule).filter(models.Schedule.id == job_id).first()
            if job:
                job.last_error = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
