"""运营计划常量 — 节点预设 & 积分运营阶段定义"""
from __future__ import annotations

from typing import Any

# ── Day Flow 节点预设 ──────────────────────────────────────────

NODE_PRESETS: list[dict[str, Any]] = [
    {
        'node_type': 'morning_breakfast',
        'title': '早安 / 早餐提醒',
        'description': '发送早安招呼，并同步早餐提醒内容。',
        'sort_order': 10,
        'msg_type': 'markdown',
        'content_json': {'content': '请填写第 {{ day_number }} 天的早安/早餐提醒内容'},
    },
    {
        'node_type': 'score_publish',
        'title': '积分相关发布',
        'description': '护士教练录入积分后，由 AI 生成表单并截图发群。',
        'sort_order': 20,
        'msg_type': 'markdown',
        'content_json': {'content': '请填写第 {{ day_number }} 天的积分发布内容与 AI 截图说明'},
    },
    {
        'node_type': 'before_lunch_content',
        'title': '午餐前内容发布',
        'description': '午餐前自动发布科普知识点、图片/视频资料和实用知识点。',
        'sort_order': 30,
        'msg_type': 'markdown',
        'content_json': {'content': '请填写第 {{ day_number }} 天的午餐前内容发布'},
    },
    {
        'node_type': 'lunch_reminder',
        'title': '午餐提醒发布',
        'description': '午餐提醒节点，发布知识点、素材和执行提醒。',
        'sort_order': 40,
        'msg_type': 'markdown',
        'content_json': {'content': '请填写第 {{ day_number }} 天的午餐提醒内容'},
    },
    {
        'node_type': 'dinner_reminder',
        'title': '晚餐提醒发布',
        'description': '按预设时间自动发送实用知识内容。',
        'sort_order': 50,
        'msg_type': 'markdown',
        'content_json': {'content': '请填写第 {{ day_number }} 天的晚餐提醒内容'},
    },
    {
        'node_type': 'night_summary',
        'title': '晚安 / 总结 / 次日预告',
        'description': '按预设时间自动发送晚安类内容、总结和次日预告。',
        'sort_order': 60,
        'msg_type': 'markdown',
        'content_json': {'content': '请填写第 {{ day_number }} 天的晚安/总结/次日预告内容'},
    },
]

NODE_PRESET_MAP = {preset['node_type']: preset for preset in NODE_PRESETS}

# ── 积分运营阶段预设 ──────────────────────────────────────────

