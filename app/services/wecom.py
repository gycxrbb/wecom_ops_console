from __future__ import annotations
import asyncio
import base64
import copy
import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import httpx
from ..security import json_dumps

RATE_LIMIT = 20
RATE_WINDOW_SECONDS = 60
_timestamps: dict[str, deque] = defaultdict(deque)
_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

class WeComService:
    @staticmethod
    def payload_for_storage(payload: dict | None) -> dict:
        if not payload:
            return {}
        compact = copy.deepcopy(payload)
        image = compact.get('image')
        if isinstance(image, dict) and isinstance(image.get('base64'), str):
            image['base64'] = f"<omitted:{len(image['base64'])} chars>"
        return compact

    @staticmethod
    async def _check_rate_limit(group_key: str):
        lock = _locks[group_key]
        async with lock:
            bucket = _timestamps[group_key]
            now = asyncio.get_running_loop().time()
            while bucket and now - bucket[0] > RATE_WINDOW_SECONDS:
                bucket.popleft()
            if len(bucket) >= RATE_LIMIT:
                raise RuntimeError('该群机器人触发了 20 条/分钟 的保护限制，请稍后重试。')
            bucket.append(now)

    @staticmethod
    def build_payload(msg_type: str, content: dict):
        if msg_type == 'raw_json':
            return content
        if msg_type == 'text':
            payload = {
                'msgtype': 'text',
                'text': {
                    'content': content.get('content', ''),
                    'mentioned_list': content.get('mentioned_list', []),
                    'mentioned_mobile_list': content.get('mentioned_mobile_list', []),
                },
            }
            return payload
        if msg_type == 'markdown':
            return {'msgtype': 'markdown', 'markdown': {'content': content.get('content', '')}}
        if msg_type == 'news':
            return {'msgtype': 'news', 'news': {'articles': content.get('articles', [])}}
        if msg_type == 'image':
            image_path = content.get('image_path')
            if not image_path:
                raise ValueError('image 消息缺少 image_path')
            raw = Path(image_path).read_bytes()
            return {
                'msgtype': 'image',
                'image': {
                    'base64': base64.b64encode(raw).decode('utf-8'),
                    'md5': hashlib.md5(raw).hexdigest(),
                },
            }
        if msg_type == 'file':
            return {'msgtype': 'file', 'file': {'media_id': content.get('media_id', '')}}
        if msg_type == 'template_card':
            card = content.get('template_card') if isinstance(content, dict) and content.get('template_card') else content
            return {'msgtype': 'template_card', 'template_card': card}
        raise ValueError(f'不支持的消息类型: {msg_type}')

    @staticmethod
    def extract_key(webhook: str) -> str:
        parsed = urlparse(webhook)
        values = parse_qs(parsed.query).get('key', [])
        if not values:
            raise ValueError('Webhook 中未找到 key 参数')
        return values[0]

    @classmethod
    async def upload_file(cls, webhook: str, file_path: str, file_name: str | None = None):
        key = cls.extract_key(webhook)
        url = f'https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={key}&type=file'
        display_name = file_name or Path(file_path).name
        async with httpx.AsyncClient(timeout=30) as client:
            with open(file_path, 'rb') as fh:
                files = {'media': (display_name, fh)}
                resp = await client.post(url, files=files)
                resp.raise_for_status()
                data = resp.json()
                if data.get('errcode') != 0:
                    raise RuntimeError(f'上传文件失败: {json_dumps(data)}')
                return data['media_id'], data

    @classmethod
    async def send(cls, webhook: str, msg_type: str, content: dict, group_key: str = 'default'):
        await cls._check_rate_limit(group_key)
        rendered_content = dict(content)
        if msg_type == 'file' and not rendered_content.get('media_id'):
            media_id, upload_resp = await cls.upload_file(webhook, rendered_content['file_path'], rendered_content.get('file_name'))
            rendered_content['media_id'] = media_id
            rendered_content['_upload_response'] = upload_resp
        payload = cls.build_payload(msg_type, rendered_content)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(webhook, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if data.get('errcode') != 0:
                raise RuntimeError(json_dumps(data))
            return payload, data
