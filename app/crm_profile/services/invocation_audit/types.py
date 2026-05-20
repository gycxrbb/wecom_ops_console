"""Error code constants and classification for invocation audit."""

_RETRIABLE_CODES = frozenset({
    "model_timeout", "model_connection_failed", "model_upstream_error",
    "rag_retrieval_timeout", "stream_interrupted",
})


class ErrorCode:
    # model
    MODEL_TIMEOUT = "model_timeout"
    MODEL_CONNECTION_FAILED = "model_connection_failed"
    MODEL_UPSTREAM_ERROR = "model_upstream_error"
    MODEL_NOT_CONFIGURED = "model_not_configured"
    MODEL_RESPONSE_INVALID = "model_response_invalid"
    # prepare
    PREPARE_PROFILE_CACHE_UNREADY = "prepare_profile_cache_unready"
    PREPARE_PROFILE_LOAD_FAILED = "prepare_profile_load_failed"
    PREPARE_PROMPT_ASSEMBLY_FAILED = "prepare_prompt_assembly_failed"
    PREPARE_ATTACHMENT_RESOLUTION_FAILED = "prepare_attachment_resolution_failed"
    # rag
    RAG_RETRIEVAL_FAILED = "rag_retrieval_failed"
    RAG_RETRIEVAL_TIMEOUT = "rag_retrieval_timeout"
    # stream
    STREAM_CANCELLED = "stream_cancelled"
    STREAM_INTERRUPTED = "stream_interrupted"
    # safety
    SAFETY_GATE_BLOCKED = "safety_gate_blocked"
    # auth
    AUTH_PERMISSION_DENIED = "auth_permission_denied"
    # system
    SYSTEM_UNKNOWN = "system_unknown"
    SYSTEM_DB_WRITE_FAILED = "system_db_write_failed"
    # visual
    VISUAL_GENERATION_FAILED = "visual_generation_failed"
    VISUAL_SAFETY_BLOCKED = "visual_safety_blocked"
    VISUAL_MODEL_NOT_CONFIGURED = "visual_model_not_configured"
    VISUAL_CONFIRMATION_TIMEOUT = "visual_confirmation_timeout"


def is_retriable(code: str) -> bool:
    return code in _RETRIABLE_CODES
