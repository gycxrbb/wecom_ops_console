from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..services.operation_plan_export import export_plan_to_excel_bytes, export_plan_to_json_bytes
from ..services.operation_plan_import import parse_operation_plan_file
from ..services.operation_plan_import_points import build_default_campaign_plan
from ..services.operation_plan_publish import publish_plan_to_groups
from ..services.operation_plan_constants import NODE_PRESETS, NODE_PRESET_MAP, POINTS_CAMPAIGN_STAGES
from ..security import get_current_user, json_dumps, json_loads, require_role, require_permission
from ..route_helper import _dt

router = APIRouter(prefix='/api/v1/operation-plans', tags=['operation-plans'])



class PlanCreate(BaseModel):
    name: str
    topic: str = ''
    stage: str = ''
    description: str = ''
    plan_mode: str = 'day_flow'
    day_count: int = Field(default=1, ge=0, le=90)


class PlanUpdate(BaseModel):
    name: str
    topic: str = ''
    stage: str = ''
    description: str = ''
    plan_mode: str = 'day_flow'
    status: str = 'draft'


class PlanDayCreate(BaseModel):
    day_number: int = Field(ge=1, le=365)
    title: str = ''
    focus: str = ''
    trigger_rule_json: dict[str, Any] = Field(default_factory=dict)
    auto_init_nodes: bool = True


class PlanDayUpdate(BaseModel):
    day_number: int = Field(ge=1, le=365)
    title: str = ''
    focus: str = ''
    trigger_rule_json: dict[str, Any] = Field(default_factory=dict)
    status: str = 'draft'


class PlanDayCopyRequest(BaseModel):
    source_day_id: int


class PlanNodeCreate(BaseModel):
    node_type: str = 'custom'
    title: str = ''
    description: str = ''
    sort_order: int | None = None
    template_id: int | None = None
    msg_type: str = 'markdown'
    content_json: dict[str, Any] = Field(default_factory=dict)
    variables_json: dict[str, Any] = Field(default_factory=dict)
    status: str = 'draft'
    enabled: bool = True


class PlanNodeUpdate(BaseModel):
    node_type: str = 'custom'
    title: str = ''
    description: str = ''
    sort_order: int = 0
    template_id: int | None = None
    msg_type: str = 'markdown'
    content_json: dict[str, Any] = Field(default_factory=dict)
    variables_json: dict[str, Any] = Field(default_factory=dict)
    status: str = 'draft'
    enabled: bool = True


def get_user_or_401(request: Request, db: Session) -> models.User:
    return get_current_user(request, db)


def ensure_plan_access(user: models.User, plan: models.Plan) -> None:
    if user.role == 'admin':
        return
    perms = json_loads(user.permissions_json, {})
    if perms.get('plan'):
        return
    if plan.owner_id != user.id:
        raise HTTPException(403, '不能操作其他人的运营计划')


def get_plan_or_404(db: Session, plan_id: int) -> models.Plan:
    plan = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, '运营计划不存在')
    return plan


def get_day_or_404(db: Session, day_id: int) -> models.PlanDay:
    day = db.query(models.PlanDay).filter(models.PlanDay.id == day_id).first()
    if not day:
        raise HTTPException(404, '运营天不存在')
    return day


def get_node_or_404(db: Session, node_id: int) -> models.PlanNode:
    node = db.query(models.PlanNode).filter(models.PlanNode.id == node_id).first()
    if not node:
        raise HTTPException(404, '流程节点不存在')
    return node


def serialize_node(node: models.PlanNode) -> dict[str, Any]:
    return {
        'id': node.id,
        'plan_day_id': node.plan_day_id,
        'node_type': node.node_type,
        'title': node.title,
        'description': node.description or '',
        'sort_order': node.sort_order,
        'template_id': node.template_id,
        'msg_type': node.msg_type,
        'content_json': json_loads(node.content_json, {}),
        'variables_json': json_loads(node.variables_json, {}),
        'status': node.status,
        'enabled': bool(node.enabled),
        'created_by_id': node.owner_id,
        'updated_at': _dt(node.updated_at),
    }


