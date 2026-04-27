"""AI decision labels module — customer label values for AI reasoning.

Sources: customer_label_values JOIN label_definition.
Only labels with is_ai_decision=1 are included.
"""
from __future__ import annotations

import logging

from ...schemas.context import ModulePayload

_log = logging.getLogger(__name__)

MODULE_KEY = "ai_decision_labels"


def load(conn, customer_id: int) -> ModulePayload:
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT clv.label_key, clv.label_value, "
                "ld.label_name_cn, ld.label_definition, ld.match_weight "
                "FROM customer_label_values clv "
                "JOIN label_definition ld ON clv.label_key = ld.label_key "
                "WHERE clv.customer_id = %s AND ld.is_ai_decision = 1 "
                "ORDER BY ld.match_weight DESC LIMIT 15",
                (customer_id,),
            )
            rows = cur.fetchall()

        if not rows:
            return ModulePayload(key=MODULE_KEY, status="empty", payload={})

        labels = []
        summary_parts = []
        for r in rows:
            val = str(r["label_value"] or "")[:120]
            defn = str(r["label_definition"] or "")[:120]
            weight = float(r["match_weight"] or 0)
            name_cn = str(r["label_name_cn"] or "")
            labels.append({
                "key": r["label_key"],
                "value": val,
                "name_cn": name_cn,
                "definition_summary": defn,
                "weight": weight,
            })
            summary_parts.append(f"{name_cn}({round(weight * 100)}%)")

        label_summary = "，".join(summary_parts)[:200]

        return ModulePayload(
            key=MODULE_KEY,
            status="ok",
            payload={
                "labels": labels,
                "label_count": len(labels),
                "label_summary": label_summary,
            },
            source_tables=["customer_label_values", "label_definition"],
            freshness="today",
            warnings=[],
        )
    except Exception:
        _log.exception("ai_decision_labels failed for customer %s", customer_id)
        return ModulePayload(key=MODULE_KEY, status="error", payload={}, warnings=["模块加载异常"])
