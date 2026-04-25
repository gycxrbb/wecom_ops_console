"""Centralized enum definitions for CRM profile module (§9.6)."""
from __future__ import annotations

from typing import Literal

# --- entry_scene ---
EntryScene = Literal[
    "customer_profile",
    "coach_reply",
    "diet_suggestion",
    "exercise_suggestion",
    "points_followup",
    "handoff_summary",
]

# --- selected_expansions ---
ExpansionKey = Literal[
    "glucose_detail_7d",
    "diet_detail_7d",
    "sleep_detail_14d",
    "exercise_detail_14d",
    "points_logs_14d",
    "todo_detail_14d",
]

# --- output_style ---
OutputStyle = Literal[
    "coach_brief",
    "customer_reply",
    "handoff_note",
    "bullet_list",
]

# --- module_status ---
ModuleStatus = Literal["ok", "empty", "partial", "timeout", "error"]

# --- source_status ---
SourceStatus = Literal[
    "ok",
    "fallback_latest_archived_or_unknown",
    "permission_denied",
    "unavailable",
]

# --- available_actions ---
ActionKey = Literal[
    "ai_chat",
    "copy_summary",
    "copy_draft",
    "create_followup",
    "mark_medical_review",
]

# --- guardrail_event types ---
GuardrailEventType = Literal[
    "prompt_field_blocked",
    "prompt_safety_missing",
    "prompt_token_exceed",
    "output_allergy_hit",
    "output_medical_term",
]
