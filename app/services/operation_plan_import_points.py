"""积分运营计划 Excel 导入解析器

解析积分运营类 Excel，支持两种 sheet 结构：
- 运营阶段配置 sheet（必须）：6 阶段定义 + 群内话术 + 1v1 动作
- 话术模板 sheet（可选）：场景 × 风格话术库
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from .operation_plan_constants import POINTS_CAMPAIGN_STAGES


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _find_header_row(rows: list[list[Any]], max_scan: int = 5) -> int | None:
    """扫描前 max_scan 行，找到包含阶段表头关键词的行索引"""
    keywords = {'阶段节点', '阶段key', '核心动作', '群内话术', '1v1'}
    for i, row in enumerate(rows[:max_scan]):
        cells = [normalize_text(c) for c in row]
        match_count = sum(1 for kw in keywords if any(kw in cell for cell in cells))
        if match_count >= 2:
            return i
    return None


def _detect_stages_sheet(rows: list[list[Any]]) -> bool:
    if not rows:
        return False
    return _find_header_row(rows) is not None


def _detect_speech_sheet(rows: list[list[Any]]) -> bool:
    if not rows:
        return False
    for row in rows[:3]:
        cells = [normalize_text(c) for c in row]
        if any('场景key' in cell or '场景名称' in cell for cell in cells):
            return True
    return False


def _build_col_map(headers: list[str], rules: list[tuple[str, list[str]]]) -> dict[str, int]:
    col_map: dict[str, int] = {}
    for key, keywords in rules:
        for i, h in enumerate(headers):
            if any(kw in h for kw in keywords):
                col_map[key] = i
                break
    return col_map


_STAGES_COL_RULES = [
    ('name', ['阶段节点', '名称']),
    ('stage_key', ['阶段key', 'stage_key']),
    ('default_time', ['执行时间', '默认时间', '时间']),
    ('core_actions', ['核心动作']),
    ('message', ['群内话术', '群内消息', '消息内容']),
    ('followup_1v1', ['1v1', '跟进']),
]


def _extract_stage_name(row: list[Any], col_map: dict[str, int]) -> str:
    """提取阶段名称：name 列可能是数字编号，右侧相邻列才是真实名称"""
    name_col = col_map.get('name', 0)
    raw = normalize_text(row[name_col]) if name_col < len(row) else ''
    # 如果 name 列是纯数字（阶段编号），尝试取下一列作为真实名称
    if raw.isdigit() and name_col + 1 < len(row):
        next_val = normalize_text(row[name_col + 1])
        if next_val:
            return next_val
    return raw

_SPEECH_COL_RULES = [
    ('scene_key', ['场景key', 'scene']),
    ('scene_name', ['场景名称']),
    ('professional', ['专业']),
    ('encouraging', ['鼓励']),
    ('competitive', ['竞争']),
]


def _parse_stages_sheet(rows: list[list[Any]]) -> list[dict[str, Any]]:
    if len(rows) < 2:
        raise HTTPException(400, '积分运营阶段配置 sheet 不足 2 行')

    header_idx = _find_header_row(rows)
    if header_idx is None:
        raise HTTPException(400, '未找到阶段配置表头行（需要包含"阶段节点"和"核心动作"列表头）')

    headers = [normalize_text(c) for c in rows[header_idx]]
    col_map = _build_col_map(headers, _STAGES_COL_RULES)

    presets_map = {s['stage_key']: s for s in POINTS_CAMPAIGN_STAGES}
    preset_list = list(presets_map.values())
    stages: list[dict[str, Any]] = []

    for row in rows[header_idx + 1:]:
        if not row or not any(c for c in row if c is not None):
            continue

        stage_name = _extract_stage_name(row, col_map) if 'name' in col_map else ''
        if not stage_name:
            continue

        # 自动匹配 stage_key：按行序匹配预设
        stage_idx = len(stages)
        if stage_idx < len(preset_list):
            preset = preset_list[stage_idx]
            stage_key = preset['stage_key']
        else:
            preset = {}
            stage_key = f'stage_{stage_idx + 1}'
        sort_order = preset.get('sort_order', (stage_idx + 1) * 10)

        def _split_lines(val: Any) -> list[str]:
            text = normalize_text(val)
            return [a.strip() for a in text.split('\n') if a.strip()] if text else []

        core_actions = _split_lines(row[col_map['core_actions']]) if 'core_actions' in col_map else []
        if not core_actions:
            core_actions = preset.get('core_actions', [])

        followup = _split_lines(row[col_map['followup_1v1']]) if 'followup_1v1' in col_map else []
        if not followup:
            followup = preset.get('followup_1v1', [])

        message = normalize_text(row[col_map['message']]) if 'message' in col_map else ''
        trigger = preset.get('trigger_type', 'daily')
        default_time = normalize_text(row[col_map['default_time']]) if 'default_time' in col_map else ''
        if not default_time:
            default_time = preset.get('default_time', '08:00')

        stages.append({
            'stage_key': stage_key,
            'title': stage_name or preset.get('title', stage_key),
            'description': preset.get('description', ''),
            'trigger_type': trigger,
            'default_time': default_time,
            'trigger_config': preset.get('trigger_config', {}),
            'sort_order': sort_order,
            'message_content': message,
            'core_actions': core_actions,
            'followup_1v1': followup,
            'node_presets': preset.get('node_presets', []),
        })

    if not stages:
        raise HTTPException(400, '未解析到有效的积分运营阶段数据')
    return stages


def _parse_speech_sheet(rows: list[list[Any]]) -> list[dict[str, Any]]:
    if len(rows) < 2:
        return []

    headers = [normalize_text(c) for c in rows[0]]
    col_map = _build_col_map(headers, _SPEECH_COL_RULES)

    templates: list[dict[str, Any]] = []
    for row in rows[1:]:
        if not row or not any(c for c in row if c is not None):
            continue
        scene_key = normalize_text(row[col_map.get('scene_key', 0)]) if 'scene_key' in col_map else ''
        if not scene_key:
            continue
        templates.append({
            'scene_key': scene_key,
            'scene_name': normalize_text(row[col_map['scene_name']]) if 'scene_name' in col_map else '',
            'professional': normalize_text(row[col_map['professional']]) if 'professional' in col_map else '',
            'encouraging': normalize_text(row[col_map['encouraging']]) if 'encouraging' in col_map else '',
            'competitive': normalize_text(row[col_map['competitive']]) if 'competitive' in col_map else '',
        })
    return templates


def _build_trigger_rule(stage: dict[str, Any]) -> dict[str, Any]:
    rule: dict[str, Any] = {
        'trigger_type': stage.get('trigger_type', 'daily'),
        'default_time': stage.get('default_time', '18:00'),
    }
    tc = stage.get('trigger_config', {})
    if tc:
        rule.update(tc)
    return rule


def _build_day_from_stage(index: int, stage: dict[str, Any]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    presets = stage.get('node_presets', [])
    for j, preset in enumerate(presets):
        nodes.append({
            'node_type': preset['node_type'],
            'title': preset['title'],
            'description': preset.get('description', ''),
            'sort_order': (j + 1) * 10,
            'msg_type': preset.get('msg_type', 'markdown'),
            'content': stage.get('message_content', ''),
            'variables_json': {
                'stage_key': stage['stage_key'],
                'core_actions': stage.get('core_actions', []),
                'followup_1v1': stage.get('followup_1v1', []),
            },
            'status': 'ready' if stage.get('message_content') else 'draft',
            'enabled': True,
        })
    if not nodes:
        nodes.append({
            'node_type': 'group_ranking_publish',
            'title': stage.get('title', f'阶段{index + 1}'),
            'description': stage.get('description', ''),
            'sort_order': 10,
            'msg_type': 'markdown',
            'content': stage.get('message_content', ''),
            'variables_json': {
                'stage_key': stage.get('stage_key', ''),
                'core_actions': stage.get('core_actions', []),
                'followup_1v1': stage.get('followup_1v1', []),
            },
            'status': 'ready' if stage.get('message_content') else 'draft',
            'enabled': True,
        })

    return {
        'day_number': index + 1,
        'week_label': stage.get('stage_key', ''),
        'day_title': stage.get('title', f'阶段{index + 1}'),
        'day_focus': '\n'.join(f'- {a}' for a in stage.get('core_actions', [])),
        'trigger_rule_json': _build_trigger_rule(stage),
        'nodes': nodes,
    }


def build_points_campaign_plan(
    stages: list[dict[str, Any]],
    speech_templates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    days = [_build_day_from_stage(i, s) for i, s in enumerate(stages)]
    warnings: list[str] = []
    if speech_templates:
        warnings.append(f'识别到 {len(speech_templates)} 条话术模板（已保存到计划数据中）')

    return {
        'plan_name': '积分运营计划',
        'stage': '积分运营',
        'topic': '积分运营',
        'description': '由积分运营 Excel 导入生成',
        'plan_mode': 'points_campaign',
        'day_count': len(days),
        'days': days,
        'speech_templates': speech_templates or [],
        'warnings': warnings,
    }


def parse_points_campaign_excel(workbook: Any) -> dict[str, Any]:
    stages_data = None
    speech_data = None

    for sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        rows = [list(row) for row in sheet.iter_rows(values_only=True)]

        if not stages_data and _detect_stages_sheet(rows):
            stages_data = _parse_stages_sheet(rows)
            continue
        if not speech_data and _detect_speech_sheet(rows):
            speech_data = _parse_speech_sheet(rows)
            continue

    if not stages_data:
        raise HTTPException(
            400,
            '未找到有效的积分运营阶段配置 sheet（需要包含"阶段节点"和"核心动作"列表头）',
        )
    return build_points_campaign_plan(stages_data, speech_data)


def build_default_campaign_plan() -> dict[str, Any]:
    """从 POINTS_CAMPAIGN_STAGES 常量直接构建默认积分运营计划"""
    return build_points_campaign_plan(POINTS_CAMPAIGN_STAGES)
