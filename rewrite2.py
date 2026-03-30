import re

with open('app/routers/api.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace sorting error
text = text.replace("models.Groupgroup_type == 'test'.desc()", "models.Group.group_type.desc()")

# Delete schedule_service imports and usage
text = re.sub(r'from \.\.services\.scheduler_service import schedule_service\n?', '', text)
text = re.sub(r'\s*schedule_service\.add_or_update_job\(.*?\)', '', text)
text = re.sub(r'\s*schedule_service\.sync_from_db\(\)', '', text)

# Rewrite perform_job_send and do_send_to_groups to queue to tasks
# Because parsing python string visually using regex is hard, I will append my custom versions at the end of the file
# and remove the old versions. Wait, no, I'll just write a script that replaces them entirely.

