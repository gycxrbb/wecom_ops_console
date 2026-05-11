"""积分运营话术模板库

按 scene_key + style 组织话术模板。
支持数据库优先读取（带 120s 缓存），fallback 到硬编码种子。
"""
from __future__ import annotations

import logging
import time
from typing import Any

_log = logging.getLogger(__name__)

STYLES = ('professional', 'encouraging', 'competitive')

# 分类体系种子数据（3 级：L1 > L2 > L3），含 code 稳定标识
CATEGORY_SEED = [
    {'name': '健康管理类', 'code': 'health', 'children': [
        {'name': '体重管理', 'code': 'health.weight', 'children': [
            {'name': '减重速度咨询', 'code': 'health.weight.loss_speed'},
            {'name': '减重原理咨询', 'code': 'health.weight.loss_principle'},
            {'name': '体重目标设定', 'code': 'health.weight.goal_setting'},
            {'name': '体重监测问题', 'code': 'health.weight.monitoring'},
        ]},
        {'name': '饮食管理', 'code': 'health.diet', 'children': [
            {'name': '饮食计划咨询', 'code': 'health.diet.plan'},
            {'name': '食物选择建议', 'code': 'health.diet.food_choice'},
            {'name': '饮食记录问题', 'code': 'health.diet.record'},
            {'name': '特殊饮食需求', 'code': 'health.diet.special'},
        ]},
        {'name': '运动管理', 'code': 'health.exercise', 'children': [
            {'name': '运动计划咨询', 'code': 'health.exercise.plan'},
            {'name': '运动强度建议', 'code': 'health.exercise.intensity'},
            {'name': '运动效果评估', 'code': 'health.exercise.evaluation'},
            {'name': '运动安全注意', 'code': 'health.exercise.safety'},
        ]},
        {'name': '生理指标管理', 'code': 'health.indicator', 'children': [
            {'name': '血糖管理咨询', 'code': 'health.indicator.blood_sugar'},
            {'name': '血压管理咨询', 'code': 'health.indicator.blood_pressure'},
            {'name': '指标监测指导', 'code': 'health.indicator.monitoring'},
            {'name': '异常指标处理', 'code': 'health.indicator.abnormal'},
        ]},
        {'name': '生活习惯管理', 'code': 'health.lifestyle', 'children': [
            {'name': '睡眠管理咨询', 'code': 'health.lifestyle.sleep'},
            {'name': '饮水管理咨询', 'code': 'health.lifestyle.water'},
            {'name': '情绪调节指导', 'code': 'health.lifestyle.emotion'},
            {'name': '作息规律建议', 'code': 'health.lifestyle.routine'},
        ]},
        {'name': '特定人群健康', 'code': 'health.special', 'children': [
            {'name': '老年人健康管理', 'code': 'health.special.elderly'},
            {'name': '孕妇健康管理', 'code': 'health.special.pregnant'},
            {'name': '慢性病患者管理', 'code': 'health.special.chronic'},
            {'name': '特殊职业人群管理', 'code': 'health.special.occupational'},
        ]},
    ]},
    {'name': '系统操作类', 'code': 'system', 'children': [
        {'name': '功能操作', 'code': 'system.function', 'children': [
            {'name': '打卡功能操作', 'code': 'system.function.checkin'},
            {'name': '数据上传操作', 'code': 'system.function.upload'},
            {'name': '课程学习操作', 'code': 'system.function.course'},
            {'name': '设备连接操作', 'code': 'system.function.device'},
        ]},
        {'name': '系统异常', 'code': 'system.error', 'children': [
            {'name': '操作入口异常', 'code': 'system.error.entry'},
            {'name': '系统兼容性问题', 'code': 'system.error.compat'},
            {'name': '数据加载异常', 'code': 'system.error.loading'},
            {'name': '功能响应缓慢', 'code': 'system.error.slow'},
        ]},
        {'name': '数据问题', 'code': 'system.data', 'children': [
            {'name': '数据记录异常', 'code': 'system.data.record'},
            {'name': '数据统计错误', 'code': 'system.data.stats'},
            {'name': '数据同步问题', 'code': 'system.data.sync'},
            {'name': '数据导出问题', 'code': 'system.data.export'},
        ]},
        {'name': '设备管理', 'code': 'system.device', 'children': [
            {'name': '设备连接问题', 'code': 'system.device.connect'},
            {'name': '设备识别失败', 'code': 'system.device.detect'},
            {'name': '设备数据同步', 'code': 'system.device.sync'},
            {'name': '设备故障排查', 'code': 'system.device.troubleshoot'},
        ]},
    ]},
    {'name': '社区运营类', 'code': 'community', 'children': [
        {'name': '社群管理', 'code': 'community.group', 'children': [
            {'name': '社群加入退出', 'code': 'community.group.join'},
            {'name': '社群互动管理', 'code': 'community.group.interact'},
            {'name': '社群规则咨询', 'code': 'community.group.rules'},
            {'name': '社群成员管理', 'code': 'community.group.members'},
        ]},
        {'name': '活动管理', 'code': 'community.activity', 'children': [
            {'name': '活动参与咨询', 'code': 'community.activity.join'},
            {'name': '活动规则了解', 'code': 'community.activity.rules'},
            {'name': '活动奖励查询', 'code': 'community.activity.reward'},
            {'name': '活动反馈建议', 'code': 'community.activity.feedback'},
        ]},
        {'name': '积分管理', 'code': 'community.points', 'children': [
            {'name': '积分获取咨询', 'code': 'community.points.earning'},
            {'name': '积分使用规则', 'code': 'community.points.usage'},
            {'name': '积分异常查询', 'code': 'community.points.issue'},
            {'name': '积分兑换问题', 'code': 'community.points.redeem'},
        ]},
        {'name': '内容管理', 'code': 'community.content', 'children': [
            {'name': '课程内容咨询', 'code': 'community.content.course'},
            {'name': '资料获取方式', 'code': 'community.content.material'},
            {'name': '内容更新通知', 'code': 'community.content.update'},
            {'name': '内容质量反馈', 'code': 'community.content.feedback'},
        ]},
    ]},
    {'name': '服务支持类', 'code': 'service', 'children': [
        {'name': '用户协助', 'code': 'service.user', 'children': [
            {'name': '操作指导协助', 'code': 'service.user.guide'},
            {'name': '问题解决协助', 'code': 'service.user.problem'},
            {'name': '需求反馈协助', 'code': 'service.user.feedback'},
            {'name': '个性化服务协助', 'code': 'service.user.personal'},
        ]},
        {'name': '教练服务', 'code': 'service.coach', 'children': [
            {'name': '教练咨询预约', 'code': 'service.coach.booking'},
            {'name': '教练服务查询', 'code': 'service.coach.query'},
            {'name': '教练指导反馈', 'code': 'service.coach.feedback'},
            {'name': '教练更换申请', 'code': 'service.coach.change'},
        ]},
        {'name': '问题反馈', 'code': 'service.issue', 'children': [
            {'name': '问题提交渠道', 'code': 'service.issue.submit'},
            {'name': '问题处理进度', 'code': 'service.issue.progress'},
            {'name': '问题解决方案', 'code': 'service.issue.solution'},
            {'name': '问题反馈评价', 'code': 'service.issue.review'},
        ]},
        {'name': '产品建议', 'code': 'service.product', 'children': [
            {'name': '功能优化建议', 'code': 'service.product.optimize'},
            {'name': '新功能需求', 'code': 'service.product.feature'},
            {'name': '产品体验反馈', 'code': 'service.product.experience'},
            {'name': '服务改进建议', 'code': 'service.product.improve'},
        ]},
    ]},
]

