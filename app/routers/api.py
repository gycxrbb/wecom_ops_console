from __future__ import annotations
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from .. import models
from ..config import UPLOAD_DIR
from ..database import get_db
from ..security import decrypt_webhook, encrypt_webhook, get_current_user, json_dumps, json_loads, require_role, hash_password
from ..services.template_engine import default_context, render_value
from ..services.wecom import WeComService
from ..services.scheduler_service import schedule_service
from ..route_helper import UnifiedResponseRoute
from ..security import create_access_token, create_refresh_token, authenticate

router = APIRouter(prefix='/api/v1', tags=['api_v1'], route_class=UnifiedResponseRoute)

@router.post('/auth/login')
async def api_login(request: Request, db: Session = Depends(get_db)):
    body = parse_body(await request.json())
    username = body.get('username')
    password = body.get('password')
    user = authenticate(db, username, password)
    if not user:
        return {'code': 40100, 'message': '用户名或密码错误', 'data': {}}
    
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return {
        'code': 0,
        'message': 'ok',
        'data': {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'display_name': user.display_name,
                'role': user.role
            }
        }
    }

@router.get('/auth/me')
def api_get_me(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return {
        'code': 0,
        'message': 'ok',
        'data': {
            'id': user.id,
            'username': user.username,
            'display_name': user.display_name,
            'role': user.role
        }
    }



def serialize_group(group: models.Group):
    return {
        'id': group.id,
        'name': group.name,
        'alias': group.alias,
        'description': group.description,
        'tags': json_loads(group.tags_json, []),
        'is_enabled': group.is_enabled,
        'is_test_group': group.group_type == 'test',
        'webhook_configured': bool(group.webhook_cipher),
        'created_at': group.created_at.isoformat(),
    }


def serialize_template(tpl: models.Template):
    return {
        'id': tpl.id,
        'name': tpl.name,
        'category': tpl.category,
        'msg_type': tpl.msg_type,
        'description': tpl.description,
        'content_json': json_loads(tpl.content, {}),
        'variables_json': json_loads(tpl.variables, {}),
        'is_system': tpl.is_system,
        'created_by_id': tpl.created_by_id,
        'updated_at': tpl.updated_at.isoformat(),
    }


def serialize_material(material: models.Material):
    return {
        'id': asset.id,
        'name': asset.name,
        'asset_type': asset.asset_type,
        'file_name': asset.file_name,
        'mime_type': asset.mime_type,
        'size': asset.size,
        'url': f'/api/assets/{asset.id}/download',
        'created_at': asset.created_at.isoformat(),
    }


def serialize_schedule(schedule: models.Schedule):
    return {
        'id': job.id,
        'title': job.title,
        'group_ids': json_loads(job.group_ids_json, []),
        'template_id': job.template_id,
        'msg_type': job.msg_type,
        'content_json': json_loads(job.content, {}),
        'variables_json': json_loads(job.variables, {}),
        'schedule_type': job.schedule_type,
        'run_at': job.run_at.isoformat() if job.run_at else None,
        'cron_expr': job.cron_expr,
        'timezone': job.timezone,
        'enabled': job.enabled,
        'approval_required': job.approval_required,
        'approved_at': job.approved_at.isoformat() if job.approved_at else None,
        'status': job.status,
        'skip_dates': json_loads(job.skip_dates_json, []),
        'skip_weekends': job.skip_weekends,
        'last_error': job.last_error,
        'created_by_id': job.created_by_id,
        'last_sent_at': job.last_sent_at.isoformat() if job.last_sent_at else None,
        'created_at': job.created_at.isoformat(),
    }


def serialize_log(log: models.MessageLog):
    return {
        'id': log.id,
        'job_id': log.job_id,
        'group_id': log.group_id,
        'group_name': log.group.name if log.group else '',
        'msg_type': log.msg_type,
        'run_mode': log.run_mode,
        'success': log.success,
        'error_message': log.error_message,
        'request_json': json_loads(log.request_json, {}),
        'response_json': json_loads(log.response_json, {}),
        'created_at': log.created_at.isoformat(),
    }


def parse_body(request_data: dict | str | bytes) -> dict:
    if isinstance(request_data, dict):
        return request_data
    if isinstance(request_data, bytes):
        request_data = request_data.decode('utf-8')
    return json.loads(request_data)


def build_context(user: models.User, group: models.Group | None = None, extra: dict | None = None, now: datetime | None = None):
    ctx = default_context(now=now, coach_name=user.display_name or user.username, group_name=group.name if group else '')
    if extra:
        ctx.update(extra)
    return ctx


def render_message_content(msg_type: str, content_json: dict, variables_json: dict, user: models.User, group: models.Group | None, now: datetime | None = None):
    ctx = build_context(user=user, group=group, extra=variables_json, now=now)
    rendered = render_value(content_json, ctx)
    if msg_type == 'image' and isinstance(rendered, dict) and rendered.get('asset_id'):
        rendered['asset_id'] = int(rendered['asset_id'])
    if msg_type == 'file' and isinstance(rendered, dict) and rendered.get('asset_id'):
        rendered['asset_id'] = int(rendered['asset_id'])
    return rendered


def attach_asset_paths(db: Session, msg_type: str, content: dict):
    if msg_type not in {'image', 'file'}:
        return content
    content = dict(content)
    asset_id = content.get('asset_id')
    if not asset_id:
        return content
    asset = db.query(models.Material).filter(models.Material.id == int(asset_id)).first()
    if not asset:
        raise HTTPException(400, '引用的资产不存在')
    content['file_path'] = asset.stored_path
    if msg_type == 'image':
        content['image_path'] = asset.stored_path
    return content



async def do_send_to_groups(db: Session, groups: list[models.Group], msg_type: str, content_json: dict, variables_json: dict, user: models.User, schedule: models.Schedule | None = None, run_mode: str = 'immediate'):
    results = []
    from ..tasks import send_message_task
    
    for group in groups:
        rendered_content = render_message_content(msg_type, content_json, variables_json, user, group)
        rendered_content = attach_asset_paths(db, msg_type, rendered_content)
        
        msg = models.Message(
            source_type='schedule' if schedule else 'manual',
            source_id=schedule.id if schedule else None,
            group_id=group.id,
            template_id=schedule.template_id if schedule else None,
            msg_type=msg_type,
            rendered_content=json_dumps(rendered_content),
            request_payload='{}',
            status='pending',
            created_by=user.id
        )
        db.add(msg)
        db.commit()
        
        send_message_task.delay(msg.id)
        results.append({'group_id': group.id, 'group_name': group.name, 'success': True, 'response': 'Queued'})
        
    return results

async def perform_job_send(db: Session, schedule: models.Schedule, run_mode: str = 'scheduled'):
    user = schedule.owner or db.query(models.User).filter(models.User.role == 'admin').first()
    if schedule.require_approval and schedule.approval_status != 'approved':
        return {'skipped': True, 'reason': 'pending approval'}
        
    group_ids = json_loads(schedule.group_ids_json, [])
    groups = db.query(models.Group).filter(models.Group.id.in_(group_ids), models.Group.is_enabled == True).all()
    
    results = await do_send_to_groups(db, groups, schedule.msg_type, json_loads(schedule.content, {}), json_loads(schedule.variables, {}), user, schedule=schedule, run_mode=run_mode)
    
    return results
def get_user_or_401(request: Request, db: Session):
    return get_current_user(request, db)

@router.get('/bootstrap')
def bootstrap(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    total_logs = db.query(models.MessageLog).count()
    success_logs = db.query(models.MessageLog).filter(models.MessageLog.success == True).count()
    return {
        'current_user': {'id': user.id, 'username': user.username, 'display_name': user.display_name, 'role': user.role},
        'dashboard': {
            'group_count': db.query(models.Group).count(),
            'template_count': db.query(models.Template).count(),
            'schedule_count': db.query(models.Schedule).filter(models.Schedule.schedule_type != 'none').count(),
            'log_count': total_logs,
            'success_rate': round((success_logs / total_logs) * 100, 2) if total_logs else 0,
        }
    }

@router.get('/groups')
def list_groups(request: Request, db: Session = Depends(get_db)):
    get_user_or_401(request, db)
    groups = db.query(models.Group).order_by(models.Groupgroup_type == 'test'.desc(), models.Group.id.desc()).all()
    return [serialize_group(g) for g in groups]

@router.post('/groups')
async def upsert_group(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin')
    data = parse_body(await request.body())
    group_id = data.get('id')
    group = db.query(models.Group).filter(models.Group.id == group_id).first() if group_id else models.Group()
    if not group_id:
        db.add(group)
    group.name = data['name']
    group.alias = data.get('alias', '')
    group.description = data.get('description', '')
    group.tags_json = json_dumps(data.get('tags', []))
    group.is_enabled = bool(data.get('is_enabled', True))
    group.group_type = 'test' if data.get('is_test_group') else 'formal'
    if data.get('webhook'):
        group.webhook_cipher = encrypt_webhook(data['webhook'])
    db.commit()
    return serialize_group(group)

@router.delete('/groups/{group_id}')
def delete_group(group_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin')
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(404, '群不存在')
    db.delete(group)
    db.commit()
    return {'ok': True}

@router.get('/templates')
def list_templates(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    query = db.query(models.Template)
    if user.role != 'admin':
        query = query.filter((models.Template.is_system == True) | (models.Template.created_by_id == user.id))
    templates = query.order_by(models.Template.is_system.desc(), models.Template.updated_at.desc()).all()
    return [serialize_template(t) for t in templates]

@router.post('/templates')
async def upsert_template(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    data = parse_body(await request.body())
    template_id = data.get('id')
    tpl = db.query(models.Template).filter(models.Template.id == template_id).first() if template_id else models.Template(created_by_id=user.id)
    if template_id and user.role != 'admin' and tpl.created_by_id != user.id and not tpl.is_system:
        raise HTTPException(403, '不能修改其他人的模板')
    if not template_id:
        db.add(tpl)
    tpl.name = data['name']
    tpl.category = data.get('category', 'general')
    tpl.msg_type = data['msg_type']
    tpl.description = data.get('description', '')
    tpl.content = json_dumps(data.get('content_json', {}))
    tpl.variables = json_dumps(data.get('variables_json', {}))
    tpl.is_system = bool(data.get('is_system', False)) if user.role == 'admin' else False
    db.commit()
    return serialize_template(tpl)

@router.post('/templates/{template_id}/clone')
def clone_template(template_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    tpl = db.query(models.Template).filter(models.Template.id == template_id).first()
    if not tpl:
        raise HTTPException(404, '模板不存在')
    cloned = models.Template(
        name=f'{tpl.name} - 副本',
        category=tpl.category,
        msg_type=tpl.msg_type,
        description=tpl.description,
        content_json=tpl.content,
        variables_json=tpl.variables,
        is_system=False,
        created_by_id=user.id,
    )
    db.add(cloned)
    db.commit()
    return serialize_template(cloned)

@router.delete('/templates/{template_id}')
def delete_template(template_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    tpl = db.query(models.Template).filter(models.Template.id == template_id).first()
    if not tpl:
        raise HTTPException(404, '模板不存在')
    if tpl.is_system and user.role != 'admin':
        raise HTTPException(403, '系统模板只能由管理员删除')
    if user.role != 'admin' and tpl.created_by_id != user.id:
        raise HTTPException(403, '不能删除其他人的模板')
    db.delete(tpl)
    db.commit()
    return {'ok': True}

@router.get('/assets')
def list_assets(request: Request, db: Session = Depends(get_db)):
    get_user_or_401(request, db)
    assets = db.query(models.Material).order_by(models.Material.id.desc()).all()
    return [serialize_material(a) for a in assets]

@router.post('/assets')
async def upload_asset(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    ext = Path(file.filename).suffix
    unique_name = f'{uuid4().hex}{ext}'
    stored_path = UPLOAD_DIR / unique_name
    with stored_path.open('wb') as fh:
        shutil.copyfileobj(file.file, fh)
    asset_type = 'image' if (file.content_type or '').startswith('image/') else 'file'
    asset = models.Material(name=Path(file.filename).stem, asset_type=asset_type, file_name=file.filename, stored_path=str(stored_path), mime_type=file.content_type or 'application/octet-stream', size=stored_path.stat().st_size, created_by_id=user.id)
    db.add(asset)
    db.commit()
    return serialize_material(asset)

@router.get('/assets/{asset_id}/download')
def download_asset(asset_id: int, request: Request, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    get_user_or_401(request, db)
    asset = db.query(models.Material).filter(models.Material.id == asset_id).first()
    if not asset:
        raise HTTPException(404, '资产不存在')
    return FileResponse(asset.stored_path, media_type=asset.mime_type, filename=asset.file_name)

@router.delete('/assets/{asset_id}')
def delete_asset(asset_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    asset = db.query(models.Material).filter(models.Material.id == asset_id).first()
    if not asset:
        raise HTTPException(404, '资产不存在')
    try:
        Path(asset.stored_path).unlink(missing_ok=True)
    except Exception:
        pass
    db.delete(asset)
    db.commit()
    return {'ok': True}

@router.post('/preview')
async def preview_message(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    data = parse_body(await request.body())
    group = None
    if data.get('group_ids'):
        group = db.query(models.Group).filter(models.Group.id == data['group_ids'][0]).first()
    rendered_content = render_message_content(data['msg_type'], data.get('content_json', {}), data.get('variables_json', {}), user, group)
    rendered_content = attach_asset_paths(db, data['msg_type'], rendered_content)
    payload = WeComService.build_payload(data['msg_type'], rendered_content if data['msg_type'] != 'file' else {**rendered_content, 'media_id': rendered_content.get('media_id', '<运行时上传后生成>')})
    return {'rendered_content': rendered_content, 'payload_preview': payload}

@router.post('/send')
async def send_message(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    data = parse_body(await request.body())
    group_ids = data.get('group_ids', [])
    if data.get('test_group_only'):
        groups = db.query(models.Group).filter(models.Groupgroup_type == 'test' == True, models.Group.is_enabled == True).all()
    else:
        groups = db.query(models.Group).filter(models.Group.id.in_(group_ids), models.Group.is_enabled == True).all()
    if not groups:
        raise HTTPException(400, '请选择至少一个已启用的群')
    results = await do_send_to_groups(db, groups, data['msg_type'], data.get('content_json', {}), data.get('variables_json', {}), user, run_mode='test' if data.get('test_group_only') else 'immediate')
    return {'results': results}

@router.get('/schedules')
def list_schedules(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    query = db.query(models.Schedule)
    if user.role != 'admin':
        query = query.filter(models.Schedule.created_by_id == user.id)
    jobs = query.order_by(models.Schedule.created_at.desc()).all()
    return [serialize_schedule(job) for job in jobs]

@router.post('/schedules')
async def create_or_update_schedule(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    data = parse_body(await request.body())
    job_id = data.get('id')
    job = db.query(models.Schedule).filter(models.Schedule.id == job_id).first() if job_id else models.Schedule(created_by_id=user.id)
    if job_id and user.role != 'admin' and job.created_by_id != user.id:
        raise HTTPException(403, '不能修改其他人的任务')
    if not job_id:
        db.add(job)
    job.title = data['title']
    job.group_ids_json = json_dumps(data.get('group_ids', []))
    job.template_id = data.get('template_id')
    job.msg_type = data['msg_type']
    job.content = json_dumps(data.get('content_json', {}))
    job.variables = json_dumps(data.get('variables_json', {}))
    job.schedule_type = data.get('schedule_type', 'none')
    run_at = data.get('run_at')
    job.run_at = datetime.fromisoformat(run_at) if run_at else None
    job.cron_expr = data.get('cron_expr', '')
    job.timezone = data.get('timezone', 'Asia/Shanghai')
    job.enabled = bool(data.get('enabled', True))
    job.approval_required = bool(data.get('approval_required', False))
    job.skip_dates_json = json_dumps(data.get('skip_dates', []))
    job.skip_weekends = bool(data.get('skip_weekends', False))
    requested_status = data.get('status') or ('pending_approval' if job.approval_required and user.role != 'admin' else 'scheduled')
    if job.schedule_type == 'none':
        requested_status = 'draft'
    if user.role == 'admin' and requested_status == 'pending_approval':
        requested_status = 'approved'
        job.approved_at = datetime.utcnow()
        job.approved_by_id = user.id
    job.status = requested_status
    db.commit()
    if requested_status == 'pending_approval':
        req = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.target_type == 'schedule', models.ApprovalRequest.target_id == job.id, models.ApprovalRequest.status == 'pending').first()
        if not req:
            db.add(models.ApprovalRequest(target_type='schedule', target_id=job.id, status='pending', applicant_id=user.id, reason=f'创建/更新定时任务 {job.title} 需要审批'))
            db.commit()
    schedule_service.add_or_update_job(job)
    return serialize_schedule(job)

@router.post('/schedules/{job_id}/clone')
def clone_schedule(job_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    job = db.query(models.Schedule).filter(models.Schedule.id == job_id).first()
    if not job:
        raise HTTPException(404, '任务不存在')
    cloned = models.Schedule(
        title=f'{job.title} - 副本',
        group_ids_json=job.group_ids_json,
        template_id=job.template_id,
        msg_type=job.msg_type,
        content_json=job.content,
        variables_json=job.variables,
        schedule_type=job.schedule_type,
        run_at=job.run_at,
        cron_expr=job.cron_expr,
        timezone=job.timezone,
        enabled=False,
        approval_required=job.approval_required,
        status='draft',
        skip_dates_json=job.skip_dates_json,
        skip_weekends=job.skip_weekends,
        created_by_id=user.id,
    )
    db.add(cloned)
    db.commit()
    return serialize_schedule(cloned)

@router.post('/schedules/{job_id}/toggle')
def toggle_schedule(job_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    job = db.query(models.Schedule).filter(models.Schedule.id == job_id).first()
    if not job:
        raise HTTPException(404, '任务不存在')
    if user.role != 'admin' and job.created_by_id != user.id:
        raise HTTPException(403, '不能操作其他人的任务')
    job.enabled = not job.enabled
    db.commit()
    schedule_service.add_or_update_job(job)
    return serialize_schedule(job)

@router.post('/schedules/{job_id}/approve')
def approve_schedule(job_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin')
    job = db.query(models.Schedule).filter(models.Schedule.id == job_id).first()
    if not job:
        raise HTTPException(404, '任务不存在')
    job.approved_at = datetime.utcnow()
    job.approved_by_id = user.id
    job.status = 'approved' if job.schedule_type in {'once', 'cron'} else 'draft'
    db.commit()
    schedule_service.add_or_update_job(job)
    return serialize_schedule(job)

@router.delete('/schedules/{job_id}')
def delete_schedule(job_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    job = db.query(models.Schedule).filter(models.Schedule.id == job_id).first()
    if not job:
        raise HTTPException(404, '任务不存在')
    if user.role != 'admin' and job.created_by_id != user.id:
        raise HTTPException(403, '不能删除其他人的任务')
    db.delete(job)
    db.commit()
    schedule_service.sync_from_db()
    return {'ok': True}

@router.post('/schedules/{job_id}/run-now')
async def run_schedule_now(job_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    job = db.query(models.Schedule).filter(models.Schedule.id == job_id).first()
    if not job:
        raise HTTPException(404, '任务不存在')
    if user.role != 'admin' and job.created_by_id != user.id:
        raise HTTPException(403, '不能执行其他人的任务')
    if job.approval_required and not job.approved_at and user.role != 'admin':
        raise HTTPException(403, '该任务尚未审批')
    results = await perform_job_send(db, job, run_mode='manual-run')
    return {'results': results}

@router.get('/logs')
def list_logs(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    query = db.query(models.MessageLog).order_by(models.MessageLog.created_at.desc())
    if user.role != 'admin':
        query = query.filter(models.MessageLog.initiated_by_id == user.id)
    logs = query.limit(200).all()
    return [serialize_log(log) for log in logs]

@router.post('/logs/{log_id}/retry')
async def retry_log(log_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    log = db.query(models.MessageLog).filter(models.MessageLog.id == log_id).first()
    if not log:
        raise HTTPException(404, '日志不存在')
    if user.role != 'admin' and log.initiated_by_id != user.id:
        raise HTTPException(403, '不能重试其他人的日志')
    if not log.group:
        raise HTTPException(400, '该日志缺少群信息，无法重试')
    webhook = decrypt_webhook(log.group.webhook_cipher)
    try:
        payload, response = await WeComService.send(webhook, log.msg_type, json_loads(log.request_json, {}), group_key=str(log.group_id))
        new_log = models.MessageLog(job_id=log.job_id, group_id=log.group_id, initiated_by_id=user.id, msg_type=log.msg_type, run_mode='retry', request_json=json_dumps(payload), response_json=json_dumps(response), success=True)
        db.add(new_log)
        db.commit()
        return serialize_log(new_log)
    except Exception as exc:
        new_log = models.MessageLog(job_id=log.job_id, group_id=log.group_id, initiated_by_id=user.id, msg_type=log.msg_type, run_mode='retry', request_json=log.request_json, response_json='{}', success=False, error_message=str(exc))
        db.add(new_log)
        db.commit()
        return JSONResponse(status_code=400, content=serialize_log(new_log))

@router.get('/users')
def list_users(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin')
    users = db.query(models.User).order_by(models.User.id.desc()).all()
    return [{'id': u.id, 'username': u.username, 'display_name': u.display_name, 'role': u.role, 'is_active': u.status, 'created_at': u.created_at.isoformat()} for u in users]

@router.post('/users')
async def upsert_user(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin')
    data = parse_body(await request.body())
    target = db.query(models.User).filter(models.User.id == data.get('id')).first() if data.get('id') else models.User()
    if not data.get('id'):
        db.add(target)
    target.username = data['username']
    target.display_name = data.get('display_name', data['username'])
    target.role = data.get('role', 'coach')
    target.status = bool(data.get('is_active', True))
    if data.get('password'):
        target.password_hash = hash_password(data['password'])
    db.commit()
    return {'id': target.id, 'username': target.username, 'display_name': target.display_name, 'role': target.role, 'is_active': target.status}


# ==========================================
# Dashboard APIs
# ==========================================

from sqlalchemy import func

@router.get('/dashboard/summary')
def get_dashboard_summary(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    total_logs = db.query(models.MessageLog).count()
    success_logs = db.query(models.MessageLog).filter(models.MessageLog.success == True).count()
    return {
        'group_count': db.query(models.Group).count(),
        'template_count': db.query(models.Template).count(),
        'schedule_count': db.query(models.Schedule).filter(models.Schedule.schedule_type != 'none').count(),
        'log_count': total_logs,
        'success_rate': round((success_logs / total_logs) * 100, 2) if total_logs else 0,
    }

import sqlalchemy
from sqlalchemy import func
from datetime import timedelta

@router.get('/dashboard/message-trend')
def get_message_trend(days: int = 7, db: Session = Depends(get_db)):
    start_date = datetime.utcnow() - timedelta(days=days)
    logs = db.query(
        func.date(models.MessageLog.created_at).label('date'),
        func.count().label('count'),
        func.sum(func.cast(models.MessageLog.success, sqlalchemy.Integer)).label('success_count')
    ).filter(models.MessageLog.created_at >= start_date).group_by(func.date(models.MessageLog.created_at)).all()
    
    trend = [{"date": str(log.date), "count": log.count, "success": log.success_count} for log in logs]
    return {"trend": trend, "days": days}

@router.get('/dashboard/failure-distribution')
def get_failure_distribution(days: int = 7, db: Session = Depends(get_db)):
    start_date = datetime.utcnow() - timedelta(days=days)
    logs = db.query(
        models.MessageLog.error_message,
        func.count().label('count')
    ).filter(
        models.MessageLog.created_at >= start_date,
        models.MessageLog.success == False,
        models.MessageLog.error_message != None
    ).group_by(models.MessageLog.error_message).all()
    
    distribution = [{"error": log.error_message, "count": log.count} for log in logs]
    return {"distribution": distribution, "days": days}


# ==========================================
# Approval APIs
# ==========================================

@router.get('/approvals')
def list_approvals(page: int = 1, page_size: int = 20, status: str = None, request: Request = None, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    query = db.query(models.ApprovalRequest)
    if status:
        query = query.filter(models.ApprovalRequest.status == status)
    # If not admin, maybe only see their own?
    if user.role != 'admin':
        query = query.filter(models.ApprovalRequest.applicant_id == user.id)
        
    total = query.count()
    approvals = query.order_by(models.ApprovalRequest.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "list": [{
            "id": a.id,
            "target_type": a.target_type,
            "target_id": a.target_id,
            "status": a.status,
            "applicant_id": a.applicant_id,
            "reason": a.reason,
            "comment": a.comment,
            "created_at": a.created_at.isoformat() if hasattr(a, 'created_at') else None
        } for a in approvals],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total
        }
    }

@router.post('/approvals')
async def create_approval(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    data = parse_body(await request.body())
    
    req = models.ApprovalRequest(
        target_type=data.get('target_type'),
        target_id=data.get('target_id'),
        reason=data.get('reason'),
        applicant_id=user.id,
        status='pending'
    )
    db.add(req)
    db.commit()
    return {"id": req.id}

@router.post('/approvals/{approval_id}/approve')
async def approve_request(approval_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin')
    
    appr = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == approval_id).first()
    if not appr:
        raise HTTPException(404, "审批单不存在")
        
    data = parse_body(await request.body())
    appr.status = 'approved'
    appr.approver_id = user.id
    appr.comment = data.get('comment', '')
    appr.approved_at = datetime.utcnow()
    
    # If target_type is schedule, update the target's approval status
    if appr.target_type == 'schedule':
        job = db.query(models.Schedule).filter(models.Schedule.id == appr.target_id).first()
        if job:
            job.approved_at = datetime.utcnow()
            job.approved_by_id = user.id
            job.status = 'approved' if job.schedule_type == 'cron' else job.status
    
    db.commit()
    return {"id": appr.id, "status": appr.status}

@router.post('/approvals/{approval_id}/reject')
async def reject_request(approval_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin')
    
    appr = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == approval_id).first()
    if not appr:
        raise HTTPException(404, "审批单不存在")
        
    data = parse_body(await request.body())
    appr.status = 'rejected'
    appr.approver_id = user.id
    appr.comment = data.get('comment', '')
    
    if appr.target_type == 'schedule':
        job = db.query(models.Schedule).filter(models.Schedule.id == appr.target_id).first()
        if job:
            job.status = 'rejected'
            
    db.commit()
    return {"id": appr.id, "status": appr.status}
