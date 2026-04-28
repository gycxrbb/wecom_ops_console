from __future__ import annotations
import asyncio
import base64
import copy
import hashlib
import json
import logging
from collections import defaultdict, deque
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import httpx
from ..config import settings
from ..security import json_dumps
from .storage import StorageResult, storage_facade

logger = logging.getLogger(__name__)

RATE_LIMIT = 20
RATE_WINDOW_SECONDS = 60
MAX_RATE_WAIT_SECONDS = 120
_timestamps: dict[str, deque] = defaultdict(deque)
_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

class WeComService:
    @staticmethod
    def _storage_result_from_content(content: dict) -> StorageResult | None:
        meta = content.get('asset_meta')
        if not isinstance(meta, dict):
            return None
        return StorageResult(
            provider=meta.get('provider', 'local'),
            object_key=meta.get('storage_key', ''),
            public_url=meta.get('public_url', ''),
            original_filename=meta.get('original_filename', content.get('file_name', 'asset')),
            stored_filename=meta.get('stored_filename', content.get('file_name', 'asset')),
            mime_type=meta.get('mime_type', 'application/octet-stream'),
            file_size=int(meta.get('file_size', 0) or 0),
            bucket=meta.get('bucket', ''),
            local_path=meta.get('local_path', ''),
            extra={},
        )

    @staticmethod
    def _ensure_static_image(raw: bytes) -> bytes:
        """检测 GIF/动态图，转为 PNG 第一帧。企微图片消息不支持动画。"""
        if raw[:6] not in (b'GIF87a', b'GIF89a'):
            return raw
        try:
            from PIL import Image
            img = Image.open(BytesIO(raw))
            img = img.convert('RGBA') if img.mode in ('RGBA', 'LA', 'P') else img.convert('RGB')
            buf = BytesIO()
            img.save(buf, format='PNG')
            return buf.getvalue()
        except Exception:
            return raw

    @staticmethod
    def _compress_image_if_needed(raw: bytes, max_size: int = 2 * 1024 * 1024) -> bytes:
        if len(raw) <= max_size:
            return raw
        try:
            from PIL import Image
            img = Image.open(BytesIO(raw))
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGBA')
            else:
                img = img.convert('RGB')
            for quality in [85, 70, 55, 40, 30, 20]:
                buf = BytesIO()
                img.save(buf, format='JPEG', quality=quality)
                if buf.tell() <= max_size:
                    logger.info('图片压缩: %d -> %d bytes (quality=%d)', len(raw), buf.tell(), quality)
                    return buf.getvalue()
            for scale in [0.75, 0.5, 0.3]:
                w, h = img.size
                resized = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
                buf = BytesIO()
                resized.save(buf, format='JPEG', quality=40)
                if buf.tell() <= max_size:
                    logger.info('图片压缩+缩放: %d -> %d bytes (scale=%.0f%%)', len(raw), buf.tell(), scale * 100)
                    return buf.getvalue()
            logger.warning('图片压缩后仍超过 %d bytes，将尽力发送', max_size)
            return buf.getvalue()
        except Exception:
            return raw

    @classmethod
    def _read_asset_bytes(cls, content: dict, *, image: bool = False) -> bytes:
        handle = cls._storage_result_from_content(content)
        if handle:
            return storage_facade.download_bytes(handle)
        fallback_path = content.get('image_path' if image else 'file_path')
        if not fallback_path:
            raise ValueError(f"{'image' if image else 'file'} 消息缺少可读取的素材引用")
        return Path(fallback_path).read_bytes()

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
        while True:
            async with lock:
                bucket = _timestamps[group_key]
                now = asyncio.get_running_loop().time()
                while bucket and now - bucket[0] > RATE_WINDOW_SECONDS:
                    bucket.popleft()
                if len(bucket) < RATE_LIMIT:
                    bucket.append(now)
                    return
                wait_seconds = bucket[0] + RATE_WINDOW_SECONDS - now + 1.0
            if wait_seconds > MAX_RATE_WAIT_SECONDS:
                raise RuntimeError(
                    f'该群机器人限流等待超过 {MAX_RATE_WAIT_SECONDS}s 上限，放弃发送。'
                )
            logger.warning(
                '群 %s 触达 %d 条/分钟限制，等待 %.1fs 后继续',
                group_key, RATE_LIMIT, wait_seconds,
            )
            await asyncio.sleep(wait_seconds)

    @classmethod
    def build_payload(cls, msg_type: str, content: dict):
        normalized_type = 'image' if msg_type == 'emotion' else msg_type
        if msg_type == 'raw_json':
            return content
        if normalized_type == 'text':
            payload = {
                'msgtype': 'text',
                'text': {
                    'content': content.get('content', ''),
                    'mentioned_list': content.get('mentioned_list', []),
                    'mentioned_mobile_list': content.get('mentioned_mobile_list', []),
                },
            }
            return payload
        if normalized_type == 'markdown':
            return {'msgtype': 'markdown', 'markdown': {'content': content.get('content', '')}}
        if normalized_type == 'news':
            return {'msgtype': 'news', 'news': {'articles': content.get('articles', [])}}
        if normalized_type == 'image':
            raw = cls._read_asset_bytes(content, image=True)
            raw = cls._ensure_static_image(raw)
            raw = cls._compress_image_if_needed(raw)
            return {
                'msgtype': 'image',
                'image': {
                    'base64': base64.b64encode(raw).decode('utf-8'),
                    'md5': hashlib.md5(raw).hexdigest(),
                },
            }
        if normalized_type == 'file':
            return {'msgtype': 'file', 'file': {'media_id': content.get('media_id', '')}}
        if normalized_type == 'voice':
            return {'msgtype': 'voice', 'voice': {'media_id': content.get('media_id', '')}}
        if normalized_type == 'template_card':
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
    async def upload_media(
        cls,
        webhook: str,
        *,
        media_type: str = 'file',
        file_path: str | None = None,
        file_name: str | None = None,
        file_bytes: bytes | None = None,
    ):
        key = cls.extract_key(webhook)
        url = f'https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={key}&type={media_type}'
        display_name = file_name or (Path(file_path).name if file_path else 'asset')
        file_size = len(file_bytes) if file_bytes else (Path(file_path).stat().st_size if file_path else 0)
        timeout = cls._compute_upload_timeout(file_size)
        logger.info(f'Uploading {media_type} "{display_name}" ({file_size} bytes, timeout={timeout}s)')
        async with httpx.AsyncClient(timeout=timeout) as client:
            if file_bytes is None:
                if not file_path:
                    raise ValueError('upload_file 缺少文件来源')
                with open(file_path, 'rb') as fh:
                    files = {'media': (display_name, fh)}
                    resp = await client.post(url, files=files)
            else:
                files = {'media': (display_name, BytesIO(file_bytes))}
                resp = await client.post(url, files=files)
            resp.raise_for_status()
            data = resp.json()
            if data.get('errcode') != 0:
                raise RuntimeError(f'上传文件失败: {json_dumps(data)}')
            logger.info(f'{media_type} "{display_name}" uploaded successfully, media_id={data.get("media_id")}')
            return data['media_id'], data

    @classmethod
    async def upload_file(cls, webhook: str, file_path: str | None = None, file_name: str | None = None, file_bytes: bytes | None = None):
        return await cls.upload_media(
            webhook,
            media_type='file',
            file_path=file_path,
            file_name=file_name,
            file_bytes=file_bytes,
        )

    @staticmethod
    def _compute_upload_timeout(file_size: int) -> int:
        """根据文件大小动态计算上传超时时间"""
        base = settings.file_upload_timeout_seconds
        if file_size <= 5 * 1024 * 1024:  # <= 5MB
            return base
        if file_size <= 20 * 1024 * 1024:  # <= 20MB
            return int(base * 1.5)
        return base * 2  # > 20MB

    @classmethod
    async def send(cls, webhook: str, msg_type: str, content: dict, group_key: str = 'default'):
        await cls._check_rate_limit(group_key)
        rendered_content = dict(content)
        if msg_type == 'file' and not rendered_content.get('media_id'):
            file_bytes = cls._read_asset_bytes(rendered_content, image=False)
            media_id, upload_resp = await cls.upload_file(
                webhook,
                rendered_content.get('file_path'),
                rendered_content.get('file_name'),
                file_bytes=file_bytes,
            )
            rendered_content['media_id'] = media_id
            rendered_content['_upload_response'] = upload_resp
        if msg_type == 'voice' and not rendered_content.get('media_id'):
            file_bytes = cls._read_asset_bytes(rendered_content, image=False)
            media_id, upload_resp = await cls.upload_media(
                webhook,
                media_type='voice',
                file_path=rendered_content.get('file_path'),
                file_name=rendered_content.get('file_name'),
                file_bytes=file_bytes,
            )
            rendered_content['media_id'] = media_id
            rendered_content['_upload_response'] = upload_resp
        payload = cls.build_payload(msg_type, rendered_content)
        timeout = settings.send_timeout_seconds
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(webhook, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if data.get('errcode') != 0:
                raise RuntimeError(json_dumps(data))
            return payload, data