# scene_key -> (L2 子类名称, L3 子类名称)
SCENE_CATEGORY_MAP: dict[str, tuple[str, str]] = {
    # 饮食管理
    'meal_checkin': ('饮食管理', '饮食记录问题'),
    'meal_review': ('饮食管理', '食物选择建议'),
    'habit_education': ('饮食管理', '饮食计划咨询'),
    # 生活习惯管理
    'emotional_support': ('生活习惯管理', '情绪调节指导'),
    'obstacle_breaking': ('生活习惯管理', '作息规律建议'),
    'maintenance': ('生活习惯管理', '作息规律建议'),
    # 生理指标管理
    'period_review': ('生理指标管理', '指标监测指导'),
    # 积分管理
    'top_leader': ('积分管理', '积分获取咨询'),
    'top_six': ('积分管理', '积分获取咨询'),
    'top_ten': ('积分管理', '积分获取咨询'),
    'consistent': ('积分管理', '积分获取咨询'),
    'surge': ('积分管理', '积分获取咨询'),
    'comeback': ('积分管理', '积分异常查询'),
    'dropout_recovery': ('积分管理', '积分异常查询'),
    'rapid_progress': ('积分管理', '积分获取咨询'),
    'reverse_bottom': ('积分管理', '积分兑换问题'),
    # 社群管理
    'lurker_remind': ('社群管理', '社群互动管理'),
    'daily_remind': ('社群管理', '社群互动管理'),
    'group_pk': ('社群管理', '社群互动管理'),
    # 用户协助
    'qa_support': ('用户协助', '问题解决协助'),
    # 内容管理
    'rag_import': ('内容管理', '课程内容咨询'),
}