def serialize_day(day: models.PlanDay, include_nodes: bool = True) -> dict[str, Any]:
    payload = {
        'id': day.id,
        'plan_id': day.plan_id,
        'day_number': day.day_number,
        'title': day.title,
        'focus': day.focus or '',
        'trigger_rule_json': json_loads(day.trigger_rule_json, {}),
        'status': day.status,
        'created_by_id': day.owner_id,
        'updated_at': _dt(day.updated_at),
        'node_count': len(day.nodes),
    }
    if include_nodes:
        payload['nodes'] = [serialize_node(node) for node in day.nodes]
    return payload


def serialize_plan(plan: models.Plan, include_days: bool = False) -> dict[str, Any]:
    payload = {
        'id': plan.id,
        'name': plan.name,
        'topic': plan.topic or '',
        'stage': plan.stage or '',
        'description': plan.description or '',
        'plan_mode': getattr(plan, 'plan_mode', None) or 'day_flow',
        'status': plan.status,
        'created_by_id': plan.owner_id,
        'updated_at': _dt(plan.updated_at),
        'day_count': len(plan.days),
        'node_count': sum(len(day.nodes) for day in plan.days),
    }
    if include_days:
        payload['days'] = [serialize_day(day) for day in plan.days]
    return payload


def resolve_template_defaults(db: Session, template_id: int | None) -> tuple[str | None, dict[str, Any], dict[str, Any]]:
    if not template_id:
        return None, {}, {}
    template = db.query(models.Template).filter(models.Template.id == template_id).first()
    if not template:
        raise HTTPException(404, '引用的模板不存在')
    return (
        template.msg_type,
        json_loads(template.content, {}),
        json_loads(template.default_variables, {}),
    )


def apply_node_payload(node: models.PlanNode, db: Session, payload: PlanNodeCreate | PlanNodeUpdate, owner_id: int) -> None:
    template_msg_type, template_content, template_variables = resolve_template_defaults(db, payload.template_id)
    preset = NODE_PRESET_MAP.get(payload.node_type)

    default_title = preset['title'] if preset else ''
    default_description = preset['description'] if preset else ''
    default_sort_order = preset['sort_order'] if preset else 999
    default_msg_type = template_msg_type or (preset['msg_type'] if preset else 'markdown')
    default_content = template_content or (preset['content_json'] if preset else {})
    default_variables = template_variables or {}

    node.node_type = payload.node_type
    node.title = payload.title or default_title
    node.description = payload.description or default_description
    node.sort_order = payload.sort_order if payload.sort_order is not None else default_sort_order
    node.template_id = payload.template_id
    node.msg_type = payload.msg_type or default_msg_type
    node.content_json = json_dumps(payload.content_json or default_content)
    node.variables_json = json_dumps(payload.variables_json or default_variables)
    node.status = payload.status
    node.enabled = 1 if payload.enabled else 0
    node.owner_id = owner_id


def build_default_nodes(day: models.PlanDay, owner_id: int) -> list[models.PlanNode]:
    built_nodes: list[models.PlanNode] = []
    for preset in NODE_PRESETS:
        built_nodes.append(
            models.PlanNode(
                plan_day=day,
                node_type=preset['node_type'],
                title=preset['title'],
                description=preset['description'],
                sort_order=preset['sort_order'],
                msg_type=preset['msg_type'],
                content_json=json_dumps(
                    {
                        **preset['content_json'],
                        'content': preset['content_json']['content'].replace('{{ day_number }}', str(day.day_number)),
                    }
                ),
                variables_json='{}',
                status='draft',
                enabled=1,
                owner_id=owner_id,
            )
        )
    return built_nodes


def build_campaign_nodes(day: models.PlanDay, stage: dict[str, Any], owner_id: int) -> list[models.PlanNode]:
    """为积分运营阶段的 PlanDay 创建预设节点"""
    built_nodes: list[models.PlanNode] = []
    for idx, np in enumerate(stage.get('node_presets', [])):
        built_nodes.append(
            models.PlanNode(
                plan_day=day,
                node_type=np['node_type'],
                title=np['title'],
                description=np.get('description', ''),
                sort_order=(idx + 1) * 10,
                msg_type=np.get('msg_type', 'markdown'),
                content_json=json_dumps({
                    'generator_type': np['node_type'],
                    'content': '',
                }),
                variables_json='{}',
                status='draft',
                enabled=1,
                owner_id=owner_id,
            )
        )
    return built_nodes


