---
name: project-progress
description: View and update the TinfoilStore project progress tracker (.process file). Use when you need to check what has been completed, what phase the project is in, or update progress after completing a milestone. Trigger when the user asks about project status, progress, milestones, or says "update progress".
---

# Project Progress Tracker

Check and update the `.process` file that tracks TinfoilStore project milestones.

## Quick Start

1. Read `.process` in the project root to see current progress
2. Read `.ai-loop/state/workflow_state.json` to get live workflow state
3. Compare — if the workflow has advanced beyond what `.process` records, update `.process`

## When to Update

Update `.process` after any of these events:
- A workflow phase completes (designing → implementing → reviewing → fixing → done)
- A new milestone is reached (new package created, tests passing, artifact produced)
- Human gate is approved or rejected
- Iteration/attempt number changes
- The project structure changes significantly (new directories, major refactors)

## How to Update

1. Read the current `.process` file
2. Update the **Phase Summary** table statuses
3. Update **Current State** section with latest workflow_state.json values
4. Add new entries to **Completed Milestones** if a phase finished
5. Update **Next Steps** to reflect what comes after the latest completion
6. Update **Last Updated** date
7. Update the **Project Structure** tree if new directories/files were added

## Output Pattern

After reading/updating, report:
- Current phase and status
- What was last completed
- What is the immediate next action
- Any blockers (human gates pending, validation failures)
