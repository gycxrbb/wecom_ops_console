"""运营计划一键发布到群 — 批量创建定时任务"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from .. import models
from ..security import json_dumps
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
) -> list[models.Schedule]:
    """将运营计划的所有节点按天转化为定时任务，批量创建。"""
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
            hour, minute = time_str.split(':')
            run_at = tz.localize(datetime.combine(target_date, datetime.strptime(time_str, '%H:%M').time()))

            if run_at < datetime.now(tz):
                continue

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

            title = f'D{day.day_number}-{node.title}'

            approval_required = 1 if require_approval else 0
            if approval_required and user.role == 'admin':
                approval_state = 'approved'
            elif approval_required:
                approval_state = 'pending'
            else:
                approval_state = 'not_required'

            status = _resolve_status('once', True, approval_required, approval_state)

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
                schedule_type='once',
                run_at=run_at,
                timezone='Asia/Shanghai',
                skip_weekends=0,
                skip_dates_json='[]',
                skip_dates='[]',
                enabled=1,
                approval_required=approval_required,
                status=status,
                owner_id=user.id,
            )
            if approval_state == 'approved':
                job.approved_at = datetime.utcnow()
                job.approved_by_id = user.id

            db.add(job)
            db.flush()

            job.next_run_at = schedule_service.compute_next_run_at(job)

            if approval_required and status == 'pending_approval':
                db.add(models.ApprovalRequest(
                    target_type='schedule',
                    target_id=job.id,
                    status='pending',
                    applicant_id=user.id,
                    reason=f'运营计划发布：{title}',
                ))

            schedule_service.add_or_update_job(job)
            created.append(job)

    db.commit()
    return created


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
