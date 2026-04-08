from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException

from ..config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPTS = {
    'text': (
        '你是一个专业的企业微信消息文案编辑助手。'
        '用户会给你一段企业微信群消息文本和一条修改指令。'
        '请根据指令对文本进行润色、改写或从零撰写，直接返回最终的纯文本内容。'
        '不要添加任何解释、标注或 markdown 格式，只返回可以直接发送的文本。'
    ),
    'markdown': (
        '你是一个专业的企业微信 Markdown 消息文案编辑助手。'
        '用户会给你一段企业微信群 Markdown 消息内容和一条修改指令。'
        '请根据指令对内容进行润色、改写或从零撰写，直接返回最终的 Markdown 内容。'
        '不要添加任何解释或标注，只返回可以直接发送的 Markdown 文本。'
    ),
}


async def polish_text(content: str, instruction: str, msg_type: str) -> str:
    if not settings.ai_api_key or settings.ai_api_key == 'your-api-key-here':
        raise HTTPException(400, 'AI 服务未配置，请在 .env 中设置 AI_API_KEY')

    system_prompt = SYSTEM_PROMPTS.get(msg_type, SYSTEM_PROMPTS['text'])

    user_parts = []
    if instruction:
        user_parts.append(f'【修改指令】{instruction}')
    if content and content.strip():
        user_parts.append(f'【原始内容】\n{content}')
    else:
        user_parts.append('【原始内容】（空，请根据指令从零撰写）')

    user_message = '\n\n'.join(user_parts)

    url = f'{settings.ai_base_url.rstrip("/")}/chat/completions'
    headers = {
        'Authorization': f'Bearer {settings.ai_api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': settings.ai_model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_message},
        ],
        'temperature': 0.7,
        'max_tokens': 2048,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data['choices'][0]['message']['content'].strip()
    except httpx.TimeoutException:
        logger.warning('AI polish request timed out')
        raise HTTPException(504, 'AI 服务响应超时，请稍后重试')
    except httpx.HTTPStatusError as e:
        logger.error(f'AI polish API error: {e.response.status_code} {e.response.text[:200]}')
        raise HTTPException(502, f'AI 服务返回错误 ({e.response.status_code})')
    except Exception as e:
        logger.error(f'AI polish unexpected error: {e}', exc_info=True)
        raise HTTPException(500, 'AI 润色服务异常')