# 场景标签映射
SCENE_LABELS: dict[str, str] = {
    'meal_checkin': '晒餐打卡',
    'meal_review': '餐评指导',
    'obstacle_breaking': '阻碍干预',
    'habit_education': '习惯科普',
    'emotional_support': '情绪陪伴',
    'qa_support': '问题答疑',
    'period_review': '阶段复盘',
    'maintenance': '长期维持',
    'rag_import': '语料导入',
    'top_leader': '头部领先 (TOP3)',
    'top_six': '前六冲刺',
    'top_ten': '前十竞争',
    'consistent': '连续活跃',
    'surge': '积分暴涨',
    'comeback': '强势回归',
    'dropout_recovery': '掉队归队',
    'rapid_progress': '进步飞快',
    'reverse_bottom': '后段激励 (绿草莓奖)',
    'lurker_remind': '潜水提醒',
    'daily_remind': '每日氛围',
    'group_pk': '社群 PK',
}

# ── 种子数据（硬编码 fallback） ──
_SEED_TEMPLATES: dict[str, dict[str, str]] = {
    'top_leader': {
        'professional': (
            '🏆 @所有人 【积分冲刺提醒】\n'
            '{name} 目前积分榜排名第{rank}，已经稳稳站在「金百花奖」第一梯队！'
            '只要继续保持每日打卡、认真学习健康课件、积极参与群内互动，最终大奖就会稳稳到手。'
            '请继续做好榜样，带动全群一起养成健康减重的好习惯！'
        ),
        'encouraging': (
            '🥇 {name} 真的太优秀啦！现在离 3 个月结营越来越近，积分咬得紧紧的，'
            '再坚持坚持，「金百花奖」大奖就在眼前啦！继续保持每天打卡、认真学习，'
            '稳稳冲刺，你超有希望，也给群里的伙伴们做了最好的榜样～'
        ),
        'competitive': (
            '⚠️前排大佬请注意！⚠️\n'
            '{name} 个人积分 TOP3 已经锁死「金百花奖」冲线区！后面的人正在疯狂追赶，'
            '千万别翻车！再努努力，3 个月结营大奖直接抱回家，稳住就是胜利！'
        ),
    },
    'top_six': {
        'professional': (
            '{name} 积分排名第{rank}，已进入「金百花奖」第一梯队。'
            '距离 3 个月结营还有一段时间，大家的积分咬得非常紧，'
            '只要继续保持每日打卡、认真学习健康课件、积极参与群内互动，最终大奖就会稳稳到手。'
        ),
        'encouraging': (
            '🎉 {name} 超优秀的！积分排名前六，距离「金百花奖」越来越近了！'
            '现在大家的积分咬得紧紧的，再坚持坚持，大奖就在眼前！'
            '继续保持每天打卡、认真学习，稳稳冲刺，你超有希望！'
        ),
        'competitive': (
            '{name} 排名第{rank}，「金百花奖」冲线区选手！后面的人正在疯狂追赶，'
            '千万别翻车！再努努力，3 个月结营大奖直接抱回家，稳住就是胜利！'
        ),
    },
    'top_ten': {
        'professional': (
            '{name} 当前第{rank}名，前十的伙伴们差距很小，'
            '稍微多互动、多打卡就能往前冲一冲，最终排名还没定，冲一把就能拿到更好奖励！'
        ),
        'encouraging': (
            '{name} 第{rank}名！只差一点点就能冲进前六啦！'
            '每天多打一次卡、多学一页课件，积分就多一分，大奖就更近一步～'
        ),
        'competitive': (
            '{name} 第{rank}名，冲一把就进前六！别犹豫，'
            '每天多打卡就能逆袭，「金百花奖」还有你的位置，给我冲！'
        ),
    },
    'consistent': {
        'professional': (
            '特别表扬 {name}！连续多日坚持打卡、认真学习减重课件，{detail}。'
            '每日稳定参与、持续积累，不仅积分稳步提升，'
            '更用自律践行了健康生活方式，这份坚持值得全体成员学习。'
        ),
        'encouraging': (
            '❤️ 每天都能准时看到 {name} 打卡、认真看课件，真的特别暖心。\n'
            '一步一步积累，积分慢慢上涨，{activity}，你们的坚持所有人都看在眼里、记在心里。'
            '减重是一场温柔的修行，谢谢你们用自律，给了大家一起变好的力量！'
        ),
        'competitive': (
            '实名表扬 {name}！天天打卡、天天看课，{activity}，'
            '积分一路狂飙，这自律程度我直接 respect！'
            '全场最佳就是你，减重路上的标杆，给我焊死在榜一！'
        ),
    },
    'surge': {
        'professional': (
            '近期发现 {name} 突然恢复打卡、积极互动，积分出现明显上涨，{detail}。\n'
            '行动永远不晚，减重从来没有"来不及"，只要从今天开始坚持，'
            '依然有机会冲刺「金百花奖」，也能在 3 个月内收获理想的减重效果。'
        ),
        'encouraging': (
            '✨ {name} 最近突然活跃起来啦，{activity}，积分一下子就上来了！\n'
            '真的太为你开心了！减重从来没有"太晚了"，只要愿意开始，什么时候都不晚。'
            '欢迎回来，我们一起慢慢走、稳稳瘦！'
        ),
        'competitive': (
            '惊现黑马！{name} 前几天还隐身，最近突然上线猛冲打卡，积分直接起飞🚀\n'
            '这是准备悄悄惊艳所有人吗？！欢迎回归，冲就完事了，'
            '「金百花奖」还有位置，给我冲！'
        ),
    },
    'comeback': {
        'professional': (
            '欢迎 {name} 归队！{detail}。\n'
            '减重路上偶尔的停顿不可怕，重新出发才最难得。'
            '欢迎归队，慢慢跟上每日打卡、学习的节奏，积分还有大幅提升空间。'
        ),
        'encouraging': (
            '💪 {name} 欢迎回来！中间偶尔停下没关系，重要的是你又重新出发了。\n'
            '不用急着追进度，慢慢跟上每天打卡、学习的节奏就好。'
            '我们一起往前冲，积分会涨，体重会降！'
        ),
        'competitive': (
            '失踪人口 {name} 回归啦！虽然断更了几天，但现在满血复活，冲就完事了！\n'
            '积分还能追，体重还能降，别摆烂，跟紧大部队，结营一起瘦成闪电！'
        ),
    },
    'dropout_recovery': {
        'professional': (
            '{name} 虽曾短暂中断打卡，但已重新跟上节奏，恢复日常参与。\n'
            '断卡不可怕，重新开始最难得！欢迎归队，'
            '慢慢跟上每日打卡、学习的节奏，积分还有大幅提升空间。'
        ),
        'encouraging': (
            '{name} 欢迎归队！之前落下的进度，现在一点点补回来就好～\n'
            '不用急着追进度，慢慢跟上节奏就行，排名还有机会，一起往前冲！'
        ),
        'competitive': (
            '{name} 虽然断更了几天，但现在满血复活，冲就完事了！\n'
            '积分还能追，体重还能降，别摆烂，跟紧大部队！'
        ),
    },
    'rapid_progress': {
        'professional': (
            '进步看得见！{name} 近期活跃度明显提升，{activity}，积分一路飙升，{detail}。\n'
            '只要每天多花一点时间参与，积分差距很快就能追上，继续保持这个势头！'
        ),
        'encouraging': (
            '✨ {name} 这几天活跃度明显提升，{activity}，积分一路飙升，太棒了！\n'
            '每一次打卡都在为你的健康加分，继续保持这个节奏，大奖离你越来越近～'
        ),
        'competitive': (
            '{name} 积分暴涨中！{activity}，这波冲刺太猛了！\n'
            '照这个节奏下去，排名还能再往上冲，大家都可以学起来！'
        ),
    },
    'lurker_remind': {
        'professional': (
            '仍在观望的伙伴请积极参与日常打卡与互动：\n'
            '个人积分榜实时更新，3 个月结营的「金百花奖」「绿草莓奖」排名还未最终确定，'
            '现在开始行动完全来得及。越活跃，积分越高，'
            '不仅能冲刺丰厚奖励，更能在群内氛围的带动下，养成受益终身的健康减重习惯！'
        ),
        'encouraging': (
            '还在默默潜水的小伙伴，也可以试着出来冒个泡呀～\n'
            '每天简单打个卡、在群里说说话，积分就会慢慢涨，'
            '还能跟着大家一起养成健康减重的好习惯。现在参与完全来得及，一起加入进来！'
        ),
        'competitive': (
            '还在潜水的家人们别蹲了！出来打卡、唠唠嗑，积分蹭蹭涨！\n'
            '再不活跃，「金百花奖」就没你的份了！赶紧动起来，'
            '跟着大部队一起瘦，一起拿奖！'
        ),
    },
    'reverse_bottom': {
        'professional': (
            '{name} 积分暂时靠后，本次结营设置「绿草莓奖」幽默反向激励，'
            '希望大家以此为契机，重新调整减重节奏，跟上每日打卡、学习的进度，'
            '在后续的健康管理中迎头赶上，收获理想的减重成果。'
        ),
        'encouraging': (
            '{name} 别灰心呀～3 个月的旅程还没结束，'
            '现在开始行动，积分和体重都能追上来！\n'
            '我们一起慢慢调整，互相陪伴，下一次榜单一定能看到你的进步！'
        ),
        'competitive': (
            '{name} 注意！后 6 名的「绿草莓奖」已经就位！\n'
            '别摆烂了！再不打卡、再不减重，就要拿反向奖励了！'
            '赶紧动起来，把积分冲上去，把体重降下来，逆袭就在下一个榜单！'
        ),
    },
    'daily_remind': {
        'professional': (
            '今日积分榜单已更新，看看自己排在第几？\n'
            '积分排名实时更新，越活跃越靠前。'
            '坚持打卡、积极互动，往前多冲几名，大奖就在前方！'
        ),
        'encouraging': (
            '积分就是努力的证明！每天简单打个卡、在群里说说话，积分就会慢慢涨，'
            '还能跟着大家一起养成健康减重的好习惯。\n'
            '越活跃，越瘦得快，越能拿大奖！家人们，冲就完事了！'
        ),
        'competitive': (
            '积分排名实时更新！再不活跃大奖就没你的份了！\n'
            '前 6 名稳住，后 6 名逆袭，中间的伙伴往前冲，'
            '咱们一起健康减重，一起拿奖！'
        ),
    },
    'group_pk': {
        'professional': (
            '【月度社群 PK 提醒】\n'
            '20 个社群的综合排名（打卡率 / 减重率 / 积分率）每月更新，每月发放团队奖！\n'
            '个人的坚持汇聚成团队的力量，每一次打卡、每一分积分，都在为咱们社群的排名助力。'
            '请大家积极活跃、认真减重，一起冲刺月度前 2 名，拿团队大奖！'
        ),
        'encouraging': (
            '🥳 咱们 20 个社群的月度 PK 赛每月都有奖励哦！\n'
            '咱们社群的排名，靠的是每一个人的打卡、每一分积分、每一斤的减重成果！'
            '大家一起活跃起来、认真减重，一起冲刺月度前 2 名，拿团队大奖，咱们一起赢！'
        ),
        'competitive': (
            '家人们！20 个社群月度 PK 赛开卷了！\n'
            '咱们社群的排名，就看你们的打卡率、减重率、积分率！'
            '每一分都算数，每一斤都关键！一起冲月度前 2，拿团队大奖，给咱们社群长脸！'
        ),
    },
}

