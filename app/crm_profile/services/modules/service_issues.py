"""Service issues module — customer obstacles and blockers.

Sources: service_issues (mfgcrmdb).
Shows latest 10 issues with status, title, date.
"""
from __future__ import annotations

import logging

from ...schemas.context import ModulePayload

_log = logging.getLogger(__name__)

MODULE_KEY = "service_issues"


def load(conn, customer_id: int) -> ModulePayload:
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, description, status, solution, "
                "completed_at, created_at "
                "FROM service_issues "
                "WHERE customer_id = %s "
                "ORDER BY created_at DESC LIMIT 10",
                (customer_id,),
            )
            rows = cur.fetchall()

        if not rows:
            return ModulePayload(key=MODULE_KEY, status="empty", payload={})

        issues = []
        unresolved = 0
        for r in rows:
            st = r["status"]
            if st == 0:
                unresolved += 1
            issues.append({
                "id": r["id"],
                "name": str(r["name"] or "未命名问题")[:120],
                "description": str(r["description"] or "")[:200],
                "status": st,
                "status_text": "未解决" if st == 0 else "已解决",
                "solution": str(r["solution"] or "")[:200] if r["solution"] else None,
                "created_at": str(r["created_at"])[:10] if r.get("created_at") else "",
                "completed_at": str(r["completed_at"])[:10] if r.get("completed_at") else None,
            })

        parts = [f"{len(issues)}项记录"]
        if unresolved > 0:
            parts.append(f"{unresolved}项未解决")
        issue_summary = "，".join(parts)
        detail_lines = []
        for issue in issues[:5]:
            desc = str(issue.get("description") or "").strip()
            solution = str(issue.get("solution") or "").strip()
            segments = [
                str(issue.get("status_text") or ""),
                str(issue.get("name") or ""),
            ]
            if desc:
                segments.append(f"描述: {desc}")
            if solution:
                segments.append(f"方案: {solution}")
            detail_lines.append(" / ".join(part for part in segments if part))
        issue_detail_summary = "\n".join(detail_lines)

        return ModulePayload(
            key=MODULE_KEY,
            status="ok",
            payload={
                "issue_count": len(issues),
                "unresolved_count": unresolved,
                "issue_summary": issue_summary,
                "issue_detail_summary": issue_detail_summary,
                "issues": issues,
            },
            source_tables=["service_issues"],
            freshness="today",
            warnings=[],
        )
    except Exception:
        _log.exception("service_issues failed for customer %s", customer_id)
        return ModulePayload(key=MODULE_KEY, status="error", payload={}, warnings=["模块加载异常"])
