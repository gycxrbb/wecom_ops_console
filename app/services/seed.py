from __future__ import annotations
from sqlalchemy.orm import Session
from .. import models
from ..config import settings
from ..security import hash_password, json_dumps, json_loads, decrypt_webhook

CRM_DEMO_URL = 'https://crm.mengfugui.com'

SYSTEM_TEMPLATES = [
    {
        'name': '08:00 早安打卡',
        'category': '训练营',
        'msg_type': 'markdown',
        'description': '早安、积分、昨日问题提醒',
        'content_json': {
            'content': '''### 早安，{{ coach_name or "教练" }}
今日日期：{{ today }}
请先完成早安打卡，再回复昨晚 20:00 后的问题。

**今日目标**
- 完成签到
- 上传餐食记录
- 回答 1 个问题'''
        },
    },
    {
        'name': '09:00 今日主题学习',
        'category': '训练营',
        'msg_type': 'markdown',
        'description': '科学原理 + 方法',
        'content_json': {
            'content': '''### 今日主题：{{ topic }}
**为什么重要**：{{ why }}

**今日动作**
1. {{ action_1 }}
2. {{ action_2 }}
3. {{ action_3 }}'''
        },
        'variables_json': {
            'topic': '211餐盘 + 餐后走',
            'why': '先稳定餐后波动，再拉高日常执行率。',
            'action_1': '一餐按 211 餐盘吃',
            'action_2': '餐后步行 10 到 15 分钟',
            'action_3': '拍照反馈执行情况',
        },
    },
    {
        'name': '11:00 餐前提醒',
        'category': '提醒',
        'msg_type': 'text',
        'description': '午餐前执行提醒',
        'content_json': {
            'content': '午餐前提醒：请围绕【{{ topic }}】执行，吃前先想好今天的 211 餐盘结构。',
            'mentioned_list': [],
            'mentioned_mobile_list': []
        },
        'variables_json': {'topic': '211餐盘 + 餐后走'},
    },
    {
        'name': '14:00 惯能H5 图文讲解',
        'category': '图文',
        'msg_type': 'news',
        'description': '适合 CRM 内容页、惯能 H5、活动页跳转',
        'content_json': {
            'articles': [
                {
                    'title': '惯能 H5 · {{ topic }}',
                    'description': '{{ summary }}',
                    'url': '{{ article_url }}',
                    'picurl': '{{ image_url }}'
                }
            ]
        },
        'variables_json': {
            'topic': '211餐盘 + 餐后走',
            'summary': '打开 CRM 内容页查看今日 H5 讲解，运营同学可直接替换成当天课程页或活动页。',
            'article_url': CRM_DEMO_URL,
            'image_url': 'https://picsum.photos/640/360'
        },
    },
    {
        'name': '16:00 实践反馈',
        'category': '互动',
        'msg_type': 'markdown',
        'description': '下午收集执行反馈',
        'content_json': {
            'content': '''### 实践反馈
今天围绕 **{{ topic }}** 的执行情况如何？

请按这个格式回复：
- 我做到了什么
- 我卡在哪里
- 我下一步准备怎么做'''
        },
        'variables_json': {'topic': '211餐盘 + 餐后走'},
    },
    {
        'name': '17:00 晚餐前提醒',
        'category': '提醒',
        'msg_type': 'text',
        'description': '晚餐前提醒',
        'content_json': {
            'content': '晚餐前提醒：继续按【{{ topic }}】执行，记得饭后走一走。',
            'mentioned_list': [],
            'mentioned_mobile_list': []
        },
        'variables_json': {'topic': '211餐盘 + 餐后走'},
    },
    {
        'name': '20:00 晚安总结',
        'category': '训练营',
        'msg_type': 'markdown',
        'description': '总结 + 次日预告',
        'content_json': {
            'content': '''### 晚安总结
请用 3 句话总结今天：
1. 我做到了什么
2. 我的最大卡点是什么
3. 我明天准备怎么优化

明日主题预告：**{{ next_topic }}**'''
        },
        'variables_json': {'next_topic': '餐前醋 + 饮食顺序'},
    },
    {
        'name': '模板卡片示例 · 文本通知',
        'category': '高级',
        'msg_type': 'template_card',
        'description': '适合截止提醒、任务确认、行动号召的完整文本通知模板卡片示例',
        'content_json': {
            'template_card': {
                'card_type': 'text_notice',
                'source': {'icon_url': 'https://picsum.photos/seed/wecom-card-icon/96/96', 'desc': '训练营运营台', 'desc_color': 0},
                'main_title': {'title': '{{ title }}', 'desc': '{{ desc }}'},
                'sub_title_text': '{{ subtitle }}',
                'emphasis_content': {'title': '{{ emphasis_title }}', 'desc': '{{ emphasis_desc }}'},
                'quote_area': {'type': 1, 'url': '{{ quote_url }}', 'title': '{{ quote_title }}', 'quote_text': '{{ quote_text }}'},
                'horizontal_content_list': [
                    {'keyname': '群聊', 'value': '{{ group_name }}'},
                    {'keyname': '教练', 'value': '{{ coach_name }}'},
                    {'keyname': '截止', 'value': '{{ deadline }}'}
                ],
                'jump_list': [
                    {'type': 1, 'title': '查看详情', 'url': '{{ detail_url }}'},
                    {'type': 1, 'title': '提交反馈', 'url': '{{ form_url }}'}
                ],
                'card_action': {'type': 1, 'url': '{{ detail_url }}'}
            }
        },
        'variables_json': {
            'title': '今晚 20:00 总结提醒',
            'desc': '请按时提交今日反馈',
            'subtitle': '运营同学可直接替换标题、时间和跳转链接，就能快速复用这张卡。',
            'emphasis_title': '20:30',
            'emphasis_desc': '提交截止',
            'deadline': '今天 20:30',
            'quote_title': '填写建议',
            'quote_text': '建议按“执行动作 / 卡点 / 下一步”三段填写，方便教练点评。',
            'quote_url': f'{CRM_DEMO_URL}/tips',
            'detail_url': CRM_DEMO_URL,
            'form_url': CRM_DEMO_URL
        },
    },
    {
        'name': '模板卡片示例 · 图文展示',
        'category': '高级',
        'msg_type': 'template_card',
        'description': '适合运营发课程图卡、海报讲解、活动介绍的完整图文展示模板卡片示例',
        'content_json': {
            'template_card': {
                'card_type': 'news_notice',
                'source': {'icon_url': 'https://picsum.photos/seed/wecom-card-icon/96/96', 'desc': '训练营运营台', 'desc_color': 0},
                'main_title': {'title': '{{ title }}', 'desc': '{{ desc }}'},
                'card_image': {'url': '{{ card_image_url }}', 'aspect_ratio': 1.3},
                'image_text_area': {
                    'type': 1,
                    'url': '{{ detail_url }}',
                    'title': '{{ image_text_title }}',
                    'desc': '{{ image_text_desc }}',
                    'image_url': '{{ image_url }}'
                },
                'quote_area': {'type': 1, 'url': '{{ quote_url }}', 'title': '{{ quote_title }}', 'quote_text': '{{ quote_text }}'},
                'vertical_content_list': [
                    {'title': '适用人群', 'desc': '{{ audience }}'},
                    {'title': '执行动作', 'desc': '{{ action }}'},
                    {'title': '截止时间', 'desc': '{{ deadline }}'}
                ],
                'horizontal_content_list': [
                    {'keyname': '群聊', 'value': '{{ group_name }}'},
                    {'keyname': '教练', 'value': '{{ coach_name }}'}
                ],
                'jump_list': [
                    {'type': 1, 'title': '查看图文详情', 'url': '{{ detail_url }}'},
                    {'type': 1, 'title': '打开打卡页', 'url': '{{ form_url }}'}
                ],
                'card_action': {'type': 1, 'url': '{{ detail_url }}'}
            }
        },
        'variables_json': {
            'title': '今日学习卡已更新',
            'desc': '3 分钟看完这张图，再去群里打卡',
            'card_image_url': 'https://picsum.photos/seed/wecom-card-cover/960/720',
            'image_text_title': '餐后走 10 分钟，为什么更容易坚持？',
            'image_text_desc': '把“降低执行门槛、提升反馈感、增加连续性”三件事浓缩成一张图，运营同学可直接替换成当天主题。',
            'image_url': 'https://picsum.photos/seed/wecom-card-inline/240/240',
            'detail_url': CRM_DEMO_URL,
            'quote_title': '运营建议',
            'quote_text': '如果今天需要带配图做讲解，优先用图文展示模板卡片，复用门槛更低。',
            'quote_url': CRM_DEMO_URL,
            'audience': '今天还没完成学习打卡的同学',
            'action': '先看图再回群里回复一句“我今天准备怎么做”',
            'deadline': '今天 21:00',
            'form_url': CRM_DEMO_URL
        },
    },
]