# 保持 TEMPLATES 别名兼容
TEMPLATES = _SEED_TEMPLATES

# ── DB 读取缓存（120 秒） ──
_db_cache: dict[str, tuple[float, dict[str, dict[str, str]]]] = {}
_DB_CACHE_TTL = 120


def _load_from_db(db) -> dict[str, dict[str, str]] | None:
    from .. import models
    rows = db.query(models.SpeechTemplate).order_by(
        models.SpeechTemplate.scene_key, models.SpeechTemplate.style,
    ).all()
    if not rows:
        return None
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        result.setdefault(row.scene_key, {})[row.style] = row.content
    return result


def _get_cached_templates(db) -> dict[str, dict[str, str]]:
    now = time.time()
    cache_key = '_global'
    if cache_key in _db_cache:
        ts, data = _db_cache[cache_key]
        if now - ts < _DB_CACHE_TTL:
            return data

    db_data = _load_from_db(db)
    if db_data is None:
        return _SEED_TEMPLATES

    _db_cache[cache_key] = (now, db_data)
    return db_data


def seed_speech_templates(db) -> int:
    """首次运行时灌入种子数据，返回插入数量"""
    from .. import models
    existing = db.query(models.SpeechTemplate).first()
    if existing:
        return 0
    count = 0
    for scene_key, styles in _SEED_TEMPLATES.items():
        label = SCENE_LABELS.get(scene_key, scene_key)
        for style, content in styles.items():
            db.add(models.SpeechTemplate(
                scene_key=scene_key,
                style=style,
                label=label,
                content=content,
                is_builtin=1,
            ))
            count += 1
    db.commit()
    _log.info('已灌入 %d 条话术模板种子数据', count)
    return count


