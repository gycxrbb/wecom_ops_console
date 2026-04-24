from __future__ import annotations

import asyncio
import logging
import time

from ..database import SessionLocal
from ..security import decrypt_webhook, json_dumps
from .wecom import WeComService

_log = logging.getLogger(__name__)


def _build_summary_markdown(success_count: int, total_count: int,
                            group_names: list[str], elapsed_sec: float) -> str:
    names = '、'.join(group_names) if group_names else '无'
    lines = [
        '📊 **积分排行推送完成**',
        f'✅ 成功：{success_count} / {total_count} 条',
        f'📦 已推送群：{names}',
        f'⏱ 总耗时：{elapsed_sec:.1f} 秒',
    ]
    return '\n'.join(lines)


def _resolve_webhook(group) -> str:
    try:
        return decrypt_webhook(group.webhook_cipher) if group.webhook_cipher else ''
    except Exception:
        return ''


async def send_ranking_summary(schedule_id: int, start_time: float) -> None:
    """排行批次发送完成后，向所有成功接收的群发一条摘要。"""
    db = SessionLocal()
    try:
        from .. import models
        schedule = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
        if not schedule:
            return

        messages = (db.query(models.Message)
                    .filter(models.Message.source_type == 'schedule',
                            models.Message.source_id == schedule_id,
                            models.Message.status == 'sent')
                    .all())

        success_count = len(messages)
        if success_count == 0:
            return

        group_ids = list({m.group_id for m in messages})
        groups = (db.query(models.Group)
                  .filter(models.Group.id.in_(group_ids), models.Group.enabled == 1)
                  .all())

        group_names = [g.name for g in groups]
        group_webhooks = [(g.name, _resolve_webhook(g)) for g in groups]

        elapsed = time.time() - start_time
        total_count = (db.query(models.Message)
                       .filter(models.Message.source_type == 'schedule',
                               models.Message.source_id == schedule_id)
                       .count())

        md = _build_summary_markdown(success_count, total_count, group_names, round(elapsed, 1))
        content = {'content': md}

        for name, webhook in group_webhooks:
            if not webhook:
                continue
            try:
                await WeComService.send(webhook, 'markdown', content, group_key=f'summary-{name}')
                _log.info('排行摘要已发送到群 %s', name)
                await asyncio.sleep(3.1)
            except Exception as e:
                _log.warning('排行摘要发送到群 %s 失败: %s', name, e)
    except Exception as e:
        _log.error('send_ranking_summary 异常: %s', e)
    finally:
        db.close()