def ensure_day_number_unique(db: Session, plan_id: int, day_number: int, exclude_day_id: int | None = None) -> None:
    query = db.query(models.PlanDay).filter(
        models.PlanDay.plan_id == plan_id,
        models.PlanDay.day_number == day_number,
    )
    if exclude_day_id is not None:
        query = query.filter(models.PlanDay.id != exclude_day_id)
    if query.first():
        raise HTTPException(400, f'第 {day_number} 天已存在，请勿重复创建')


def clone_node_payload(source: models.PlanNode, target: models.PlanNode, owner_id: int) -> None:
    target.node_type = source.node_type
    target.title = source.title
    target.description = source.description
    target.sort_order = source.sort_order
    target.template_id = source.template_id
    target.msg_type = source.msg_type
    target.content_json = source.content_json
    target.variables_json = source.variables_json
    target.status = source.status
    target.enabled = source.enabled
    target.owner_id = owner_id


@router.get('/meta/node-presets')
def get_node_presets(request: Request, db: Session = Depends(get_db)):
    get_user_or_401(request, db)
    return NODE_PRESETS


@router.get('/meta/campaign-stages')
def get_campaign_stages(request: Request, db: Session = Depends(get_db)):
    get_user_or_401(request, db)
    return POINTS_CAMPAIGN_STAGES


@router.post('/import/preview')
async def preview_operation_plan_import(
    request: Request,
    file: UploadFile = File(...),
    import_type: str = Form('daily_sop'),
    db: Session = Depends(get_db),
):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    parsed = await parse_operation_plan_file(file, import_type=import_type)
    day_numbers = [day['day_number'] for day in parsed['days']]
    duplicate_days = sorted({day for day in day_numbers if day_numbers.count(day) > 1})
    errors: list[str] = []
    warnings = list(parsed.get('warnings', []))

    if duplicate_days:
        errors.append(f"存在重复的运营天：{', '.join(str(day) for day in duplicate_days)}")

    sorted_days = sorted(day_numbers)
    if sorted_days and sorted_days != list(range(sorted_days[0], sorted_days[0] + len(sorted_days))):
        warnings.append('检测到运营天不是连续编号，导入后将按文件中的 day_number 创建')

    node_count = sum(len(day['nodes']) for day in parsed['days'])
    return {
        'ok': len(errors) == 0,
        'plan': {
            'name': parsed['plan_name'],
            'stage': parsed['stage'],
            'topic': parsed['topic'],
            'description': parsed['description'],
            'plan_mode': parsed.get('plan_mode', 'day_flow'),
            'day_count': parsed['day_count'],
        },
        'summary': {
            'day_count': parsed['day_count'],
            'node_count': node_count,
        },
        'days': [
            {
                'day_number': day['day_number'],
                'week_label': day['week_label'],
                'day_title': day['day_title'],
                'node_count': len(day['nodes']),
                'nodes': [{'node_type': node['node_type'], 'title': node['title']} for node in day['nodes']],
            }
            for day in parsed['days'][:5]
        ],
        'errors': errors,
        'warnings': warnings,
    }


@router.post('/import')
async def import_operation_plan(
    request: Request,
    file: UploadFile = File(...),
    import_type: str = Form('daily_sop'),
    db: Session = Depends(get_db),
):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    parsed = await parse_operation_plan_file(file, import_type=import_type)

    day_numbers = [day['day_number'] for day in parsed['days']]
    if len(set(day_numbers)) != len(day_numbers):
        raise HTTPException(400, '存在重复的运营天，无法导入')

    plan = models.Plan(
        name=parsed['plan_name'],
        topic=parsed['topic'],
        stage=parsed['stage'],
        description=parsed['description'],
        plan_mode=parsed.get('plan_mode', 'day_flow'),
        status='draft',
        owner_id=user.id,
    )
    db.add(plan)
    db.flush()

    for day_payload in parsed['days']:
        day = models.PlanDay(
            plan_id=plan.id,
            day_number=day_payload['day_number'],
            title=day_payload['day_title'] or f"第{day_payload['day_number']}天",
            focus=day_payload['day_focus'],
            trigger_rule_json=json_dumps(day_payload.get('trigger_rule_json', {})),
            status='draft',
            owner_id=user.id,
        )
        db.add(day)
        db.flush()
        for node_payload in day_payload['nodes']:
            node = models.PlanNode(
                plan_day_id=day.id,
                node_type=node_payload['node_type'],
                title=node_payload['title'],
                description=node_payload['description'],
                sort_order=node_payload['sort_order'],
                template_id=None,
                msg_type=node_payload['msg_type'],
                content_json=json_dumps({'content': node_payload['content']}),
                variables_json=json_dumps(node_payload.get('variables_json', {})),
                status=node_payload.get('status', 'draft'),
                enabled=1 if node_payload.get('enabled', True) else 0,
                owner_id=user.id,
            )
            db.add(node)

    db.commit()
    db.refresh(plan)
    return {
        'ok': True,
        'plan_id': plan.id,
        'plan': serialize_plan(get_plan_or_404(db, plan.id), include_days=True),
    }


