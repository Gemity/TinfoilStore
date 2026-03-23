# Claude Fix Prompt Template

## Role

You are Claude Code acting in the `fixing` phase.

## Runtime Metadata

- run_id: `{{RUN_ID}}`
- iteration: `{{ITERATION}}`
- phase: `fixing`
- phase_attempt: `{{PHASE_ATTEMPT}}`
- producer: `claude`

## Inputs

- `.ai-loop/state/workflow_state.json`
- `.ai-loop/artifacts/current/design.md`
- `.ai-loop/artifacts/current/review.md`
- `.ai-loop/artifacts/current/review.json`

## Required Output

Fix only the unresolved review findings and rewrite:

- `.ai-loop/artifacts/current/implementation_report.md`
