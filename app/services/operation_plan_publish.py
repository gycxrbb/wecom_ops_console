"""运营计划一键发布到群 — 批量创建定时任务"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from .. import models
from ..security import json_dumps, json_loads
from ..services.scheduler_service import schedule_service


# node_type → 默认发送时段映射
NODE_TYPE_SEND_TIMES: dict[str, str] = {
    'morning_breakfast': '08:00',
    'score_publish': '09:30',
    'before_lunch_content': '11:00',
    'lunch_reminder': '12:00',
    'afternoon_content': '15:00',
    'dinner_reminder': '18:00',
    'night_summary': '21:00',
}

DEFAULT_SEND_TIME = '09:00'


def publish_plan_to_groups(
    db: Session,
    plan: models.Plan,
    group_ids: list[int],
    start_date: str,
    send_times: dict[str, str],
    skip_weekends: bool,
    require_approval: bool,
    user: models.User,
    end_date: str = '',
) -> list[models.Schedule]:
    """将运营计划的所有节点转化为定时任务。"""
    plan_mode = getattr(plan, 'plan_mode', None) or 'day_flow'
    if plan_mode == 'points_campaign':
        return _publish_campaign_plan(db, plan, group_ids, start_date, end_date, require_approval, user)
    return _publish_dayflow_plan(db, plan, group_ids, start_date, send_times, skip_weekends, require_approval, user)


def _publish_dayflow_plan(
    db: Session,
    plan: models.Plan,
    group_ids: list[int],
    start_date: str,
    send_times: dict[str, str],
    skip_weekends: bool,
    require_approval: bool,
    user: models.User,
) -> list[models.Schedule]:
    """day_flow 模式：按天偏移量创建一次性定时任务"""
    tz = ZoneInfo('Asia/Shanghai')
    base_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    created: list[models.Schedule] = []

    if not plan.days:
        return created

    for day in sorted(plan.days, key=lambda d: d.day_number):
        if not day.nodes:
            continue

        target_date = base_date + timedelta(days=day.day_number - 1)

        if skip_weekends and target_date.weekday() >= 5:
            continue

        for node in day.nodes:
            if not node.enabled:
                continue

            time_str = _resolve_send_time(node.node_type, send_times)
            run_at = tz.localize(datetime.combine(target_date, datetime.strptime(time_str, '%H:%M').time()))

            if run_at < datetime.now(tz):
                continue

            job = _create_schedule_job(
                db, title=f'D{day.day_number}-{node.title}',
                group_ids=group_ids, node=node,
                schedule_type='once', run_at=run_at,
                require_approval=require_approval, user=user,
            )
            created.append(job)

    db.commit()
    return created


def _publish_campaign_plan(
    db: Session,
    plan: models.Plan,
    group_ids: list[int],
    start_date: str,
    end_date: str,
    require_approval: bool,
    user: models.User,
) -> list[models.Schedule]:
    """points_campaign 模式：按触发规则创建定时任务"""
    tz = ZoneInfo('Asia/Shanghai')
    base_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_dt = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else base_date + timedelta(days=30)
    created: list[models.Schedule] = []

    if not plan.days:
        return created

    for day in sorted(plan.days, key=lambda d: d.day_number):
        if not day.nodes:
            continue

        trigger_rule = json_loads(day.trigger_rule_json, {})
        trigger_type = trigger_rule.get('trigger_type', 'manual')
        trigger_time = trigger_rule.get('time', DEFAULT_SEND_TIME)

        for node in day.nodes:
            if not node.enabled:
                continue

            schedule_type, cron_expr, run_at = _resolve_trigger(
                trigger_type, trigger_rule, base_date, end_dt, trigger_time, tz,
            )

            # manual 模式只创建 draft，不自动调度
            if trigger_type == 'manual':
                job = _create_schedule_job(
                    db, title=f'{day.title}-{node.title}',
                    group_ids=group_ids, node=node,
                    schedule_type='once', run_at=None,
                    require_approval=require_approval, user=user,
                    force_draft=True,
                )
                created.append(job)
                continue

            if schedule_type == 'cron' and cron_expr:
                job = _create_schedule_job(
                    db, title=f'{day.title}-{node.title}',
                    group_ids=group_ids, node=node,
                    schedule_type='cron', cron_expr=cron_expr,
                    require_approval=require_approval, user=user,
                )
                created.append(job)
            elif schedule_type == 'once' and run_at:
                if run_at < datetime.now(tz):
                    continue
                job = _create_schedule_job(
                    db, title=f'{day.title}-{node.title}',
                    group_ids=group_ids, node=node,
                    schedule_type='once', run_at=run_at,
                    require_approval=require_approval, user=user,
                )
                created.append(job)

    db.commit()
    return created


def _resolve_trigger(
    trigger_type: str,
    trigger_rule: dict,
    base_date,
    end_date,
    trigger_time: str,
    tz: ZoneInfo,
) -> tuple[str, str | None, datetime | None]:
    """根据触发规则计算调度类型、cron 表达式和运行时间"""
    time_parts = trigger_time.split(':')
    hour = int(time_parts[0]) if len(time_parts) > 0 else 9
    minute = int(time_parts[1]) if len(time_parts) > 1 else 0

    if trigger_type == 'daily':
        cron_expr = f'{minute} {hour} * * *'
        return 'cron', cron_expr, None

    if trigger_type == 'weekly':
        weekday = trigger_rule.get('weekday', 1)
        # cron weekday: 0=Sunday → 需要将中国习惯 (1=周一, 7=周日) 映射
        cron_wd = weekday % 7  # 7→0 (Sunday)
        cron_expr = f'{minute} {hour} * * {cron_wd}'
        return 'cron', cron_expr, None

    if trigger_type == 'countdown_range':
        days_start = trigger_rule.get('days_before_start', 14)
        days_end = trigger_rule.get('days_before_end', 7)
        # 从 end_date 倒推，创建多条 once 任务
        # 这里返回第一条的 run_at，后续由调用方循环
        target_date = end_date - timedelta(days=days_start)
        run_at = tz.localize(datetime.combine(target_date, datetime.strptime(f'{hour:02d}:{minute:02d}', '%H:%M').time()))
        return 'once', None, run_at

    if trigger_type == 'final_day':
        days_before = trigger_rule.get('days_before', 0)
        target_date = end_date - timedelta(days=days_before)
        run_at = tz.localize(datetime.combine(target_date, datetime.strptime(f'{hour:02d}:{minute:02d}', '%H:%M').time()))
        return 'once', None, run_at

    # manual
    return 'once', None, None


def _create_schedule_job(
    db: Session,
    title: str,
    group_ids: list[int],
    node: models.PlanNode,
    schedule_type: str,
    require_approval: bool,
    user: models.User,
    run_at: datetime | None = None,
    cron_expr: str | None = None,
    force_draft: bool = False,
) -> models.Schedule:
    """创建单条定时任务"""
    tz = ZoneInfo('Asia/Shanghai')

    content_data = node.content_json
    if isinstance(content_data, str):
        try:
            content_data = json.loads(content_data)
        except Exception:
            content_data = {'content': content_data}

    variables_data = node.variables_json
    if isinstance(variables_data, str):
        try:
            variables_data = json.loads(variables_data)
        except Exception:
            variables_data = {}

    approval_required = 1 if require_approval else 0
    if force_draft:
        approval_state = 'not_required'
        status = 'draft'
    elif approval_required and user.role == 'admin':
        approval_state = 'approved'
        status = 'approved'
    elif approval_required:
        approval_state = 'pending'
        status = 'pending_approval'
    else:
        approval_state = 'not_required'
        status = 'scheduled'

    job = models.Schedule(
        name=title,
        title=title,
        group_id=group_ids[0] if group_ids else 0,
        group_ids_json=json_dumps(group_ids),
        template_id=node.template_id,
        msg_type=node.msg_type,
        content_snapshot=json_dumps(content_data),
        content=json_dumps(content_data),
        variables=json_dumps(variables_data),
        schedule_type=schedule_type,
        run_at=run_at,
        timezone='Asia/Shanghai',
        skip_weekends=0,
        skip_dates_json='[]',
        skip_dates='[]',
        cron_expr=cron_expr,
        enabled=0 if force_draft else 1,
        approval_required=approval_required,
        status=status,
        owner_id=user.id,
    )
    if approval_state == 'approved':
        job.approved_at = datetime.utcnow()
        job.approved_by_id = user.id

    db.add(job)
    db.flush()

    if not force_draft and run_at:
        job.next_run_at = schedule_service.compute_next_run_at(job)

    if approval_required and status == 'pending_approval':
        db.add(models.ApprovalRequest(
            target_type='schedule',
            target_id=job.id,
            status='pending',
            applicant_id=user.id,
            reason=f'运营计划发布：{title}',
        ))

    if not force_draft:
        schedule_service.add_or_update_job(job)

    return job


def _resolve_send_time(node_type: str, send_times: dict[str, str]) -> str:
    """根据 node_type 查找用户指定的发送时间，找不到则用默认值。"""
    mapping = {
        'morning_breakfast': 'morning',
        'score_publish': 'morning',
        'before_lunch_content': 'before_lunch',
        'lunch_reminder': 'lunch',
        'afternoon_content': 'afternoon',
        'dinner_reminder': 'evening',
        'night_summary': 'night',
    }
    period = mapping.get(node_type, '')
    if period and period in send_times:
        return send_times[period]
    fallback = NODE_TYPE_SEND_TIMES.get(node_type, DEFAULT_SEND_TIME)
    return fallback


def _resolve_status(schedule_type: str, enabled: bool, approval_required: bool, approval_state: str) -> str:
    if not enabled:
        return 'draft'
    if approval_required:
        if approval_state == 'approved':
            return 'approved'
        return 'pending_approval'
    return 'scheduled'
