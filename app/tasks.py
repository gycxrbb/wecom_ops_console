import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from celery.utils.log import get_task_logger
import asyncio

from app.celery_app import celery_app
from app.database import SessionLocal
from app import models
from app.services.wecom import WeComService
from app.security import decrypt_webhook, json_loads, json_dumps
import time

logger = get_task_logger(__name__)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_message_task(self, message_id: int):
    logger.info(f"Processing message {message_id}")
    db = SessionLocal()
    try:
        message = db.query(models.Message).filter(models.Message.id == message_id).first()
        if not message or message.status not in ['pending', 'failed', 'awaiting_approval']:
            return 'Message not valid for sending'

        group = db.query(models.Group).filter(models.Group.id == message.group_id).first()
        if not group or not group.enabled:
            message.status = 'failed'
            db.commit()
            return 'Group disabled or not found'

        webhook_url = decrypt_webhook(group.webhook_cipher)
        payload = json_loads(message.rendered_content)

        start_time = time.time()
        success = False
        error_msg = None
        resp_data = {}
        http_status = 200

        try:
            # WeComService.send is async, we run it in a sync wrapper
            # Wait, payload here is raw payload or content?
            # WeComService.send expects msg_type and content dictionary!
            msg_type = message.msg_type
            payload_data, resp_data = asyncio.run(WeComService.send(webhook_url, msg_type, payload, group_key=str(group.id)))
            success = True
            message.status = 'sent'
        except Exception as e:
            success = False
            error_msg = str(e)
            message.status = 'failed'
            http_status = 500

        latency_ms = int((time.time() - start_time) * 1000)
        message.sent_at = datetime.utcnow()
        message.retry_count += 1
        
        log = models.MessageLog(
            message_id=message.id,
            request_payload=json_dumps(payload),
            response_payload=json_dumps(resp_data),
            http_status=http_status,
            success=1 if success else 0,
            latency_ms=latency_ms,
            error_message=error_msg,
            attempt_no=message.retry_count
        )
        db.add(log)
        db.commit()

        if not success:
            if self.request.retries < self.max_retries:
                logger.warning(f"Retrying message {message_id}")
                raise self.retry(exc=Exception(error_msg))
            
    finally:
        db.close()
