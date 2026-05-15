"""AI auto-title generation for sessions — calls a cheap model to summarise the first user message."""
from __future__ import annotations

import logging

from ....clients.ai_chat_client import chat_completion
from ....config import settings
from ...services.audit import load_session_messages
from ._session_admin import update_auto_title

_log = logging.getLogger(__name__)

_AUTO_TITLE_PROMPT = "请为以下对话生成不超过15字的简短标题，直接输出标题，不要任何前缀或标点。"


async def generate_auto_title(session_id: str) -> str | None:
    """Generate an AI title from the first few user messages and persist it."""
    msgs = load_session_messages(session_id, limit=3)
    user_msgs = [m["content"] for m in msgs if m["role"] == "user" and m.get("content")]
    if not user_msgs:
        return None

    combined = "\n".join(user_msgs)[:2000]
    try:
        content, _ = await chat_completion(
            messages=[
                {"role": "system", "content": _AUTO_TITLE_PROMPT},
                {"role": "user", "content": combined},
            ],
            temperature=0.3,
            max_tokens=40,
            provider="aihubmix",
            model=getattr(settings, "auto_title_model", None) or settings.vision_model,
        )
        title = content.strip().strip("\"'").strip()
        if not title or len(title) > 60:
            return None
        update_auto_title(session_id, title)
        _log.info("Auto-title generated for %s: %s", session_id, title)
        return title
    except Exception:
        _log.warning("Auto-title generation failed for %s", session_id, exc_info=True)
        return None
