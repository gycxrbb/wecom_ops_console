from __future__ import annotations
from sqlalchemy.orm import Session
from .. import models
from ..config import settings
from ..security import hash_password, json_dumps, encrypt_webhook

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
        'name': '14:00 图文讲解',
        'category': '图文',
        'msg_type': 'news',
        'description': '适合文章、海报、课程页',
        'content_json': {
            'articles': [
                {
                    'title': '{{ topic }} 常见误区与修正方法',
                    'description': '{{ summary }}',
                    'url': '{{ article_url }}',
                    'picurl': '{{ image_url }}'
                }
            ]
        },
        'variables_json': {
            'topic': '211餐盘 + 餐后走',
            'summary': '为什么看起来吃得少，餐后波动还是很高？这张图帮你快速定位。',
            'article_url': 'https://example.com/course',
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
        'name': 'Template Card 示例',
        'category': '高级',
        'msg_type': 'template_card',
        'description': 'JSON 模式的模板卡片示例',
        'content_json': {
            'template_card': {
                'card_type': 'text_notice',
                'source': {'icon_url': 'https://picsum.photos/48', 'desc': '训练营后台', 'desc_color': 0},
                'main_title': {'title': '{{ title }}', 'desc': '{{ desc }}'},
                'sub_title_text': '{{ subtitle }}',
                'horizontal_content_list': [
                    {'keyname': '群聊', 'value': '{{ group_name }}'},
                    {'keyname': '教练', 'value': '{{ coach_name }}'}
                ],
                'jump_list': [{'type': 1, 'title': '查看详情', 'url': '{{ jump_url }}'}],
                'card_action': {'type': 1, 'url': '{{ jump_url }}'}
            }
        },
        'variables_json': {
            'title': '今晚 20:00 总结提醒',
            'desc': '请按时提交今日反馈',
            'subtitle': '表单会在 20:30 截止',
            'jump_url': 'https://example.com/form'
        },
    },
]


def seed_all(db: Session):
    if db.query(models.User).count() == 0:
        db.add_all([
            models.User(username=settings.admin_username, display_name='系统管理员', role='admin', password_hash=hash_password(settings.admin_password)),
            models.User(username=settings.coach_username, display_name='教练示例账号', role='coach', password_hash=hash_password(settings.coach_password)),
        ])
        db.commit()

    if db.query(models.Group).count() == 0:
        db.add_all([
            models.Group(name='测试群', alias='TEST_GROUP', group_type='test', tags='["测试"]', webhook_cipher=encrypt_webhook('https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=replace-test-key')),
            models.Group(name='正式训练营1群', alias='CAMP_1', group_type='formal', tags='["正式"]', webhook_cipher=encrypt_webhook('https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=replace-prod-key')),
        ])
        db.commit()

    if db.query(models.Template).count() == 0:
        admin = db.query(models.User).filter(models.User.role == 'admin').first()
        for item in SYSTEM_TEMPLATES:
            db.add(models.Template(
                name=item['name'],
                category=item.get('category', 'general'),
                msg_type=item['msg_type'],
                content=json_dumps(item['content_json']),
                variable_schema=json_dumps(item.get('variables_json', {})),
                is_system=1,
                owner_id=admin.id if admin else None,
            ))
        db.commit()
