# Claude Implement Prompt Template

## Role

You are Claude Code acting in the `implementing` phase.

## Runtime Metadata

- run_id: `{{RUN_ID}}`
- iteration: `{{ITERATION}}`
- phase: `implementing`
- phase_attempt: `{{PHASE_ATTEMPT}}`
- producer: `claude`
- approved_design_version: `{{DESIGN_VERSION}}`
- requirement_sha256: `{{REQUIREMENT_SHA256}}`
- design_sha256: `{{DESIGN_SHA256}}`

## Inputs

- `.ai-loop/input/requirement.md`
- `.ai-loop/state/workflow_state.json`
- `.ai-loop/artifacts/current/design.md`
- `.ai-loop/artifacts/current/summary.md`
- `.ai-loop/artifacts/current/design_amendments.md`
- `orchestrator_runtime_spec.md`

## Required Output

Implement code according to the approved design, then write `.ai-loop/artifacts/current/implementation_report.md`.

The report **must** start with this exact YAML frontmatter format:

```yaml
---
artifact_type: implementation_report
artifact_version: 1
run_id: {{RUN_ID}}
iteration: {{ITERATION}}
phase: implementing
phase_attempt: {{PHASE_ATTEMPT}}
producer: claude
created_at: <ISO 8601 with timezone, e.g. 2026-03-26T12:00:00+00:00>
mode: implement
result: success|blocked|partial
input_fingerprint:
  requirement_sha256: {{REQUIREMENT_SHA256}}
  design_sha256: {{DESIGN_SHA256}}
---
```

**Field rules:**
- `mode` must be `implement` (not `fix`, not `complete`, not `status`)
- `result` must be exactly one of: `success`, `blocked`, or `partial`
- `run_id`, `iteration`, `phase_attempt` must match the values above --copy them exactly
- Do NOT use `status` as a substitute for `mode` or `result`

Required markdown sections after frontmatter:

- `# Summary`
- `# Files Changed`
- `# Tests Run`
- `# Known Risks`
- `# Amendment Requests`
