"""自动排行发送记录辅助 — 创建/更新 Message + MessageLog。"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import Message, MessageLog


def create_send_record(
    db: Session,
    group_id: int,
    msg_type: str,
    content_json: dict,
    config_id: int,
) -> Message:
    msg = Message(
        source_type='auto_ranking',
        source_id=config_id,
        group_id=group_id,
        msg_type=msg_type,
        rendered_content=json.dumps(content_json, ensure_ascii=False) if isinstance(content_json, dict) else str(content_json),
        request_payload='{}',
        status='pending',
        created_by=None,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def mark_send_success(db: Session, msg: Message, payload: dict = None, response: dict = None) -> None:
    msg.status = 'sent'
    msg.sent_at = datetime.utcnow()
    from ..services.wecom import WeComService
    stored = WeComService.payload_for_storage(payload) if payload else {}
    msg.request_payload = json.dumps(stored, ensure_ascii=False)
    db.add(MessageLog(
        message_id=msg.id,
        request_payload=json.dumps(stored, ensure_ascii=False),
        response_payload=json.dumps(response, ensure_ascii=False) if response else '{}',
        http_status=200,
        success=1,
        attempt_no=1,
    ))
    db.commit()


def mark_send_failure(db: Session, msg: Message, error: str, payload: dict = None) -> None:
    msg.status = 'failed'
    msg.sent_at = datetime.utcnow()
    from ..services.wecom import WeComService
    stored = WeComService.payload_for_storage(payload) if payload else {}
    msg.request_payload = json.dumps(stored, ensure_ascii=False)
    db.add(MessageLog(
        message_id=msg.id,
        request_payload=json.dumps(stored, ensure_ascii=False),
        response_payload='{}',
        http_status=0,
        success=0,
        error_message=error,
        attempt_no=1,
    ))
    db.commit()
