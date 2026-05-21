"""Register built-in agent tools."""
from ._registry import ToolDef, register_tool


def _register_all() -> None:
    register_tool(ToolDef(
        name="rag_search",
        description="RAG knowledge retrieval — search internal knowledge base and scripts",
        input_schema={"query": "string", "intent": "string", "filters": "object"},
        output_schema={"sources": "array", "recommended_assets": "array"},
        category="rag",
    ))
    register_tool(ToolDef(
        name="profile_query",
        description="Customer profile query — retrieve official customer truth",
        input_schema={"customer_id": "int", "window_days": "int"},
        output_schema={"profile_summary": "object"},
        category="profile",
    ))
    register_tool(ToolDef(
        name="visual_generate",
        description="AI visual generation — create knowledge card images via configured image model",
        input_schema={"topic": "string", "brief": "object", "safety_level": "string"},
        output_schema={"job_id": "string", "asset_id": "string", "image_url": "string"},
        category="visual",
    ))
    register_tool(ToolDef(
        name="llm_call",
        description="LLM text generation — streaming chat completion",
        input_schema={"messages": "array", "model": "string"},
        output_schema={"content": "string", "token_usage": "object"},
        category="llm",
    ))


_register_all()