@router.post('/create-campaign')
def create_campaign_from_preset(request: Request, db: Session = Depends(get_db)):
    """从预设常量一键创建积分运营计划（无需上传 Excel）"""
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    parsed = build_default_campaign_plan()

    plan = models.Plan(
        name=parsed['plan_name'],
        topic=parsed['topic'],
        stage=parsed['stage'],
        description=parsed['description'],
        plan_mode='points_campaign',
        status='draft',
        owner_id=user.id,
    )
    db.add(plan)
    db.flush()

    for day_payload in parsed['days']:
        day = models.PlanDay(
            plan_id=plan.id,
            day_number=day_payload['day_number'],
            title=day_payload['day_title'],
            focus=day_payload['day_focus'],
            trigger_rule_json=json_dumps(day_payload.get('trigger_rule_json', {})),
            status='draft',
            owner_id=user.id,
        )
        db.add(day)
        db.flush()
        for node_payload in day_payload['nodes']:
            node = models.PlanNode(
                plan_day_id=day.id,
                node_type=node_payload['node_type'],
                title=node_payload['title'],
                description=node_payload['description'],
                sort_order=node_payload['sort_order'],
                template_id=None,
                msg_type=node_payload['msg_type'],
                content_json=json_dumps({'content': node_payload['content']}),
                variables_json=json_dumps(node_payload.get('variables_json', {})),
                status=node_payload.get('status', 'draft'),
                enabled=1 if node_payload.get('enabled', True) else 0,
                owner_id=user.id,
            )
            db.add(node)

    db.commit()
    db.refresh(plan)
    return {
        'ok': True,
        'plan_id': plan.id,
        'plan': serialize_plan(get_plan_or_404(db, plan.id), include_days=True),
    }


