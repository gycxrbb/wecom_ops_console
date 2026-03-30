---
name: todo-list-csv
description: "Cross-thread progress synchronization using a CSV-based todo state tracker. Perfect for higher-level control, multi-agent/multi-thread coordination, and non-dev stakeholders reviewing project progress."
---
# Todo-List-CSV Workflow Skill

When invoked, generate and maintain `todo-list.csv` in the root (or specified `.tasks` directory).
Every row should list:
- Task ID
- Name
- Assigned Agent/Thread
- Status (Draft, In-Progress, Blocked, Completed)
- Evidence (e.g. Test output file path, or Commit)
Every parallel thread must update the same CSV to maintain the whole-project view.