POINTS_CAMPAIGN_STAGES: list[dict[str, Any]] = [
    {
        'stage_key': 'daily_ranking',
        'title': '每日发榜',
        'description': '每天定时发送积分排行消息到群',
        'trigger_type': 'daily',
        'default_time': '18:00',
        'sort_order': 10,
        'node_presets': [
            {'node_type': 'group_ranking_publish', 'title': '积分排行发布', 'msg_type': 'markdown',
             'description': '自动生成各群积分排行并发送'},
        ],
        'core_actions': [
            '发榜：生成并推送各群积分排行',
            '表扬前6名（金百花奖冲刺区）',
            '表扬连续打卡成员',
            '鼓励回归用户',
            '提醒潜水/观望用户',
            '提及社群月度PK',
        ],
        'followup_1v1': [
            '私发TOP3：鼓励稳住排名',
            '私发连续打卡7+天：肯定坚持',
            '私发3天未打卡：温和提醒',
        ],
    },
    {
        'stage_key': 'weekly_review',
        'title': '每周复盘',
        'description': '每周固定时间发送本周积分回顾',
        'trigger_type': 'weekly',
        'trigger_config': {'weekday': 7, 'time': '19:30'},
        'sort_order': 20,
        'node_presets': [
            {'node_type': 'weekly_points_review', 'title': '周积分复盘', 'msg_type': 'markdown',
             'description': '本周各群积分汇总与亮点'},
        ],
        'core_actions': [
            '本周积分总结：各群总分、个人TOP6',
            '表扬周TOP6',
            '表扬本周暴涨/黑马成员',
            '鼓励掉队成员重新跟上',
            '社群PK排名播报',
            '轻科普：健康减重小知识',
        ],
        'followup_1v1': [
            '表扬进步最快成员',
            '邀请分享减重心得',
            '2周未打卡成员1v1关怀',
        ],
    },
    {
        'stage_key': 'sprint_14_7',
        'title': '冲刺阶段（14-7天前）',
        'description': '结营前14-7天冲刺激励',
        'trigger_type': 'countdown_range',
        'trigger_config': {'days_before_start': 14, 'days_before_end': 7},
        'sort_order': 30,
        'node_presets': [
            {'node_type': 'surge_user_highlight', 'title': '黑马表扬', 'msg_type': 'markdown',
             'description': '识别并表扬近期积分爆发增长的成员'},
            {'node_type': 'group_pk_broadcast', 'title': '群PK播报', 'msg_type': 'markdown',
             'description': '跨群积分PK排行'},
        ],
        'core_actions': [
            '倒计时提醒：结营还有XX天',
            '动员前6名稳住排名',
            '中间段成员冲刺动员',
            '后段成员逆袭鼓励',
        ],
        'followup_1v1': [
            '重点用户群内@提醒打卡',
            '差几分进前6的私发鼓励',
        ],
    },
    {
        'stage_key': 'sprint_7_3',
        'title': '冲刺阶段（7-3天前）',
        'description': '结营前7-3天冲刺激励',
        'trigger_type': 'countdown_range',
        'trigger_config': {'days_before_start': 7, 'days_before_end': 3},
        'sort_order': 40,
        'node_presets': [
            {'node_type': 'surge_user_highlight', 'title': '黑马表扬', 'msg_type': 'markdown',
             'description': '识别并表扬近期积分爆发增长的成员'},
            {'node_type': 'comeback_user_welcome', 'title': '回归欢迎', 'msg_type': 'markdown',
             'description': '欢迎回归的成员'},
            {'node_type': 'group_pk_broadcast', 'title': '群PK播报', 'msg_type': 'markdown',
             'description': '跨群积分PK排行'},
        ],
        'core_actions': [
            '早晚双重动员提醒',
            '强化前6名稳住',
            '重点鼓励中间段冲刺',
        ],
        'followup_1v1': [
            '差几分进前6的群内@鼓励',
            '3天未打卡紧急提醒',
        ],
    },
    {
        'stage_key': 'sprint_final_1',
        'title': '结营前1天',
        'description': '结营前最后1天的冲刺总动员',
        'trigger_type': 'final_day',
        'trigger_config': {'days_before': 1},
        'sort_order': 50,
        'node_presets': [
            {'node_type': 'group_ranking_publish', 'title': '积分排行发布', 'msg_type': 'markdown',
             'description': '最新排行发布'},
            {'node_type': 'group_pk_broadcast', 'title': '最终PK排行', 'msg_type': 'markdown',
             'description': '最终跨群PK排行'},
        ],
        'core_actions': [
            '最终冲刺提醒',
            '最后打卡号召',
            '强调明天就是结营',
        ],
        'followup_1v1': [
            'TOP10务必打卡提醒',
            '后6名最后鼓励',
        ],
    },
    {
        'stage_key': 'closing_day',
        'title': '结营当天',
        'description': '结营当天的总结与颁奖',
        'trigger_type': 'final_day',
        'trigger_config': {'days_before': 0},
        'sort_order': 60,
        'node_presets': [
            {'node_type': 'group_ranking_publish', 'title': '最终排行', 'msg_type': 'markdown',
             'description': '最终积分排行发布'},
            {'node_type': 'dropout_reactivation', 'title': '未达标关怀', 'msg_type': 'markdown',
             'description': '对未达标成员的鼓励关怀'},
        ],
        'core_actions': [
            '公布最终榜单',
            '获奖公示（金百花奖 / 绿草莓奖）',
            '感谢全员参与',
            '社群PK最终排名',
        ],
        'followup_1v1': [
            '获奖成员恭喜私发',
            '绿草莓奖温柔鼓励',
        ],
    },
]
