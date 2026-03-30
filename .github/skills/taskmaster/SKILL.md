---
name: taskmaster
description: "Engineering task tracker using SPEC/TODO/PROGRESS/SUBTASKS to track steps and recovery points for complex projects. Use for tasks with >3 steps, multi-thread collaboration, or multiple files, ensuring solid recovery anchors."
---
# Taskmaster Workflow Skill

When invoked, switch to Taskmaster mode:
1. Parse the goal into `spec.md`, `todo.md`, `progress.md`, and `subtasks.md` in the `.tasks/` directory if they don't exist.
2. Formulate 3-5 subtasks based on context recovery.
3. Continually track progress and update the true state.
4. Leave a solid anchor for recovery on completion.