def invalidate_cache() -> None:
    _db_cache.clear()


def get_all_templates(db) -> dict[str, list[dict]]:
    """返回按 scene_key 分组的全部模板（DB 优先）"""
    from .. import models
    rows = db.query(models.SpeechTemplate).order_by(
        models.SpeechTemplate.scene_key, models.SpeechTemplate.style,
    ).all()
    if not rows:
        rows = []
        for scene_key, styles in _SEED_TEMPLATES.items():
            label = SCENE_LABELS.get(scene_key, scene_key)
            for style, content in styles.items():
                rows.append(type('Row', (), {
                    'id': 0, 'scene_key': scene_key, 'style': style,
                    'label': label, 'content': content, 'is_builtin': 1,
                })())
    result: dict[str, list[dict]] = {}
    for row in rows:
        result.setdefault(row.scene_key, []).append({
            'id': row.id,
            'scene_key': row.scene_key,
            'style': row.style,
            'label': row.label,
            'content': row.content,
            'is_builtin': row.is_builtin,
        })
    return result


def get_speech(scene_key: str, style: str = 'professional', **kwargs: Any) -> str:
    """获取场景话术，填充占位符（使用硬编码 fallback）"""
    templates = _SEED_TEMPLATES.get(scene_key)
    if not templates:
        return ''
    text = templates.get(style) or templates.get('professional', '')
    if not text:
        return ''
    try:
        return text.format(**kwargs)
    except KeyError:
        return text