def _is_placeholder_webhook(webhook: str | None) -> bool:
    if not webhook:
        return False
    lowered = webhook.lower()
    return 'replace-test-key' in lowered or 'replace-prod-key' in lowered


def _should_be_test_group(group: models.Group) -> bool:
    alias = (group.alias or '').upper()
    name = (group.name or '').strip()
    return alias == 'TEST_GROUP' or name == '测试群'


def seed_all(db: Session):
    all_perms = '{"send":true,"schedule":true,"group":true,"template":true,"plan":true,"asset":true,"log":true,"approval":true,"sop":true}'
    if db.query(models.User).count() == 0:
        db.add_all([
            models.User(username=settings.admin_username, display_name='系统管理员', role='admin', auth_source='local', password_hash=hash_password(settings.admin_password)),
            models.User(username=settings.coach_username, display_name='教练示例账号', role='coach', auth_source='local', password_hash=hash_password(settings.coach_password), permissions_json=all_perms),
        ])
        db.commit()
    else:
        # 确保 coach 示例账号拥有全部权限
        coach = db.query(models.User).filter(models.User.username == settings.coach_username).first()
        if coach:
            perms = json_loads(coach.permissions_json, {})
            if not perms.get('sop'):
                perms['sop'] = True
                coach.permissions_json = json_dumps(perms)
                db.commit()

    if db.query(models.Group).count() == 0:
        db.add_all([
            models.Group(name='测试群', alias='TEST_GROUP', group_type='test', tags='["测试"]', webhook_cipher=''),
            models.Group(name='正式训练营1群', alias='CAMP_1', group_type='formal', tags='["正式"]', webhook_cipher=''),
        ])
        db.commit()

    groups = db.query(models.Group).all()
    updated_groups = False
    has_test_group = any(group.group_type == 'test' for group in groups)
    for group in groups:
        try:
            webhook = decrypt_webhook(group.webhook_cipher) if group.webhook_cipher else ''
        except Exception:
            webhook = ''
        if _is_placeholder_webhook(webhook):
            group.webhook_cipher = ''
            updated_groups = True
        if not has_test_group and _should_be_test_group(group):
            group.group_type = 'test'
            has_test_group = True
            updated_groups = True
    if updated_groups:
        db.commit()

    admin = db.query(models.User).filter(models.User.role == 'admin').first()
    existing_template_names = {
        name for (name,) in db.query(models.Template.name).filter(models.Template.is_system == 1).all()
    }
    new_templates_added = False
    for item in SYSTEM_TEMPLATES:
        if item['name'] in existing_template_names:
            continue
        db.add(models.Template(
            name=item['name'],
            category=item.get('category', 'general'),
            msg_type=item['msg_type'],
            content=json_dumps(item['content_json']),
            default_variables=json_dumps(item.get('variables_json', {})),
            is_system=1,
            owner_id=admin.id if admin else None,
        ))
        new_templates_added = True
    if new_templates_added:
        db.commit()

    # ── External Docs: seed workspaces, terms, migration ──
    from ..models_external_docs import ExternalDocWorkspace, ExternalDocTerm, ExternalDocResource

    # inbox workspace
    if not db.query(ExternalDocWorkspace).filter(ExternalDocWorkspace.workspace_type == 'inbox').first():
        db.add(ExternalDocWorkspace(name='收件箱', workspace_type='inbox', status='running'))
        db.commit()

    # template_hub workspace
    if not db.query(ExternalDocWorkspace).filter(ExternalDocWorkspace.workspace_type == 'template_hub').first():
        db.add(ExternalDocWorkspace(name='模板中心', workspace_type='template_hub', status='running'))
        db.commit()

    # stage terms
    if db.query(ExternalDocTerm).filter(ExternalDocTerm.dimension == 'stage').count() == 0:
        stage_terms = [
            ExternalDocTerm(dimension='stage', code='lead_intake', label='线索接入', sort_order=1),
            ExternalDocTerm(dimension='stage', code='solution_design', label='方案设计', sort_order=2),
            ExternalDocTerm(dimension='stage', code='launch_preparation', label='启动准备', sort_order=3),
            ExternalDocTerm(dimension='stage', code='delivery_running', label='执行中', sort_order=4),
            ExternalDocTerm(dimension='stage', code='mid_review', label='中期复盘', sort_order=5),
            ExternalDocTerm(dimension='stage', code='final_delivery', label='结项交付', sort_order=6),
        ]
        db.add_all(stage_terms)
        db.commit()

    # deliverable_type terms
    if db.query(ExternalDocTerm).filter(ExternalDocTerm.dimension == 'deliverable_type').count() == 0:
        deliverable_terms = [
            ExternalDocTerm(dimension='deliverable_type', code='positioning_sheet', label='定位表', sort_order=1),
            ExternalDocTerm(dimension='deliverable_type', code='schedule_sheet', label='排期表', sort_order=2),
            ExternalDocTerm(dimension='deliverable_type', code='daily_report', label='日报', sort_order=3),
            ExternalDocTerm(dimension='deliverable_type', code='weekly_review', label='周报', sort_order=4),
            ExternalDocTerm(dimension='deliverable_type', code='material_list', label='物料清单', sort_order=5),
            ExternalDocTerm(dimension='deliverable_type', code='script_sheet', label='话术表', sort_order=6),
            ExternalDocTerm(dimension='deliverable_type', code='replay_sheet', label='复盘表', sort_order=7),
            ExternalDocTerm(dimension='deliverable_type', code='delivery_checklist', label='交付清单', sort_order=8),
        ]
        db.add_all(deliverable_terms)
        db.commit()

    # legacy_category terms
    if db.query(ExternalDocTerm).filter(ExternalDocTerm.dimension == 'legacy_category').count() == 0:
        legacy_terms = [
            ExternalDocTerm(dimension='legacy_category', code='运营流程', label='运营流程', sort_order=1),
            ExternalDocTerm(dimension='legacy_category', code='话术库', label='话术库', sort_order=2),
            ExternalDocTerm(dimension='legacy_category', code='经验库', label='经验库', sort_order=3),
            ExternalDocTerm(dimension='legacy_category', code='营养知识', label='营养知识', sort_order=4),
            ExternalDocTerm(dimension='legacy_category', code='培训手册', label='培训手册', sort_order=5),
            ExternalDocTerm(dimension='legacy_category', code='其他', label='其他', sort_order=6),
        ]
        db.add_all(legacy_terms)
        db.commit()

    # migrate old sop_documents
    from ..models import SopDocument
    if db.query(SopDocument).count() > 0 and db.query(ExternalDocResource).count() == 0:
        from .external_doc_migration import migrate_sop_documents
        migrate_sop_documents(db)

    # --- Seed rag_tags from vocabulary (per-code upsert + aliases) ---
    try:
        from ..rag.tag_service import refresh_tags_from_vocabulary
        refresh_tags_from_vocabulary(db)
    except Exception:
        db.rollback()
