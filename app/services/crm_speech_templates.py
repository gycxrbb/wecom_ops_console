"""积分运营话术模板库

按 scene_key + style 组织话术模板。
基于首钢减重健康群积分激励专属话术 Excel 提炼。
后续可迁移到数据库表，现阶段用代码管理。
"""
from __future__ import annotations

from typing import Any

# 话术风格枚举
STYLES = ('professional', 'encouraging', 'competitive')

# ── 场景 → 话术模板 ────────────────────────────────────────
# 每个场景支持 3 种风格，使用 {name} {rank} {detail} {activity} 占位符

TEMPLATES: dict[str, dict[str, str]] = {
    # 个人洞察场景
    'top_leader': {
        'professional': '🏆 {name} 当前排名第{rank}，稳居榜首，继续保持！',
        'encouraging': '🥇 {name} 太棒啦！积分领跑全场，再坚持一下，大奖就在眼前！',
        'competitive': '⚠️ {name} 排名第{rank}！后面的人正在疯狂追赶，千万别翻车！',
    },
    'top_six': {
        'professional': '{name} 积分排名第{rank}，已进入第一梯队，保持稳定输出即可锁定排名。',
        'encouraging': '🎉 {name} 超优秀的！排名前六，距离大奖越来越近了，继续加油～',
        'competitive': '{name} 排名第{rank}，「金百花奖」冲线区选手！再努努力直接抱回家！',
    },
    'top_ten': {
        'professional': '{name} 当前第{rank}名，差距不大，增加打卡频次即可进入前六。',
        'encouraging': '{name} 只差一点点就能冲进前六啦！每天多打一次卡，排名就会不一样～',
        'competitive': '{name} 第{rank}名，冲一把就进前六！别犹豫，每天多打卡就能逆袭！',
    },
    'consistent': {
        'professional': '特别表扬 {name}，{detail}，自律践行了健康生活方式，值得全体学习。',
        'encouraging': '❤️ 每天都能看到 {name} 准时打卡，{activity}，你们的坚持所有人都看在眼里！',
        'competitive': '实名表扬 {name}！{activity}，这自律程度我直接 respect！给我焊死在榜上！',
    },
    'surge': {
        'professional': '{name} 近期积分涨幅明显，{detail}，行动力值得肯定。',
        'encouraging': '✨ {name} 最近好活跃呀！{activity}，积分一下子就上来了，太为你开心了！',
        'competitive': '惊现黑马！{name} 前几天还隐身，最近突然上线猛冲，积分直接起飞🚀！',
    },
    'comeback': {
        'professional': '欢迎 {name} 回归，{detail}，重新跟上节奏，积分仍有提升空间。',
        'encouraging': '💪 {name} 欢迎回来！不用急着追进度，慢慢跟上节奏就好，我们陪着你～',
        'competitive': '失踪人口 {name} 回归啦！满血复活冲就完事了，积分还能追，给我冲！',
    },
    # 通用氛围场景
    'daily_remind': {
        'professional': '积分排名实时更新中，越活跃越靠前，坚持打卡、积极互动，大奖就在前方！',
        'encouraging': '今天也要记得打卡哦～每一分都是努力的证明，我们一起慢慢变好！',
        'competitive': '积分榜已更新！再不活跃大奖就没你的份了，赶紧动起来！',
    },
    'group_pk': {
        'professional': '社群月度 PK 排名实时更新！每一次打卡、每一分积分都在为团队加分，一起冲刺月度前列！',
        'encouraging': '🥳 咱们社群的排名靠的是每一个人！大家一起活跃起来，拿团队大奖！',
        'competitive': '家人们！社群 PK 赛开卷了！每一分都算数，冲月度前 2，给咱们群长脸！',
    },
}


def get_speech(scene_key: str, style: str = 'professional', **kwargs: Any) -> str:
    """获取场景话术，填充占位符

    Args:
        scene_key: 场景 key（如 top_leader, surge, comeback 等）
        style: 话术风格
        **kwargs: 占位符变量（name, rank, detail, activity 等）

    Returns:
        填充后的话术文本
    """
    templates = TEMPLATES.get(scene_key)
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
    """根据洞察结果生成话术列表

    Args:
        insight: 单个洞察结果（来自 crm_points_insights）
        style: 话术风格
        max_speeches: 最多生成几条话术

    Returns:
        话术文本列表
    """
    speeches = []
    name = insight.get('customer_name', '')
    rank = insight.get('rank', 0)

    # 拼接活动类型描述
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