def get_speech_from_db(db, scene_key: str, style: str = 'professional', **kwargs: Any) -> str:
    """从 DB 获取话术（带缓存），fallback 到硬编码"""
    all_templates = _get_cached_templates(db)
    templates = all_templates.get(scene_key)
    if not templates:
        return ''
    text = templates.get(style) or templates.get('professional', '')
    if not text:
        return ''
    try:
        return text.format(**kwargs)
    except KeyError:
        return text


def build_insight_speech(
    insight: dict,
    style: str = 'professional',
    max_speeches: int = 3,
) -> list[str]:
    """根据洞察结果生成话术列表"""
    speeches = []
    name = insight.get('customer_name', '')
    rank = insight.get('rank', 0)

    activity_types = insight.get('activity_types', {})
    if activity_types:
        top_activities = sorted(activity_types.items(), key=lambda x: x[1], reverse=True)[:3]
        activity_desc = '、'.join([label for label, _ in top_activities])
    else:
        activity_desc = '积极参与'

    for scene in insight.get('scenes', []):
        if len(speeches) >= max_speeches:
            break
        key = scene['key']
        detail = scene.get('detail', '')
        speech = get_speech(
            key, style,
            name=name, rank=rank, detail=detail, activity=activity_desc,
        )
        if speech:
            speeches.append(speech)

    return speeches


