"""运营编排导出服务：Plan → JSON / Excel"""
from __future__ import annotations

import json
from io import BytesIO
from typing import Any

import openpyxl

from app.services.operation_plan_import import (
    JSON_STAGE_RULE_MAP,
    NODE_COLUMN_RULES,
    normalize_text,
)

# node_type → 友好标题（从已有映射反查）
_NODE_TYPE_TITLES: dict[str, str] = {}
for _rule in NODE_COLUMN_RULES:
    _NODE_TYPE_TITLES[_rule["node_type"]] = _rule["title"]
for _mapping in JSON_STAGE_RULE_MAP.values():
    _NODE_TYPE_TITLES.setdefault(_mapping["node_type"], _mapping["title"])


def _get_node_title(node_type: str) -> str:
    return _NODE_TYPE_TITLES.get(node_type, node_type)


# ── 通用序列化 ────────────────────────────────────────────────────────────

def export_plan_to_dict(plan: Any) -> dict[str, Any]:
    """将 Plan ORM 对象序列化为通用 dict（可 JSON 化）"""
    days_out: list[dict[str, Any]] = []
    for day in sorted(plan.days, key=lambda d: d.day_number):
        nodes_out: list[dict[str, Any]] = []
        for node in sorted(day.nodes, key=lambda n: n.sort_order):
            content_json = node.content_json
            if isinstance(content_json, str):
                try:
                    content_json = json.loads(content_json)
                except (json.JSONDecodeError, TypeError):
                    content_json = {}
            variables_json = node.variables_json
            if isinstance(variables_json, str):
                try:
                    variables_json = json.loads(variables_json)
                except (json.JSONDecodeError, TypeError):
                    variables_json = {}

            nodes_out.append({
                "node_type": node.node_type or "custom",
                "title": node.title or "",
                "msg_type": node.msg_type or "markdown",
                "description": node.description or "",
                "content": content_json.get("content", "") if isinstance(content_json, dict) else str(content_json),
                "sort_order": node.sort_order,
                "variables_json": variables_json if isinstance(variables_json, dict) else {},
            })

        days_out.append({
            "day": day.day_number,
            "week_label": _infer_week_label(day.day_number),
            "day_title": day.title or f"第{day.day_number}天",
            "day_focus": day.focus or "",
            "nodes": nodes_out,
        })

    # 收集所有 node_type 生成 stage_templates
    seen_types: dict[str, dict[str, Any]] = {}
    for day_data in days_out:
        for node_data in day_data["nodes"]:
            nt = node_data["node_type"]
            if nt not in seen_types:
                seen_types[nt] = {
                    "stage_key": nt,
                    "stage_name": node_data["title"] or _get_node_title(nt),
                    "stage_order": node_data["sort_order"],
                    "scheduled_time": "",
                    "owner": "",
                    "fixed_action": "",
                }

    stage_templates = sorted(seen_types.values(), key=lambda s: s["stage_order"])

    plan_name = plan.name or ""
    stage = plan.stage or ""
    topic = plan.topic or ""

    return {
        "plan_name": plan_name,
        "stage": stage,
        "topic": topic,
        "description": plan.description or "",
        "stage_templates": stage_templates,
        "days": days_out,
    }


def _infer_week_label(day_number: int) -> str:
    """根据天数推断周次标签"""
    week = (day_number - 1) // 7 + 1
    week_map = {1: "第一周", 2: "第二周", 3: "第三周", 4: "第四周", 5: "第五周"}
    return week_map.get(week, f"第{week}周")


# ── JSON 导出 ─────────────────────────────────────────────────────────────

def export_plan_to_json_bytes(plan: Any) -> bytes:
    """导出为 JSON bytes"""
    data = export_plan_to_dict(plan)
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


# ── Excel 导出 ────────────────────────────────────────────────────────────

def export_plan_to_excel_bytes(plan: Any) -> bytes:
    """导出为 Excel bytes"""
    data = export_plan_to_dict(plan)
    plan_dict = data
    days = plan_dict["days"]

    if not days:
        raise ValueError("计划中没有可导出的天数")

    # 收集所有 node_type 并排序
    all_node_types: list[str] = []
    seen: set[str] = set()
    for day_data in days:
        for node_data in day_data["nodes"]:
            nt = node_data["node_type"]
            if nt not in seen:
                seen.add(nt)
                all_node_types.append(nt)

    # node_type → 列索引（从 col=3 开始）
    col_map: dict[str, int] = {}
    for idx, nt in enumerate(all_node_types):
        col_map[nt] = 3 + idx  # 0-indexed

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "运营编排导出"

    # Row 1: 计划名称
    scope = plan_dict["plan_name"]
    if plan_dict["stage"]:
        scope = f"{plan_dict['stage']}：{plan_dict['topic'] or scope}"
    ws.cell(row=1, column=1, value=scope)

    # Row 3: 表头
    ws.cell(row=3, column=1, value="每周")
    ws.cell(row=3, column=2, value="时间（第x天）")
    ws.cell(row=3, column=3, value="节点说明")
    for nt in all_node_types:
        title = _get_node_title(nt)
        ws.cell(row=3, column=col_map[nt] + 1, value=title)  # openpyxl is 1-indexed

    # Row 4: 描述（从 stage_templates 提取）
    for nt in all_node_types:
        for st in plan_dict["stage_templates"]:
            if st["stage_key"] == nt:
                desc = st.get("fixed_action", "")
                if desc:
                    ws.cell(row=4, column=col_map[nt] + 1, value=desc)
                break

    # Row 6+: 数据行
    row_num = 6
    for day_data in days:
        day_num = day_data["day"]
        week_label = day_data.get("week_label", "")

        # 构建 node_type → content 映射
        node_contents: dict[str, str] = {}
        for node_data in day_data["nodes"]:
            nt = node_data["node_type"]
            content = node_data.get("content", "")
            node_contents[nt] = content

        # 写入主行
        ws.cell(row=row_num, column=1, value=week_label)
        ws.cell(row=row_num, column=2, value=f"第{day_num}天")
        for nt in all_node_types:
            content = node_contents.get(nt, "")
            if content:
                ws.cell(row=row_num, column=col_map[nt] + 1, value=content)

        row_num += 1

    # 调整列宽
    ws.column_dimensions["A"].width = 10
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 14
    for nt in all_node_types:
        col_letter = openpyxl.utils.get_column_letter(col_map[nt] + 1)
        ws.column_dimensions[col_letter].width = 40

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
