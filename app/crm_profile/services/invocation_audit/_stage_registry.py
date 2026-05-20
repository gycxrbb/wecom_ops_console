"""Open stage / step-kind registries — no Enum lock-in."""
import logging

_log = logging.getLogger(__name__)

SINGLE_TURN_STAGES = frozenset({
    "entry", "attachment_resolution", "prepare", "rag_retrieval",
    "prompt_assembly", "shortcut_check", "llm_stream",
    "safety_gate", "audit_write", "done",
})

AGENT_STAGES = frozenset({
    "intent_classification", "agent_plan", "tool_call",
    "tool_observation", "agent_synthesize",
})

VISUAL_STAGES = frozenset({
    "visual_decision", "visual_brief_build", "visual_safety_check",
    "visual_generation", "visual_qa", "visual_storage",
})

KNOWN_STAGES = SINGLE_TURN_STAGES | AGENT_STAGES | VISUAL_STAGES

KNOWN_STEP_KINDS = frozenset({
    "llm_call", "rag_retrieval", "vision_analysis",
    "safety_gate", "context_snapshot", "prompt_assembly",
    "shortcut_evaluation", "tool_call",
    "visual_generation", "visual_safety_check",
})


def validate_stage(stage: str) -> str:
    if stage not in KNOWN_STAGES:
        _log.warning("Unknown invocation stage: %s", stage)
    return stage


def validate_step_kind(kind: str) -> str:
    if kind not in KNOWN_STEP_KINDS:
        _log.warning("Unknown step kind: %s", kind)
    return kind
