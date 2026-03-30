import os

with open('app/routers/api.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace do_send_to_groups to just enqueue items
replacement = '''
async def do_send_to_groups(db: Session, groups: list[models.Group], msg_type: str, content_json: dict, variables_json: dict, user: models.User, schedule: models.Schedule | None = None, run_mode: str = 'immediate'):
    results = []
    from ..tasks import send_message_task
    
    for group in groups:
        rendered_content = render_message_content(msg_type, content_json, variables_json, user, group)
        rendered_content = attach_asset_paths(db, msg_type, rendered_content)
        
        msg = models.Message(
            source_type='schedule' if schedule else 'manual',
            source_id=schedule.id if schedule else None,
            group_id=group.id,
            template_id=schedule.template_id if schedule else None,
            msg_type=msg_type,
            rendered_content=json_dumps(rendered_content),
            request_payload='{}',
            status='pending',
            created_by=user.id
        )
        db.add(msg)
        db.commit()
        
        send_message_task.delay(msg.id)
        results.append({'group_id': group.id, 'group_name': group.name, 'success': True, 'response': 'Queued'})
        
    return results

async def perform_job_send(db: Session, schedule: models.Schedule, run_mode: str = 'scheduled'):
    user = schedule.owner or db.query(models.User).filter(models.User.role == 'admin').first()
    if schedule.require_approval and schedule.approval_status != 'approved':
        return {'skipped': True, 'reason': 'pending approval'}
        
    group_ids = json_loads(schedule.group_ids_json, [])
    groups = db.query(models.Group).filter(models.Group.id.in_(group_ids), models.Group.is_enabled == True).all()
    
    results = await do_send_to_groups(db, groups, schedule.msg_type, json_loads(schedule.content, {}), json_loads(schedule.variables, {}), user, schedule=schedule, run_mode=run_mode)
    
    return results
'''

import re
text = re.sub(r'async def do_send_to_groups.*?return results\n\n\nasync def perform_job_send.*?return results\s*\n', replacement, text, flags=re.DOTALL)

with open('app/routers/api.py', 'w', encoding='utf-8') as f:
    f.write(text)

