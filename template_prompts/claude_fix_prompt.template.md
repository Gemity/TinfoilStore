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

Fix only the unresolved review findings, then rewrite `.ai-loop/artifacts/current/implementation_report.md`.

The report **must** start with this exact YAML frontmatter format:

```yaml
---
artifact_type: implementation_report
artifact_version: 1
run_id: {{RUN_ID}}
iteration: {{ITERATION}}
phase: fixing
phase_attempt: {{PHASE_ATTEMPT}}
producer: claude
created_at: <ISO 8601 with timezone, e.g. 2026-03-26T12:00:00+00:00>
mode: fix
result: success|blocked|partial
input_fingerprint:
  requirement_sha256: {{REQUIREMENT_SHA256}}
  design_sha256: {{DESIGN_SHA256}}
---
```

**Field rules:**
- `mode` must be `fix` (not `implement`, not `complete`, not `status`)
- `result` must be exactly one of: `success`, `blocked`, or `partial`
- `run_id`, `iteration`, `phase_attempt` must match the values above --copy them exactly
- Do NOT use `status` as a substitute for `mode` or `result`

Required markdown sections after frontmatter:

- `# Summary`
- `# Files Changed`
- `# Tests Run`
- `# Known Risks`
- `# Amendment Requests`