# 场景描述片段，用于生成合并话术
_SCENE_SUMMARY: dict[str, str] = {
    'top_leader': '积分榜稳居 TOP3',
    'top_six': '冲进积分前六',
    'top_ten': '积分排名前十',
    'consistent': '连续多日坚持打卡',
    'surge': '近期积分暴涨',
    'comeback': '强势回归打卡',
    'dropout_recovery': '掉队后重新归队',
    'rapid_progress': '近期进步飞快',
    'reverse_bottom': '正在努力追赶',
    'lurker_remind': '很久没冒泡了',
}


def build_grouped_insight_speeches(
    insights: list[dict],
    style: str = 'professional',
    max_scenes: int = 5,
) -> list[str]:
    """按场景分组生成合并话术：同场景多人合成一句"""
    def _build_multi_member_grouped_speech(scene_key: str, names: str, summary: str) -> str:
        rank_scene_summary = {
            'top_leader': '稳居积分榜 TOP3',
            'top_six': '已经冲进积分榜前六',
            'top_ten': '正在积分榜前十持续竞争',
        }
        normalized_summary = rank_scene_summary.get(scene_key, summary)

        if style == 'encouraging':
            return f'{names} 最近都很棒，{normalized_summary}，继续保持打卡、学习和互动，大奖会越来越近！'
        if style == 'competitive':
            return f'{names} 这波一起 {normalized_summary}，状态拉满，继续冲，别给后面的人反超机会！'
        return f'{names} {normalized_summary}，继续保持当前节奏，也请带动群内伙伴一起进步。'

    from collections import OrderedDict
    grouped: OrderedDict[str, list[dict]] = OrderedDict()
    for insight in insights:
        for scene in insight.get('scenes', []):
            key = scene['key']
            grouped.setdefault(key, []).append({
                'name': insight.get('customer_name', ''),
                'rank': insight.get('rank', 0),
                'detail': scene.get('detail', ''),
                'activity': insight.get('activity_types', {}),
            })

    speeches: list[str] = []
    for scene_key, members in grouped.items():
        if len(speeches) >= max_scenes:
            break
        if not members:
            continue
        names = '、'.join(m['name'] for m in members if m['name'])
        if not names:
            continue
        summary = _SCENE_SUMMARY.get(scene_key, '表现突出')
        detail = members[0].get('detail', '')

        if len(members) > 1:
            speeches.append(_build_multi_member_grouped_speech(scene_key, names, summary))
            continue

        # 单人场景仍沿用原模板渲染
        template_speech = get_speech(scene_key, style, name=names, rank=members[0].get('rank', 0), detail=detail, activity='积极参与')
        if template_speech:
            speeches.append(template_speech)
        else:
            speeches.append(f'{names} {summary}！{detail}')

    return speeches
