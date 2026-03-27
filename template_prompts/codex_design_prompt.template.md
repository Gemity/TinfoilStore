# Codex Design Prompt Template

## Role

You are Codex acting in the `designing` phase.

## Runtime Metadata

- run_id: `{{RUN_ID}}`
- iteration: `{{ITERATION}}`
- phase: `designing`
- phase_attempt: `{{PHASE_ATTEMPT}}`
- producer: `codex`
- artifact_version: `1`
- target_design_version: `{{TARGET_DESIGN_VERSION}}`
- requirement_sha256: `{{REQUIREMENT_SHA256}}`

## Inputs

- `.ai-loop/input/requirement.md`
- `.ai-loop/state/workflow_state.json`
- `.ai-loop/artifacts/current/summary.md`
- `.ai-loop/artifacts/current/design_amendments.md`
- `orchestrator_runtime_spec.md`

## Required Output

Write `.ai-loop/artifacts/current/design.md`.

The document **must** start with this exact YAML frontmatter format:

```yaml
---
artifact_type: design
artifact_version: 1
run_id: {{RUN_ID}}
iteration: {{ITERATION}}
phase: designing
phase_attempt: {{PHASE_ATTEMPT}}
producer: codex
created_at: <ISO 8601 with timezone, e.g. 2026-03-26T12:00:00+00:00>
design_version: {{TARGET_DESIGN_VERSION}}
status: approved
input_fingerprint:
  requirement_sha256: {{REQUIREMENT_SHA256}}
---
```

**Field rules:**
- `design_version` must be an integer starting at 1
- `status` must be exactly one of: `draft`, `approved`, or `superseded`
- `run_id`, `iteration`, `phase_attempt` must match the values above --copy them exactly

Required markdown sections after frontmatter:

- `# Objective`
- `# Scope`
- `# Constraints`
- `# Architecture`
- `# Execution Plan`
- `# Acceptance Criteria`
- `# Non-Goals`
