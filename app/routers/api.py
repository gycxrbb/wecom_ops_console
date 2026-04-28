from __future__ import annotations
import asyncio
import hashlib
import json
import logging
from collections import defaultdict
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.orm import Session
from .. import models
from ..config import settings
from ..database import get_db
from ..security import decrypt_webhook, encrypt_webhook, get_current_user, json_dumps, json_loads, require_role, require_permission, hash_password
from ..services.material_storage_service import build_storage_result_from_material, log_material_storage_event, resolve_material_storage_path
from ..services.audio_transcode import AudioTranscodeError, guess_audio_extension, is_amr_filename, is_supported_audio_upload, transcode_audio_to_amr
from ..services.storage import UploadPayload, storage_facade
from ..services.template_engine import default_context, render_value
from ..services.wecom import WeComService
from ..services.scheduler_service import schedule_service
from ..services.crm_admin_auth import CrmAdminAuthUnavailable
from ..services import login_rate_limiter as rate_limiter
from ..route_helper import UnifiedResponseRoute, _dt, _fmt
from ..services.batch_summary import send_ranking_summary
from ..security import create_access_token, create_refresh_token, authenticate

router = APIRouter(prefix='/api/v1', tags=['api_v1'], route_class=UnifiedResponseRoute)
logger = logging.getLogger(__name__)

_TZ = ZoneInfo(settings.default_timezone)

@router.get('/auth/public-key')
async def api_public_key():
    from ..security import get_rsa_public_key
    return {'code': 0, 'message': 'success', 'data': {'public_key': get_rsa_public_key()}}

@router.post('/auth/login')
async def api_login(request: Request, db: Session = Depends(get_db)):
    body = parse_body(await request.json())
    username = body.get('username')
    password = body.get('password')
    client_ip = get_request_ip(request)

    # 暴力破解防护
    allowed, retry_after = rate_limiter.check(client_ip, username or '')
    if not allowed:
        return {'code': 42900, 'message': f'登录失败次数过多，请 {retry_after} 秒后重试', 'data': {'retry_after': retry_after}}

    from ..security import decrypt_rsa_password
    password = decrypt_rsa_password(password)

    try:
        user = authenticate(db, username, password)
    except CrmAdminAuthUnavailable:
        return {'code': 50300, 'message': 'CRM 用户库暂时不可用，请稍后重试', 'data': {}}
    if not user:
        rate_limiter.record_failure(client_ip, username or '')
        return {'code': 40100, 'message': '用户名或密码错误', 'data': {}}

    rate_limiter.reset(client_ip, username or '')
    
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
                'avatar_url': user.avatar_url or '',
                'auth_source': user.auth_source or 'local',
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
            'avatar_url': user.avatar_url or '',
            'auth_source': user.auth_source or 'local',
            'role': user.role
        }
    }



def serialize_group(group: models.Group):
    try:
        webhook = decrypt_webhook(group.webhook_cipher) if group.webhook_cipher else ''
    except Exception:
        webhook = ''
    return {
        'id': group.id,
        'name': group.name,
        'alias': group.alias,
        'description': '',
        'tags': json_loads(group.tags, []) if group.tags else [],
        'is_enabled': bool(group.enabled),
        'is_test_group': group.group_type == 'test',
        'webhook_configured': has_real_webhook(webhook),
        'created_at': _dt(group.created_at),
    }


def serialize_template(tpl: models.Template):
    return {
        'id': tpl.id,
        'name': tpl.name,
        'category': tpl.category,
        'msg_type': tpl.msg_type,
        'description': '',
        'content_json': json_loads(tpl.content, {}),
        'variables_json': json_loads(tpl.default_variables, {}),
        'is_system': tpl.is_system,
        'created_by_id': tpl.owner_id,
        'updated_at': _dt(tpl.updated_at),
    }


def serialize_material(material: models.Material):
    preview_url = material.public_url if material.material_type == 'image' and material.public_url else (
        f'/api/v1/assets/{material.id}/preview' if material.material_type == 'image' else ''
    )
    download_url = f'/api/v1/assets/{material.id}/download'
    public_url = material.public_url or material.url or ''
    return {
        'id': material.id,
        'name': material.name,
        'material_type': material.material_type,
        'mime_type': material.mime_type,
        'file_size': material.file_size,
        'folder_id': material.folder_id,
        'storage_provider': material.storage_provider or 'local',
        'storage_status': material.storage_status or 'ready',
        'bucket_name': material.bucket_name or '',
        'storage_key': material.storage_key or '',
        'public_url': public_url,
        'url': public_url or download_url,
        'preview_url': preview_url,
        'download_url': download_url,
        'created_at': _dt(material.created_at),
        'tags': json.loads(material.tags) if material.tags else [],
        'rag_meta': json.loads(material.rag_meta_json) if material.rag_meta_json else {},
    }