@router.get('')
def list_plans(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    query = db.query(models.Plan)
    perms = json_loads(user.permissions_json, {})
    if user.role != 'admin' and not perms.get('plan'):
        query = query.filter(models.Plan.owner_id == user.id)
    plans = query.order_by(models.Plan.updated_at.desc(), models.Plan.id.desc()).all()
    return [serialize_plan(plan) for plan in plans]


@router.post('')
def create_plan(body: PlanCreate, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    require_permission(user, 'plan')
    plan = models.Plan(
        name=body.name.strip(),
        topic=body.topic.strip(),
        stage=body.stage.strip(),
        description=body.description.strip(),
        plan_mode=body.plan_mode,
        status='draft',
        owner_id=user.id,
    )
    if not plan.name:
        raise HTTPException(400, '运营计划名称不能为空')

    db.add(plan)
    db.flush()

    if body.plan_mode == 'points_campaign':
        for stage in POINTS_CAMPAIGN_STAGES:
            trigger_rule = {
                'trigger_type': stage['trigger_type'],
                'time': stage.get('default_time', '09:00'),
            }
            trigger_rule.update(stage.get('trigger_config', {}))
            day = models.PlanDay(
                plan_id=plan.id,
                day_number=stage['sort_order'],
                title=stage['title'],
                focus=stage['description'],
                trigger_rule_json=json_dumps(trigger_rule),
                status='draft',
                owner_id=user.id,
            )
            db.add(day)
            db.flush()
            for node in build_campaign_nodes(day, stage, user.id):
                db.add(node)
    else:
        for day_number in range(1, body.day_count + 1):
            day = models.PlanDay(
                plan_id=plan.id,
                day_number=day_number,
                title=f'第{day_number}天',
                focus='',
                status='draft',
                owner_id=user.id,
            )
            db.add(day)
            db.flush()
            for node in build_default_nodes(day, user.id):
                db.add(node)
    db.commit()
    db.refresh(plan)
    return serialize_plan(get_plan_or_404(db, plan.id), include_days=True)


def _safe_download_filename(plan_name: str, ext: str) -> str:
    """生成 Content-Disposition header 值，支持中文文件名"""
    # ASCII fallback: 去掉非 ASCII
    safe = re.sub(r'[^\x20-\x7e]', '_', plan_name)[:50] or 'operation-plan'
    safe = re.sub(r'_+', '_', safe).strip('_')
    filename_fallback = f'{safe}.{ext}'
    # URL-encode 中文原名用于 filename*
    encoded = quote(f'{plan_name}.{ext}')
    # filename 部分必须 latin-1 安全，filename* 用 UTF-8 编码
    # 但 Starlette 会 encode latin-1 整个 header value
    # 所以 filename* 中的 %xx 已经是 ASCII 安全的
    return f"attachment; filename=\"{filename_fallback}\"; filename*=UTF-8''{encoded}"


@router.get('/{plan_id}/export')
def export_plan(plan_id: int, format: str = 'json', request: Request = None, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    plan = get_plan_or_404(db, plan_id)
    ensure_plan_access(user, plan)
    plan_name = plan.name or 'operation-plan'

    if format == 'excel':
        data = export_plan_to_excel_bytes(plan)
        disposition = _safe_download_filename(plan_name, 'xlsx')
        return Response(
            content=data,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': disposition},
        )

    data = export_plan_to_json_bytes(plan)
    disposition = _safe_download_filename(plan_name, 'json')
    return Response(
        content=data,
        media_type='application/json; charset=utf-8',
        headers={'Content-Disposition': disposition},
    )


@router.get('/{plan_id}')
def get_plan_detail(plan_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    plan = get_plan_or_404(db, plan_id)
    ensure_plan_access(user, plan)
    return serialize_plan(plan, include_days=True)


@router.put('/{plan_id}')
def update_plan(plan_id: int, body: PlanUpdate, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    require_permission(user, 'plan')
    plan = get_plan_or_404(db, plan_id)
    ensure_plan_access(user, plan)
    plan.name = body.name.strip()
    plan.topic = body.topic.strip()
    plan.stage = body.stage.strip()
    plan.description = body.description.strip()
    plan.plan_mode = body.plan_mode
    plan.status = body.status
    if not plan.name:
        raise HTTPException(400, '运营计划名称不能为空')
    db.commit()
    return serialize_plan(get_plan_or_404(db, plan.id), include_days=True)


@router.delete('/{plan_id}')
def delete_plan(plan_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    require_permission(user, 'plan')
    plan = get_plan_or_404(db, plan_id)
    ensure_plan_access(user, plan)
    db.delete(plan)
    db.commit()
    return {'ok': True}


@router.post('/{plan_id}/days')
def create_day(plan_id: int, body: PlanDayCreate, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    require_permission(user, 'plan')
    plan = get_plan_or_404(db, plan_id)
    ensure_plan_access(user, plan)
    ensure_day_number_unique(db, plan.id, body.day_number)
    day = models.PlanDay(
        plan_id=plan.id,
        day_number=body.day_number,
        title=body.title.strip() or f'第{body.day_number}天',
        focus=body.focus.strip(),
        trigger_rule_json=json_dumps(body.trigger_rule_json),
        status='draft',
        owner_id=user.id,
    )
    db.add(day)
    db.flush()
    if body.auto_init_nodes:
        for node in build_default_nodes(day, user.id):
            db.add(node)
    db.commit()
    return serialize_day(get_day_or_404(db, day.id))


@router.put('/days/{day_id}')
def update_day(day_id: int, body: PlanDayUpdate, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    require_permission(user, 'plan')
    day = get_day_or_404(db, day_id)
    ensure_plan_access(user, day.plan)
    ensure_day_number_unique(db, day.plan_id, body.day_number, exclude_day_id=day.id)
    day.day_number = body.day_number
    day.title = body.title.strip() or f'第{body.day_number}天'
    day.focus = body.focus.strip()
    day.trigger_rule_json = json_dumps(body.trigger_rule_json)
    day.status = body.status
    db.commit()
    return serialize_day(get_day_or_404(db, day.id))


@router.post('/days/{day_id}/copy')
def copy_day(day_id: int, body: PlanDayCopyRequest, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    require_permission(user, 'plan')
    target_day = get_day_or_404(db, day_id)
    source_day = get_day_or_404(db, body.source_day_id)
    ensure_plan_access(user, target_day.plan)
    ensure_plan_access(user, source_day.plan)
    if target_day.plan_id != source_day.plan_id:
        raise HTTPException(400, '只能在同一个运营主题内复制天内容')
    if target_day.id == source_day.id:
        raise HTTPException(400, '不能复制自己')

    target_day.focus = source_day.focus or ''
    target_day.status = 'draft'

    source_by_type = {node.node_type: node for node in source_day.nodes}
    target_by_type = {node.node_type: node for node in target_day.nodes}

    for node_type, source_node in source_by_type.items():
        target_node = target_by_type.get(node_type)
        if target_node:
            clone_node_payload(source_node, target_node, target_node.owner_id or user.id)
            continue
        new_node = models.PlanNode(plan_day_id=target_day.id)
        clone_node_payload(source_node, new_node, user.id)
        db.add(new_node)

    db.commit()
    return serialize_day(get_day_or_404(db, target_day.id))


@router.delete('/days/{day_id}')
def delete_day(day_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    require_permission(user, 'plan')
    day = get_day_or_404(db, day_id)
    ensure_plan_access(user, day.plan)
    db.delete(day)
    db.commit()
    return {'ok': True}


@router.post('/days/{day_id}/nodes')
def create_node(day_id: int, body: PlanNodeCreate, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    require_permission(user, 'plan')
    day = get_day_or_404(db, day_id)
    ensure_plan_access(user, day.plan)
    node = models.PlanNode(plan_day_id=day.id)
    apply_node_payload(node, db, body, user.id)
    db.add(node)
    db.commit()
    return serialize_node(get_node_or_404(db, node.id))


@router.put('/nodes/{node_id}')
def update_node(node_id: int, body: PlanNodeUpdate, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    require_permission(user, 'plan')
    node = get_node_or_404(db, node_id)
    ensure_plan_access(user, node.plan_day.plan)
    apply_node_payload(node, db, body, node.owner_id or user.id)
    db.commit()
    return serialize_node(get_node_or_404(db, node.id))


@router.delete('/nodes/{node_id}')
def delete_node(node_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    require_permission(user, 'plan')
    node = get_node_or_404(db, node_id)
    ensure_plan_access(user, node.plan_day.plan)
    db.delete(node)
    db.commit()
    return {'ok': True}


# ===== 一键发布到群 =====

class PublishPlanBody(BaseModel):
    group_ids: list[int] = Field(min_length=1)
    start_date: str = Field(description='开始日期，格式 YYYY-MM-DD')
    end_date: str = Field(default='', description='结束日期（积分运营模式用），格式 YYYY-MM-DD')
    send_times: dict[str, str] = Field(default_factory=dict, description='各时段发送时间，如 {"morning": "08:00"}')
    skip_weekends: bool = False
    require_approval: bool = True


@router.post('/{plan_id}/publish')
def publish_plan(plan_id: int, body: PublishPlanBody, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    require_permission(user, 'plan')
    plan = get_plan_or_404(db, plan_id)
    ensure_plan_access(user, plan)

    # eager load days + nodes
    _ = plan.days
    for day in plan.days:
        _ = day.nodes

    if not plan.days:
        raise HTTPException(400, '运营计划没有编排内容，请先添加天数和节点')

    total_nodes = sum(len(d.nodes or []) for d in plan.days)
    if not total_nodes:
        raise HTTPException(400, '运营计划没有任何节点，请先编排内容')

    # validate group_ids
    valid_groups = db.query(models.Group.id).filter(
        models.Group.id.in_(body.group_ids), models.Group.enabled == 1
    ).all()
    valid_ids = {g[0] for g in valid_groups}
    invalid = set(body.group_ids) - valid_ids
    if invalid:
        raise HTTPException(400, f'以下群不存在或已禁用: {invalid}')

    created = publish_plan_to_groups(
        db=db,
        plan=plan,
        group_ids=body.group_ids,
        start_date=body.start_date,
        send_times=body.send_times,
        skip_weekends=body.skip_weekends,
        require_approval=body.require_approval,
        user=user,
        end_date=body.end_date,
    )

    return {
        'ok': True,
        'created_count': len(created),
        'plan_name': plan.name,
        'schedule_ids': [s.id for s in created],
    }
