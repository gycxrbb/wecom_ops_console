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
from ..config import settings

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
        self._register_auto_ranking_job()

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
        scheduled_job = self.scheduler.add_job(execute_job, trigger=trigger, id=aps_id, args=[job.id], replace_existing=True, misfire_grace_time=300, max_instances=1, coalesce=True)
        job.next_run_at = scheduled_job.next_run_time
        logger.info(f'Job {job.id} registered: type={job.schedule_type} next_run={scheduled_job.next_run_time}')

    def _register_auto_ranking_job(self):
        """为每个 enabled 的自动排行配置注册独立的 cron job。"""
        from .auto_ranking_push import execute_auto_ranking

        # 移除所有旧的 auto-ranking-* job
        for job in self.scheduler.get_jobs():
            if job.id.startswith('auto-ranking-'):
                self.scheduler.remove_job(job.id)

        db = SessionLocal()
        try:
            from ..models_auto_ranking import AutoRankingConfig
            configs = db.query(AutoRankingConfig).filter(AutoRankingConfig.enabled == 1).all()
        finally:
            db.close()

        tz = ZoneInfo('Asia/Shanghai')

        def _make_fire(cfg_id: int, cfg_name: str):
            async def _fire():
                # Redis 分布式锁：多 worker 环境下只有一个能执行
                import redis as _redis
                lock_key = f'auto_ranking_lock:{cfg_id}'
                lock_ttl = 600  # 10 分钟，覆盖整个发送周期
                r = _redis.from_url(settings.redis_url)
                acquired = r.set(lock_key, '1', nx=True, ex=lock_ttl)
                if not acquired:
                    logger.info('Auto ranking %s skipped: another worker holds the lock', cfg_name)
                    return

                logger.info('Auto ranking push: firing config %s (%s)', cfg_id, cfg_name)
                db2 = SessionLocal()
                try:
                    cfg = db2.query(AutoRankingConfig).get(cfg_id)
                    if not cfg or not cfg.enabled:
                        logger.info('Auto ranking %s skipped: not found or disabled', cfg_id)
                        r.delete(lock_key)
                        return
                    result = await execute_auto_ranking(cfg)
                    logger.info('Auto ranking %s: sent=%d skipped=%d failed=%d error=%s cooldown=%s', cfg_name, result.get('sent', 0), result.get('skipped', 0), result.get('failed', 0), str(result.get('error', ''))[:80], result.get('cooldown', False))
                    cfg.last_run_at = datetime.now(tz).replace(tzinfo=None)
                    cfg.last_error = result.get('error', '')
                    db2.commit()
                except Exception as exc:
                    logger.exception('Auto ranking %s failed', cfg_name)
                    try:
                        cfg = db2.query(AutoRankingConfig).get(cfg_id)
                        if cfg:
                            cfg.last_run_at = datetime.now(tz).replace(tzinfo=None)
                            cfg.last_error = str(exc)[:200]
                            db2.commit()
                    except Exception:
                        pass
                finally:
                    db2.close()
                    r.delete(lock_key)
            return _fire

        for cfg in configs:
            job_id = f'auto-ranking-{cfg.id}'
            hour = cfg.push_hour or 0
            minute = cfg.push_minute or 0
            # 提前 1 分钟触发，为预生成排行消息留足时间
            prep_minute = (minute - 1) % 60
            prep_hour = (hour - 1) % 24 if minute == 0 else hour
            self.scheduler.add_job(
                _make_fire(cfg.id, cfg.name),
                trigger=CronTrigger(minute=str(prep_minute), hour=str(prep_hour), timezone=tz),
                id=job_id,
                replace_existing=True,
                misfire_grace_time=None,  # 禁止 misfire 补发，防止重复发送
                max_instances=1,
                coalesce=True,
            )
            logger.info('Auto ranking cron job registered: %s → %02d:%02d prep, %02d:%02d send Asia/Shanghai daily', cfg.name, prep_hour, prep_minute, hour, minute)

        if not configs:
            logger.info('No enabled auto ranking configs found')

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
        db.expire(job)
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