def get_request_ip(request: Request) -> str:
    forwarded = request.headers.get('x-forwarded-for', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.client.host if request.client else ''


def get_schedule_status(schedule: models.Schedule) -> str:
    return schedule.status or 'draft'


def sync_schedule_legacy_fields(schedule: models.Schedule) -> None:
    group_ids = json_loads(schedule.group_ids_json, [])
    schedule.name = schedule.title or schedule.name
    valid_gids = [g for g in group_ids if g and g != 0]
    if valid_gids:
        schedule.group_id = int(valid_gids[0])
    schedule.content_snapshot = schedule.content or schedule.content_snapshot
    schedule.skip_dates = schedule.skip_dates_json or schedule.skip_dates
    schedule.require_approval = 1 if schedule.approval_required else 0
    if schedule.status == 'approved':
        schedule.approval_status = 'approved'
    elif schedule.status == 'rejected':
        schedule.approval_status = 'rejected'
    elif schedule.status == 'pending_approval':
        schedule.approval_status = 'pending'
    elif schedule.approval_required:
        schedule.approval_status = 'pending'
    else:
        schedule.approval_status = 'not_required'


def resolve_schedule_status(schedule_type: str, enabled: bool, approval_required: bool, approval_state: str) -> str:
    if schedule_type == 'none':
        return 'draft'
    if not enabled:
        return 'draft'
    if approval_required:
        if approval_state == 'approved':
            return 'approved'
        if approval_state == 'rejected':
            return 'rejected'
        return 'pending_approval'
    return 'scheduled'


def serialize_schedule(schedule: models.Schedule, group_names: dict[int, str] | None = None):
    gids = json_loads(schedule.group_ids_json, [])
    next_runs = schedule_service.compute_next_runs(schedule, count=5)
    names_map = group_names or {}
    group_labels = [names_map.get(gid, f'群#{gid}') for gid in gids if gid and gid != 0]
    return {
        'id': schedule.id,
        'title': schedule.title,
        'group_ids': gids,
        'group_names': group_labels,
        'group_count': len(gids),
        'template_id': schedule.template_id,
        'msg_type': schedule.msg_type,
        'content_json': json_loads(schedule.content, {}),
        'variables_json': json_loads(schedule.variables, {}),
        'schedule_type': schedule.schedule_type,
        'run_at': _fmt(schedule.run_at),
        'next_run_at': _fmt(schedule.next_run_at),
        'next_runs': [_fmt(item) for item in next_runs],
        'cron_expr': schedule.cron_expr,
        'timezone': schedule.timezone,
        'enabled': bool(schedule.enabled),
        'approval_required': bool(schedule.approval_required),
        'approved_at': _dt(schedule.approved_at),
        'status': get_schedule_status(schedule),
        'skip_dates': json_loads(schedule.skip_dates_json, []),
        'skip_weekends': bool(schedule.skip_weekends),
        'last_error': schedule.last_error or '',
        'created_by_id': schedule.owner_id,
        'last_sent_at': _fmt(schedule.last_sent_at),
        'last_error': schedule.last_error or '',
        'created_at': _dt(schedule.created_at),
        'batch_items': json_loads(schedule.batch_items_json, None) if schedule.batch_items_json else None,
        'source_tag': schedule.source_tag,
    }


def serialize_log(log: models.MessageLog):
    message = log.message
    group = message.group if message and message.group else None
    return {
        'id': log.id,
        'job_id': message.source_id if message and message.source_type == 'schedule' else None,
        'group_id': message.group_id if message else None,
        'group_name': group.name if group else '',
        'msg_type': message.msg_type if message else '',
        'run_mode': 'retry' if log.attempt_no > 1 else (message.source_type if message else 'manual'),
        'success': bool(log.success),
        'resolved': bool(log.resolved),
        'error_message': log.error_message,
        'request_json': json_loads(log.request_payload, {}),
        'response_json': json_loads(log.response_payload, {}),
        'created_at': _dt(log.created_at),
    }


def parse_body(request_data: dict | str | bytes) -> dict:
    if isinstance(request_data, dict):
        return request_data
    if isinstance(request_data, bytes):
        request_data = request_data.decode('utf-8')
    return json.loads(request_data)


def has_real_webhook(webhook: str | None) -> bool:
    if not webhook:
        return False
    lowered = webhook.lower()
    return 'replace-test-key' not in lowered and 'replace-prod-key' not in lowered


def resolve_group_webhook(group: models.Group) -> str:
    try:
        webhook = decrypt_webhook(group.webhook_cipher) if group.webhook_cipher else ''
    except Exception:
        webhook = ''
    if not has_real_webhook(webhook):
        raise HTTPException(400, f'群“{group.name}”的 webhook 尚未配置为真实企业微信群机器人地址')
    return webhook


def build_context(user: models.User, group: models.Group | None = None, extra: dict | None = None, now: datetime | None = None):
    ctx = default_context(now=now, coach_name=user.display_name or user.username, group_name=group.name if group else '')
    if extra:
        ctx.update(extra)
    return ctx


def render_message_content(msg_type: str, content_json: dict, variables_json: dict, user: models.User, group: models.Group | None, now: datetime | None = None):
    ctx = build_context(user=user, group=group, extra=variables_json, now=now)
    rendered = render_value(content_json, ctx)
    if msg_type in {'image', 'emotion'} and isinstance(rendered, dict) and rendered.get('asset_id'):
        rendered['asset_id'] = int(rendered['asset_id'])
    if msg_type in {'file', 'voice'} and isinstance(rendered, dict) and rendered.get('asset_id'):
        rendered['asset_id'] = int(rendered['asset_id'])
    return rendered


def attach_asset_paths(db: Session, msg_type: str, content: dict):
    if msg_type not in {'image', 'emotion', 'file', 'voice', 'video'}:
        return content
    content = dict(content)
    asset_id = content.get('asset_id')
    if not asset_id:
        return content
    asset = db.query(models.Material).filter(models.Material.id == int(asset_id)).first()
    if not asset or asset.enabled != 1:
        raise HTTPException(400, '引用的资产不存在')
    if (asset.storage_status or 'ready') in {'source_missing', 'deleted'}:
        raise HTTPException(400, f'素材“{asset.name}”当前不可用，请重新上传后再发送')
    content['asset_meta'] = {
        'provider': asset.storage_provider or 'local',
        'storage_key': asset.storage_key or '',
        'public_url': asset.public_url or asset.url or '',
        'bucket': asset.bucket_name or '',
        'local_path': asset.storage_path or '',
        'mime_type': asset.mime_type or 'application/octet-stream',
        'file_size': asset.file_size or 0,
        'stored_filename': Path(asset.storage_key or asset.storage_path or asset.name).name,
        'original_filename': asset.source_filename or asset.name,
    }
    content['file_path'] = asset.storage_path
    content['file_name'] = asset.name
    content['file_url'] = asset.public_url or asset.url or ''
    if msg_type in {'image', 'emotion'}:
        content['image_path'] = asset.storage_path
        content['image_url'] = asset.public_url or asset.url or ''
    return content


def is_public_http_url(value: str | None) -> bool:
    if not value or not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def validate_outbound_content(msg_type: str, content: dict) -> None:
    if msg_type == 'voice':
        file_name = str(content.get('file_name') or content.get('asset_name') or '').lower()
        mime_type = str(content.get('asset_meta', {}).get('mime_type') or '').lower()
        file_size = int(content.get('asset_meta', {}).get('file_size') or 0)
        if not (file_name.endswith('.amr') or 'amr' in mime_type):
            raise HTTPException(400, '语音消息当前只支持 .amr 素材，请先上传 AMR 语音')
        if file_size > 2 * 1024 * 1024:
            raise HTTPException(400, '语音消息素材不能超过 2MB')
        return
    if msg_type != 'news':
        return
    articles = content.get('articles', [])
    if not isinstance(articles, list) or not articles:
        raise HTTPException(400, '图文消息至少需要一条文章')

    for index, article in enumerate(articles, start=1):
        if not isinstance(article, dict):
            raise HTTPException(400, f'图文第 {index} 条文章格式不正确')
        article_url = article.get('url', '')
        if not is_public_http_url(article_url):
            raise HTTPException(400, f'图文第 {index} 条文章链接必须是公网可访问的 http(s) 地址')
        if len(article_url) > 2000:
            raise HTTPException(400, f'图文第 {index} 条文章链接过长，请缩短后重试')
        picurl = article.get('picurl', '')
        if picurl:
            if not is_public_http_url(picurl):
                raise HTTPException(400, f'图文第 {index} 条封面图必须是公网可访问的 http(s) 图片地址')
            if len(picurl) > 2000:
                raise HTTPException(400, f'图文第 {index} 条封面图地址过长，请缩短后重试')




async def _send_to_single_group(
    group: models.Group, msg_type: str, content_json: dict, variables_json: dict,
    user: models.User, schedule: models.Schedule | None, max_retries: int, retry_delay: float,
    cached_media_id: dict[int, str],
) -> dict:
    """向单个群发送消息（含重试），使用独立 DB session 避免并发锁冲突。"""
    from ..database import SessionLocal
    is_file_type = msg_type in {'file', 'image', 'emotion', 'voice'}
    db = SessionLocal()
    try:
        rendered_content = render_message_content(msg_type, content_json, variables_json, user, group)
        rendered_content = attach_asset_paths(db, msg_type, rendered_content)
        validate_outbound_content(msg_type, rendered_content)

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

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                if is_file_type and 'asset_id' in rendered_content:
                    asset_id = int(rendered_content['asset_id'])
                    if asset_id in cached_media_id:
                        rendered_content['media_id'] = cached_media_id[asset_id]

                webhook = resolve_group_webhook(group)
                payload, response = await WeComService.send(webhook, msg_type, rendered_content, group_key=str(group.id))
                stored_payload = WeComService.payload_for_storage(payload)

                if is_file_type and 'asset_id' in rendered_content and rendered_content.get('media_id'):
                    cached_media_id[int(rendered_content['asset_id'])] = rendered_content['media_id']

                msg.request_payload = json_dumps(stored_payload)
                msg.status = 'sent'
                msg.sent_at = datetime.utcnow()
                msg.retry_count = attempt
                db.add(
                    models.MessageLog(
                        message_id=msg.id,
                        request_payload=json_dumps(stored_payload),
                        response_payload=json_dumps(response),
                        http_status=200,
                        success=1,
                        latency_ms=0,
                        attempt_no=attempt,
                    )
                )
                db.commit()
                result: dict = {'group_id': group.id, 'group_name': group.name, 'success': True, 'response': response}
                if attempt > 1:
                    result['retries'] = attempt
                return result
            except Exception as exc:
                last_error = exc
                error_str = str(exc).lower()
                # 检测到限流错误时，长等待让滑动窗口释放
                if '45009' in error_str or 'freq out of limit' in error_str or 'api freq' in error_str:
                    wait = 30 if attempt == 1 else 15
                    logger.warning('触发限流(45009)，等待 %ds 后重试 (attempt %d/%d)', wait, attempt, max_retries)
                    await asyncio.sleep(wait)
                elif '限流等待超过' in error_str or '条/分钟' in error_str:
                    wait = 35
                    logger.warning('本地限流保护触发，等待 %ds 后重试 (attempt %d/%d)', wait, attempt, max_retries)
                    await asyncio.sleep(wait)
                elif attempt < max_retries:
                    await asyncio.sleep(retry_delay)

        msg.status = 'failed'
        msg.sent_at = datetime.utcnow()
        msg.retry_count = max_retries
        db.add(
            models.MessageLog(
                message_id=msg.id,
                request_payload=json_dumps(rendered_content),
                response_payload='{}',
                http_status=500,
                success=0,
                latency_ms=0,
                error_message=f'{last_error} (已重试{max_retries}次)',
                attempt_no=max_retries,
            )
        )
        db.commit()
        return {'group_id': group.id, 'group_name': group.name, 'success': False, 'response': f'{last_error} (已重试{max_retries}次)'}
    finally:
        db.close()


_send_semaphore = asyncio.Semaphore(10)

async def do_send_to_groups(db: Session, groups: list[models.Group], msg_type: str, content_json: dict, variables_json: dict, user: models.User, schedule: models.Schedule | None = None, run_mode: str = 'immediate'):
    is_file_type = msg_type in {'file', 'image', 'emotion', 'voice'}
    max_retries = settings.file_send_max_retries if is_file_type else settings.send_max_retries
    retry_delay = settings.file_send_retry_delay_seconds if is_file_type else settings.send_retry_delay_seconds
    cached_media_id: dict[int, str] = {}

    async def _throttled_send(group):
        async with _send_semaphore:
            return await _send_to_single_group(group, msg_type, content_json, variables_json, user, schedule, max_retries, retry_delay, cached_media_id)

    # 多群并发发送，通过 Semaphore 限制同时最多 10 个并发；每个群使用独立 session 避免锁冲突
    tasks = [_throttled_send(group) for group in groups]
    results = await asyncio.gather(*tasks)
    return list(results)

async def perform_job_send(db: Session, schedule: models.Schedule, run_mode: str = 'scheduled'):
    import time as _time
    user = schedule.owner or db.query(models.User).filter(models.User.role == 'admin').first()
    if schedule.approval_required and schedule.status != 'approved':
        return {'skipped': True, 'reason': 'pending approval'}

    start_time = _time.time()

    # ── 队列模式：逐条执行 batch_items ──
    batch_items = json_loads(schedule.batch_items_json, None) if schedule.batch_items_json else None
    if batch_items:
        global_group_ids = json_loads(schedule.group_ids_json, [])
        all_results = []
        last_error = ''
        group_send_count: dict[int, int] = defaultdict(int)
        for idx, item in enumerate(batch_items):
            item_group_ids = item.get('group_ids') or global_group_ids
            if not item_group_ids:
                last_error = f'队列项 {item.get("msg_type")} 缺少目标群'
                continue
            groups = db.query(models.Group).filter(models.Group.id.in_(item_group_ids), models.Group.enabled == 1).all()

            # 预检：若同一群即将超过 18 条，提前等待一个完整窗口（留 2 条安全余量）
            for g in groups:
                if group_send_count[g.id] >= 18:
                    logger.info('群 %s 已发 %d 条，提前等待限流窗口', g.name, group_send_count[g.id])
                    await asyncio.sleep(30)
                    group_send_count.clear()
                    break

            try:
                results = await do_send_to_groups(
                    db, groups, item.get('msg_type', 'markdown'),
                    item.get('content_json', {}), item.get('variables_json', {}),
                    user, schedule=schedule, run_mode=run_mode,
                )
                all_results.extend(results or [])
                for g in groups:
                    group_send_count[g.id] += 1
            except Exception as exc:
                last_error = str(exc)[:200]
            # 同一 webhook 限 20条/分钟，由 WeComService._check_rate_limit 按 group_key 控制
            await asyncio.sleep(1.0)
        db.expire(schedule)
        schedule.last_error = last_error
        schedule.last_sent_at = datetime.now(ZoneInfo('Asia/Shanghai')).replace(tzinfo=None)
        db.commit()

        if schedule.source_tag == 'ranking' and all_results:
            try:
                await send_ranking_summary(schedule.id, start_time)
            except Exception as e:
                logger.warning('排行摘要发送失败: %s', e)

        return all_results

    # ── 单条模式（原有逻辑） ──
    group_ids = json_loads(schedule.group_ids_json, [])
    groups = db.query(models.Group).filter(models.Group.id.in_(group_ids), models.Group.enabled == 1).all()
    results = await do_send_to_groups(
        db,
        groups,
        schedule.msg_type,
        json_loads(schedule.content, {}),
        json_loads(schedule.variables, {}),
        user,
        schedule=schedule,
        run_mode=run_mode,
    )
    db.expire(schedule)
    schedule.last_error = ''
    schedule.last_sent_at = datetime.now(ZoneInfo('Asia/Shanghai')).replace(tzinfo=None)
    db.commit()

    return results
def get_user_or_401(request: Request, db: Session):
    return get_current_user(request, db)

@router.get('/bootstrap')
def bootstrap(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    total_logs = db.query(models.MessageLog).count()
    success_logs = db.query(models.MessageLog).filter(models.MessageLog.success == True).count()
    pending_approval_count = db.query(models.Schedule).filter(models.Schedule.approval_required == 1, models.Schedule.status == 'pending_approval').count()
    return {
        'current_user': {'id': user.id, 'username': user.username, 'display_name': user.display_name, 'role': user.role, 'permissions': json_loads(user.permissions_json, {})},
        'dashboard': {
            'group_count': db.query(models.Group).count(),
            'template_count': db.query(models.Template).count(),
            'schedule_count': db.query(models.Schedule).filter(models.Schedule.schedule_type != 'none').count(),
            'log_count': total_logs,
            'success_rate': round((success_logs / total_logs) * 100, 2) if total_logs else 0,
            'pending_approval_count': pending_approval_count,
        }
    }

@router.get('/groups')
def list_groups(request: Request, db: Session = Depends(get_db)):
    get_user_or_401(request, db)
    groups = db.query(models.Group).order_by(models.Group.group_type.desc(), models.Group.id.desc()).all()
    return [serialize_group(g) for g in groups]

@router.post('/groups')
async def upsert_group(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'group')
    data = parse_body(await request.body())
    group_id = data.get('id')
    group = db.query(models.Group).filter(models.Group.id == group_id).first() if group_id else models.Group()
    if not group_id:
        db.add(group)
    group.name = data['name']
    group.alias = data.get('alias', '')
    group.tags = json_dumps(data.get('tags', []))
    group.enabled = 1 if data.get('is_enabled', True) else 0
    group.group_type = 'test' if data.get('is_test_group') else 'formal'
    if data.get('webhook'):
        group.webhook_cipher = encrypt_webhook(data['webhook'])
    db.commit()
    return serialize_group(group)

@router.delete('/groups/{group_id}')
def delete_group(group_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'group')
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
    perms = json_loads(user.permissions_json, {})
    if user.role != 'admin' and not perms.get('template'):
        query = query.filter((models.Template.is_system == True) | (models.Template.owner_id == user.id))
    templates = query.order_by(models.Template.is_system.desc(), models.Template.updated_at.desc()).all()
    return [serialize_template(t) for t in templates]

@router.post('/templates')
async def upsert_template(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'template')
    data = parse_body(await request.body())
    template_id = data.get('id')
    tpl = db.query(models.Template).filter(models.Template.id == template_id).first() if template_id else models.Template(owner_id=user.id)
    if template_id and user.role != 'admin' and tpl.owner_id != user.id and not tpl.is_system:
        raise HTTPException(403, '不能修改其他人的模板')
    if not template_id:
        db.add(tpl)
    tpl.name = data['name']
    tpl.category = data.get('category', 'general')
    tpl.msg_type = data['msg_type']
    tpl.content = json_dumps(data.get('content_json', {}))
    tpl.default_variables = json_dumps(data.get('variables_json', {}))
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
        content=tpl.content,
        default_variables=tpl.default_variables,
        is_system=0,
        owner_id=user.id,
    )
    db.add(cloned)
    db.commit()
    return serialize_template(cloned)

@router.delete('/templates/{template_id}')
def delete_template(template_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'template')
    tpl = db.query(models.Template).filter(models.Template.id == template_id).first()
    if not tpl:
        raise HTTPException(404, '模板不存在')
    if tpl.is_system and user.role != 'admin':
        raise HTTPException(403, '系统模板只能由管理员删除')
    if user.role != 'admin' and tpl.owner_id != user.id:
        raise HTTPException(403, '不能删除其他人的模板')
    db.delete(tpl)
    db.commit()
    return {'ok': True}

@router.get('/assets')
def list_assets(request: Request, folder_id: str = None, db: Session = Depends(get_db)):
    get_user_or_401(request, db)
    query = db.query(models.Material).filter(models.Material.enabled == 1).order_by(models.Material.id.desc())
    if folder_id == 'uncategorized':
        query = query.filter(models.Material.folder_id == None)
    elif folder_id is not None and folder_id.isdigit():
        query = query.filter(models.Material.folder_id == int(folder_id))
    assets = query.all()
    return [serialize_material(a) for a in assets]


@router.post('/assets/prepare-upload')
async def prepare_asset_upload(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'asset')
    body = await request.json()
    filename = str(body.get('filename', '')).strip()
    mime_type = str(body.get('mime_type', 'application/octet-stream'))
    if not filename:
        raise HTTPException(400, '缺少 filename')
    config = storage_facade.prepare_client_upload(filename, mime_type)
    if not config:
        return {'mode': 'server'}
    return config


@router.post('/assets/confirm-upload')
async def confirm_asset_upload(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'asset')
    body = await request.json()
    object_key = str(body.get('object_key', '')).strip()
    public_url = str(body.get('public_url', '')).strip()
    name = str(body.get('name', '')).strip()
    folder_id = body.get('folder_id')
    file_size = int(body.get('file_size', 0))
    mime_type = str(body.get('mime_type', 'application/octet-stream'))
    if not object_key or not name:
        raise HTTPException(400, '缺少 object_key 或 name')
    material_type = 'image' if mime_type.startswith('image/') else 'file'
    asset = models.Material(
        name=name,
        material_type=material_type,
        storage_path=resolve_material_storage_path(object_key=object_key, public_url=public_url),
        url=public_url,
        mime_type=mime_type,
        file_size=file_size,
        folder_id=int(folder_id) if folder_id and str(folder_id) not in ('', 'null', 'undefined') else None,
        owner_id=user.id,
        storage_provider='qiniu',
        storage_status='ready',
        storage_key=object_key,
        domain=urlparse(public_url).netloc if public_url else '',
        public_url=public_url,
        source_filename=name,
        bucket_name=storage_facade.active_provider.config.bucket if hasattr(storage_facade.active_provider, 'config') else '',
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return serialize_material(asset)


@router.post('/assets')
async def upload_asset(request: Request, file: UploadFile = File(...), folder_id: str = Form(None), db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'asset')
    raw = await file.read()
    fid = int(folder_id) if folder_id and folder_id.isdigit() else None
    folder = db.query(models.AssetFolder).filter(models.AssetFolder.id == fid).first() if fid else None
    is_voice_folder = bool(folder and folder.parent_id is None and folder.name == '语音')
    upload_filename = Path(file.filename).name
    upload_mime_type = file.content_type or 'application/octet-stream'

    if is_voice_folder:
        normalized_audio_ext = guess_audio_extension(upload_filename, upload_mime_type)
        if not is_supported_audio_upload(upload_filename, upload_mime_type):
            raise HTTPException(400, '语音文件夹只支持上传常见音频文件，系统会自动转成 AMR')
        if normalized_audio_ext and Path(upload_filename).suffix.lower() != normalized_audio_ext:
            upload_filename = f'{Path(upload_filename).stem or "voice"}{normalized_audio_ext}'
        if not is_amr_filename(upload_filename):
            try:
                raw, upload_filename, upload_mime_type = transcode_audio_to_amr(raw, upload_filename)
            except AudioTranscodeError as exc:
                raise HTTPException(400, str(exc))

    asset_type = 'image' if upload_mime_type.startswith('image/') else 'file'
    storage_result = storage_facade.upload(
        UploadPayload(
            content=raw,
            filename=upload_filename,
            mime_type=upload_mime_type,
        )
    )
    asset = models.Material(
        name=upload_filename,
        source_filename=Path(file.filename).name,
        material_type=asset_type,
        storage_path=storage_result.local_path,
        url=storage_result.public_url,
        public_url=storage_result.public_url,
        storage_provider=storage_result.provider,
        storage_key=storage_result.object_key,
        bucket_name=storage_result.bucket,
        domain=urlparse(storage_result.public_url).netloc if storage_result.public_url else '',
        storage_status='ready',
        provider_etag=storage_result.extra.get('hash', ''),
        mime_type=upload_mime_type,
        file_size=storage_result.file_size,
        file_hash=hashlib.sha256(raw).hexdigest(),
        folder_id=fid,
        owner_id=user.id,
    )
    db.add(asset)
    db.commit()
    log_material_storage_event(
        db,
        asset,
        operation_type='upload',
        operation_status='success',
        user_id=user.id,
        operator_ip=get_request_ip(request),
        extra={'provider_extra': storage_result.extra},
    )
    db.commit()
    return serialize_material(asset)

@router.get('/assets/{asset_id}/download')
def download_asset(asset_id: int, request: Request, db: Session = Depends(get_db)):
    get_user_or_401(request, db)
    asset = db.query(models.Material).filter(models.Material.id == asset_id).first()
    if not asset:
        raise HTTPException(404, '资产不存在')
    payload = storage_facade.download_bytes(build_storage_result_from_material(asset))
    headers = {'Content-Disposition': f'attachment; filename="{asset.name}"'}
    return StreamingResponse(BytesIO(payload), media_type=asset.mime_type, headers=headers)

@router.get('/assets/{asset_id}/preview')
def preview_asset(asset_id: int, request: Request, db: Session = Depends(get_db)):
    get_user_or_401(request, db)
    asset = db.query(models.Material).filter(models.Material.id == asset_id).first()
    if not asset:
        raise HTTPException(404, '资产不存在')
    if asset.material_type != 'image':
        raise HTTPException(400, '当前素材不支持图片预览')
    payload = storage_facade.download_bytes(build_storage_result_from_material(asset))
    return Response(content=payload, media_type=asset.mime_type)

@router.delete('/assets/{asset_id}')
def delete_asset(asset_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    require_permission(user, 'asset')
    asset = db.query(models.Material).filter(models.Material.id == asset_id).first()
    if not asset:
        raise HTTPException(404, '资产不存在')
    try:
        storage_facade.delete(build_storage_result_from_material(asset))
        asset.deleted_from_storage_at = datetime.utcnow()
        log_material_storage_event(
            db,
            asset,
            operation_type='delete',
            operation_status='success',
            user_id=user.id,
            operator_ip=get_request_ip(request),
        )
    except Exception as exc:
        log_material_storage_event(
            db,
            asset,
            operation_type='delete',
            operation_status='failed',
            user_id=user.id,
            operator_ip=get_request_ip(request),
            error_message=str(exc),
        )
        db.commit()
        raise HTTPException(500, f'删除存储资源失败: {exc}') from exc
    asset.enabled = 0
    asset.storage_status = 'deleted'
    asset.deleted_at = datetime.utcnow()
    db.commit()
    return {'ok': True}


@router.patch('/assets/{asset_id}/rename')
async def rename_asset(asset_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'asset')
    asset = db.query(models.Material).filter(models.Material.id == asset_id).first()
    if not asset:
        raise HTTPException(404, '素材不存在')
    body = await request.json()
    name = str(body.get('name', '')).strip()
    if not name:
        raise HTTPException(400, '文件名不能为空')
    asset.name = name
    db.commit()
    db.refresh(asset)
    return serialize_material(asset)


@router.patch('/assets/{asset_id}/tags')
async def update_asset_tags(asset_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'asset')
    asset = db.query(models.Material).filter(models.Material.id == asset_id).first()
    if not asset:
        raise HTTPException(404, '素材不存在')
    body = await request.json()
    tags = body.get('tags', [])
    if not isinstance(tags, list):
        raise HTTPException(400, 'tags 必须是数组')
    asset.tags = json.dumps([str(t).strip() for t in tags if str(t).strip()])
    db.commit()
    db.refresh(asset)
    return serialize_material(asset)


@router.patch('/assets/{asset_id}/move')
async def move_asset(asset_id: int, request: Request, db: Session = Depends(get_db)):
    get_user_or_401(request, db)
    asset = db.query(models.Material).filter(models.Material.id == asset_id).first()
    if not asset:
        raise HTTPException(404, '素材不存在')
    body = await request.json()
    folder_id = body.get('folder_id')
    if folder_id is not None:
        folder = db.query(models.AssetFolder).filter(models.AssetFolder.id == int(folder_id)).first()
        if not folder:
            raise HTTPException(404, '文件夹不存在')
    asset.folder_id = int(folder_id) if folder_id is not None else None
    db.commit()
    return serialize_material(asset)


@router.patch('/assets/{asset_id}/rag-meta')
async def update_asset_rag_meta(asset_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'asset')
    asset = db.query(models.Material).filter(models.Material.id == asset_id).first()
    if not asset:
        raise HTTPException(404, '素材不存在')
    body = await request.json()
    from ..schemas.material_rag import RagMetaUpdate
    rag_data = RagMetaUpdate(**body)
    from ..services.material_rag_service import save_rag_meta_and_index
    result = await save_rag_meta_and_index(db, asset_id, rag_data.model_dump())
    return result


@router.post('/preview')
async def preview_message(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'send')
    data = parse_body(await request.body())
    group = None
    if data.get('group_ids'):
        group = db.query(models.Group).filter(models.Group.id == data['group_ids'][0]).first()
    rendered_content = render_message_content(data['msg_type'], data.get('content_json', {}), data.get('variables_json', {}), user, group)
    rendered_content = attach_asset_paths(db, data['msg_type'], rendered_content)
    validate_outbound_content(data['msg_type'], rendered_content)
    payload = WeComService.build_payload(
        data['msg_type'],
        rendered_content if data['msg_type'] not in {'file', 'voice'} else {**rendered_content, 'media_id': rendered_content.get('media_id', '<运行时上传后生成>')}
    )
    return {'rendered_content': rendered_content, 'payload_preview': payload}

@router.post('/send')
async def send_message(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'send')
    data = parse_body(await request.body())
    group_ids = data.get('group_ids', [])
    if data.get('test_group_only'):
        groups = db.query(models.Group).filter(models.Group.group_type == 'test', models.Group.enabled == 1).all()
        if not groups:
            groups = db.query(models.Group).filter(models.Group.enabled == 1).filter(
                (models.Group.alias == 'TEST_GROUP') | (models.Group.name == '测试群')
            ).all()
    else:
        groups = db.query(models.Group).filter(models.Group.id.in_(group_ids), models.Group.enabled == 1).all()
    if not groups:
        raise HTTPException(400, '请选择至少一个已启用的群')
    results = await do_send_to_groups(db, groups, data['msg_type'], data.get('content_json', {}), data.get('variables_json', {}), user, run_mode='test' if data.get('test_group_only') else 'immediate')
    return {'results': results}

@router.get('/schedules')
def list_schedules(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    query = db.query(models.Schedule)
    perms = json_loads(user.permissions_json, {})
    if user.role != 'admin' and not perms.get('schedule'):
        query = query.filter(models.Schedule.owner_id == user.id)
    jobs = query.order_by(models.Schedule.created_at.desc()).all()
    # 批量加载所有目标群组名称
    all_gids: set[int] = set()
    for job in jobs:
        for gid in json_loads(job.group_ids_json, []):
            if gid and gid != 0:
                all_gids.add(gid)
    group_names: dict[int, str] = {}
    if all_gids:
        for g in db.query(models.Group).filter(models.Group.id.in_(all_gids)).all():
            group_names[g.id] = g.name
    return [serialize_schedule(job, group_names) for job in jobs]

@router.post('/schedules')
async def create_or_update_schedule(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'schedule')
    data = parse_body(await request.body())
    job_id = data.get('id')
    job = db.query(models.Schedule).filter(models.Schedule.id == job_id).first() if job_id else models.Schedule(owner_id=user.id)
    if job_id and user.role != 'admin' and job.owner_id != user.id:
        raise HTTPException(403, '不能修改其他人的任务')
    if not job_id:
        db.add(job)
    group_ids = data.get('group_ids', [])
    batch_items = data.get('batch_items_json')
    # 队列调度时，每条 item 自带 group_ids，全局 group_ids 可为空
    if not group_ids and not batch_items:
        raise HTTPException(400, '请选择至少一个群')
    job.title = data['title']
    # batch_items 模式：从 batch_items 中提取真实目标群 ID（前端可能传 [0] 占位）
    if batch_items and (not group_ids or group_ids == [0]):
        extracted_gids: set[int] = set()
        for item in batch_items:
            for gid in (item.get('group_ids') or []):
                if gid and gid != 0:
                    extracted_gids.add(gid)
        if extracted_gids:
            group_ids = sorted(extracted_gids)
    job.group_ids_json = json_dumps(group_ids) if group_ids else '[]'
    job.template_id = data.get('template_id')
    job.msg_type = data.get('msg_type', 'markdown')
    job.content = json_dumps(data.get('content_json', {}))
    job.variables = json_dumps(data.get('variables_json', {}))
    job.batch_items_json = json_dumps(batch_items) if batch_items else None
    # group_id 外键：取第一个有效的群 ID
    primary_gid = data.get('group_id')
    if (not primary_gid or primary_gid == 0) and group_ids:
        primary_gid = group_ids[0] if group_ids[0] != 0 else None
    if primary_gid:
        job.group_id = primary_gid
    job.schedule_type = data.get('schedule_type', 'none')
    run_at = data.get('run_at')
    job.run_at = datetime.fromisoformat(run_at) if run_at else None
    job.cron_expr = data.get('cron_expr', '')
    job.timezone = data.get('timezone', 'Asia/Shanghai')
    job.enabled = 1 if data.get('enabled', True) else 0
    job.approval_required = 1 if data.get('approval_required', False) else 0
    job.skip_dates_json = json_dumps(data.get('skip_dates', []))
    job.skip_weekends = 1 if data.get('skip_weekends', False) else 0
    job.source_tag = data.get('source_tag') or None
    if job.schedule_type == 'none':
        job.enabled = 0
    approval_state = 'approved' if job.approval_required and user.role == 'admin' else 'pending' if job.approval_required else 'not_required'
    job.status = resolve_schedule_status(job.schedule_type, bool(job.enabled), bool(job.approval_required), approval_state)
    if approval_state == 'approved':
        job.approved_at = datetime.utcnow()
        job.approved_by_id = user.id
    sync_schedule_legacy_fields(job)
    job.next_run_at = schedule_service.compute_next_run_at(job)
    db.commit()
    if job.approval_required and job.status == 'pending_approval':
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
        name=f'{job.title} - 副本',
        title=f'{job.title} - 副本',
        group_id=job.group_id,
        group_ids_json=job.group_ids_json,
        template_id=job.template_id,
        msg_type=job.msg_type,
        content_snapshot=job.content_snapshot,
        content=job.content,
        variables=job.variables,
        schedule_type=job.schedule_type,
        run_at=job.run_at,
        cron_expr=job.cron_expr,
        timezone=job.timezone,
        enabled=0,
        require_approval=job.require_approval,
        approval_required=job.approval_required,
        approval_status='pending' if job.require_approval else 'not_required',
        status='pending_approval' if job.approval_required else 'draft',
        skip_dates=job.skip_dates,
        skip_dates_json=job.skip_dates_json,
        skip_weekends=job.skip_weekends,
        owner_id=user.id,
    )
    db.add(cloned)
    cloned.next_run_at = schedule_service.compute_next_run_at(cloned)
    db.commit()
    return serialize_schedule(cloned)

@router.post('/schedules/{job_id}/toggle')
def toggle_schedule(job_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'schedule')
    job = db.query(models.Schedule).filter(models.Schedule.id == job_id).first()
    if not job:
        raise HTTPException(404, '任务不存在')
    if user.role != 'admin' and job.owner_id != user.id:
        raise HTTPException(403, '不能操作其他人的任务')
    job.enabled = not job.enabled
    job.status = resolve_schedule_status(job.schedule_type, bool(job.enabled), bool(job.approval_required), job.approval_status)
    sync_schedule_legacy_fields(job)
    job.next_run_at = schedule_service.compute_next_run_at(job)
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
    job.approval_required = 1
    job.status = 'approved'
    job.approved_at = datetime.utcnow()
    job.approved_by_id = user.id
    sync_schedule_legacy_fields(job)
    job.next_run_at = schedule_service.compute_next_run_at(job)
    db.commit()
    schedule_service.add_or_update_job(job)
    return serialize_schedule(job)

@router.delete('/schedules/{job_id}')
def delete_schedule(job_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'schedule')
    job = db.query(models.Schedule).filter(models.Schedule.id == job_id).first()
    if not job:
        raise HTTPException(404, '任务不存在')
    if user.role != 'admin' and job.owner_id != user.id:
        raise HTTPException(403, '不能删除其他人的任务')
    db.delete(job)
    db.commit()
    schedule_service.sync_from_db()
    return {'ok': True}

@router.post('/schedules/{job_id}/run-now')
async def run_schedule_now(job_id: int, request: Request, db: Session = Depends(get_db)):
    import logging
    _log = logging.getLogger(__name__)
    user = get_user_or_401(request, db)
    require_permission(user, 'schedule')
    job = db.query(models.Schedule).filter(models.Schedule.id == job_id).first()
    if not job:
        raise HTTPException(404, '任务不存在')
    if user.role != 'admin' and job.owner_id != user.id:
        raise HTTPException(403, '不能执行其他人的任务')
    if job.approval_required and job.status != 'approved' and user.role != 'admin':
        raise HTTPException(403, '该任务尚未审批')
    _log.info(f'Manual run triggered: job {job_id} ({job.title}) by user {user.username}')
    results = await perform_job_send(db, job, run_mode='manual-run')
    return {'results': results}

@router.get('/logs')
def list_logs(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    query = db.query(models.MessageLog).order_by(models.MessageLog.created_at.desc())
    if user.role != 'admin':
        query = query.join(models.Message).filter(models.Message.created_by == user.id)
    logs = query.limit(200).all()
    return [serialize_log(log) for log in logs]

@router.post('/logs/{log_id}/retry')
async def retry_log(log_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_permission(user, 'log')
    log = db.query(models.MessageLog).filter(models.MessageLog.id == log_id).first()
    if not log:
        raise HTTPException(404, '日志不存在')
    if not log.message:
        raise HTTPException(400, '该日志缺少消息记录，无法重试')
    if user.role != 'admin' and log.message.created_by != user.id:
        raise HTTPException(403, '不能重试其他人的日志')
    if not log.message.group:
        raise HTTPException(400, '该日志缺少群信息，无法重试')
    webhook = resolve_group_webhook(log.message.group)
    try:
        rendered_content = json_loads(log.message.rendered_content, {})
        validate_outbound_content(log.message.msg_type, rendered_content)
        payload, response = await WeComService.send(
            webhook,
            log.message.msg_type,
            rendered_content,
            group_key=str(log.message.group_id),
        )
        stored_payload = WeComService.payload_for_storage(payload)
        new_log = models.MessageLog(
            message_id=log.message_id,
            request_payload=json_dumps(stored_payload),
            response_payload=json_dumps(response),
            http_status=200,
            success=1,
            latency_ms=0,
            attempt_no=log.attempt_no + 1,
        )
        db.add(new_log)
        # 重试成功：将同一 message 的所有失败日志标记为已补发
        failed_logs = db.query(models.MessageLog).filter(
            models.MessageLog.message_id == log.message_id,
            models.MessageLog.success == 0,
            models.MessageLog.resolved == False,
        ).all()
        for fl in failed_logs:
            fl.resolved = True
        db.commit()
        return serialize_log(new_log)
    except Exception as exc:
        new_log = models.MessageLog(
            message_id=log.message_id,
            request_payload=log.request_payload,
            response_payload='{}',
            http_status=500,
            success=0,
            latency_ms=0,
            error_message=str(exc),
            attempt_no=log.attempt_no + 1,
        )
        db.add(new_log)
        db.commit()
        return JSONResponse(status_code=400, content=serialize_log(new_log))

@router.get('/users')
def list_users(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin')
    users = db.query(models.User).order_by(models.User.id.desc()).all()
    return [{'id': u.id, 'username': u.username, 'display_name': u.display_name, 'role': u.role, 'is_active': u.status, 'created_at': _dt(u.created_at)} for u in users]

@router.post('/users')
async def upsert_user(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin')
    data = parse_body(await request.body())
    username = (data.get('username') or '').strip()
    if not username:
        raise HTTPException(400, '用户名不能为空')

    target = db.query(models.User).filter(models.User.id == data.get('id')).first() if data.get('id') else models.User()
    if data.get('id') and not target:
        raise HTTPException(404, '用户不存在')

    duplicate = (
        db.query(models.User)
        .filter(models.User.username == username)
        .first()
    )
    if duplicate and duplicate.id != target.id:
        source_label = 'CRM 同步账号' if (duplicate.auth_source or 'local') == 'crm' else '本地账号'
        raise HTTPException(400, f'用户名“{username}”已存在，当前为{source_label}')

    password = (data.get('password') or '').strip()
    if not data.get('id') and not password:
        raise HTTPException(400, '新增用户时必须设置登录密码')

    if not data.get('id'):
        db.add(target)
        target.auth_source = 'local'
        target.permissions_json = target.permissions_json or '{}'
    target.username = username
    target.display_name = data.get('display_name', username)
    target.role = data.get('role', 'coach')
    target.status = bool(data.get('is_active', True))
    if password:
        target.password_hash = hash_password(password)
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
    pending_approval_count = db.query(models.Schedule).filter(models.Schedule.approval_required == 1, models.Schedule.status == 'pending_approval').count()

    result = {
        'group_count': db.query(models.Group).count(),
        'template_count': db.query(models.Template).count(),
        'schedule_count': db.query(models.Schedule).filter(models.Schedule.schedule_type != 'none').count(),
        'log_count': total_logs,
        'success_rate': round((success_logs / total_logs) * 100, 2) if total_logs else 0,
        'pending_approval_count': pending_approval_count,
    }

    # === 教练工作台数据 ===
    tz = ZoneInfo('Asia/Shanghai')
    now_local = datetime.now(tz)
    today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)

    # 今日待发送：一次性任务 run_at 在今天，且状态为 scheduled/approved
    today_schedules = db.query(models.Schedule).filter(
        models.Schedule.schedule_type == 'once',
        models.Schedule.enabled == 1,
        models.Schedule.run_at >= today_start,
        models.Schedule.run_at <= today_end,
        models.Schedule.status.in_(['scheduled', 'approved']),
    ).order_by(models.Schedule.run_at).all()

    result['today_schedules'] = [{
        'id': s.id,
        'title': s.title,
        'run_at': _fmt(s.run_at),
        'msg_type': s.msg_type,
        'group_ids': json_loads(s.group_ids_json, []),
    } for s in today_schedules]

    # 最近编辑的运营计划
    recent_plans = db.query(models.Plan).order_by(models.Plan.updated_at.desc()).limit(5).all()
    result['recent_plans'] = [{
        'id': p.id,
        'name': p.name,
        'stage': p.stage,
        'status': p.status,
        'day_count': len(p.days) if p.days else 0,
        'updated_at': _dt(p.updated_at),
    } for p in recent_plans]

    # 今日已发送（sent_at 存 naive UTC，需用 UTC 范围匹配）
    utc_today_start = today_start.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
    utc_today_end = today_end.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
    today_sent = db.query(models.Message).filter(
        models.Message.sent_at >= utc_today_start,
        models.Message.sent_at <= utc_today_end,
        models.Message.status == 'sent',
    ).count()
    result['today_sent'] = today_sent

    return result

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
            "created_at": _dt(a.created_at) if hasattr(a, 'created_at') else None
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
    require_permission(user, 'approval')
    
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
            job.approval_required = 1
            job.status = 'approved'
            job.approved_at = datetime.utcnow()
            job.approved_by_id = user.id
            sync_schedule_legacy_fields(job)
            schedule_service.add_or_update_job(job)
    
    db.commit()
    return {"id": appr.id, "status": appr.status}

@router.post('/approvals/{approval_id}/reject')
async def reject_request(approval_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin')
    require_permission(user, 'approval')
    
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
            job.approval_required = 1
            job.status = 'rejected'
            sync_schedule_legacy_fields(job)
            schedule_service.add_or_update_job(job)

    db.commit()
    return {"id": appr.id, "status": appr.status}


@router.post('/ai/polish')
async def ai_polish(request: Request, db: Session = Depends(get_db)):
    get_user_or_401(request, db)
    from ..services.ai_polish import polish_text
    body = parse_body(await request.body())
    content = body.get('content', '')
    instruction = body.get('instruction', '')
    msg_type = body.get('msg_type', 'text')
    if not instruction and not content:
        raise HTTPException(400, '请输入修改指令或原始内容')
    result = await polish_text(content, instruction or '润色优化这段文字', msg_type)
    return {'content': result}
